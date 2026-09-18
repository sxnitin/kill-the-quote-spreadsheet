"""Supabase persistence layer. Browser clients must never receive a service-role key."""
from __future__ import annotations

from typing import Any
from supabase import Client, create_client
from gemini_engine import VendorQuoteSchema, make_readonly_sql

def connect(url: str, key: str) -> Client:
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY are required.")
    return create_client(url, key)

def upsert_normalized_quote(client: Client, quote: VendorQuoteSchema) -> str:
    record = client.table("vendor_quotes").insert({"vendor_name": quote.vendor_name, "currency": quote.currency, "payment_terms": quote.payment_terms}).execute().data[0]
    rows = [{"quote_id": record["id"], **item.model_dump()} for item in quote.line_items]
    if rows:
        client.table("normalized_line_items").insert(rows).execute()
    clauses = [{"quote_id": record["id"], **clause.model_dump()} for clause in quote.clauses]
    if clauses:
        client.table("vendor_clauses").insert(clauses).execute()
    return record["id"]

def upsert_demo_rows(client: Client, vendor_name: str, rows: list[dict[str, Any]], clauses: list[dict[str, str]] | None = None) -> str:
    record = client.table("vendor_quotes").insert({"vendor_name": vendor_name, "currency": "INR", "payment_terms": "Demo terms"}).execute().data[0]
    client.table("normalized_line_items").insert([{"quote_id": record["id"], **row} for row in rows]).execute()
    if clauses:
        client.table("vendor_clauses").insert([{"quote_id": record["id"], **clause} for clause in clauses]).execute()
    return record["id"]

def comparison_grid(client: Client) -> list[dict[str, Any]]:
    catalog = client.table("rfx_catalog").select("*").order("item_id").execute().data
    quotes = client.table("vendor_quotes").select("id,vendor_name,created_at").order("created_at", desc=True).execute().data
    latest: dict[str, str] = {}
    for quote in quotes:
        latest.setdefault(quote["vendor_name"], quote["id"])
    ids = list(latest.values())
    line_items = client.table("normalized_line_items").select("*").in_("quote_id", ids).execute().data if ids else []
    lookup = {(row["rfx_item_id"], row["quote_id"]): row for row in line_items if row["rfx_item_id"]}
    return [{**item, "quotes": {vendor: lookup.get((item["item_id"], quote_id)) for vendor, quote_id in latest.items()}} for item in catalog]

def quote_detail(client: Client, quote_id: str) -> dict[str, Any]:
    return {"quote": client.table("vendor_quotes").select("*").eq("id", quote_id).single().execute().data,
            "items": client.table("normalized_line_items").select("*").eq("quote_id", quote_id).execute().data,
            "clauses": client.table("vendor_clauses").select("*").eq("quote_id", quote_id).execute().data}

def text_to_postgres(client: Client, gemini_api_key: str, question: str) -> tuple[str, Any]:
    sql = make_readonly_sql(gemini_api_key, question)
    blocked = (";", "insert", "update", "delete", "drop", "alter", "grant", "revoke", "copy", "pg_")
    if not sql.lower().startswith("select") or any(word in sql.lower() for word in blocked):
        raise ValueError("Rejected unsafe generated SQL.")
    return sql, client.rpc("run_readonly_procurement_sql", {"query_text": sql}).execute().data
