"""Flask application entry point with production access and storage settings."""

import os
import secrets
from xml.sax.saxutils import escape
from urllib.parse import urlsplit

from flask import Flask, Response, abort, g, redirect, request, send_file, url_for
from werkzeug.security import check_password_hash

from storage import UPLOAD_ROOT, connect_database, initialize_storage
from utils.anti_abuse import (
    clear_staff_auth_failures,
    record_staff_auth_failure,
    staff_auth_retry_after,
)


APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
if APP_ENV not in {"development", "test", "production"}:
    raise RuntimeError("APP_ENV must be development, test, or production.")
IS_PRODUCTION = APP_ENV == "production"
STAFF_USERNAME = os.environ.get("STAFF_USERNAME", "").strip()
STAFF_PASSWORD_HASH = os.environ.get("STAFF_PASSWORD_HASH", "").strip()
SECRET_KEY = os.environ.get("SECRET_KEY", "")
TRUSTED_HOSTS = [
    host.strip().lower()
    for host in os.environ.get("TRUSTED_HOSTS", "").split(",")
    if host.strip()
]
try:
    TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))
except ValueError as exc:
    raise RuntimeError("TRUSTED_PROXY_COUNT must be an integer from 0 to 5") from exc
if not 0 <= TRUSTED_PROXY_COUNT <= 5:
    raise RuntimeError("TRUSTED_PROXY_COUNT must be an integer from 0 to 5")
if IS_PRODUCTION and TRUSTED_PROXY_COUNT == 0:
    raise RuntimeError(
        "Production requires TRUSTED_PROXY_COUNT to match the HTTPS reverse "
        "proxy in front of Waitress. Confirm the exact count with the host."
    )

if IS_PRODUCTION:
    missing_settings = [
        key for key, value in (
            ("SECRET_KEY", SECRET_KEY),
            ("STAFF_USERNAME", STAFF_USERNAME),
            ("STAFF_PASSWORD_HASH", STAFF_PASSWORD_HASH),
            ("TRUSTED_HOSTS", TRUSTED_HOSTS),
        ) if not value
    ]
    if missing_settings:
        raise RuntimeError(
            "Production startup requires: " + ", ".join(missing_settings)
        )
    if len(SECRET_KEY) < 32 or SECRET_KEY.startswith("replace-with-"):
        raise RuntimeError(
            "Production SECRET_KEY must be a long, randomly generated value "
            "of at least 32 characters."
        )
    if STAFF_USERNAME.startswith("replace-with-") or STAFF_PASSWORD_HASH.startswith("replace-with-"):
        raise RuntimeError("Replace the example staff credentials before production startup.")
    if any(host == "*" for host in TRUSTED_HOSTS):
        raise RuntimeError("TRUSTED_HOSTS must list specific host names, not '*'.")

initialize_storage()
from ai.database import initialize_database  # noqa: E402

initialize_database()

app = Flask(__name__)
if TRUSTED_PROXY_COUNT:
    from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=TRUSTED_PROXY_COUNT,
        x_proto=TRUSTED_PROXY_COUNT,
        x_host=TRUSTED_PROXY_COUNT,
    )
app.config.update(
    SECRET_KEY=SECRET_KEY or secrets.token_urlsafe(32),
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    MAX_FORM_MEMORY_SIZE=64 * 1024,
    MAX_FORM_PARTS=20,
    TRUSTED_HOSTS=TRUSTED_HOSTS or None,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    SESSION_COOKIE_SAMESITE="Lax",
    PREFERRED_URL_SCHEME="https" if IS_PRODUCTION else "http",
)

from flask_wtf.csrf import CSRFProtect  # noqa: E402

csrf = CSRFProtect(app)

from routes.dashboard import dashboard_bp  # noqa: E402
from routes.register_missing import register_missing_bp  # noqa: E402
from routes.register_found import register_found_bp  # noqa: E402
from routes.view_missing import view_missing_bp  # noqa: E402
from routes.view_found import view_found_bp  # noqa: E402
from routes.ai_match import ai_match_bp  # noqa: E402
from routes.verify_match import verify_match_bp  # noqa: E402
from routes.match_history import match_history_bp  # noqa: E402
from routes.reports import reports_bp  # noqa: E402
from routes.public_directory import public_directory_bp  # noqa: E402
from routes.sightings import public_sightings_bp  # noqa: E402

for blueprint in (
    dashboard_bp,
    register_missing_bp,
    register_found_bp,
    view_missing_bp,
    view_found_bp,
    ai_match_bp,
    verify_match_bp,
    match_history_bp,
    reports_bp,
    public_directory_bp,
    public_sightings_bp,
):
    app.register_blueprint(blueprint)

from ai.match_queue import start_match_worker  # noqa: E402

start_match_worker(app)


PUBLIC_ENDPOINTS = {
    "dashboard.dashboard",
    "register_missing.register_missing",
    "register_found.register_found",
    "static",
    "healthz",
    "robots_txt",
    "sitemap_xml",
    "public_directory.missing_children",
    "public_directory.missing_child",
    "public_directory.found_children",
    "public_directory.found_child",
    "public_sightings.report_sighting",
}


def is_public_case_photo_request():
    """Allow image access for cases shown in either public directory."""
    if not request.path.startswith("/static/uploads/"):
        return False

    filename = (request.view_args or {}).get("filename", "")
    if filename.startswith("uploads/"):
        filename = filename[len("uploads/"):]
    normalized = filename.replace("\\", "/")
    if not normalized or ".." in normalized.split("/"):
        return False
    try:
        image_path = (UPLOAD_ROOT / normalized).resolve(strict=True)
        if not image_path.is_relative_to(UPLOAD_ROOT.resolve(strict=True)):
            return False
        if not image_path.is_file():
            return False
    except (OSError, RuntimeError):
        return False

    stored_path = f"static/uploads/{normalized}"
    connection = connect_database()
    try:
        row = connection.execute(
            """SELECT 1 FROM missing_children
               WHERE public_listing = 1
                 AND replace(photo_path, char(92), '/') = ?
               UNION ALL
               SELECT 1 FROM found_children
               WHERE replace(photo_path, char(92), '/') = ?
               LIMIT 1""",
            (stored_path, stored_path),
        ).fetchone()
    finally:
        connection.close()
    return row is not None


def is_public_request():
    if request.path.startswith("/static/uploads/"):
        return is_public_case_photo_request()
    return request.endpoint in PUBLIC_ENDPOINTS


def staff_auth_response():
    return Response(
        "Staff access required.",
        401,
        {"WWW-Authenticate": 'Basic realm="Reunify AI staff", charset="UTF-8"'},
    )


@app.before_request
def protect_case_management():
    """Require staff credentials for case data and uploaded child photos."""
    if IS_PRODUCTION and TRUSTED_HOSTS:
        host = (urlsplit(f"//{request.host}").hostname or "").lower().rstrip(".")
        if host not in TRUSTED_HOSTS:
            abort(400)

    # Waitress is not configured for TLS here. The deployment proxy must set
    # X-Forwarded-Proto and be represented by TRUSTED_PROXY_COUNT. Redirect
    # safe navigation requests; reject submissions and Basic credentials over
    # HTTP because redirecting them would still expose their first request.
    if IS_PRODUCTION and not request.is_secure:
        if request.method not in {"GET", "HEAD", "OPTIONS"} or request.authorization:
            abort(400, description="HTTPS is required for this request.")
        secure_url = urlsplit(request.url)._replace(scheme="https").geturl()
        return redirect(secure_url, code=308)

    if not IS_PRODUCTION:
        g.staff_authenticated = True
        return None

    if is_public_request():
        g.staff_authenticated = False
        return None

    retry_after = staff_auth_retry_after()
    if retry_after:
        g.staff_authenticated = False
        response = Response("Too many failed staff sign-in attempts.", 429)
        response.headers["Retry-After"] = str(retry_after)
        return response

    credentials = request.authorization
    if not credentials or credentials.username != STAFF_USERNAME:
        g.staff_authenticated = False
    else:
        try:
            g.staff_authenticated = check_password_hash(
                STAFF_PASSWORD_HASH,
                credentials.password or "",
            )
        except (TypeError, ValueError):
            g.staff_authenticated = False

    if g.staff_authenticated:
        clear_staff_auth_failures()
        return None

    record_staff_auth_failure()
    return staff_auth_response()


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; base-uri 'self'; object-src 'none'; "
        "frame-ancestors 'none'; form-action 'self'; img-src 'self' data: blob:; "
        "font-src 'self' data: https://fonts.gstatic.com "
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/; "
        "style-src 'self' 'unsafe-inline' "
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css "
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css "
        "https://fonts.googleapis.com; "
        "script-src 'self' "
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js; "
        "connect-src 'self'",
    )

    if IS_PRODUCTION:
        if request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000"
            )
        response.headers["Cache-Control"] = "no-store"
        if not is_public_request():
            response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"

    return response


@app.get("/static/uploads/<path:filename>")
def private_uploads(filename):
    """Serve case photos privately, except photos approved for public listings."""
    if not UPLOAD_ROOT.is_dir():
        abort(404)
    try:
        resolved_root = UPLOAD_ROOT.resolve(strict=True)
        image_path = (resolved_root / filename).resolve(strict=True)
    except (OSError, RuntimeError):
        abort(404)
    if not image_path.is_relative_to(resolved_root) or not image_path.is_file():
        abort(404)
    response = send_file(image_path, conditional=False)
    response.headers["Cache-Control"] = "no-store, private"
    return response


@app.get("/healthz")
def healthz():
    return {"status": "ok"}, 200


@app.get("/robots.txt")
def robots_txt():
    body = "\n".join((
        "User-agent: *",
        f"Sitemap: {url_for('sitemap_xml', _external=True)}",
        "",
    ))
    return Response(body, mimetype="text/plain")


@app.get("/sitemap.xml")
def sitemap_xml():
    public_urls = [
        url_for("dashboard.dashboard", _external=True),
        url_for("register_missing.register_missing", _external=True),
        url_for("register_found.register_found", _external=True),
        url_for("public_directory.missing_children", _external=True),
        url_for("public_directory.found_children", _external=True),
    ]
    connection = connect_database()
    try:
        public_cases = connection.execute(
            """SELECT 'missing' AS case_type, id FROM missing_children
               WHERE public_listing = 1
               UNION ALL
               SELECT 'found' AS case_type, id FROM found_children
               ORDER BY id DESC LIMIT 49995"""
        ).fetchall()
    finally:
        connection.close()
    for case_type, case_id in public_cases:
        endpoint = (
            "public_directory.missing_child"
            if case_type == "missing"
            else "public_directory.found_child"
        )
        public_urls.append(url_for(endpoint, child_id=case_id, _external=True))
    entries = "".join(
        f"<url><loc>{escape(url)}</loc></url>" for url in public_urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}</urlset>"
    )
    return Response(xml, mimetype="application/xml")


if __name__ == "__main__":
    app.run(debug=False)
