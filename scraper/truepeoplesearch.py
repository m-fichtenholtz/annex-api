"""
ANNEX — TruePeopleSearch Scraper
Uses Playwright headless Chromium to pull public records.
"""

import asyncio
import re
from playwright.async_api import async_playwright
from fake_useragent import UserAgent

ua = UserAgent()

async def scrape_truepeoplesearch(name: str, location: str = "", phone: str = "", dob: str = "") -> dict:
    """
    Search TruePeopleSearch for a subject.
    Returns structured dict of found records.
    """
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )

        context = await browser.new_context(
            user_agent=ua.random,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

        page = await context.new_page()

        # Remove automation fingerprints
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        try:
            # Build search URL
            name_slug = name.strip().lower().replace(" ", "-")
            loc_parts = location.strip().split(",")
            if len(loc_parts) >= 2:
                city = loc_parts[0].strip().lower().replace(" ", "-")
                state = loc_parts[1].strip().upper()
                url = f"https://www.truepeoplesearch.com/results?name={name_slug}&citystatezip={city}%2C+{state}"
            else:
                url = f"https://www.truepeoplesearch.com/results?name={name_slug}"

            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)

            # Check for CAPTCHA or block
            content = await page.content()
            if "captcha" in content.lower() or "access denied" in content.lower():
                return {"status": "blocked", "results": [], "message": "Site returned CAPTCHA or access denied. Flag for manual investigation."}

            # Extract result cards
            cards = await page.query_selector_all('[data-link-to-details]')

            if not cards:
                # Try alternate selector
                cards = await page.query_selector_all('.card-summary')

            for card in cards[:5]:  # Top 5 results max
                record = {}

                # Name
                name_el = await card.query_selector('span[data-id="1"]')
                if not name_el:
                    name_el = await card.query_selector('.h4, h4, .name')
                if name_el:
                    record["name"] = (await name_el.inner_text()).strip()

                # Age
                age_el = await card.query_selector('[data-id="2"], .age')
                if age_el:
                    age_text = (await age_el.inner_text()).strip()
                    record["age"] = age_text

                # Addresses
                addr_els = await card.query_selector_all('[data-id="3"] li, .address-info li, .info-line')
                addrs = []
                for a in addr_els:
                    t = (await a.inner_text()).strip()
                    if t:
                        addrs.append(t)
                if addrs:
                    record["addresses"] = addrs

                # Phone numbers
                phone_els = await card.query_selector_all('[data-id="4"] li, .phone-info li')
                phones = []
                for ph in phone_els:
                    t = (await ph.inner_text()).strip()
                    if t:
                        phones.append(t)
                if phones:
                    record["phones"] = phones

                # Relatives / associates
                rel_els = await card.query_selector_all('[data-id="5"] li, .relative-info li')
                rels = []
                for r in rel_els:
                    t = (await r.inner_text()).strip()
                    if t:
                        rels.append(t)
                if rels:
                    record["relatives"] = rels

                # Get detail page link
                link_attr = await card.get_attribute("data-link-to-details")
                if link_attr:
                    record["detail_url"] = "https://www.truepeoplesearch.com" + link_attr

                if record.get("name"):
                    results.append(record)

            # If DOB filter provided, score results
            if dob and results:
                results = _filter_by_dob(results, dob)

            await browser.close()
            return {
                "status": "success",
                "count": len(results),
                "query": {"name": name, "location": location},
                "results": results
            }

        except Exception as e:
            await browser.close()
            return {
                "status": "error",
                "results": [],
                "message": str(e)
            }


def _filter_by_dob(results: list, dob: str) -> list:
    """Score and sort results by DOB match."""
    # Extract year from dob input
    year_match = re.search(r'\b(19|20)\d{2}\b', dob)
    if not year_match:
        return results
    target_year = int(year_match.group())

    scored = []
    for r in results:
        age_str = r.get("age", "")
        age_match = re.search(r'\d+', age_str)
        if age_match:
            from datetime import datetime
            approx_birth_year = datetime.now().year - int(age_match.group())
            diff = abs(approx_birth_year - target_year)
            r["dob_confidence"] = max(0, 100 - (diff * 20))
        else:
            r["dob_confidence"] = 50
        scored.append(r)

    return sorted(scored, key=lambda x: x.get("dob_confidence", 0), reverse=True)


# Sync wrapper for FastAPI
def run_scrape(name: str, location: str = "", phone: str = "", dob: str = "") -> dict:
    return asyncio.run(scrape_truepeoplesearch(name, location, phone, dob))
