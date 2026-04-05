"""
ANNEX v3 — Python AI Backend
FastAPI app — deploy to Render.com
"""

import os
from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import base64

from scraper.truepeoplesearch import run_scrape
from scraper.image_search import reverse_image_search, face_match, search_mugshots
from ai.extractor import extract_entities, summarize_for_dossier, cross_reference

# ── App setup ──────────────────────────────────────────────────────────────
app = FastAPI(title="ANNEX API", version="3.0", docs_url=None, redoc_url=None)

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")
ADMIN_SECRET   = os.getenv("ADMIN_SECRET", "changeme")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ── Auth ───────────────────────────────────────────────────────────────────
def verify_secret(x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")


# ── Models ─────────────────────────────────────────────────────────────────
class ScrapeRequest(BaseModel):
    name: str
    location: Optional[str] = ""
    phone: Optional[str] = ""
    dob: Optional[str] = ""

class ExtractRequest(BaseModel):
    raw_text: str
    source: Optional[str] = "unknown"

class ImageSearchRequest(BaseModel):
    image_base64: str

class FaceMatchRequest(BaseModel):
    probe_base64: str
    candidates: List[str]

class MugshotRequest(BaseModel):
    name: str
    state: Optional[str] = ""
    dob: Optional[str] = ""

class CrossRefRequest(BaseModel):
    records: List[dict]

class SummarizeRequest(BaseModel):
    extracted_data: dict
    subject_name: str


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "online", "service": "ANNEX API v3"}


@app.post("/scrape/truepeoplesearch")
def scrape_tps(req: ScrapeRequest, x_admin_secret: str = Header(...)):
    verify_secret(x_admin_secret)
    result = run_scrape(
        name=req.name,
        location=req.location,
        phone=req.phone,
        dob=req.dob
    )
    # Auto-extract entities from raw scraped text
    if result.get("status") == "success" and result.get("results"):
        raw_combined = "\n\n".join([
            f"Record {i+1}:\n" + "\n".join([f"{k}: {v}" for k, v in r.items()])
            for i, r in enumerate(result["results"])
        ])
        extracted = extract_entities(raw_combined, source="TruePeopleSearch")
        result["extracted"] = extracted.get("extracted", {})
    return result


@app.post("/extract")
def extract(req: ExtractRequest, x_admin_secret: str = Header(...)):
    verify_secret(x_admin_secret)
    return extract_entities(req.raw_text, req.source)


@app.post("/summarize")
def summarize(req: SummarizeRequest, x_admin_secret: str = Header(...)):
    verify_secret(x_admin_secret)
    summary = summarize_for_dossier(req.extracted_data, req.subject_name)
    return {"status": "success", "summary": summary}


@app.post("/crossref")
def crossref(req: CrossRefRequest, x_admin_secret: str = Header(...)):
    verify_secret(x_admin_secret)
    return cross_reference(req.records)


@app.post("/search/image")
async def image_search(req: ImageSearchRequest, x_admin_secret: str = Header(...)):
    verify_secret(x_admin_secret)
    return await reverse_image_search(req.image_base64)


@app.post("/search/face")
def face_search(req: FaceMatchRequest, x_admin_secret: str = Header(...)):
    verify_secret(x_admin_secret)
    return face_match(req.probe_base64, req.candidates)


@app.post("/search/mugshot")
async def mugshot_search(req: MugshotRequest, x_admin_secret: str = Header(...)):
    verify_secret(x_admin_secret)
    return await search_mugshots(req.name, req.state, req.dob)


# Upload image as file (alternative to base64)
@app.post("/upload/image")
async def upload_image(file: UploadFile = File(...), x_admin_secret: str = Header(...)):
    verify_secret(x_admin_secret)
    contents = await file.read()
    b64 = base64.b64encode(contents).decode("utf-8")
    # Run reverse search immediately
    result = await reverse_image_search(b64)
    result["image_base64"] = b64  # Return so frontend can use for face match
    return result
