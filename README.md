# PackSight API

FastAPI backend for PackSight: real user accounts, persistent scan history,
and server-side OCR + LMPC 2011 rule checking (SQLite for storage).

## 1. Install prerequisites

**Tesseract OCR** (the actual OCR engine — `pytesseract` is just a Python wrapper around it):

- **Windows:** install from https://github.com/UB-Mannheim/tesseract/wiki, then make sure
  `tesseract.exe` is on your PATH (or set `pytesseract.pytesseract.tesseract_cmd` in `ocr_rules.py`
  to the full install path).
- **macOS:** `brew install tesseract`
- **Linux (Debian/Ubuntu):** `sudo apt-get install tesseract-ocr`

**Python 3.10+**

## 2. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Note: `bcrypt==4.0.1` is pinned deliberately — newer `bcrypt` releases trip a known
compatibility bug in `passlib`'s backend detection. Don't upgrade it without testing.

## 3. Run the server

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

This creates `packsight.db` (SQLite) in this folder on first run — no separate database
setup needed for the demo. Visit `http://127.0.0.1:8000/docs` for interactive API docs.

## 4. Point the frontend at it

Open `index.html` and confirm the `API_BASE` constant near the top of the `<script>` block
points at `http://127.0.0.1:8000` (that's the default). Then just open `index.html` in a
browser — sign up, sign in, and scans will now hit this real backend.

## API summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/signup` | — | Create an account: `{full_name, user_id, password}` → JWT |
| POST | `/auth/login` | — | Sign in: `{user_id, password}` → JWT |
| POST | `/scans` | Bearer token | Upload a label image (`multipart/form-data`: `image`, `product_name`) → OCR + rule-engine verdict |
| GET | `/scans` | Bearer token | List the signed-in user's past scans, newest first |
| GET | `/stats` | Bearer token | Aggregate dashboard stats for the signed-in user |

## What's real vs. still a stub

- **Real:** password hashing (bcrypt), JWT auth, SQLite persistence across restarts,
  server-side OCR (Tesseract) and the same rule engine as the original browser demo, ported to Python.
- **Still a demo simplification:** the rule engine is regex/pattern-matching, not a trained
  NER model, and there's no image pre-processing (deskew/crop) or font-height calibration —
  see `PLAN.md` in the frontend deliverable for the full production-scope design of those.
- **Security note:** `SECRET_KEY` in `auth_utils.py` and CORS `allow_origins=["*"]` in `main.py`
  are fine for local demo use only — replace both before deploying anywhere real.
=======
# SIH26034 — Legal Metrology Packaged Commodity Compliance Checker

Software system that scans packaged-commodity labels and checks compliance
against the **Legal Metrology (Packaged Commodities) Rules, 2011**.

## Problem Statement

> SIH26034 — Ministry of Consumer Affairs, Food & Public Distribution
> Develop a system to automatically detect, extract and validate mandatory
> declarations (manufacturer details, net quantity, MRP, mfg date, consumer
> care, font size, etc.) on packaged commodity labels and flag violations.

## Architecture

```
Upload → Preprocess → OCR + Layout Detection → Field Extraction
       → Rule Engine (Rules, 2011) → Report + Dashboard
```

See `backend/app/rules/ruleset.json` for the encoded compliance rules and
`backend/app/rules/engine.py` for the checker logic.

## Repo Layout

```
backend/    FastAPI service — OCR pipeline, rule engine, reports, API
frontend/   React (Vite) app — upload UI + enforcement dashboard
data/       Synthetic label generator for training/testing without a real dataset
```

## Quickstart (local, no Docker)

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev
```
App: http://localhost:5173

### Generate synthetic test labels
```bash
cd data
python synthetic_label_generator.py --count 50 --out ./synthetic_labels
```

## Quickstart (Docker)
```bash
docker compose up --build
```

## OCR Backend

Defaults to **Tesseract** (offline, free — good for hackathon demo reliability).
To use Google Cloud Vision instead, set `OCR_ENGINE=google_vision` and
`GOOGLE_APPLICATION_CREDENTIALS` in `backend/.env` (see `.env.example`).

## Compliance Rules Covered (v1)

- Manufacturer/packer/importer name & address
- Net quantity + unit
- MRP (inclusive-of-taxes wording)
- Month & year of manufacture/packing/import
- Consumer care details
- Country of origin (when applicable)
- Font-size / readability threshold by pack-size slab (approximate, see `rules/engine.py`)

## Pushing to your own Git repo

```bash
git init
git add .
git commit -m "Initial scaffold: SIH26034 compliance checker"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

## License
MIT — for hackathon/educational use.