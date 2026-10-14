"""Public, rate-limited sighting submissions and staff-only review."""

from datetime import datetime, timezone
import time

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from storage import connect_database
from utils.anti_abuse import consume_public_submission_limit


public_sightings_bp = Blueprint("public_sightings", __name__)
def _public_case(case_id):
    connection = connect_database(row_factory=True)
    child = connection.execute(
        """SELECT id, name, age, gender, city, missing_date, photo_path
           FROM missing_children
           WHERE id = ? AND public_listing = 1""",
        (case_id,),
    ).fetchone()
    connection.close()
    return child


def _form_serializer():
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt="reunify-public-sighting-form",
    )


@public_sightings_bp.route("/report-sighting/<int:child_id>", methods=["GET", "POST"])
def report_sighting(child_id):
    child = _public_case(child_id)
    if child is None:
        abort(404)

    if request.method == "GET":
        form_token = _form_serializer().dumps({"issued_at": int(time.time())})
        return render_template(
            "public_sighting_form.html",
            child=child,
            form_token=form_token,
            errors=[],
            contact_value="",
            details_value="",
        )

    # A filled honeypot is treated like success but never stored.
    if request.form.get("company_website", "").strip():
        return render_template("public_sighting_received.html", child=child)

    try:
        token_data = _form_serializer().loads(
            request.form.get("form_token", ""), max_age=3600
        )
        age_seconds = int(time.time()) - int(token_data["issued_at"])
        if age_seconds < 3:
            abort(400, description="Please take a moment to review the form before submitting.")
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        abort(400, description="This form expired. Please reload it and try again.")

    if not consume_public_submission_limit("sighting", limit=5):
        abort(429, description="Too many reports were submitted. Please try again later.")

    reporter_contact = " ".join(request.form.get("reporter_contact", "").split())
    details = request.form.get("details", "").strip()
    errors = []
    if not 5 <= len(reporter_contact) <= 160:
        errors.append("Enter a contact method between 5 and 160 characters.")
    if any(ord(char) < 32 and char not in "\n\t" for char in reporter_contact):
        errors.append("The contact method contains invalid characters.")
    if not 15 <= len(details) <= 2000:
        errors.append("Describe the sighting in 15 to 2,000 characters.")
    if any(ord(char) < 32 and char not in "\n\t" for char in details):
        errors.append("The sighting details contain invalid control characters.")

    if errors:
        form_token = _form_serializer().dumps({"issued_at": int(time.time())})
        return render_template(
            "public_sighting_form.html",
            child=child,
            form_token=form_token,
            errors=errors,
            contact_value=reporter_contact,
            details_value=details[:2000],
        ), 400

    submitted_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    connection = connect_database()
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """INSERT INTO sightings
               (missing_child_id, reporter_contact, details, submitted_at)
               VALUES (?, ?, ?, ?)""",
            (child_id, reporter_contact, details, submitted_at),
        )
        connection.commit()
    finally:
        connection.close()

    return render_template("public_sighting_received.html", child=child)


@public_sightings_bp.get("/sightings")
def review_sightings():
    connection = connect_database(row_factory=True)
    sightings = connection.execute(
        """SELECT s.id, s.reporter_contact, s.details, s.submitted_at,
                  s.status, s.reviewed_at, m.id AS child_id, m.name AS child_name
           FROM sightings s
           JOIN missing_children m ON m.id = s.missing_child_id
           ORDER BY CASE WHEN s.status = 'New' THEN 0 ELSE 1 END,
                    s.submitted_at DESC"""
    ).fetchall()
    connection.close()
    return render_template("staff_sightings.html", sightings=sightings)


@public_sightings_bp.post("/sightings/<int:sighting_id>/mark-reviewed")
def mark_sighting_reviewed(sighting_id):
    reviewed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    connection = connect_database()
    connection.execute(
        "UPDATE sightings SET status = 'Reviewed', reviewed_at = ? WHERE id = ?",
        (reviewed_at, sighting_id),
    )
    connection.commit()
    connection.close()
    return redirect(url_for("public_sightings.review_sightings"))
