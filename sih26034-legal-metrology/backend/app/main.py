from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import scan, reports, auth

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SIH26034 — Legal Metrology Compliance Checker",
    description="Scans packaged-commodity labels and checks compliance with "
                "the Legal Metrology (Packaged Commodities) Rules, 2011.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before real deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(scan.router)
app.include_router(reports.router)


@app.get("/health")
def health():
    return {"status": "ok"}
