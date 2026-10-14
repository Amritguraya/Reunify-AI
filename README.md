Reunify AI

**An AI-powered child reunification platform that helps connect missing-child and found-child reports.**

Reunify AI brings case registration, public case directories, face-based matching, and human match review together in one web application. It is built to help families and community members find relevant reports and help staff review possible matches.

## What it does

- Register missing-child and found-child cases with identifying details and a photograph.
- Browse public directories of listed missing children and found children, including their public case details and contact information.
- Submit a sighting report from a missing-child profile. Sighting reports are handled through the staff review workflow.
- Compare face embeddings from missing and found case photos with InsightFace and ONNX Runtime.
- Retain possible cross-age matches when reported dates and ages suggest a child may have been missing for several years.
- Review possible matches, mark them verified or rejected, and view match history and reports.

### How matching should be understood

AI results are **possible leads**, not identity confirmation. Face-similarity scores are not probabilities. A person must review a candidate and use the match-verification workflow before treating it as verified. Age-aware matching compares photos taken at different ages; it does not generate an age-progressed photograph.

## Public information and data handling

The missing-child and found-child directories are intentionally public. Listed profiles can show photographs, names, locations, and contact details so that members of the public can recognize a case and contact the family or reporter. Public sighting forms are available for listed missing-child cases.

Only publish case information and photographs that are authorized for public release. Public information can be copied or shared by others. Before using real cases, establish who verifies authorization, responds to sightings, and removes a case when it should no longer be public. The application does not automatically confirm consent or moderate every report before publication; see [DEPLOYMENT.md](DEPLOYMENT.md) for the current data-exposure and launch guidance.

The local SQLite database, uploaded photographs, backups, and environment files are excluded from this repository by `.gitignore`. Do not add real case records, private photographs, passwords, API keys, or production secrets to GitHub. Use synthetic information for demonstrations and development.

## Technology

- Python 3.11
- Flask and SQLite
- InsightFace, ONNX Runtime, OpenCV, and NumPy for face matching
- HTML, CSS, and JavaScript templates for the web interface
- Waitress for the production WSGI server

## Run locally

### 1. Get the source and create a virtual environment

```powershell
git clone https://github.com/Amritguraya/Reunify-AI.git
cd Reunify-AI
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, use the Python executable directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Start the development server

```powershell
python app.py
```

While it is running, open <http://127.0.0.1:5000/> on the same computer. This is a local development address; it is not a public website URL. In development mode, the app does not ask you to create a staff account.

The production app has HTTP Basic Authentication for staff-only pages. It uses credentials configured in the hosting environment; there is no staff sign-up or account-management page. For a public deployment, configure secrets and persistent storage through the host, then follow [DEPLOYMENT.md](DEPLOYMENT.md) for HTTPS, trusted hosts and proxies, and public-case handling. Never commit production credentials.

The local server uses SQLite and an uploads directory. These files are ignored by Git.

## Repository contents

- `app.py`, `routes/`, and `storage.py` — application setup, web routes, and local data storage
- `ai/` — face embeddings, matching, age-aware candidate handling, and match queue
- `templates/`, `static/`, and `utils/` — web pages, styles, browser scripts, and supporting utilities
- `scripts/` — staff password-hash, backup, and public-case management tools
- `requirements.txt` — Python dependencies
- `DEPLOYMENT.md` — production configuration and operational guidance

## Project status

Reunify AI is an evolving project. Review and test it in a non-production environment with synthetic data before using real cases. AI candidates require human review, and public case publication requires an authorized process and an owner for follow-up and removal requests.
