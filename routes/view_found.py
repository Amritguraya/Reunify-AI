from flask import Blueprint, render_template, abort

view_found_bp = Blueprint("view_found", __name__)

from storage import connect_database


@view_found_bp.route("/view_found")
def view_found():

    conn = connect_database(row_factory=True)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            f.id,
            f.estimated_age,
            f.gender,
            f.country,
            f.location_found,
            f.description,
            f.reporter_name,
            f.reporter_contact,
            f.found_date,
            f.photo_path,
            f.status,

            mh.missing_child_id,
            mh.confidence,
            mh.match_date,
            mh.verification_status

        FROM found_children f

        LEFT JOIN match_history mh
            ON f.id = mh.found_child_id

        ORDER BY f.id DESC
    """)

    children = cursor.fetchall()

    conn.close()

    return render_template(
        "view_found.html",
        children=children
    )

@view_found_bp.route("/view_found/<int:child_id>")
def found_child_detail(child_id):

    conn = connect_database(row_factory=True)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM found_children WHERE id = ?", (child_id,))
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
            mc.id AS missing_id,
            mc.name AS missing_name,
            mc.age AS missing_age,
            mc.city AS missing_city,
            mc.photo_path AS missing_photo
        FROM match_history mh
        LEFT JOIN missing_children mc ON mh.missing_child_id = mc.id
        WHERE mh.found_child_id = ?
        ORDER BY mh.match_date DESC
    """, (child_id,))
    matches = cursor.fetchall()
    conn.close()

    return render_template(
        "found_child_detail.html",
        child=child,
        matches=matches
    )
