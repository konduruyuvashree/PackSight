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
