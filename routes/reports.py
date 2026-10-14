from flask import Blueprint, render_template
from datetime import datetime

reports_bp = Blueprint("reports", __name__)

from storage import connect_database


@reports_bp.route("/reports")
def reports():

    conn = connect_database(row_factory=True)
    cursor = conn.cursor()

    # =========================================================
    # TOTAL MISSING CHILDREN
    # =========================================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM missing_children
    """)

    total_missing = cursor.fetchone()[0]


    # =========================================================
    # TOTAL FOUND CHILDREN
    # =========================================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM found_children
    """)

    total_found = cursor.fetchone()[0]


    # =========================================================
    # TOTAL AI MATCHES
    # =========================================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM match_history
    """)

    total_matches = cursor.fetchone()[0]


    # =========================================================
    # PENDING MATCHES
    # =========================================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM match_history
        WHERE verification_status = 'Pending'
           OR verification_status IS NULL
           OR verification_status = ''
    """)

    pending = cursor.fetchone()[0]


    # =========================================================
    # VERIFIED MATCHES
    # =========================================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM match_history
        WHERE verification_status = 'Verified'
    """)

    verified = cursor.fetchone()[0]


    # =========================================================
    # REJECTED MATCHES
    # =========================================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM match_history
        WHERE verification_status = 'Rejected'
    """)

    rejected = cursor.fetchone()[0]


    # =========================================================
    # EXACT AI MATCH INFORMATION
    #
    # Join match_history with both child tables so the report
    # contains actual child names/details instead of only IDs.
    # =========================================================

    cursor.execute("""
        SELECT

            mh.id AS match_id,

            mh.missing_child_id,
            mh.found_child_id,

            mh.confidence,
            mh.match_date,
            mh.verification_status,

            mc.name AS missing_name,
            mc.age AS missing_age,
            mc.gender AS missing_gender,
            mc.city AS missing_city,
            mc.parent_name AS parent_name,
            mc.phone AS parent_phone,

            fc.estimated_age AS found_age,
            fc.gender AS found_gender,
            fc.location_found AS found_location,
            fc.country AS found_country,
            fc.reporter_name AS reporter_name,
            fc.reporter_contact AS reporter_contact

        FROM match_history mh

        LEFT JOIN missing_children mc
            ON mh.missing_child_id = mc.id

        LEFT JOIN found_children fc
            ON mh.found_child_id = fc.id

        ORDER BY mh.id DESC
    """)

    report_matches = cursor.fetchall()


    # =========================================================
    # CLOSE DATABASE
    # =========================================================

    conn.close()


    # =========================================================
    # SEND DATA TO TEMPLATE
    # =========================================================

    return render_template(
        "reports.html",

        # Main statistics
        missing=total_missing,
        found=total_found,
        matches=total_matches,

        # Verification statistics
        pending=pending,
        verified=verified,
        rejected=rejected,

        # Detailed match records
        report_matches=report_matches,

        # Report date
        current_date=datetime.now().strftime("%d %B %Y")
    )
