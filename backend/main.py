from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from backend.scraper import check_courts, check_month

from backend.scraper import check_courts

app = FastAPI(title="Rose Park Court Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/availability")
def get_availability(date: str = Query(..., description="Date in MM/DD/YYYY format")):
    return check_courts(date)


@app.get("/api/month")
def get_month(year: int, month: int):
    return check_month(year, month)


WEB_DIR = Path(__file__).resolve().parents[1] / "web"

app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")