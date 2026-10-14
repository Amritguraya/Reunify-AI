"""Public intake for found-child reports."""

from datetime import datetime
import re
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from storage import UPLOAD_ROOT, connect_database
from utils.anti_abuse import consume_public_submission_limit
from utils.uploads import save_child_photo
from ai.match_queue import MatchQueueFull, enqueue_match_job


register_found_bp = Blueprint("register_found", __name__)

_ALLOWED_GENDERS = {"Male", "Female", "Other"}
_ALLOWED_COUNTRIES = {
    "India",
    "United States",
    "United Kingdom",
    "Canada",
    "Australia",
    "United Arab Emirates",
}
_NAME_PATTERN = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ '.-][A-Za-zÀ-ÖØ-öø-ÿ]+)*$")
_PHONE_PATTERN = re.compile(r"^\d{7,15}$")


@register_found_bp.route("/register_found", methods=["GET", "POST"])
def register_found():
    if request.method == "POST":
        # Treat automated honeypot submissions like success without storing them.
        if request.form.get("company_website", "").strip():
            return redirect(url_for("dashboard.dashboard"))

        if not consume_public_submission_limit("found-registration", limit=5):
            abort(429, description="Too many reports were submitted. Please try again later.")

        age_text = request.form.get("estimated_age", "").strip()
        gender = request.form.get("gender", "").strip()
        country = request.form.get("country", "").strip()
        location = request.form.get("location_found", "").strip()
        description = request.form.get("description", "").strip()
        reporter_name = request.form.get("reporter_name", "").strip()
        reporter_contact = request.form.get("reporter_contact", "").strip()
        day = request.form.get("day", "").strip()
        month = request.form.get("month", "").strip()
        year = request.form.get("year", "").strip()

        try:
            age = int(age_text)
        except ValueError:
            abort(400, description="Enter a whole-number estimated age between 0 and 99.")

        if not 0 <= age <= 18:
            abort(400, description="Enter a whole-number estimated age between 0 and 18.")
        if gender not in _ALLOWED_GENDERS or country not in _ALLOWED_COUNTRIES:
            abort(400, description="Select a valid gender and country.")
        if not location or len(location) > 100:
            abort(400, description="Enter a location of 1 to 100 characters.")
        if any(ord(char) < 32 and char not in "\n\t" for char in location):
            abort(400, description="The location contains invalid control characters.")
        if len(description) > 500:
            abort(400, description="Keep identifying details within 500 characters.")
        if any(ord(char) < 32 and char not in "\n\t" for char in description):
            abort(400, description="The report contains invalid control characters.")
        if (
            not 1 <= len(reporter_name) <= 100
            or not _NAME_PATTERN.fullmatch(reporter_name)
        ):
            abort(400, description="Enter a valid reporter name.")
        if not _PHONE_PATTERN.fullmatch(reporter_contact):
            abort(400, description="Enter a contact number containing 7 to 15 digits.")

        try:
            found_day = datetime(int(year), int(month), int(day))
        except (ValueError, TypeError):
            abort(400, description="Enter a valid date when the child was found.")
        if found_day.year < 1900 or found_day.date() > datetime.now().date():
            abort(400, description="The found date must be between 1900 and today.")

        photo = request.files.get("photo")
        if not photo or not photo.filename:
            abort(400, description="A child photograph is required.")
        try:
            photo_path = save_child_photo(photo, "found_children")
        except ValueError as exc:
            abort(400, description=str(exc))

        found_date = f"{found_day.day}-{found_day.month}-{found_day.year}"
        connection = connect_database()
        match_queued = False
        try:
            connection.execute("BEGIN IMMEDIATE")
            insert_cursor = connection.execute(
                """INSERT INTO found_children
                   (estimated_age, gender, country, location_found, description,
                    reporter_name, reporter_contact, found_date, photo_path, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    age,
                    gender,
                    country,
                    location,
                    description,
                    reporter_name,
                    reporter_contact,
                    found_date,
                    photo_path,
                    "Pending",
                ),
            )
            found_child_id = insert_cursor.lastrowid
            try:
                enqueue_match_job("found", found_child_id, connection=connection)
                match_queued = True
            except MatchQueueFull:
                pass
            connection.commit()
        except Exception:
            connection.rollback()
            (UPLOAD_ROOT / "found_children" / photo_path.rsplit("/", 1)[-1]).unlink(missing_ok=True)
            current_app.logger.exception("Unable to save found-child report")
            abort(500)
        finally:
            connection.close()

        if match_queued:
            flash(
                "Found-child report saved. AI face matching is queued; possible "
                "leads will appear after the scan and still require review.",
                "success",
            )
        else:
            flash(
                "Report saved. AI matching is busy and was not queued; staff can "
                "run a scan from AI Matching.",
                "warning",
            )

        return redirect(
            url_for("public_directory.found_child", child_id=found_child_id)
        )

    return render_template("register_found.html")
