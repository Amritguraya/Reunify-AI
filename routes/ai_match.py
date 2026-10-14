from flask import Blueprint, current_app, render_template, request

from ai.match_queue import MatchQueueFull, enqueue_match_job

ai_match_bp = Blueprint("ai_match", __name__)

from storage import connect_database


@ai_match_bp.route("/ai_match", methods=["GET", "POST"])
def ai_match():

    message = None
    message_type = "info"

    # -----------------------------------------
    # RUN AI MATCHING
    # -----------------------------------------

    if request.method == "POST":

        try:
            enqueue_match_job("all")
            message = "A full AI candidate scan has been queued. Refresh this page later to review new candidates."
            message_type = "success"
        except MatchQueueFull:
            message = "The AI matching queue is full. Wait for the current scans to finish and try again."
            message_type = "danger"
        except Exception:
            current_app.logger.exception("Unable to queue full AI match scan")
            message = "AI matching could not be queued. Check the application logs."
            message_type = "danger"


    # -----------------------------------------
    # LOAD MATCH HISTORY
    # -----------------------------------------

    conn = connect_database(row_factory=True)

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            mh.id,
            mh.confidence,
            mh.match_date,
            mh.verification_status,
            mh.match_type,
            mh.age_gap_years,

            mc.id AS missing_child_id,
            mc.name AS missing_name,
            mc.age AS missing_age,
            mc.gender AS missing_gender,
            mc.city AS missing_city,
            mc.parent_name,
            mc.phone,
            mc.photo_path AS missing_photo,

            fc.id AS found_child_id,
            fc.estimated_age AS found_age,
            fc.found_date,
            fc.gender AS found_gender,
            fc.location_found,
            fc.description,
            fc.photo_path AS found_photo

        FROM match_history mh

        LEFT JOIN missing_children mc
            ON mh.missing_child_id = mc.id

        LEFT JOIN found_children fc
            ON mh.found_child_id = fc.id

        ORDER BY mh.confidence DESC
    """)

    matches = cursor.fetchall()


    # -----------------------------------------
    # DATABASE COUNTS
    # -----------------------------------------

    cursor.execute("""
        SELECT COUNT(*) FROM missing_children
    """)

    missing_count = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*) FROM found_children
    """)

    found_count = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*) FROM match_history
    """)

    match_count = cursor.fetchone()[0]


    conn.close()


    return render_template(
        "ai_match.html",
        matches=matches,
        missing_count=missing_count,
        found_count=found_count,
        match_count=match_count,
        message=message,
        message_type=message_type
    )
