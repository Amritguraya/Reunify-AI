from flask import Blueprint, render_template

dashboard_bp = Blueprint("dashboard", __name__)

from storage import connect_database

@dashboard_bp.route("/")
def dashboard():

    conn = connect_database()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM missing_children")
    missing = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM found_children")
    found = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM match_history")
    matches = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM match_history
        WHERE verification_status='Pending'
    """)
    pending = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        missing=missing,
        found=found,
        matches=matches,
        pending=pending
    )
