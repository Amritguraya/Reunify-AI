from flask import Blueprint, render_template, abort

view_missing_bp = Blueprint("view_missing", __name__)

from storage import connect_database


@view_missing_bp.route("/view_missing")
def view_missing():

    conn = connect_database(row_factory=True)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            m.id,
            m.name,
            m.age,
            m.gender,
            m.city,
            m.parent_name,
            m.phone,
            m.missing_date,
            m.photo_path,

            mh.found_child_id,
            mh.confidence,
            mh.match_date,
            mh.verification_status

        FROM missing_children m

        LEFT JOIN match_history mh
            ON m.id = mh.missing_child_id

        ORDER BY m.id DESC
    """)

    children = cursor.fetchall()

    conn.close()

    return render_template(
        "view_missing.html",
        children=children
    )

@view_missing_bp.route("/view_missing/<int:child_id>")
def missing_child_detail(child_id):

    conn = connect_database(row_factory=True)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM missing_children WHERE id = ?", (child_id,))
    child = cursor.fetchone()

    if child is None:
        conn.close()
        abort(404)

    cursor.execute("""
        SELECT
            mh.id AS match_id,
            mh.confidence,
            mh.match_date,
            mh.verification_status,
            mh.match_type,
            mh.age_gap_years,
            fc.id AS found_id,
            fc.estimated_age AS found_age,
            fc.location_found AS found_location,
            fc.photo_path AS found_photo
        FROM match_history mh
        LEFT JOIN found_children fc ON mh.found_child_id = fc.id
        WHERE mh.missing_child_id = ?
        ORDER BY mh.match_date DESC
    """, (child_id,))
    matches = cursor.fetchall()
    conn.close()

    return render_template(
        "missing_child_detail.html",
        child=child,
        matches=matches
    )
