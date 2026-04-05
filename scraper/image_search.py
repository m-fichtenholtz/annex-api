"""
ANNEX — Image Search + Face Matching
Reverse image search routing + DeepFace comparison.
"""

import base64
import httpx
import os
import tempfile
from PIL import Image
import io

# ── Reverse Image Search ─────────────────────────────────────────────────────

async def reverse_image_search(image_base64: str) -> dict:
    """
    Route image through multiple reverse search engines.
    Returns list of matching URLs and sources.
    """
    results = {
        "google": [],
        "bing": [],
        "tineye": [],
    }

    try:
        image_bytes = base64.b64decode(image_base64)

        # ── Google Lens (via SerpAPI free tier if key available, else direct) ──
        serpapi_key = os.getenv("SERPAPI_KEY", "")
        if serpapi_key:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://serpapi.com/search",
                    params={
                        "engine": "google_reverse_image",
                        "api_key": serpapi_key,
                    },
                    files={"image": ("image.jpg", image_bytes, "image/jpeg")}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("image_results", [])[:8]:
                        results["google"].append({
                            "title": item.get("title", ""),
                            "url": item.get("link", ""),
                            "source": item.get("displayed_link", ""),
                        })

        # ── TinEye ──────────────────────────────────────────────────────────
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://tineye.com/api/1.0/result_json/",
                files={"image": ("image.jpg", image_bytes, "image/jpeg")},
                headers={"User-Agent": "Mozilla/5.0 (ANNEX Research)"}
            )
            if resp.status_code == 200:
                data = resp.json()
                for match in data.get("matches", [])[:8]:
                    results["tineye"].append({
                        "url": match.get("image_url", ""),
                        "source": match.get("domain", ""),
                        "crawl_date": match.get("crawl_date", ""),
                    })

    except Exception as e:
        results["error"] = str(e)

    total = len(results["google"]) + len(results["bing"]) + len(results["tineye"])
    return {
        "status": "success",
        "total_matches": total,
        "results": results
    }


# ── Face Matching ─────────────────────────────────────────────────────────────

def face_match(probe_base64: str, candidate_base64s: list) -> dict:
    """
    Compare a probe face image against a list of candidate images.
    Uses DeepFace with ArcFace model.
    Returns confidence scores per candidate.
    """
    try:
        from deepface import DeepFace
    except ImportError:
        return {"status": "error", "message": "DeepFace not installed"}

    probe_bytes = base64.b64decode(probe_base64)
    probe_img   = Image.open(io.BytesIO(probe_bytes)).convert("RGB")

    matches = []

    with tempfile.TemporaryDirectory() as tmpdir:
        probe_path = os.path.join(tmpdir, "probe.jpg")
        probe_img.save(probe_path)

        for idx, cand_b64 in enumerate(candidate_base64s):
            try:
                cand_bytes = base64.b64decode(cand_b64)
                cand_img   = Image.open(io.BytesIO(cand_bytes)).convert("RGB")
                cand_path  = os.path.join(tmpdir, f"candidate_{idx}.jpg")
                cand_img.save(cand_path)

                result = DeepFace.verify(
                    img1_path=probe_path,
                    img2_path=cand_path,
                    model_name="ArcFace",
                    enforce_detection=False,
                    silent=True
                )

                confidence = round((1 - result.get("distance", 1)) * 100, 1)
                matches.append({
                    "candidate_index": idx,
                    "verified": result.get("verified", False),
                    "confidence": max(0, confidence),
                    "distance": round(result.get("distance", 1), 4),
                })

            except Exception as e:
                matches.append({
                    "candidate_index": idx,
                    "verified": False,
                    "confidence": 0,
                    "error": str(e)
                })

    matches.sort(key=lambda x: x["confidence"], reverse=True)
    return {
        "status": "success",
        "probe_compared_against": len(candidate_base64s),
        "matches": matches
    }


# ── Mugshot Search ────────────────────────────────────────────────────────────

async def search_mugshots(name: str, state: str = "", dob: str = "") -> dict:
    """
    Search public mugshot databases for subject.
    Returns booking records and image URLs.
    """
    results = []

    # Public county jail portals — state dependent
    # These are illustrative endpoints; actual URLs vary by county
    search_targets = [
        f"https://www.vinelink.com/#/search/person?firstName={name.split()[0]}&lastName={name.split()[-1]}&state={state}",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    # BustedMugshots public search
    try:
        name_encoded = name.replace(" ", "+")
        async with httpx.AsyncClient(timeout=12, headers=headers, follow_redirects=True) as client:
            resp = await client.get(f"https://bustedmugshots.com/search?q={name_encoded}")
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.select(".mugshot-card, .result-card, article")[:6]
                for card in cards:
                    record = {}
                    name_tag = card.select_one("h2, h3, .name")
                    if name_tag:
                        record["name"] = name_tag.get_text(strip=True)
                    age_tag = card.select_one(".age, .dob")
                    if age_tag:
                        record["age_dob"] = age_tag.get_text(strip=True)
                    charge_tags = card.select(".charge, .charges li")
                    charges = [c.get_text(strip=True) for c in charge_tags]
                    if charges:
                        record["charges"] = charges
                    img = card.select_one("img")
                    if img and img.get("src"):
                        record["image_url"] = img["src"]
                    date_tag = card.select_one(".date, .arrest-date")
                    if date_tag:
                        record["arrest_date"] = date_tag.get_text(strip=True)
                    if record.get("name"):
                        results.append(record)
    except Exception as e:
        pass

    return {
        "status": "success",
        "count": len(results),
        "query": {"name": name, "state": state, "dob": dob},
        "results": results,
        "note": "Results from public booking records only. Verify all findings."
    }
