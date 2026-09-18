"""Messy, deliberately incomplete procurement artefacts used by the demo."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CATALOG: list[dict[str, Any]] = [
    {"item_id": f"PKG-{i:03d}", "description": description, "uom": uom, "base_price": price}
    for i, (description, uom, price) in enumerate([
        ("3-ply corrugated carton 12 x 9 x 6 in", "piece", 28), ("5-ply corrugated carton 18 x 12 x 12 in", "piece", 58),
        ("7-ply corrugated carton 24 x 18 x 18 in", "piece", 115), ("Die-cut mailer 10 x 8 x 4 in", "piece", 22),
        ("Kraft paper roll 24 in x 50 m", "roll", 420), ("Bubble wrap roll 1 m x 50 m", "roll", 980),
        ("Stretch film roll 18 in x 300 m", "roll", 690), ("BOPP packing tape 2 in x 65 m", "roll", 42),
        ("Fragile label 100 x 50 mm", "piece", 1.2), ("Shipping label 100 x 150 mm", "piece", .85),
        ("Void fill paper roll 15 in x 250 m", "roll", 1250), ("Air pillow film roll 400 mm x 300 m", "roll", 1450),
        ("Poly mailer 10 x 12 in", "piece", 4.5), ("Poly mailer 14 x 16 in", "piece", 6.8),
        ("Zip lock pouch 6 x 8 in", "piece", 3.2), ("Zip lock pouch 10 x 12 in", "piece", 6.1),
        ("Corner protector 50 mm", "piece", 8.5), ("Edge board 50 x 50 x 1000 mm", "piece", 19),
        ("Wooden pallet 1200 x 1000 mm", "piece", 1250), ("Plastic pallet 1200 x 1000 mm", "piece", 1650),
        ("Carton sealing dispenser 2 in", "piece", 185), ("PP strapping roll 12 mm x 1000 m", "roll", 1120),
        ("Metal buckle 12 mm", "piece", 2.8), ("Silica gel sachet 5 g", "piece", 1.6),
        ("Thermal liner 1 m x 25 m", "roll", 1620), ("Foam sheet 2 mm 1 m x 50 m", "roll", 880),
        ("Carton cutter safety knife", "piece", 135), ("Document enclosed pouch A5", "piece", 3.5),
        ("Return label 100 x 150 mm", "piece", 1.1), ("Tamper-evident tape 2 in x 50 m", "roll", 78),
    ], start=1)
]

@dataclass(frozen=True)
class MockDocument:
    vendor_name: str
    kind: str
    filename: str
    raw_text: str

MOCK_DOCUMENTS = [
    MockDocument("Apex Packaging", "Excel", "Apex_modified_rfx.xlsx", """Workbook tabs: [Commercial, Notes, Sheet 2, Quote]. Quote tab has merged A1:D2.\nSKU | Description | Price INR\nPKG-008 | BOPP tape 2in/65m | 39.50\nPKG-002 | 5-ply carton 18x12x12 | 55.00\nTerms: Net 30. Layout order is intentionally non-RFx."""),
    MockDocument("BoxCraft Corp", "PDF", "BoxCraft_quote.pdf", """Page 1: BoxCraft Corp USD quotation. 5-ply carton: $0.63/pc. Bubble wrap: $11.40/roll.\nPage 2: Standard items continue. Payment: 50% advance.\nPage 3 footnote (6pt): A 5% rebate applies if aggregate order volume exceeds 50,000 units; freight excluded."""),
    MockDocument("PackSys India", "Angled photo", "packsys_rate_card.jpg", """PHONE PHOTO OCR (skew 11 degrees): Printed rate card. 3-ply carton ₹29.50; 5-ply carton ₹61.00; BOPP tape ₹43.\nHandwritten blue-ink revisions: 3-ply = ₹27.75, 5-ply = ₹59.25, BOPP = ₹40.00. Handwriting supersedes print."""),
    MockDocument("EcoWrap Solutions", "Word", "ecowrap_offer.docx", """EcoWrap proposal paragraph: We offer 24 requested packaging supplies, including Kraft paper roll at INR 398, bubble wrap roll at INR 945 and all poly mailers at a 4% discount. Items PKG-025 through PKG-030 are not quoted. Payment in 45 days."""),
    MockDocument("Speedy Pack", "Raw email", "speedy_pack.eml", """From: sales@speedypack.example\nSubject: Re: Packaging RFx\n42/kg for 5-ply, 38 for 3-ply, rest same as last year, freight extra.\nRegards, Speedy Pack"""),
]

def seed_catalog_if_absent(client: Any) -> int:
    """Insert the baseline catalog once; safe to call from the Streamlit sidebar."""
    existing = client.table("rfx_catalog").select("item_id", count="exact").limit(1).execute()
    if existing.count:
        return 0
    client.table("rfx_catalog").upsert(CATALOG, on_conflict="item_id").execute()
    return len(CATALOG)

def deterministic_demo_rows(vendor_name: str) -> list[dict[str, Any]]:
    """Fallback data for a demo when no Gemini key/upload is available; never used as AI output."""
    multipliers = {"Apex Packaging": .95, "BoxCraft Corp": 1.03, "PackSys India": .99, "EcoWrap Solutions": .96, "Speedy Pack": 1.08}
    if vendor_name == "EcoWrap Solutions":
        catalog = CATALOG[:24]
    elif vendor_name == "Speedy Pack":
        catalog = CATALOG[:2]
    else:
        catalog = CATALOG
    rows = []
    for item in catalog:
        price = round(item["base_price"] * multipliers[vendor_name], 2)
        confidence = .94 if vendor_name not in {"PackSys India", "Speedy Pack"} else (.78 if vendor_name == "PackSys India" else .42)
        audit = ["Demo fallback: price derived from baseline for UI demonstration."]
        if vendor_name == "BoxCraft Corp": audit.append("USD quote normalized using 1 USD = INR 83.50; rebate stored as clause.")
        if vendor_name == "PackSys India" and item["item_id"] in {"PKG-001", "PKG-002", "PKG-008"}: audit.append("Handwritten photo correction overrides printed rate.")
        if vendor_name == "Speedy Pack": audit.append("/kg cannot be converted to /piece without item weight; needs buyer verification.")
        rows.append({"rfx_item_id": item["item_id"], "raw_description": item["description"], "raw_price": price,
                     "raw_unit": item["uom"], "raw_currency": "INR", "normalized_price_inr": price,
                     "confidence_score": confidence, "audit_trail": audit, "source_location": "synthetic fallback"})
    return rows
