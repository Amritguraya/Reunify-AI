# Public deployment

The app can be deployed without changing its existing visual design. Public
visitors can submit missing-child and found-child reports, search both public
case directories, view the associated contact details, and send a sighting
report. Staff credentials are still required for case management, match review,
and private sighting reports.

## Before launch

1. Put the source in a private Git repository. Never commit `database.db`, an
   `.env` file, `uploads/`, or legacy `static/uploads/`; they may contain
   sensitive child and family information. `.gitignore` excludes them.
2. Choose a host that provides persistent storage for both SQLite and uploaded
   photos. Set `DATA_DIR` to that mounted storage path. Production startup fails
   if `DATA_DIR` is missing or points inside the project source tree, so the
   sample database and photos cannot silently become production data. Free
   plans often use temporary filesystems; if the host does, records and photos
   can disappear after a restart or redeploy. This app currently stores data
   in SQLite and local files under `DATA_DIR` (`database.db` and `uploads/`).
   The database and upload paths must stay outside the project source tree.
   The upload directory is deliberately outside Flask's public static
   directory; the app rejects an `UPLOAD_ROOT` inside `static/` as well.
3. Configure the service to install `requirements.txt` and run the included
   `Procfile`. It listens on the host-provided `PORT`.
   `.python-version` specifies the 3.11 series so the host can select its
   latest available security patch.
4. Set `APP_ENV=production`, a long random `SECRET_KEY`, `STAFF_USERNAME`, and
   `STAFF_PASSWORD_HASH` in the host's secret settings. Create the password
   hash locally with `python scripts/create_password_hash.py`; keep the
   password and hash out of Git.
5. Set `TRUSTED_HOSTS` to the exact host name(s) visitors will use, separated
   by commas (for example, the host-provided domain and your custom domain).
   Production startup refuses to run without this allowlist.
6. Set `TRUSTED_PROXY_COUNT` to the exact number of trusted reverse proxies
   documented by the selected host. Production startup refuses `0` because
   Waitress relies on the host proxy for TLS. The proxy must overwrite or
   correctly sanitize `X-Forwarded-Proto`, `X-Forwarded-For`, and
   `X-Forwarded-Host`; trusting forwarded headers from arbitrary clients would
   weaken HTTPS detection, host validation, and rate limits. The `.env.example`
   value of `1` is only an example; confirm the actual count with the host.
7. Enable HTTPS at the host proxy, add the host domain, and configure DNS. The
   app redirects HTTP page visits to HTTPS and rejects HTTP submissions or
   Basic-auth requests. A custom domain needs a domain you control; the
   host-provided domain can be used first.
8. Set the host health-check path to `/healthz` and make sure the health check
   uses the public HTTPS endpoint (or is configured to send the trusted proxy
   headers expected by the app).

Production does not copy a project-local database or upload directory into a
new persistent volume. This prevents sample/local case data from silently
becoming production data. To intentionally migrate a reviewed database and its
matching uploads, set `COPY_LEGACY_DATA=true` for the migration deployment, then
turn it off again.

If moving existing records, transfer the SQLite database and its matching
uploads through a private admin or file-transfer mechanism. Do not upload the
database or photos to a public repository or public file bucket.

## Public case directories

Public case search is one of the platform's two reunification paths, alongside
AI face matching. Existing missing-child cases are added to the public directory
once on the first startup after this update. New missing-child reports appear
there when submitted. Public missing profiles include the child's name, photo,
age, gender, city, missing date, parent or guardian name, and contact number.

Found-child reports are searchable by location, country, description, reporter,
or case number. Their public profiles include the photo, estimated age, gender,
found location and date, description, reporter name, and reporter contact.
Pending AI candidates appear on the related public case pages as possible leads,
with a face-similarity score and an explicit unverified label. Staff-verified
matches are labelled separately.

When a new missing or found report is submitted, the app queues a background
scan against existing unverified reports instead of running face recognition
inside the visitor's web request. The queue is stored in SQLite, allows at most
50 waiting/running jobs, deduplicates active jobs for the same case, and runs
one scan at a time. A scan that fails is retried up to three times. If the queue
is full, the report is still saved and staff can run a full scan from AI
Matching. If the missing and found dates are at least five years apart and the
reported ages fit that timeline within four years, the engine uses
`CROSS_AGE_REVIEW_THRESHOLD` (default `0.40`) to retain lower-score cross-age
leads. Other candidates use `FACE_MATCH_THRESHOLD` (default `0.52`). These are
face-similarity screening thresholds, not identity probabilities. Calibrate
them on representative known pairs before relying on them. Both values can be
set in the host's environment settings.

Use the private server terminal to review cases and manage publication:

```text
python scripts/manage_public_cases.py list
python scripts/manage_public_cases.py publish CASE_ID --approval-reference CONSENT-REFERENCE
python scripts/manage_public_cases.py unpublish CASE_ID
python scripts/manage_public_cases.py audit CASE_ID
```

The approval reference should identify the authorization to restore a case to
the public directory; do not enter a child's or guardian's name as the
reference. Public sighting forms are available for listed missing-child cases.
Their reports are private and visible in the staff-only `/sightings` review
page.

Sighting contacts and descriptions remain in the database until removed
directly from the database. Set a retention period and an operational deletion
process before launch; no deletion tool or automatic expiry is configured.

`/sitemap.xml` contains both public search pages and the listed case pages.
Submit the sitemap to Google Search Console or another search engine's
webmaster tools. Indexing can take time. Search engines may retain cached
snippets after unpublishing, so remove stale URLs through the relevant webmaster
tools when needed.

## Submission safeguards

Public POST forms use CSRF tokens, a hidden honeypot, server-side input and
photo validation, an 8 MB request limit, bounded form parsing, and a limit of
five submissions per hour per client address for each form type. Uploaded
photos are decoded and re-encoded, have metadata removed, and are stored under
random filenames. The rate limiter stores only a keyed hash of the address, not
the raw address. Staff authentication is also throttled after ten failed
attempts per address in a 15-minute window. Configure the trusted proxy count
above so visitors behind the host's proxy are rate-limited individually.

The app sets an allowlisted-host check, enforces HTTPS for production requests,
uses HTTPS-only staff cookies, HSTS, CSP,
frame restrictions, content-type protections, and no-store caching for
production responses. Bootstrap and Google Fonts still load from their pinned
CDN URLs; the CSP allows those origins.

## Backups

Run `python scripts/backup_data.py` to create a SQLite snapshot and include the
uploaded photos. By default, the archive is written under `DATA_DIR/backups`
and the newest seven archives are retained. Set `BACKUP_DIR` to a separate,
access-controlled mounted location for protection against loss of the app's
primary disk. The ZIP is not encrypted; restrict access and encrypt it using
your storage provider or backup process. Copy backups off-host and schedule
the script through the host's scheduler if regular backups are required.

## Private routes

`robots.txt` and the sitemap help search engines find public pages; they do not
secure private information. Production staff access is enforced by HTTP Basic
Authentication over HTTPS. Keep staff credentials private and use a strong
unique password. Use one app instance with the SQLite volume; this setup is not
a multi-region or horizontally scaled database architecture.

## Public data exposure

Public directory pages currently expose child photos, names and locations, as
well as the missing child's guardian name and phone number and the found-report
submitter's name and contact number. Pending candidate leads are also shown as
unverified. That visibility matches the product direction requested for this
project, but it means anyone can copy, scrape, or misuse those details. Secure
hosting does not make deliberately public personal information private. Do not
put real cases or contact details online until each report is authorized for
publication and there is an operational process to verify reports, respond to
abuse, and remove a case promptly when it is no longer appropriate to publish.
New missing reports are immediately marked public, and every found report is
included in the public directory; this app does not currently verify consent
or moderate reports before publication. Treat that as a launch blocker for real
child and family data until an authorized publication process and response
owner are in place.
