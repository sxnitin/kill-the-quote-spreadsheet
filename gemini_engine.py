"""Gemini extraction and guarded Text-to-SQL planning for procurement quotes."""
from __future__ import annotations

import json
from typing import Literal, Sequence

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

MODEL = "gemini-2.0-flash"
USD_TO_INR = 83.50

class LineItemExtraction(BaseModel):
    rfx_item_id: str | None = Field(None, description="Best matching PKG-### catalog identifier, or null when unresolved")
    raw_description: str
    raw_price: float | None
    raw_unit: str | None
    raw_currency: str | None
    normalized_price_inr: float | None
    confidence_score: float = Field(ge=0, le=1)
    audit_trail: list[str] = Field(default_factory=list)
    source_location: str | None = None

class ClauseOrFootnote(BaseModel):
    clause_type: Literal["rebate", "freight", "payment_terms", "lead_time", "minimum_order", "other"]
    raw_text: str
    commercial_impact: str

class VendorQuoteSchema(BaseModel):
    vendor_name: str
    currency: str = "INR"
    payment_terms: str | None = None
    line_items: list[LineItemExtraction]
    clauses: list[ClauseOrFootnote] = Field(default_factory=list)

EXTRACTION_RULES = f"""
You are a procurement data-normalization specialist. Extract only evidence present in the source.
Base currency is INR; 1 USD = {USD_TO_INR:.2f} INR. For USD prices, calculate price * {USD_TO_INR:.2f} and put the exact math in audit_trail.
Target UOM is per piece or per roll. Never invent an /kg to /piece conversion: if an item weight/quantity is supplied,
show the complete math in audit_trail; otherwise set normalized_price_inr null, lower confidence, and request verification.
For photographs, handwritten price updates override printed values, and source_location must name the photo region.
Capture fine print, rebates, freight, payment terms, exclusions, and missing line items as clauses. Confidence must reflect ambiguity.
Use these catalog rows to match identifiers:\n{{catalog_json}}\n"""

SQL_SCHEMA = """Tables: rfx_catalog(item_id,description,uom,base_price); vendor_quotes(id,vendor_name,currency,payment_terms,created_at); normalized_line_items(quote_id,rfx_item_id,raw_description,raw_price,raw_unit,raw_currency,normalized_price_inr,confidence_score,audit_trail,source_location); vendor_clauses(quote_id,clause_type,raw_text,commercial_impact)."""

def _client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)

def extract_quote(api_key: str, raw_text: str, catalog: Sequence[dict], file_bytes: bytes | None = None,
                  mime_type: str | None = None) -> VendorQuoteSchema:
    """Use structured output. Attach original PDF/image/Office bytes when Gemini supports the supplied MIME type."""
    prompt = EXTRACTION_RULES.format(catalog_json=json.dumps(list(catalog), ensure_ascii=False)) + "\nSOURCE:\n" + raw_text
    contents: list[types.Part | str] = [prompt]
    if file_bytes and mime_type:
        contents.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))
    response = _client(api_key).models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction="Return a complete, auditable procurement extraction. Never fabricate evidence.",
            response_mime_type="application/json",
            response_schema=VendorQuoteSchema,
            temperature=0,
        ),
    )
    return VendorQuoteSchema.model_validate_json(response.text)

def make_readonly_sql(api_key: str, question: str) -> str:
    """Ask Gemini for one constrained PostgreSQL SELECT; database.py validates it again."""
    prompt = f"""Convert the buyer question into exactly one PostgreSQL SELECT. {SQL_SCHEMA}
Only use these tables. Do not write CTEs containing data modification, comments, semicolons, or multiple statements.
Return JSON with one key sql. Buyer question: {question}"""
    response = _client(api_key).models.generate_content(
        model=MODEL, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema={"type":"object", "properties":{"sql":{"type":"string"}}, "required":["sql"]}, temperature=0),
    )
    sql = json.loads(response.text)["sql"].strip()
    if not sql.lower().startswith("select") or ";" in sql:
        raise ValueError("Gemini returned a query outside the read-only contract.")
    return sql
