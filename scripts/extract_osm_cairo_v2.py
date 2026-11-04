"""
Home Services Lead Intelligence — Cairo OSM discovery v2.

Run from project root:
    .\.venv\Scripts\python.exe .\scripts\extract_osm_cairo_v2.py

Read-only extraction from OpenStreetMap through Overpass API.
This version broadens the first query and preserves exact OSM tags so
adjacent trades are not silently mislabeled as target businesses.
"""
from __future__ import annotations
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://overpass-api.de/api/interpreter"
SOURCE = "OpenStreetMap via Overpass API"
LICENSE = "Open Database License (ODbL) 1.0"
BBOX = (29.90, 31.10, 30.20, 31.55)  # south, west, north, east

TAG_QUERIES = [
    ('nwr["craft"="hvac"]', "HVAC installer/service"),
    ('nwr["shop"="hvac"]', "HVAC equipment retailer"),
    ('nwr["shop"="air_conditioning"]', "Air-conditioning retailer/candidate"),
    ('nwr["craft"="roofer"]', "Roofing contractor"),
    ('nwr["craft"="photovoltaic"]', "Solar/PV installer or planner"),
    ('nwr["shop"="photovoltaic"]', "Solar/PV retailer"),
    ('nwr["craft"="plumber"]', "Adjacent trade — plumbing"),
    ('nwr["craft"="electrician"]', "Adjacent trade — electrical"),
]

def build_query() -> str:
    s, w, n, e = BBOX
    lines = ["[out:json][timeout:60];", "("]
    for selector, _label in TAG_QUERIES:
        lines.append(f"  {selector}({s},{w},{n},{e});")
    lines.extend([");", "out center tags;"])
    return "\n".join(lines)

def make_session() -> requests.Session:
    retry = Retry(
        total=3, connect=3, read=2, status=3, backoff_factor=2,
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=frozenset({"POST"}),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({
        "User-Agent": "HomeServicesLeadIntelligence/0.2 (educational portfolio extraction)",
        "Accept": "application/json",
    })
    return session

def coordinates(element: dict[str, Any]) -> tuple[Any, Any]:
    if "lat" in element and "lon" in element:
        return element.get("lat"), element.get("lon")
    center = element.get("center") or {}
    return center.get("lat"), center.get("lon")

def classify(tags: dict[str, Any]) -> tuple[str, str]:
    craft = tags.get("craft", "").lower()
    shop = tags.get("shop", "").lower()
    if craft == "hvac":
        return "HVAC", "direct_service_tag"
    if shop == "hvac":
        return "HVAC_RETAIL_CANDIDATE", "retail_not_confirmed_installer"
    if shop == "air_conditioning":
        return "HVAC_RELATED_CANDIDATE", "retail_or_service_requires_review"
    if craft == "roofer":
        return "Roofing", "direct_service_tag"
    if craft == "photovoltaic":
        return "Solar", "direct_service_tag"
    if shop == "photovoltaic":
        return "Solar_RETAIL_CANDIDATE", "retail_not_confirmed_installer"
    if craft == "plumber":
        return "Adjacent_Plumbing", "adjacent_trade_requires_review"
    if craft == "electrician":
        return "Adjacent_Electrical", "adjacent_trade_requires_review"
    return "Unclassified", "manual_review"

def main() -> None:
    folders = {
        "raw": ROOT / "data" / "raw",
        "processed": ROOT / "data" / "processed",
        "metadata": ROOT / "data" / "metadata",
        "queries": ROOT / "queries",
    }
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)

    query = build_query()
    query_path = folders["queries"] / "cairo_metro_discovery_v2.overpassql"
    query_path.write_text(query, encoding="utf-8")

    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    extracted_at = started.isoformat(timespec="seconds")
    print(f"Source: {SOURCE}")
    print(f"Endpoint: {ENDPOINT}")
    print(f"Cairo metro bbox: {BBOX}")
    print("Searching direct-service, retail and adjacent-trade tags separately...")
    response = make_session().post(ENDPOINT, data={"data": query}, timeout=(20, 120))
    response.raise_for_status()
    payload = response.json()

    raw_path = folders["raw"] / f"osm_cairo_metro_v2_{stamp}.json"
    raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = []
    for el in payload.get("elements", []):
        tags = el.get("tags") or {}
        lat, lon = coordinates(el)
        vertical, note = classify(tags)
        kind, osm_id = el.get("type", ""), el.get("id", "")
        rows.append({
            "business_name": tags.get("name", "").strip(),
            "name_present": bool(tags.get("name", "").strip()),
            "service_vertical": vertical,
            "classification_note": note,
            "osm_primary_tags": json.dumps(
                {k: tags[k] for k in ("craft", "shop", "office", "industrial") if k in tags},
                ensure_ascii=False, sort_keys=True
            ),
            "osm_type": kind, "osm_id": osm_id,
            "osm_url": f"https://www.openstreetmap.org/{kind}/{osm_id}",
            "latitude": lat, "longitude": lon,
            "phone": tags.get("contact:phone") or tags.get("phone", ""),
            "email": tags.get("contact:email") or tags.get("email", ""),
            "website": tags.get("contact:website") or tags.get("website", ""),
            "street": tags.get("addr:street", ""),
            "housenumber": tags.get("addr:housenumber", ""),
            "suburb": tags.get("addr:suburb", ""),
            "city": tags.get("addr:city", ""),
            "postcode": tags.get("addr:postcode", ""),
            "country": tags.get("addr:country", ""),
            "source_name": SOURCE, "source_endpoint": ENDPOINT,
            "source_license": LICENSE,
            "source_query_file": str(query_path.relative_to(ROOT)),
            "extracted_at_utc": extracted_at,
            "osm_version": el.get("version", ""),
            "osm_timestamp": el.get("timestamp", ""),
            "contact_permission_status": "unknown",
            "campaign_eligible": "false",
        })

    unique = {}
    for row in rows:
        unique.setdefault((row["osm_type"], row["osm_id"]), row)
    rows = list(unique.values())

    csv_path = folders["processed"] / f"osm_cairo_metro_discovery_v2_{stamp}.csv"
    columns = list(rows[0].keys()) if rows else [
        "business_name", "name_present", "service_vertical", "classification_note",
        "osm_primary_tags", "osm_type", "osm_id", "osm_url", "latitude", "longitude",
        "phone", "email", "website", "street", "housenumber", "suburb", "city",
        "postcode", "country", "source_name", "source_endpoint", "source_license",
        "source_query_file", "extracted_at_utc", "osm_version", "osm_timestamp",
        "contact_permission_status", "campaign_eligible"
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    by_vertical = Counter(r["service_vertical"] for r in rows)
    with_name = sum(bool(r["name_present"]) for r in rows)
    with_contact = sum(bool(r["phone"] or r["email"] or r["website"]) for r in rows)
    metadata = {
        "source": SOURCE, "endpoint": ENDPOINT, "license": LICENSE,
        "attribution": "© OpenStreetMap contributors",
        "attribution_url": "https://www.openstreetmap.org/copyright",
        "query_file": str(query_path.relative_to(ROOT)),
        "bbox_south_west_north_east": BBOX,
        "requested_tags_and_intended_meaning": TAG_QUERIES,
        "extracted_at_utc": extracted_at,
        "osm_base_timestamp": payload.get("osm3s", {}).get("timestamp_osm_base"),
        "http_status": response.status_code,
        "raw_response_file": str(raw_path.relative_to(ROOT)),
        "processed_csv_file": str(csv_path.relative_to(ROOT)),
        "raw_elements": len(payload.get("elements", [])),
        "unique_elements": len(rows),
        "records_by_classification": dict(by_vertical),
        "named_elements": with_name,
        "elements_with_any_public_contact_field": with_contact,
        "deduplication_key": ["osm_type", "osm_id"],
        "permission_policy": {
            "default_status": "unknown", "campaign_eligible_default": False,
            "note": "Publicly mapped contact details do not establish marketing consent."
        },
        "limitations": [
            "OSM coverage in Cairo may be incomplete or uneven.",
            "Retailers and adjacent trades are candidates, not confirmed installers.",
            "Records must be manually checked for active business status and service fit.",
            "This is not a verified or consent-cleared outbound lead list."
        ]
    }
    metadata_path = folders["metadata"] / f"osm_cairo_metro_discovery_v2_{stamp}.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nEXTRACTION RESULT")
    print(f"HTTP status: {response.status_code}")
    print(f"Raw elements: {len(payload.get('elements', []))}")
    print(f"Unique elements: {len(rows)}")
    print(f"By classification: {dict(by_vertical)}")
    print(f"Named elements: {with_name}")
    print(f"Elements with phone/email/website: {with_contact}")
    print(f"Raw JSON: {raw_path}")
    print(f"CSV: {csv_path}")
    print(f"Run metadata: {metadata_path}")
    print("Attribution: © OpenStreetMap contributors")
    print("Campaign eligibility remains FALSE for every record.")

if __name__ == "__main__":
    main()
