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
