"""Persistent, bounded work queue for face-matching scans."""

from __future__ import annotations

import threading
import time

from flask import Flask

from storage import connect_database


MAX_PENDING_MATCH_JOBS = 50
MAX_ATTEMPTS = 3
RUNNING_JOB_LEASE_SECONDS = 2 * 60 * 60
_worker_lock = threading.Lock()
_worker_started = False
_stop_event = threading.Event()


class MatchQueueFull(Exception):
    """Raised when the bounded AI queue has no capacity."""


def enqueue_match_job(
    case_type: str = "all",
    case_id: int | None = None,
    *,
    connection=None,
) -> int:
    """Add a de-duplicated job, optionally in the caller's current transaction."""
    if case_type not in {"missing", "found", "all"}:
        raise ValueError("Unsupported match job type.")
    if case_type == "all" and case_id is not None:
        raise ValueError("A full scan cannot include a case ID.")
    if case_type != "all" and (not isinstance(case_id, int) or case_id < 1):
        raise ValueError("A case scan requires a positive case ID.")

    owns_connection = connection is None
    if owns_connection:
        connection = connect_database()
    try:
        if owns_connection:
            connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            """SELECT id FROM match_jobs
               WHERE case_type = ? AND case_id IS ?
                 AND status IN ('queued', 'running')
               ORDER BY id LIMIT 1""",
            (case_type, case_id),
        ).fetchone()
        if existing:
            if owns_connection:
                connection.commit()
            return existing[0]

        pending = connection.execute(
            "SELECT COUNT(*) FROM match_jobs WHERE status IN ('queued', 'running')"
        ).fetchone()[0]
        if pending >= MAX_PENDING_MATCH_JOBS:
            if owns_connection:
                connection.rollback()
            raise MatchQueueFull

        cursor = connection.execute(
            """INSERT INTO match_jobs (case_type, case_id, status, created_at)
               VALUES (?, ?, 'queued', ?)""",
            (case_type, case_id, int(time.time())),
        )
        if owns_connection:
            connection.commit()
        return cursor.lastrowid
    except Exception:
        if owns_connection:
            connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()


def _claim_next_job():
    now = int(time.time())
    connection = connect_database(row_factory=True)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """UPDATE match_jobs
               SET status = CASE WHEN attempts >= ? THEN 'failed' ELSE 'queued' END,
                   started_at = NULL,
                   next_attempt_at = ?
               WHERE status = 'running' AND started_at < ?""",
            (MAX_ATTEMPTS, now, now - RUNNING_JOB_LEASE_SECONDS),
        )
        active = connection.execute(
            "SELECT 1 FROM match_jobs WHERE status = 'running' LIMIT 1"
        ).fetchone()
        if active:
            connection.commit()
            return None

        job = connection.execute(
            """SELECT id, case_type, case_id, attempts
               FROM match_jobs
               WHERE status = 'queued' AND next_attempt_at <= ?
               ORDER BY id LIMIT 1""",
            (now,),
        ).fetchone()
        if not job:
            connection.commit()
            return None

        connection.execute(
            """UPDATE match_jobs
               SET status = 'running', attempts = attempts + 1, started_at = ?
               WHERE id = ? AND status = 'queued'""",
            (now, job["id"]),
        )
        connection.commit()
        return dict(job)
    finally:
        connection.close()


def _finish_job(job_id: int, *, status: str, result_count: int = 0,
                error_type: str | None = None, retry_at: int = 0) -> None:
    connection = connect_database()
    try:
        connection.execute(
            """UPDATE match_jobs
               SET status = ?, result_count = ?, last_error = ?,
                   finished_at = ?, started_at = NULL, next_attempt_at = ?
               WHERE id = ?""",
            (
                status,
                result_count,
                error_type,
                int(time.time()) if status in {"completed", "failed"} else None,
                retry_at,
                job_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _process_job(app: Flask, job) -> None:
    from ai.face_matching import run_ai_matching

    try:
        with app.app_context():
            if job["case_type"] == "missing":
                count = run_ai_matching(missing_child_id=job["case_id"])
            elif job["case_type"] == "found":
                count = run_ai_matching(found_child_id=job["case_id"])
            else:
                count = run_ai_matching()
        _finish_job(job["id"], status="completed", result_count=count)
        app.logger.info("AI match job %s completed; candidates=%s", job["id"], count)
    except Exception as exc:
        connection = connect_database()
        try:
            attempts = connection.execute(
                "SELECT attempts FROM match_jobs WHERE id = ?", (job["id"],)
            ).fetchone()[0]
        finally:
            connection.close()
        retry = attempts < MAX_ATTEMPTS
        _finish_job(
            job["id"],
            status="queued" if retry else "failed",
            error_type=type(exc).__name__,
            retry_at=int(time.time()) + 60 if retry else 0,
        )
        app.logger.exception("AI match job %s failed", job["id"])


def _worker(app: Flask) -> None:
    while not _stop_event.is_set():
        try:
            job = _claim_next_job()
            if job:
                _process_job(app, job)
            else:
                _stop_event.wait(2)
        except Exception:
            app.logger.exception("AI match queue worker encountered an error")
            _stop_event.wait(5)


def start_match_worker(app: Flask) -> None:
    """Start one daemon worker per app process; unfinished jobs remain in SQLite."""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _stop_event.clear()
        thread = threading.Thread(
            target=_worker,
            args=(app,),
            name="reunify-ai-match-worker",
            daemon=True,
        )
        thread.start()
        _worker_started = True
