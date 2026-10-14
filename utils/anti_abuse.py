"""Small persistent rate limit for internet-facing form submissions."""

import hashlib
import hmac
import sqlite3
import time

from flask import current_app, request

from storage import DATABASE


STAFF_AUTH_FAILURE_LIMIT = 10
STAFF_AUTH_WINDOW_SECONDS = 15 * 60


def consume_public_submission_limit(bucket: str, limit: int = 5, window_seconds: int = 3600) -> bool:
    """Rate-limit by a keyed hash of the remote address; never store raw IPs."""
    remote_address = request.remote_addr or "unknown"
    secret = str(current_app.config["SECRET_KEY"]).encode("utf-8")
    key_material = f"{bucket}:{remote_address}".encode("utf-8")
    client_key = hmac.new(secret, key_material, hashlib.sha256).hexdigest()
    now = int(time.time())

    connection = sqlite3.connect(DATABASE, timeout=10)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT window_started_at, attempts FROM public_submission_limits "
            "WHERE client_key = ?",
            (client_key,),
        ).fetchone()

        if row and now - row[0] < window_seconds:
            if row[1] >= limit:
                connection.rollback()
                return False
            connection.execute(
                "UPDATE public_submission_limits SET attempts = attempts + 1 "
                "WHERE client_key = ?",
                (client_key,),
            )
        else:
            connection.execute(
                "INSERT OR REPLACE INTO public_submission_limits "
                "(client_key, window_started_at, attempts) VALUES (?, ?, 1)",
                (client_key, now),
            )

        connection.execute(
            "DELETE FROM public_submission_limits WHERE window_started_at < ?",
            (now - 86400,),
        )
        connection.commit()
        return True
    finally:
        connection.close()


def _staff_auth_key() -> str:
    remote_address = request.remote_addr or "unknown"
    secret = str(current_app.config["SECRET_KEY"]).encode("utf-8")
    material = f"staff-auth:{remote_address}".encode("utf-8")
    return hmac.new(secret, material, hashlib.sha256).hexdigest()


def staff_auth_retry_after() -> int:
    """Return remaining lockout seconds after repeated failed staff logins."""
    connection = sqlite3.connect(DATABASE, timeout=10)
    try:
        row = connection.execute(
            "SELECT window_started_at, attempts FROM public_submission_limits "
            "WHERE client_key = ?",
            (_staff_auth_key(),),
        ).fetchone()
    finally:
        connection.close()

    if not row or row[1] < STAFF_AUTH_FAILURE_LIMIT:
        return 0
    remaining = STAFF_AUTH_WINDOW_SECONDS - (int(time.time()) - row[0])
    return max(0, remaining)


def record_staff_auth_failure() -> None:
    """Record a failed staff login without persisting a raw network address."""
    now = int(time.time())
    client_key = _staff_auth_key()
    connection = sqlite3.connect(DATABASE, timeout=10)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT window_started_at, attempts FROM public_submission_limits "
            "WHERE client_key = ?",
            (client_key,),
        ).fetchone()
        if row and now - row[0] < STAFF_AUTH_WINDOW_SECONDS:
            if row[1] < STAFF_AUTH_FAILURE_LIMIT:
                connection.execute(
                    "UPDATE public_submission_limits SET attempts = attempts + 1 "
                    "WHERE client_key = ?",
                    (client_key,),
                )
        else:
            connection.execute(
                "INSERT OR REPLACE INTO public_submission_limits "
                "(client_key, window_started_at, attempts) VALUES (?, ?, 1)",
                (client_key, now),
            )
        connection.execute(
            "DELETE FROM public_submission_limits WHERE window_started_at < ?",
            (now - 86400,),
        )
        connection.commit()
    finally:
        connection.close()


def clear_staff_auth_failures() -> None:
    """Reset the failure counter after a successful staff authentication."""
    connection = sqlite3.connect(DATABASE, timeout=10)
    try:
        client_key = _staff_auth_key()
        exists = connection.execute(
            "SELECT 1 FROM public_submission_limits WHERE client_key = ?",
            (client_key,),
        ).fetchone()
        if exists:
            connection.execute(
                "DELETE FROM public_submission_limits WHERE client_key = ?",
                (client_key,),
            )
            connection.commit()
    finally:
        connection.close()
