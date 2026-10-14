"""Age-aware candidate search for missing and found child photographs."""

import os
from datetime import datetime

from ai.database import get_connection
from ai.embeddings import get_face_embedding
from ai.matcher import cosine_similarity


# The cross-age floor is only for review leads whose reported ages and dates
# form a plausible timeline. It is deliberately separate from standard matches.
STANDARD_MATCH_THRESHOLD = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.52"))
CROSS_AGE_REVIEW_THRESHOLD = float(
    os.environ.get("CROSS_AGE_REVIEW_THRESHOLD", "0.40")
)
if not 0.0 <= STANDARD_MATCH_THRESHOLD <= 1.0:
    raise RuntimeError("FACE_MATCH_THRESHOLD must be between 0 and 1.")
if not 0.0 <= CROSS_AGE_REVIEW_THRESHOLD <= 1.0:
    raise RuntimeError("CROSS_AGE_REVIEW_THRESHOLD must be between 0 and 1.")

CROSS_AGE_MIN_YEARS = 5
AGE_TIMELINE_TOLERANCE_YEARS = 4
MAX_CANDIDATES_PER_FOUND_REPORT = 3


def _parse_case_date(value):
    if not value:
        return None

    text = str(value).strip()
    for date_format in ("%d-%m-%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _cross_age_gap(missing, found):
    """Return elapsed years only when the reported ages fit the case timeline."""
    missing_age = missing["age"]
    found_age = found["estimated_age"]
    missing_date = _parse_case_date(missing["missing_date"])
    found_date = _parse_case_date(found["found_date"])

    if missing_age is None or found_age is None or not missing_date or not found_date:
        return None

    elapsed_years = (found_date - missing_date).days / 365.2425
    if elapsed_years < CROSS_AGE_MIN_YEARS:
        return None

    reported_age_gap = float(found_age) - float(missing_age)
    if abs(reported_age_gap - elapsed_years) > AGE_TIMELINE_TOLERANCE_YEARS:
        return None

    return max(0, int(round(reported_age_gap)))


def run_ai_matching(found_child_id=None, missing_child_id=None):
    """Create up to three review candidates per new found report.

    Supplying one ID runs an incremental scan after a new report is submitted.
    With neither ID, the staff action scans all unverified records.
    """
    if found_child_id is not None and missing_child_id is not None:
        raise ValueError("Choose a found-child scan or a missing-child scan, not both.")

    conn = get_connection()
    try:
        cursor = conn.cursor()

        missing_query = """
            SELECT m.id, m.name, m.age, m.missing_date, m.photo_path
            FROM missing_children m
            WHERE NOT EXISTS (
                SELECT 1
                FROM match_history verified
                WHERE verified.missing_child_id = m.id
                  AND verified.verification_status = 'Verified'
            )
        """
        missing_params = ()
        if missing_child_id is not None:
            missing_query += " AND m.id = ?"
            missing_params = (missing_child_id,)
        cursor.execute(missing_query, missing_params)
        missing_children = cursor.fetchall()

        found_query = """
            SELECT f.id, f.estimated_age, f.found_date, f.photo_path
            FROM found_children f
            WHERE NOT EXISTS (
                SELECT 1
                FROM match_history verified
                WHERE verified.found_child_id = f.id
                  AND verified.verification_status = 'Verified'
            )
        """
        found_params = ()
        if found_child_id is not None:
            found_query += " AND f.id = ?"
            found_params = (found_child_id,)
        cursor.execute(found_query, found_params)
        found_children = cursor.fetchall()

        if not missing_children or not found_children:
            return 0

        cursor.execute(
            "SELECT missing_child_id, found_child_id FROM match_history"
        )
        existing_pairs = {
            (row["missing_child_id"], row["found_child_id"])
            for row in cursor.fetchall()
        }
    finally:
        conn.close()

    missing_embeddings = {
        child["id"]: embedding
        for child in missing_children
        if (embedding := get_face_embedding(child["photo_path"])) is not None
    }
    found_embeddings = {
        child["id"]: embedding
        for child in found_children
        if (embedding := get_face_embedding(child["photo_path"])) is not None
    }

    candidates_by_found = {}
    for found in found_children:
        found_id = found["id"]
        found_embedding = found_embeddings.get(found_id)
        if found_embedding is None:
            continue

        for missing in missing_children:
            missing_id = missing["id"]
            missing_embedding = missing_embeddings.get(missing_id)
            if missing_embedding is None or (missing_id, found_id) in existing_pairs:
                continue

            similarity = cosine_similarity(missing_embedding, found_embedding)
            age_gap = _cross_age_gap(missing, found)
            is_cross_age = age_gap is not None
            threshold = (
                CROSS_AGE_REVIEW_THRESHOLD
                if is_cross_age
                else STANDARD_MATCH_THRESHOLD
            )
            if similarity < threshold:
                continue

            candidates_by_found.setdefault(found_id, []).append(
                {
                    "missing_id": missing_id,
                    "found_id": found_id,
                    "similarity": similarity,
                    "match_type": "cross_age" if is_cross_age else "standard",
                    "age_gap_years": age_gap,
                }
            )

    total_matches = 0
    matched_at = datetime.now().astimezone().isoformat(timespec="seconds")
    write_connection = get_connection()
    try:
        write_connection.execute("BEGIN IMMEDIATE")
        write_cursor = write_connection.cursor()
        for found_id, candidates in candidates_by_found.items():
            candidates.sort(key=lambda candidate: candidate["similarity"], reverse=True)
            for candidate in candidates[:MAX_CANDIDATES_PER_FOUND_REPORT]:
                write_cursor.execute(
                    """INSERT OR IGNORE INTO match_history
                       (missing_child_id, found_child_id, confidence, match_date,
                        verification_status, match_type, age_gap_years)
                       SELECT ?, ?, ?, ?, 'Pending', ?, ?
                       WHERE EXISTS (
                           SELECT 1 FROM missing_children WHERE id = ?
                       )
                         AND EXISTS (
                           SELECT 1 FROM found_children WHERE id = ?
                       )
                         AND NOT EXISTS (
                           SELECT 1 FROM match_history
                           WHERE missing_child_id = ?
                             AND verification_status = 'Verified'
                       )
                         AND NOT EXISTS (
                           SELECT 1 FROM match_history
                           WHERE found_child_id = ?
                             AND verification_status = 'Verified'
                         )
                         AND NOT EXISTS (
                             SELECT 1 FROM match_history
                             WHERE missing_child_id = ?
                               AND found_child_id = ?
                       )""",
                    (
                        candidate["missing_id"],
                        candidate["found_id"],
                        candidate["similarity"],
                        matched_at,
                        candidate["match_type"],
                        candidate["age_gap_years"],
                        candidate["missing_id"],
                        candidate["found_id"],
                        candidate["missing_id"],
                        candidate["found_id"],
                        candidate["missing_id"],
                        candidate["found_id"],
                    ),
                )
                total_matches += write_cursor.rowcount
        write_connection.commit()
    except Exception:
        write_connection.rollback()
        raise
    finally:
        write_connection.close()
    return total_matches
