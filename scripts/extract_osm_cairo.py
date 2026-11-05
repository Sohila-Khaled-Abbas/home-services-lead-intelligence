"""
Home Services Lead Intelligence
Live OpenStreetMap / Overpass API extraction for Cairo metro, Egypt.

Run from the project root:
    .\.venv\Scripts\python.exe .\scripts\extract_osm_cairo.py

This script only reads public OSM data. It does not crawl private pages,
bypass access controls, or determine marketing consent.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
QUERY_DIR = PROJECT_ROOT / "queries"

ENDPOINT = "https://overpass-api.de/api/interpreter"
SOURCE_NAME = "OpenStreetMap via Overpass API"
SOURCE_LICENSE = "Open Database License (ODbL) 1.0"
# Broad Cairo metro bounding box (south, west, north, east).
# It is a rectangular search area, not an administrative boundary.
BBOX = (29.90, 31.10, 30.20, 31.55)

QUERY = f"""[out:json][timeout:45];
(
  nwr["craft"="hvac"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
  nwr["craft"="roofer"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
);
out center tags;
"""

FIELDS = [
    "business_name", "service_vertical", "osm_type", "osm_id", "osm_url",
    "latitude", "longitude", "phone", "email", "website",
    "street", "housenumber", "suburb", "city", "postcode", "country",
    "source_name", "source_endpoint", "source_license", "source_query_file",
    "extracted_at_utc", "osm_version", "osm_timestamp",
    "contact_permission_status", "campaign_eligible",
]


def build_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=2,
        status=3,
        backoff_factor=2,
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=frozenset({"POST"}),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({
        "User-Agent": (
            "HomeServicesLeadIntelligence/0.1 "
            "(educational portfolio data extraction)"
        ),
        "Accept": "application/json",
    })
    return session


def element_coordinates(element: dict[str, Any]) -> tuple[Any, Any]:
    if "lat" in element and "lon" in element:
        return element.get("lat"), element.get("lon")
    center = element.get("center") or {}
    return center.get("lat"), center.get("lon")


def classify_vertical(tags: dict[str, Any]) -> str:
    craft = tags.get("craft", "").strip().lower()
    if craft == "hvac":
        return "HVAC"
    if craft == "roofer":
        return "Roofing"
    return "Unclassified"


def normalize_element(
    element: dict[str, Any], extracted_at: str, query_file: str
) -> dict[str, Any]:
    tags = element.get("tags") or {}
    lat, lon = element_coordinates(element)
    osm_type = element.get("type", "")
    osm_id = element.get("id", "")
    osm_url = (
        f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
        if osm_type and osm_id else ""
    )
    row = {
        "business_name": tags.get("name", "").strip(),
        "service_vertical": classify_vertical(tags),
        "osm_type": osm_type,
        "osm_id": osm_id,
        "osm_url": osm_url,
        "latitude": lat,
        "longitude": lon,
        "phone": tags.get("contact:phone") or tags.get("phone", ""),
        "email": tags.get("contact:email") or tags.get("email", ""),
        "website": tags.get("contact:website") or tags.get("website", ""),
        "street": tags.get("addr:street", ""),
        "housenumber": tags.get("addr:housenumber", ""),
        "suburb": tags.get("addr:suburb", ""),
        "city": tags.get("addr:city", ""),
        "postcode": tags.get("addr:postcode", ""),
        "country": tags.get("addr:country", ""),
        "source_name": SOURCE_NAME,
        "source_endpoint": ENDPOINT,
        "source_license": SOURCE_LICENSE,
        "source_query_file": query_file,
        "extracted_at_utc": extracted_at,
        "osm_version": element.get("version", ""),
        "osm_timestamp": element.get("timestamp", ""),
        # Publicly listed contact details do NOT establish consent.
        "contact_permission_status": "unknown",
        "campaign_eligible": "false",
    }
    return row


def main() -> None:
    for folder in (RAW_DIR, PROCESSED_DIR, METADATA_DIR, QUERY_DIR):
        folder.mkdir(parents=True, exist_ok=True)

    run_time = datetime.now(timezone.utc)
    stamp = run_time.strftime("%Y%m%dT%H%M%SZ")
    extracted_at = run_time.isoformat(timespec="seconds")
    query_path = QUERY_DIR / "cairo_metro_hvac_roofing.overpassql"
    raw_path = RAW_DIR / f"osm_cairo_metro_{stamp}.json"
    csv_path = PROCESSED_DIR / f"osm_cairo_metro_leads_{stamp}.csv"
    metadata_path = METADATA_DIR / f"osm_cairo_metro_run_{stamp}.json"

    query_path.write_text(QUERY, encoding="utf-8")

    print(f"Source: {SOURCE_NAME}")
    print(f"Endpoint: {ENDPOINT}")
    print(f"Area: Cairo metro bbox {BBOX} (not an administrative boundary)")
    print("Tags: craft=hvac, craft=roofer")
    print("Sending one read-only API request. Please allow it to finish...")

    response = build_session().post(
        ENDPOINT,
        data={"data": QUERY},
        timeout=(15, 90),
    )
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        preview = response.text[:500]
        raise RuntimeError(
            f"Overpass did not return valid JSON. Response preview: {preview}"
        ) from exc

    # Save the original response before transforming it.
    raw_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    elements = payload.get("elements", [])
    rows = [
        normalize_element(element, extracted_at, str(query_path.relative_to(PROJECT_ROOT)))
        for element in elements
    ]

    # Stable OSM identity: element type + ID. Keep the first occurrence.
    deduplicated: dict[tuple[str, Any], dict[str, Any]] = {}
    for row in rows:
        key = (str(row["osm_type"]), row["osm_id"])
        deduplicated.setdefault(key, row)
    rows = list(deduplicated.values())

    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[str, int] = {}
    for row in rows:
        vertical = row["service_vertical"]
        counts[vertical] = counts.get(vertical, 0) + 1

    metadata = {
        "project": "Home Services Lead Intelligence",
        "source_name": SOURCE_NAME,
        "source_endpoint": ENDPOINT,
        "source_license": SOURCE_LICENSE,
        "attribution": "© OpenStreetMap contributors",
        "attribution_url": "https://www.openstreetmap.org/copyright",
        "query_file": str(query_path.relative_to(PROJECT_ROOT)),
        "bounding_box_south_west_north_east": BBOX,
        "geographic_scope_note": (
            "Broad Cairo metro rectangular bounding box; not an administrative boundary."
        ),
        "tags_queried": ["craft=hvac", "craft=roofer"],
        "requested_at_utc": extracted_at,
        "osm_base_timestamp": payload.get("osm3s", {}).get("timestamp_osm_base"),
        "raw_response_file": str(raw_path.relative_to(PROJECT_ROOT)),
        "processed_csv_file": str(csv_path.relative_to(PROJECT_ROOT)),
        "http_status": response.status_code,
        "http_response_bytes": len(response.content),
        "records_returned": len(elements),
        "records_after_deduplication": len(rows),
        "records_by_vertical": counts,
        "deduplication_key": ["osm_type", "osm_id"],
        "contact_permission_status_default": "unknown",
        "campaign_eligible_default": False,
        "limitations": [
            "OpenStreetMap is community-maintained; coverage is incomplete and uneven.",
            "A mapped feature is not necessarily a verified active business.",
            "Public contact details do not establish consent for direct marketing.",
            "Only HVAC and roofing craft tags are queried in this first pass.",
            "Solar providers require a separately validated source/tag strategy.",
        ],
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nEXTRACTION COMPLETE")
    print(f"HTTP status: {response.status_code}")
    print(f"Raw OSM elements: {len(elements)}")
    print(f"Unique records: {len(rows)}")
    print(f"By vertical: {counts}")
    print(f"Raw response: {raw_path}")
    print(f"Processed CSV: {csv_path}")
    print(f"Run metadata: {metadata_path}")
    print("\nAttribution: © OpenStreetMap contributors")
    print("Campaign eligibility remains FALSE until separately reviewed.")


if __name__ == "__main__":
    main()
