from flask import Blueprint, render_template

match_history_bp = Blueprint("match_history", __name__)

from storage import connect_database


@match_history_bp.route("/match-history")
def match_history():

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
        mc.id AS missing_id,
        mc.name AS missing_name,
        mc.photo_path AS missing_photo,
        fc.id AS found_id,
        fc.photo_path AS found_photo

    FROM match_history mh

    LEFT JOIN missing_children mc
        ON mh.missing_child_id = mc.id

    LEFT JOIN found_children fc
        ON mh.found_child_id = fc.id

    ORDER BY mh.match_date DESC
    """)

    matches = cursor.fetchall()

    conn.close()

    return render_template(
        "match_history.html",
        matches=matches
    )
