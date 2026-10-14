"""Staff review actions for AI-generated candidate matches."""

from flask import Blueprint, abort, redirect, render_template, url_for

from storage import connect_database


verify_match_bp = Blueprint("verify_match", __name__)


@verify_match_bp.route("/verify-match/<int:match_id>")
def verify_page(match_id):
    connection = connect_database(row_factory=True)
    try:
        match = connection.execute(
            """SELECT mh.*,
                      mc.name AS missing_name, mc.age AS missing_age,
                      mc.gender AS missing_gender, mc.city AS missing_city,
                      mc.photo_path AS missing_photo,
                      fc.estimated_age AS found_age, fc.gender AS found_gender,
                      fc.location_found AS found_location, fc.found_date AS found_date,
                      fc.photo_path AS found_photo
               FROM match_history mh
               LEFT JOIN missing_children mc ON mh.missing_child_id = mc.id
               LEFT JOIN found_children fc ON mh.found_child_id = fc.id
               WHERE mh.id = ?""",
            (match_id,),
        ).fetchone()
    finally:
        connection.close()

    if match is None:
        abort(404)
    return render_template("verify_match.html", match=match)


@verify_match_bp.post("/verify/<int:match_id>")
def verify(match_id):
    connection = connect_database()
    try:
        connection.execute("BEGIN IMMEDIATE")
        match = connection.execute(
            """SELECT missing_child_id, found_child_id, verification_status
               FROM match_history WHERE id = ?""",
            (match_id,),
        ).fetchone()
        if match is None:
            abort(404)
        if match[2] == "Rejected":
            abort(409, description="A rejected candidate cannot be verified.")

        conflict = connection.execute(
            """SELECT 1 FROM match_history
               WHERE verification_status = 'Verified' AND id <> ?
                 AND (missing_child_id = ? OR found_child_id = ?)
               LIMIT 1""",
            (match_id, match[0], match[1]),
        ).fetchone()
        if conflict:
            abort(
                409,
                description="One of these cases already has a different verified match.",
            )

        connection.execute(
            "UPDATE match_history SET verification_status = 'Verified' WHERE id = ?",
            (match_id,),
        )
        connection.execute(
            "UPDATE found_children SET status = 'Matched' WHERE id = ?",
            (match[1],),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return redirect(url_for("match_history.match_history"))


@verify_match_bp.post("/reject/<int:match_id>")
def reject(match_id):
    connection = connect_database()
    try:
        connection.execute("BEGIN IMMEDIATE")
        match = connection.execute(
            "SELECT found_child_id, verification_status FROM match_history WHERE id = ?",
            (match_id,),
        ).fetchone()
        if match is None:
            abort(404)
        if match[1] == "Verified":
            abort(409, description="A verified match cannot be rejected here.")

        connection.execute(
            "UPDATE match_history SET verification_status = 'Rejected' WHERE id = ?",
            (match_id,),
        )
        connection.execute(
            """UPDATE found_children
               SET status = CASE WHEN EXISTS (
                   SELECT 1 FROM match_history
                   WHERE found_child_id = found_children.id
                     AND verification_status = 'Verified'
               ) THEN 'Matched' ELSE 'Pending' END
               WHERE id = ?""",
            (match[0],),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return redirect(url_for("match_history.match_history"))
