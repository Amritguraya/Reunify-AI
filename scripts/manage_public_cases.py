"""Staff CLI for publishing/unpublishing approved missing-child cases."""

import argparse
from datetime import datetime, timezone
import getpass
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.database import initialize_database  # noqa: E402
from storage import DATABASE, resolve_upload_path  # noqa: E402


REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{2,79}$")


def connect():
    import sqlite3

    connection = sqlite3.connect(DATABASE, timeout=10)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def list_cases():
    connection = connect()
    rows = connection.execute(
        """SELECT id, name, city, missing_date, public_listing,
                  public_listing_approved_at, public_listing_approval_reference
           FROM missing_children ORDER BY id DESC"""
    ).fetchall()
    connection.close()
    if not rows:
        print("No missing-child cases found.")
        return
    print("ID | Child | City | Missing date | Public | Approval reference")
    for row in rows:
        print(
            f"{row[0]} | {row[1]} | {row[2]} | {row[3]} | "
            f"{'yes' if row[4] else 'no'} | {row[6] or '—'}"
        )


def publish_case(case_id, approval_reference):
    if not REFERENCE_PATTERN.fullmatch(approval_reference):
        raise SystemExit(
            "Approval reference must be 3–80 letters, numbers, dots, underscores, "
            "slashes, or hyphens. Do not enter a child's or guardian's name here."
        )

    connection = connect()
    row = connection.execute(
        "SELECT photo_path FROM missing_children WHERE id = ?", (case_id,)
    ).fetchone()
    if row is None:
        connection.close()
        raise SystemExit(f"Missing-child case {case_id} was not found.")
    photo_path = resolve_upload_path(row[0])
    if not photo_path or not Path(photo_path).is_file():
        connection.close()
        raise SystemExit("This case has no available photograph; it cannot be published.")

    approved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    actor = os.environ.get("STAFF_USERNAME") or getpass.getuser()
    connection.execute(
        """UPDATE missing_children
           SET public_listing = 1,
               public_listing_approved_at = ?,
               public_listing_approval_reference = ?
           WHERE id = ?""",
        (approved_at, approval_reference, case_id),
    )
    connection.execute(
        """INSERT INTO public_case_audit
           (missing_child_id, action, approval_reference, actor, occurred_at)
           VALUES (?, 'published', ?, ?, ?)""",
        (case_id, approval_reference, actor, approved_at),
    )
    connection.commit()
    connection.close()
    print(f"Case {case_id} is now listed publicly. Keep the approval record securely.")


def unpublish_case(case_id):
    connection = connect()
    row = connection.execute(
        "SELECT public_listing FROM missing_children WHERE id = ?", (case_id,)
    ).fetchone()
    if row is None:
        connection.close()
        raise SystemExit(f"Missing-child case {case_id} was not found.")
    occurred_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    actor = os.environ.get("STAFF_USERNAME") or getpass.getuser()
    if row[0]:
        connection.execute(
            "UPDATE missing_children SET public_listing = 0 WHERE id = ?",
            (case_id,),
        )
        connection.execute(
            """INSERT INTO public_case_audit
               (missing_child_id, action, approval_reference, actor, occurred_at)
               VALUES (?, 'unpublished', NULL, ?, ?)""",
            (case_id, actor, occurred_at),
        )
        connection.commit()
    connection.close()
    print(f"Case {case_id} is not publicly listed.")


def show_audit(case_id):
    connection = connect()
    rows = connection.execute(
        """SELECT action, approval_reference, actor, occurred_at
           FROM public_case_audit WHERE missing_child_id = ?
           ORDER BY id DESC""",
        (case_id,),
    ).fetchall()
    connection.close()
    if not rows:
        print("No publication actions recorded for this case.")
        return
    for action, reference, actor, occurred_at in rows:
        print(f"{occurred_at} | {action} | {actor} | {reference or '—'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List cases and current publication state")
    publish = commands.add_parser("publish", help="Publish after approval is documented")
    publish.add_argument("case_id", type=int)
    publish.add_argument("--approval-reference", required=True)
    unpublish = commands.add_parser("unpublish", help="Remove a public listing")
    unpublish.add_argument("case_id", type=int)
    audit = commands.add_parser("audit", help="Show publication actions for a case")
    audit.add_argument("case_id", type=int)
    args = parser.parse_args()

    initialize_database()
    if args.command == "list":
        list_cases()
    elif args.command == "publish":
        publish_case(args.case_id, args.approval_reference)
    elif args.command == "unpublish":
        unpublish_case(args.case_id)
    else:
        show_audit(args.case_id)


if __name__ == "__main__":
    main()
