"""Public case search for the two paths to reunification: missing and found."""

import math

from flask import Blueprint, abort, render_template, request

from storage import connect_database


public_directory_bp = Blueprint("public_directory", __name__)
PAGE_SIZE = 36


def _page_number():
    try:
        page = int(request.args.get("page", "1"))
    except (TypeError, ValueError):
        abort(400, description="Page number must be a positive integer.")
    if not 1 <= page <= 100_000:
        abort(400, description="Page number must be between 1 and 100000.")
    return page


def _like_pattern(value):
    escaped = value.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{escaped}%"


@public_directory_bp.get("/missing-children")
def missing_children():
    query = request.args.get("q", "").strip()[:80]
    page = _page_number()
    offset = (page - 1) * PAGE_SIZE
    connection = connect_database(row_factory=True)
    where_sql = "public_listing = 1"
    params = ()
    if query:
        pattern = _like_pattern(query)
        where_sql += " AND (name LIKE ? ESCAPE '!' OR city LIKE ? ESCAPE '!')"
        params = (pattern, pattern)
    try:
        total_cases = connection.execute(
            f"SELECT COUNT(*) FROM missing_children WHERE {where_sql}", params
        ).fetchone()[0]
        children = connection.execute(
            f"""SELECT id, name, age, gender, city, missing_date, photo_path
                FROM missing_children WHERE {where_sql}
                ORDER BY id DESC LIMIT ? OFFSET ?""",
            (*params, PAGE_SIZE, offset),
        ).fetchall()
    finally:
        connection.close()
    total_pages = max(1, math.ceil(total_cases / PAGE_SIZE))
    if page > total_pages:
        abort(404)
    return render_template(
        "public_missing_children.html",
        children=children,
        search_query=query,
        page=page,
        total_pages=total_pages,
        total_cases=total_cases,
    )


@public_directory_bp.get("/missing-children/<int:child_id>")
def missing_child(child_id):
    connection = connect_database(row_factory=True)
    child = connection.execute(
        """SELECT id, name, age, gender, city, parent_name, phone,
                  missing_date, photo_path
           FROM missing_children
           WHERE id = ? AND public_listing = 1""",
        (child_id,),
    ).fetchone()
    connection.close()

    if child is None:
        abort(404)

    connection = connect_database(row_factory=True)
    try:
        potential_found_matches = connection.execute(
            """SELECT f.id, f.estimated_age, f.location_found, f.country,
                      f.found_date, f.photo_path, mh.confidence,
                      mh.match_type, mh.age_gap_years, mh.verification_status
               FROM match_history mh
               JOIN found_children f ON f.id = mh.found_child_id
               WHERE mh.missing_child_id = ?
                 AND mh.verification_status IN ('Pending', 'Verified')
                 AND (
                     mh.verification_status = 'Verified'
                     OR (
                         NOT EXISTS (
                             SELECT 1 FROM match_history confirmed
                             WHERE confirmed.missing_child_id = mh.missing_child_id
                               AND confirmed.verification_status = 'Verified'
                         )
                         AND NOT EXISTS (
                             SELECT 1 FROM match_history confirmed
                             WHERE confirmed.found_child_id = mh.found_child_id
                               AND confirmed.verification_status = 'Verified'
                         )
                     )
                 )
               ORDER BY
                   CASE WHEN mh.verification_status = 'Verified' THEN 0 ELSE 1 END,
                   mh.confidence DESC""",
            (child_id,),
        ).fetchall()
    finally:
        connection.close()

    return render_template(
        "public_missing_child_detail.html",
        child=child,
        potential_found_matches=potential_found_matches,
    )


@public_directory_bp.get("/found-children")
def found_children():
    """Let families search reports about children who have been found."""
    query = request.args.get("q", "").strip()[:80]
    page = _page_number()
    offset = (page - 1) * PAGE_SIZE
    connection = connect_database(row_factory=True)

    sql = """SELECT f.id, f.estimated_age, f.gender, f.country,
                    f.location_found, f.found_date, f.photo_path, f.status,
                    EXISTS (
                        SELECT 1 FROM match_history mh
                        WHERE mh.found_child_id = f.id
                          AND mh.verification_status = 'Verified'
                    ) AS has_verified_match
             FROM found_children f"""
    params = ()
    where_sql = ""
    if query:
        pattern = _like_pattern(query)
        where_sql = """ WHERE f.location_found LIKE ? ESCAPE '!'
                          OR f.country LIKE ? ESCAPE '!'
                          OR f.description LIKE ? ESCAPE '!'
                          OR f.reporter_name LIKE ? ESCAPE '!'
                          OR CAST(f.id AS TEXT) LIKE ? ESCAPE '!'"""
        params = (pattern, pattern, pattern, pattern, pattern)
    try:
        total_cases = connection.execute(
            "SELECT COUNT(*) FROM found_children f" + where_sql, params
        ).fetchone()[0]
        children = connection.execute(
            sql + where_sql + " ORDER BY f.id DESC LIMIT ? OFFSET ?",
            (*params, PAGE_SIZE, offset),
        ).fetchall()
    finally:
        connection.close()

    total_pages = max(1, math.ceil(total_cases / PAGE_SIZE))
    if page > total_pages:
        abort(404)
    return render_template(
        "public_found_children.html",
        children=children,
        search_query=query,
        page=page,
        total_pages=total_pages,
        total_cases=total_cases,
    )


@public_directory_bp.get("/found-children/<int:child_id>")
def found_child(child_id):
    """Show the complete public report and the submitter's contact details."""
    connection = connect_database(row_factory=True)
    try:
        child = connection.execute(
            """SELECT f.id, f.estimated_age, f.gender, f.country,
                      f.location_found, f.description, f.reporter_name,
                      f.reporter_contact, f.found_date, f.photo_path, f.status,
                      EXISTS (
                          SELECT 1 FROM match_history mh
                          WHERE mh.found_child_id = f.id
                            AND mh.verification_status = 'Verified'
                      ) AS has_verified_match
               FROM found_children f WHERE f.id = ?""",
            (child_id,),
        ).fetchone()
    finally:
        connection.close()

    if child is None:
        abort(404)

    connection = connect_database(row_factory=True)
    try:
        potential_matches = connection.execute(
            """SELECT mc.id, mc.name, mc.age, mc.gender, mc.city,
                      mc.missing_date, mc.photo_path, mh.confidence,
                      mh.match_type, mh.age_gap_years
               FROM match_history mh
               JOIN missing_children mc ON mc.id = mh.missing_child_id
               WHERE mh.found_child_id = ?
                 AND mh.verification_status = 'Pending'
                 AND mc.public_listing = 1
                 AND NOT EXISTS (
                     SELECT 1 FROM match_history confirmed
                     WHERE confirmed.found_child_id = mh.found_child_id
                       AND confirmed.verification_status = 'Verified'
                 )
               ORDER BY mh.confidence DESC""",
            (child_id,),
        ).fetchall()
        verified_matches = connection.execute(
            """SELECT mc.id, mc.name, mc.age, mc.gender, mc.city,
                      mc.missing_date, mc.photo_path
               FROM match_history mh
               JOIN missing_children mc ON mc.id = mh.missing_child_id
               WHERE mh.found_child_id = ?
                 AND mh.verification_status = 'Verified'
                 AND mc.public_listing = 1
               ORDER BY mh.match_date DESC""",
            (child_id,),
        ).fetchall()
    finally:
        connection.close()

    return render_template(
        "public_found_child_detail.html",
        child=child,
        potential_matches=potential_matches,
        verified_matches=verified_matches,
    )
