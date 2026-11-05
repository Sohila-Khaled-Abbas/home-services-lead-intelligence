"""Read-only Cairo business discovery through the OpenStreetMap Overpass API.

The module preserves source provenance and treats every extracted contact as
unapproved for marketing until a separate compliance review is completed.
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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENDPOINT = "https://overpass-api.de/api/interpreter"
SOURCE_NAME = "OpenStreetMap via Overpass API"
SOURCE_LICENSE = "Open Database License (ODbL) 1.0"
SCRIPT_VERSION = "0.2.0"
# (south, west, north, east): a broad discovery rectangle, not an admin boundary.
BBOX = (29.90, 31.10, 30.20, 31.55)

TAG_QUERIES: tuple[tuple[str, str], ...] = (
    ('nwr["craft"="hvac"]', "HVAC installer/service tag"),
    ('nwr["shop"="hvac"]', "HVAC equipment retailer candidate"),
    ('nwr["shop"="air_conditioning"]', "Air-conditioning retailer/service candidate"),
    ('nwr["craft"="roofer"]', "Roofing trade tag"),
    ('nwr["craft"="photovoltaic"]', "Solar/PV trade tag candidate"),
    ('nwr["shop"="photovoltaic"]', "Solar/PV retailer candidate"),
    ('nwr["craft"="plumber"]', "Adjacent trade: plumbing"),
    ('nwr["craft"="electrician"]', "Adjacent trade: electrical"),
)

CSV_FIELDS = [
    "business_name",
    "name_present",
    "service_vertical",
    "classification_note",
    "osm_primary_tags",
    "osm_type",
    "osm_id",
    "osm_url",
    "latitude",
    "longitude",
    "phone",
    "email",
    "website",
    "street",
    "housenumber",
    "suburb",
    "city",
    "postcode",
    "country",
    "source_name",
    "source_endpoint",
    "source_license",
    "source_query_file",
    "extracted_at_utc",
    "osm_version",
    "osm_timestamp",
    "contact_permission_status",
    "campaign_eligible",
]


def build_query() -> str:
    """Build the reproducible Overpass query for the configured Cairo bbox."""
    south, west, north, east = BBOX
    lines = ["[out:json][timeout:60];", "("]
    lines.extend(
        f"  {selector}({south},{west},{north},{east});"
        for selector, _meaning in TAG_QUERIES
    )
    lines.extend((");", "out center tags;"))
    return "\n".join(lines)


def classify(tags: dict[str, Any]) -> tuple[str, str]:
    """Return a conservative segment label and a classification caveat."""
    craft = str(tags.get("craft") or "").strip().casefold()
    shop = str(tags.get("shop") or "").strip().casefold()

    if craft == "hvac":
        return "HVAC", "direct_osm_craft_tag_requires_business_verification"
    if shop == "hvac":
        return "HVAC_RETAIL_CANDIDATE", "retail_not_confirmed_installer"
    if shop == "air_conditioning":
        return "HVAC_RELATED_CANDIDATE", "retail_or_service_requires_review"
    if craft == "roofer":
        return "Roofing", "direct_osm_craft_tag_requires_business_verification"
    if craft == "photovoltaic":
        return "Solar", "osm_tag_candidate_requires_business_verification"
    if shop == "photovoltaic":
        return "Solar_RETAIL_CANDIDATE", "retail_not_confirmed_installer"
    if craft == "plumber":
        return "Adjacent_Plumbing", "adjacent_trade_not_target_vertical"
    if craft == "electrician":
        return "Adjacent_Electrical", "adjacent_trade_not_target_vertical"
    return "Unclassified", "manual_review_required"


def get_coordinates(element: dict[str, Any]) -> tuple[Any, Any]:
    """Read node coordinates or the center supplied for a way/relation."""
    if "lat" in element and "lon" in element:
        return element.get("lat"), element.get("lon")
    center = element.get("center") or {}
    return center.get("lat"), center.get("lon")


def normalize_element(
    element: dict[str, Any], extracted_at: str, query_file: str
) -> dict[str, Any]:
    """Normalize one OSM element without inferring missing business details."""
    tags = element.get("tags") or {}
    latitude, longitude = get_coordinates(element)
    service_vertical, classification_note = classify(tags)
    osm_type = str(element.get("type") or "")
    osm_id = element.get("id")
    primary_tags = {
        key: tags[key]
        for key in ("craft", "shop", "office", "industrial")
        if key in tags
    }
    name = str(tags.get("name") or "").strip()
    contact_phone = tags.get("contact:phone") or tags.get("phone") or ""
    contact_email = tags.get("contact:email") or tags.get("email") or ""
    contact_website = tags.get("contact:website") or tags.get("website") or ""

    return {
        "business_name": name,
        "name_present": bool(name),
        "service_vertical": service_vertical,
        "classification_note": classification_note,
        "osm_primary_tags": json.dumps(primary_tags, ensure_ascii=False, sort_keys=True),
        "osm_type": osm_type,
        "osm_id": osm_id,
        "osm_url": (
            f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
            if osm_type and osm_id is not None
            else ""
        ),
        "latitude": latitude,
        "longitude": longitude,
        "phone": contact_phone,
        "email": contact_email,
        "website": contact_website,
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
        # A public listing is not proof of consent or permission to contact.
        "contact_permission_status": "unknown",
        "campaign_eligible": "false",
    }


def deduplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate on the stable OSM identity (element type + element ID)."""
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        osm_type = str(record.get("osm_type") or "")
        osm_id = record.get("osm_id")
        if not osm_type or osm_id is None or str(osm_id) == "":
            raise ValueError("Every OSM record must have both an element type and ID.")
        unique.setdefault((osm_type, str(osm_id)), record)
    return list(unique.values())


def build_session() -> requests.Session:
    """Create a polite HTTP session with bounded retries for transient errors."""
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
    session.headers.update(
        {
            "User-Agent": "HomeServicesLeadIntelligence/0.2.0 (educational portfolio project)",
            "Accept": "application/json",
        }
    )
    return session


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    """Write normalized records with stable headers, including for empty results."""
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def run_extraction(
    project_root: Path = PROJECT_ROOT,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Run one live, read-only Overpass extraction and return run metadata."""
    directories = {
        "raw": project_root / "data" / "raw",
        "processed": project_root / "data" / "processed",
        "metadata": project_root / "data" / "metadata",
        "queries": project_root / "queries",
    }
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    extracted_at = started.isoformat(timespec="seconds")
    query = build_query()
    query_path = directories["queries"] / "cairo_metro_discovery_v2.overpassql"
    raw_path = directories["raw"] / f"osm_cairo_metro_v2_{stamp}.json"
    csv_path = directories["processed"] / f"osm_cairo_metro_discovery_v2_{stamp}.csv"
    metadata_path = (
        directories["metadata"] / f"osm_cairo_metro_discovery_v2_{stamp}.json"
    )
    query_path.write_text(query, encoding="utf-8")
    relative_query_path = query_path.relative_to(project_root).as_posix()

    http = session or build_session()
    try:
        response = http.post(ENDPOINT, data={"data": query}, timeout=(20, 120))
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Overpass API request failed: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError("Overpass API returned a response that is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Overpass response: expected a JSON object.")
    if payload.get("remark"):
        raise RuntimeError(f"Overpass reported a query issue: {payload['remark']}")

    # Preserve the complete source response before any transformation.
    raw_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    source_elements = payload.get("elements") or []
    if not isinstance(source_elements, list):
        raise RuntimeError("Unexpected Overpass response: 'elements' is not a list.")
    if any(not isinstance(element, dict) for element in source_elements):
        raise RuntimeError("Unexpected Overpass response: an element is not a JSON object.")

    normalized = [
        normalize_element(element, extracted_at, relative_query_path)
        for element in source_elements
    ]
    records = deduplicate_records(normalized)
    write_csv(csv_path, records)

    by_vertical = Counter(record["service_vertical"] for record in records)
    named_count = sum(record["name_present"] for record in records)
    contact_count = sum(
        bool(record["phone"] or record["email"] or record["website"])
        for record in records
    )
    osm3s = payload.get("osm3s") or {}
    metadata: dict[str, Any] = {
        "project": "Home Services Lead Intelligence",
        "script_version": SCRIPT_VERSION,
        "source_name": SOURCE_NAME,
        "source_endpoint": ENDPOINT,
        "source_license": SOURCE_LICENSE,
        "attribution": "© OpenStreetMap contributors",
        "attribution_url": "https://www.openstreetmap.org/copyright",
        "query_file": relative_query_path,
        "bbox_south_west_north_east": BBOX,
        "geographic_scope_note": (
            "Broad Cairo metro bounding rectangle; it is not an administrative boundary."
        ),
        "requested_tags_and_intended_meaning": TAG_QUERIES,
        "extracted_at_utc": extracted_at,
        "osm_base_timestamp": osm3s.get("timestamp_osm_base")
        if isinstance(osm3s, dict)
        else None,
        "http_status": response.status_code,
        "http_response_bytes": len(response.content),
        "raw_response_file": raw_path.relative_to(project_root).as_posix(),
        "processed_csv_file": csv_path.relative_to(project_root).as_posix(),
        "raw_elements": len(source_elements),
        "unique_elements": len(records),
        "records_by_classification": dict(by_vertical),
        "named_elements": named_count,
        "elements_with_any_public_contact_field": contact_count,
        "deduplication_key": ["osm_type", "osm_id"],
        "permission_policy": {
            "default_status": "unknown",
            "campaign_eligible_default": False,
            "note": "Publicly mapped contact details do not establish marketing consent.",
        },
        "limitations": [
            "OpenStreetMap coverage is community-maintained and may be incomplete or uneven.",
            "Tags identify mapped features; they do not verify active business status.",
            "Retail and adjacent-trade matches are candidates, not confirmed installers.",
            "A city or country is not inferred when the source does not provide it.",
            "This output is not a verified or consent-cleared outbound lead list.",
        ],
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metadata


def main() -> None:
    """Command-line entry point used by the repository script and console command."""
    print(f"Source: {SOURCE_NAME}")
    print(f"Endpoint: {ENDPOINT}")
    print(f"Cairo metro bbox (south, west, north, east): {BBOX}")
    print("Searching service tags, retail candidates and adjacent trades...")
    metadata = run_extraction()
    print("\nEXTRACTION COMPLETE")
    print(f"HTTP status: {metadata['http_status']}")
    print(f"Raw OSM elements: {metadata['raw_elements']}")
    print(f"Unique records: {metadata['unique_elements']}")
    print(f"By classification: {metadata['records_by_classification']}")
    print(f"Named elements: {metadata['named_elements']}")
    print(
        "Elements with phone/email/website: "
        f"{metadata['elements_with_any_public_contact_field']}"
    )
    print(f"Raw JSON: {metadata['raw_response_file']}")
    print(f"Processed CSV: {metadata['processed_csv_file']}")
    print("Run metadata: data/metadata/osm_cairo_metro_discovery_v2_*.json")
    print("Attribution: © OpenStreetMap contributors")
    print("Campaign eligibility remains FALSE for every record.")


if __name__ == "__main__":
    main()
