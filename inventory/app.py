"""Inventory webhooks, persistent mock appointments, and a gated voice demo."""
from __future__ import annotations

import hmac
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
CATALOG = json.loads((Path(__file__).with_name("catalog.json")).read_text(encoding="utf-8"))
ARGENTINA = timezone(timedelta(hours=-3))


def tool_auth(x_tools_secret: str = Header(default="")) -> None:
    expected = os.getenv("TOOLS_SECRET", "")
    if not expected:
        raise HTTPException(503, "Tool authentication is not configured")
    if not hmac.compare_digest(x_tools_secret.encode(), expected.encode()):
        raise HTTPException(401, "Invalid tool credentials")


def database() -> sqlite3.Connection:
    location = Path(os.getenv("DATABASE_PATH", str(ROOT / ".local/concierge.sqlite3")))
    location.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(location, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS visits (id TEXT PRIMARY KEY, request_id TEXT UNIQUE, vehicle_id TEXT, starts_at TEXT, UNIQUE(vehicle_id, starts_at))")
    db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, day TEXT)")
    return db


def vehicle_by_id(vehicle_id: str) -> dict:
    for vehicle in CATALOG:
        if vehicle["id"] == vehicle_id:
            return vehicle
    raise HTTPException(404, "Vehicle does not exist in this fictional inventory")


class Visit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vehicle_id: str = Field(min_length=1, max_length=30)
    starts_at: AwareDatetime
    confirmed: Literal[True]
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")


class SessionRequest(BaseModel):
    access_code: str = Field(min_length=1, max_length=200)


app = FastAPI(title="Concierge · fictional used-car marketplace", version="0.1.0")
app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(ROOT / "web/index.html")


@app.get("/health")
def health():
    return {"status": "ok", "fictional": True}


@app.get("/api/catalog")
def public_catalog():
    return {"fictional": True, "currency": "USD", "vehicles": CATALOG}


@app.get("/api/config")
def config():
    enabled = all(os.getenv(key) for key in ("AGENT_ID", "ELEVENLABS_API_KEY", "DEMO_ACCESS_CODE", "TOOLS_SECRET"))
    return {"voice_enabled": enabled, "max_duration_seconds": int(os.getenv("DEMO_MAX_DURATION_SECONDS", "180"))}


@app.get("/vehicles", dependencies=[Depends(tool_auth)])
def search_vehicles(
    max_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    body: Literal["sedan", "suv", "hatchback", "pickup"] | None = None,
    feature: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=3, ge=1, le=3),
):
    matches = [v for v in CATALOG if (max_price is None or v["price_usd"] <= max_price)
               and (body is None or v["body"] == body)
               and (not feature or any(feature.casefold() in f.casefold() for f in v["features"]))]
    matches.sort(key=lambda v: v["price_usd"])
    return {"fictional": True, "currency": "USD", "total": len(matches), "vehicles": matches[:limit]}


@app.get("/vehicles/{vehicle_id}", dependencies=[Depends(tool_auth)])
def get_vehicle(vehicle_id: str):
    return {"fictional": True, "currency": "USD", "vehicle": vehicle_by_id(vehicle_id)}


@app.post("/visits", dependencies=[Depends(tool_auth)])
def schedule_visit(visit: Visit):
    vehicle_by_id(visit.vehicle_id)
    starts = visit.starts_at.astimezone(ARGENTINA)
    normalized = starts.isoformat()
    db = database()
    try:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT * FROM visits WHERE request_id = ?", (visit.request_id,)).fetchone()
        if existing:
            if existing["vehicle_id"] != visit.vehicle_id or existing["starts_at"] != normalized:
                raise HTTPException(409, "request_id already belongs to a different appointment")
            return {"fictional": True, "status": "confirmed_mock", "visit_id": existing["id"], "vehicle_id": visit.vehicle_id, "starts_at": normalized}
        if not datetime.now(ARGENTINA) < starts <= datetime.now(ARGENTINA) + timedelta(days=30):
            raise HTTPException(422, "Choose a future appointment within the next 30 days")
        if starts.weekday() > 4 or not 9 <= starts.hour < 18 or starts.minute not in (0, 30) or starts.second or starts.microsecond:
            raise HTTPException(422, "Demo hours: Monday-Friday, 09:00-18:00 Argentina, half-hour slots")
        visit_id = f"demo-{uuid4().hex[:12]}"
        try:
            db.execute("INSERT INTO visits VALUES (?, ?, ?, ?)", (visit_id, visit.request_id, visit.vehicle_id, normalized))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "That vehicle already has a visit in this slot") from None
        db.commit()
        return {"fictional": True, "status": "confirmed_mock", "visit_id": visit_id, "vehicle_id": visit.vehicle_id, "starts_at": normalized}
    finally:
        db.close()


@app.post("/api/session")
def voice_session(request: SessionRequest):
    expected = os.getenv("DEMO_ACCESS_CODE", "")
    if not expected or not hmac.compare_digest(request.access_code.encode(), expected.encode()):
        raise HTTPException(401, "Use the demo access code supplied by the owner")
    key, agent = os.getenv("ELEVENLABS_API_KEY"), os.getenv("AGENT_ID")
    if not key or not agent:
        raise HTTPException(503, "ElevenLabs is not configured yet")
    db, session_id = database(), uuid4().hex
    try:
        db.execute("BEGIN IMMEDIATE")
        day = datetime.now(timezone.utc).date().isoformat()
        count = db.execute("SELECT COUNT(*) FROM sessions WHERE day = ?", (day,)).fetchone()[0]
        if count >= int(os.getenv("DEMO_DAILY_SESSIONS", "10")):
            raise HTTPException(429, "Daily voice demo allowance reached; explore the catalog instead")
        db.execute("INSERT INTO sessions VALUES (?, ?)", (session_id, day))
        db.commit()
        # Conservative quota: a reserved session also counts if the upstream call fails.
    finally:
        db.close()
    try:
        response = httpx.get("https://api.elevenlabs.io/v1/convai/conversation/get-signed-url", params={"agent_id": agent}, headers={"xi-api-key": key}, timeout=20)
        response.raise_for_status()
        return {"signed_url": response.json()["signed_url"]}
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(502, "Could not start ElevenLabs; retry later") from None
