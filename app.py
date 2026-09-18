"""Streamlit front end for the Kill the Quote Spreadsheet prototype."""
from __future__ import annotations
import json
import pandas as pd
import streamlit as st
from database import comparison_grid, connect, quote_detail, text_to_postgres, upsert_demo_rows, upsert_normalized_quote
from gemini_engine import extract_quote
from mock_data import MOCK_DOCUMENTS, deterministic_demo_rows, seed_catalog_if_absent

st.set_page_config(page_title="Kill the Quote Spreadsheet", page_icon="📦", layout="wide")
st.title("📦 Kill the Quote Spreadsheet")
st.caption("Auditable quote ingestion for corrugated packaging and shipping supplies · Base currency INR")

def secret(name: str) -> str:
    return str(st.secrets.get(name, "")) if hasattr(st, "secrets") else ""

with st.sidebar:
    st.header("Connections")
    gemini_key = st.text_input("GEMINI_API_KEY", value=secret("GEMINI_API_KEY"), type="password")
    supabase_url = st.text_input("SUPABASE_URL", value=secret("SUPABASE_URL"), type="password")
    supabase_key = st.text_input("SUPABASE_KEY (service role for demo)", value=secret("SUPABASE_KEY"), type="password")
    st.caption("Keep credentials in Streamlit secrets; never commit them.")
    if st.button("Re-seed Supabase", use_container_width=True):
        try:
            count = seed_catalog_if_absent(connect(supabase_url, supabase_key))
            st.success(f"Catalog ready ({count} new rows).")
        except Exception as exc: st.error(str(exc))

def db(): return connect(supabase_url, supabase_key)
def confidence_color(value: float) -> str:
    return "#DCFCE7" if value > .90 else "#FEF3C7" if value >= .70 else "#FEE2E2"

tab_ingest, tab_matrix, tab_copilot = st.tabs(["1 · Ingestion & Verification", "2 · Comparison Matrix", "3 · AI Co-Pilot"])

with tab_ingest:
    st.subheader("Source documents and structured extraction")
    source_names = [f"{doc.vendor_name} · {doc.kind}" for doc in MOCK_DOCUMENTS]
    selected = st.selectbox("Select a messy demo input", source_names)
    doc = MOCK_DOCUMENTS[source_names.index(selected)]
    uploaded = st.file_uploader("Optionally replace with an actual quote", type=["xlsx", "xls", "pdf", "png", "jpg", "jpeg", "docx", "txt", "eml"])
    left, right = st.columns(2)
    with left:
        st.markdown(f"**{doc.filename}**")
        st.code(doc.raw_text, language="text")
        if uploaded: st.info(f"Uploaded: {uploaded.name} ({uploaded.size:,} bytes)")
    with right:
        st.markdown("**Gemini extraction**")
        if st.button("Extract with Gemini", type="primary"):
            if not gemini_key: st.error("Enter GEMINI_API_KEY first.")
            elif not supabase_url or not supabase_key: st.error("Enter Supabase connection details first.")
            else:
                try:
                    catalog = db().table("rfx_catalog").select("*").execute().data
                    payload = uploaded.getvalue() if uploaded else None
                    mime = uploaded.type if uploaded else None
                    quote = extract_quote(gemini_key, doc.raw_text, catalog, payload, mime)
                    quote_id = upsert_normalized_quote(db(), quote)
                    st.success(f"Saved normalized quote {quote_id}")
                    st.json(quote.model_dump())
                except Exception as exc: st.exception(exc)
        if st.button("Load deterministic demo fallback"):
            try:
                quote_id = upsert_demo_rows(db(), doc.vendor_name, deterministic_demo_rows(doc.vendor_name),
                    [{"clause_type":"rebate","raw_text":"5% aggregate volume rebate; freight excluded.","commercial_impact":"Reduce BoxCraft effective prices when threshold is met."}] if doc.vendor_name == "BoxCraft Corp" else [{"clause_type":"freight","raw_text":"Freight extra.","commercial_impact":"Landed cost unknown."}] if doc.vendor_name == "Speedy Pack" else None)
                st.success(f"Demo fallback saved: {quote_id}")
            except Exception as exc: st.error(str(exc))

with tab_matrix:
    st.subheader("Latest quoted prices by vendor")
    st.caption("Green: >0.90 confidence · Yellow: 0.70–0.89 · Red: <0.70. Blank means no matching quote.")
    if st.button("Refresh matrix") or (supabase_url and supabase_key):
        try:
            grid = comparison_grid(db())
            vendors = sorted({vendor for row in grid for vendor in row["quotes"]})
            records = []
            for row in grid:
                record = {"Item": row["item_id"], "Description": row["description"], "UOM": row["uom"]}
                for vendor in vendors:
                    item = row["quotes"].get(vendor)
                    record[vendor] = None if not item or item["normalized_price_inr"] is None else float(item["normalized_price_inr"])
                records.append(record)
            frame = pd.DataFrame(records)
            st.dataframe(frame.style.format(precision=2, na_rep="—"), use_container_width=True, hide_index=True)
            for row in grid:
                with st.expander(f"{row['item_id']} · {row['description']}"):
                    for vendor, item in row["quotes"].items():
                        if item:
                            st.markdown(f"<div style='padding:8px;background:{confidence_color(float(item['confidence_score']))}'>"
                                        f"<b>{vendor}</b> · confidence {float(item['confidence_score']):.0%}<br>{item.get('source_location') or 'No source location'}<br>"
                                        f"<small>{' | '.join(item.get('audit_trail') or [])}</small></div>", unsafe_allow_html=True)
        except Exception as exc: st.info("Connect Supabase and run schema.sql, then load the five demo inputs.")

with tab_copilot:
    st.subheader("Ask the procurement co-pilot")
    question = st.text_area("Example: Find vendors with hidden freight and compare lowest quoted price per item.")
    if st.button("Run read-only analysis", type="primary"):
        try:
            sql, answer = text_to_postgres(db(), gemini_key, question)
            st.code(sql, language="sql")
            st.json(answer)
        except Exception as exc: st.error(str(exc))
