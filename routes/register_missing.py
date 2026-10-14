from flask import Blueprint, abort, current_app, flash, render_template, request, redirect, url_for
import re
import os
from datetime import datetime
from pathlib import Path
from utils.uploads import save_child_photo
from utils.anti_abuse import consume_public_submission_limit
from ai.match_queue import MatchQueueFull, enqueue_match_job


register_missing_bp = Blueprint(
    "register_missing",
    __name__
)


# =========================================================
# PATHS
# =========================================================

from storage import UPLOAD_ROOT, connect_database


# =========================================================
# VALIDATION FUNCTIONS
# =========================================================

def valid_name(value):

    pattern = r"^[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ '\-.][A-Za-zÀ-ÖØ-öø-ÿ]+)*$"

    return bool(
        re.fullmatch(
            pattern,
            value.strip()
        )
    )


def valid_phone(value):

    return bool(
        re.fullmatch(
            r"\d{7,15}",
            value.strip()
        )
    )


def valid_date(day, month, year):

    try:

        missing_date = datetime(
            int(year),
            int(month),
            int(day)
        )

        return missing_date.year >= 1900 and missing_date.date() <= datetime.now().date()

    except ValueError:

        return False


# =========================================================
# ROUTE
# =========================================================

@register_missing_bp.route(
    "/register-missing",
    methods=["GET", "POST"]
)
def register_missing():

    if request.method == "POST":

        # Ignore automated submissions that fill the off-screen honeypot.
        if request.form.get("company_website", "").strip():
            return redirect(url_for("dashboard.dashboard"))

        if not consume_public_submission_limit("missing-registration", limit=5):
            abort(429, description="Too many reports were submitted. Please try again later.")

        # -------------------------------------------------
        # GET FORM DATA
        # -------------------------------------------------

        name = request.form.get(
            "name",
            ""
        ).strip()

        age = request.form.get(
            "age",
            ""
        ).strip()

        gender = request.form.get(
            "gender",
            ""
        ).strip()

        city = request.form.get(
            "city",
            ""
        ).strip()

        parent_name = request.form.get(
            "parent_name",
            ""
        ).strip()

        country_code = request.form.get(
            "country_code",
            ""
        ).strip()

        phone_number = request.form.get(
            "phone",
            ""
        ).strip()

        day = request.form.get(
            "day",
            ""
        ).strip()

        month = request.form.get(
            "month",
            ""
        ).strip()

        year = request.form.get(
            "year",
            ""
        ).strip()

        photo = request.files.get(
            "photo"
        )


        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        errors = []


        # NAME

        if not name:

            errors.append(
                "Child name is required."
            )

        elif len(name) > 100 or not valid_name(name):

            errors.append(
                "Child name cannot contain numbers or invalid characters."
            )


        # AGE

        try:

            age_number = int(age)

            if age_number < 0 or age_number > 18:

                errors.append(
                    "Age must be between 0 and 18."
                )

        except ValueError:

            errors.append(
                "Age must be a whole number."
            )


        # GENDER

        allowed_genders = {
            "Male",
            "Female",
            "Other"
        }

        if gender not in allowed_genders:

            errors.append(
                "Please select a valid gender."
            )


        # CITY

        if not city:

            errors.append(
                "City is required."
            )

        elif len(city) > 100 or not valid_name(city):

            errors.append(
                "City cannot contain numbers or invalid characters."
            )


        # PARENT NAME

        if not parent_name:

            errors.append(
                "Parent / guardian name is required."
            )

        elif len(parent_name) > 100 or not valid_name(parent_name):

            errors.append(
                "Parent / guardian name cannot contain numbers."
            )


        # COUNTRY CODE

        allowed_country_codes = {
            "+91",
            "+1",
            "+44",
            "+61",
            "+971"
        }

        if country_code not in allowed_country_codes:

            errors.append(
                "Invalid country code."
            )


        # PHONE

        if not valid_phone(phone_number):

            errors.append(
                "Contact number must contain 7–15 digits only."
            )


        # DATE

        if not valid_date(
            day,
            month,
            year
        ):

            errors.append(
                "Please enter a valid missing date."
            )


        # PHOTO

        if not photo or not photo.filename:

            errors.append(
                "Child photograph is required."
            )

        else:

            allowed_extensions = {
                ".jpg",
                ".jpeg",
                ".png",
                ".webp"
            }

            extension = os.path.splitext(
                photo.filename
            )[1].lower()

            if extension not in allowed_extensions:

                errors.append(
                    "Only JPG, JPEG, PNG and WEBP images are allowed."
                )


        # -------------------------------------------------
        # STOP IF INVALID
        # -------------------------------------------------

        if errors:

            return render_template(
                "register_missing.html",
                errors=errors
            )


        # -------------------------------------------------
        # PHONE
        # -------------------------------------------------

        phone = (
            country_code
            + " "
            + phone_number
        )


        # -------------------------------------------------
        # DATE
        # -------------------------------------------------

        missing_date = (
            f"{day}-{month}-{year}"
        )


        # -------------------------------------------------
        # PHOTO
        # -------------------------------------------------

        try:
            photo_path = save_child_photo(photo, "missing_children")
        except ValueError as exc:
            abort(400, description=str(exc))


        # -------------------------------------------------
        # DATABASE
        # -------------------------------------------------

        connection = connect_database()
        match_queued = False
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """INSERT INTO missing_children
                   (name, age, gender, city, parent_name, phone, missing_date,
                    photo_path, public_listing, public_listing_approved_at,
                    public_listing_approval_reference)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 'public-report-submission')""",
                (
                    name, age_number, gender, city, parent_name, phone,
                    missing_date, photo_path,
                    datetime.now().astimezone().isoformat(timespec="seconds"),
                ),
            )
            missing_child_id = cursor.lastrowid
            try:
                enqueue_match_job("missing", missing_child_id, connection=connection)
                match_queued = True
            except MatchQueueFull:
                pass
            connection.commit()
        except Exception:
            connection.rollback()
            (UPLOAD_ROOT / "missing_children" / Path(photo_path).name).unlink(missing_ok=True)
            current_app.logger.exception("Unable to save missing-child report")
            abort(500)
        finally:
            connection.close()

        if match_queued:
            flash(
                "Missing-child report saved. AI face matching is queued; possible "
                "leads will appear after the scan and still require review.",
                "success",
            )
        else:
            flash(
                "Report saved. AI matching is busy and was not queued; staff can "
                "run a scan from AI Matching.",
                "warning",
            )

        # -------------------------------------------------
        # REDIRECT
        # -------------------------------------------------

        return redirect(
            url_for("public_directory.missing_child", child_id=missing_child_id)
        )


    # =====================================================
    # GET
    # =====================================================

    return render_template(
        "register_missing.html"
    )
