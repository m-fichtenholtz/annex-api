"""
ANNEX — AI Entity Extractor
Uses Groq (Llama 3.3 70B) to structure raw scraped text into clean JSON.
"""

import os
import json
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are an OSINT data structuring assistant for the ANNEX research framework.
Your job is to take raw, messy text scraped from public records and extract structured information.

Always respond with ONLY valid JSON — no explanation, no markdown, no code blocks.
If a field is not present in the text, use null.
Never invent or hallucinate data. Only extract what is explicitly present."""

EXTRACTION_SCHEMA = """
Extract the following fields from the raw text and return as JSON:
{
  "full_name": string or null,
  "age": string or null,
  "date_of_birth": string or null,
  "current_address": string or null,
  "previous_addresses": [string],
  "phone_numbers": [string],
  "email_addresses": [string],
  "relatives": [string],
  "associates": [string],
  "employers": [string],
  "education": [string],
  "social_profiles": [{"platform": string, "url_or_handle": string}],
  "corporate_affiliations": [string],
  "legal_records": [{"case": string, "type": string, "date": string, "court": string}],
  "domains_owned": [string],
  "other_identifiers": [string],
  "confidence_notes": string
}
"""


def extract_entities(raw_text: str, source: str = "unknown") -> dict:
    """
    Send raw scraped text to Groq/Llama for structured extraction.
    Returns clean JSON dict.
    """
    if not raw_text or not raw_text.strip():
        return {"status": "error", "message": "No text provided"}

    # Truncate if too long (Llama context limit)
    text = raw_text[:8000]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Source: {source}\n\nRaw text:\n{text}\n\n{EXTRACTION_SCHEMA}"}
            ],
            temperature=0.1,
            max_tokens=1500,
        )

        content = response.choices[0].message.content.strip()

        # Strip any accidental markdown fences
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        parsed = json.loads(content)
        return {
            "status": "success",
            "source": source,
            "extracted": parsed
        }

    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"JSON parse failed: {e}", "raw": content}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def summarize_for_dossier(extracted_data: dict, subject_name: str) -> str:
    """
    Generate a human-readable paragraph summary of extracted data.
    Used in the dossier narrative section.
    """
    try:
        data_str = json.dumps(extracted_data, indent=2)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional intelligence analyst writing concise, factual summaries for research dossiers. Write in third person. Be precise and neutral. Never speculate. Only state what the data confirms."
                },
                {
                    "role": "user",
                    "content": f"Write a 2-3 paragraph factual summary for a research dossier on {subject_name} based on this extracted data:\n\n{data_str}"
                }
            ],
            temperature=0.3,
            max_tokens=500,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Summary generation failed: {e}"


def cross_reference(records: list) -> dict:
    """
    Take multiple extracted records from different sources
    and identify overlapping / corroborating data points.
    Returns a unified profile with confidence scores.
    """
    if not records:
        return {"status": "error", "message": "No records provided"}

    records_str = json.dumps(records, indent=2)[:10000]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"""You are cross-referencing multiple OSINT records about the same subject.

Records from different sources:
{records_str}

Return a unified JSON profile:
{{
  "unified_name": string,
  "confirmed_fields": {{"field": "value", "sources": [list of sources that agree]}},
  "conflicting_fields": {{"field": {{"source1": "value1", "source2": "value2"}}}},
  "overall_confidence": number (0-100),
  "identity_notes": string
}}"""
                }
            ],
            temperature=0.1,
            max_tokens=1000,
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        return {
            "status": "success",
            "unified": json.loads(content.strip())
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
