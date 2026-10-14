from datetime import datetime, timezone
from storage import DATABASE, connect_database, initialize_storage


# =========================================================
# DATABASE LOCATION
# =========================================================

initialize_storage()


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    return connect_database(row_factory=True)


# =========================================================
# CREATE DATABASE TABLES
# =========================================================

def initialize_database():

    conn = get_connection()

    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    cursor = conn.cursor()


    # =====================================================
    # MISSING CHILDREN
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS missing_children (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            age INTEGER,

            gender TEXT NOT NULL,

            city TEXT NOT NULL,

            parent_name TEXT NOT NULL,

            phone TEXT NOT NULL,

            missing_date TEXT NOT NULL,

            photo_path TEXT NOT NULL,

            public_listing INTEGER NOT NULL DEFAULT 0,

            public_listing_approved_at TEXT,

            public_listing_approval_reference TEXT,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP

        )
    """)


    # =====================================================
    # FOUND CHILDREN
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS found_children (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            estimated_age INTEGER,

            gender TEXT NOT NULL,

            country TEXT NOT NULL,

            location_found TEXT NOT NULL,

            description TEXT,

            reporter_name TEXT NOT NULL,

            reporter_contact TEXT NOT NULL,

            found_date TEXT NOT NULL,

            photo_path TEXT NOT NULL,

            status TEXT DEFAULT 'Pending',

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP

        )
    """)


    # =====================================================
    # MATCH HISTORY
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_history (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            missing_child_id INTEGER NOT NULL,

            found_child_id INTEGER NOT NULL,

            confidence REAL NOT NULL,

            match_date TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            verification_status TEXT
                DEFAULT 'Pending',

            FOREIGN KEY (missing_child_id)
                REFERENCES missing_children(id)
                ON DELETE CASCADE,

            FOREIGN KEY (found_child_id)
                REFERENCES found_children(id)
                ON DELETE CASCADE

        )
    """)

    # Add age-aware match fields in place for existing databases.
    match_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(match_history)")
    }
    if "match_type" not in match_columns:
        cursor.execute(
            "ALTER TABLE match_history "
            "ADD COLUMN match_type TEXT NOT NULL DEFAULT 'standard'"
        )
    if "age_gap_years" not in match_columns:
        cursor.execute(
            "ALTER TABLE match_history ADD COLUMN age_gap_years INTEGER"
        )

    # A candidate is not a verified reunion; reset legacy status values that
    # were set automatically when a candidate was first generated.
    cursor.execute(
        """UPDATE found_children
           SET status = 'Pending'
           WHERE status = 'Matched'
             AND NOT EXISTS (
                 SELECT 1 FROM match_history
                 WHERE match_history.found_child_id = found_children.id
                   AND match_history.verification_status = 'Verified'
             )"""
    )

    # Add public-listing fields in place for existing databases.
    missing_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(missing_children)")
    }
    if "public_listing" not in missing_columns:
        cursor.execute(
            "ALTER TABLE missing_children "
            "ADD COLUMN public_listing INTEGER NOT NULL DEFAULT 0"
        )
    if "public_listing_approved_at" not in missing_columns:
        cursor.execute(
            "ALTER TABLE missing_children ADD COLUMN public_listing_approved_at TEXT"
        )
    if "public_listing_approval_reference" not in missing_columns:
        cursor.execute(
            "ALTER TABLE missing_children "
            "ADD COLUMN public_listing_approval_reference TEXT"
        )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS public_case_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            missing_child_id INTEGER NOT NULL,
            action TEXT NOT NULL CHECK (action IN ('published', 'unpublished')),
            approval_reference TEXT,
            actor TEXT NOT NULL,
            occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (missing_child_id)
                REFERENCES missing_children(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_migrations (
            migration_key TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Public case search is a core discovery path chosen by the platform owner.
    # Apply that choice once to records already in the database; staff can
    # still unpublish a case when it is reunited or should leave the directory.
    public_rollout = "public-case-search-rollout-2026-10"
    rollout_applied = cursor.execute(
        "SELECT 1 FROM app_migrations WHERE migration_key = ?",
        (public_rollout,),
    ).fetchone()
    if not rollout_applied:
        existing_private_cases = cursor.execute(
            "SELECT id FROM missing_children WHERE public_listing = 0"
        ).fetchall()
        rollout_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        for (case_id,) in existing_private_cases:
            cursor.execute(
                """UPDATE missing_children
                   SET public_listing = 1,
                       public_listing_approved_at = ?,
                       public_listing_approval_reference = 'owner-requested-public-rollout'
                   WHERE id = ?""",
                (rollout_at, case_id),
            )
            cursor.execute(
                """INSERT INTO public_case_audit
                   (missing_child_id, action, approval_reference, actor, occurred_at)
                   VALUES (?, 'published', 'owner-requested-public-rollout',
                           'system-migration', ?)""",
                (case_id, rollout_at),
            )
        cursor.execute(
            "INSERT INTO app_migrations (migration_key) VALUES (?)",
            (public_rollout,),
        )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sightings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            missing_child_id INTEGER NOT NULL,
            reporter_contact TEXT NOT NULL,
            details TEXT NOT NULL,
            submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'New',
            reviewed_at TEXT,
            FOREIGN KEY (missing_child_id)
                REFERENCES missing_children(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS public_submission_limits (
            client_key TEXT PRIMARY KEY,
            window_started_at INTEGER NOT NULL,
            attempts INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_type TEXT NOT NULL CHECK (case_type IN ('missing', 'found', 'all')),
            case_id INTEGER,
            status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
            attempts INTEGER NOT NULL DEFAULT 0,
            result_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at INTEGER NOT NULL,
            started_at INTEGER,
            finished_at INTEGER,
            next_attempt_at INTEGER NOT NULL DEFAULT 0,
            CHECK ((case_type = 'all' AND case_id IS NULL)
                OR (case_type IN ('missing', 'found') AND case_id > 0))
        )
    """)

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_missing_public_listing "
        "ON missing_children(public_listing, id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sightings_review "
        "ON sightings(status, submitted_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_submission_limit_window "
        "ON public_submission_limits(window_started_at)"
    )
    duplicate_match_pair = cursor.execute(
        """SELECT 1 FROM match_history
           GROUP BY missing_child_id, found_child_id
           HAVING COUNT(*) > 1 LIMIT 1"""
    ).fetchone()
    if duplicate_match_pair:
        # Preserve historical rows from older databases. The matcher also
        # checks for an existing pair inside its write transaction.
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_match_history_case_pair_lookup "
            "ON match_history(missing_child_id, found_child_id)"
        )
    else:
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_match_history_case_pair "
            "ON match_history(missing_child_id, found_child_id)"
        )
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_match_jobs_active_case
        ON match_jobs(case_type, IFNULL(case_id, -1))
        WHERE status IN ('queued', 'running')
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_match_jobs_queue "
        "ON match_jobs(status, next_attempt_at, id)"
    )


    # =====================================================
    # SAVE DATABASE
    # =====================================================

    conn.commit()

    conn.close()


# =========================================================
# RUN DATABASE INITIALIZATION
# =========================================================

if __name__ == "__main__":

    initialize_database()

    print("Database initialized successfully.")

    print("Database Path:")
    print(DATABASE)
