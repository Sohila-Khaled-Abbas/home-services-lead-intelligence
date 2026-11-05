"""Unit tests for the OSM discovery pipeline; tests do not call the live API."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from home_services_lead_intelligence.osm import (
    BBOX,
    CSV_FIELDS,
    ENDPOINT,
    SOURCE_LICENSE,
    SOURCE_NAME,
    TAG_QUERIES,
    build_query,
    classify,
    deduplicate_records,
    get_coordinates,
    normalize_element,
    run_extraction,
    write_csv,
)


def test_query_includes_configured_bbox_and_each_discovery_tag() -> None:
    query = build_query()

    assert f"({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]})" in query
    assert len(TAG_QUERIES) == 8
    for selector, _meaning in TAG_QUERIES:
        assert selector in query
    assert query.endswith("out center tags;")


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({"craft": "hvac"}, "HVAC"),
        ({"shop": "hvac"}, "HVAC_RETAIL_CANDIDATE"),
        ({"shop": "air_conditioning"}, "HVAC_RELATED_CANDIDATE"),
        ({"craft": "roofer"}, "Roofing"),
        ({"craft": "photovoltaic"}, "Solar"),
        ({"shop": "photovoltaic"}, "Solar_RETAIL_CANDIDATE"),
        ({"craft": "plumber"}, "Adjacent_Plumbing"),
        ({"craft": "electrician"}, "Adjacent_Electrical"),
        ({"craft": "unknown"}, "Unclassified"),
    ],
)
def test_classification_is_explicit_and_conservative(
    tags: dict[str, str], expected: str
) -> None:
    actual, _note = classify(tags)
    assert actual == expected


def test_coordinates_support_nodes_and_centered_ways() -> None:
    assert get_coordinates({"lat": 30.1, "lon": 31.2}) == (30.1, 31.2)
    assert get_coordinates({"center": {"lat": 30.2, "lon": 31.3}}) == (30.2, 31.3)
    assert get_coordinates({}) == (None, None)


def test_normalization_preserves_provenance_and_defaults_to_not_eligible() -> None:
    element = {
        "type": "node",
        "id": 123,
        "lat": 30.0,
        "lon": 31.0,
        "version": 2,
        "timestamp": "2026-11-04T10:00:00Z",
        "tags": {
            "name": "Example HVAC",
            "craft": "hvac",
            "phone": "+20200000000",
            "addr:city": "Cairo",
        },
    }

    record = normalize_element(
        element, "2026-11-05T00:00:00+00:00", "queries/test.overpassql"
    )

    assert record["business_name"] == "Example HVAC"
    assert record["service_vertical"] == "HVAC"
    assert record["osm_url"] == "https://www.openstreetmap.org/node/123"
    assert record["source_name"] == SOURCE_NAME
    assert record["source_endpoint"] == ENDPOINT
    assert record["source_license"] == SOURCE_LICENSE
    assert record["contact_permission_status"] == "unknown"
    assert record["campaign_eligible"] == "false"


def test_deduplication_uses_element_type_and_id() -> None:
    records = [
        {"osm_type": "node", "osm_id": 10, "business_name": "first"},
        {"osm_type": "node", "osm_id": 10, "business_name": "duplicate"},
        {"osm_type": "way", "osm_id": 10, "business_name": "different type"},
    ]

    result = deduplicate_records(records)

    assert len(result) == 2
    assert result[0]["business_name"] == "first"


def test_deduplication_rejects_records_without_stable_identity() -> None:
    with pytest.raises(ValueError, match="element type and ID"):
        deduplicate_records([{"osm_type": "node", "osm_id": None}])


def test_empty_csv_still_contains_stable_schema(tmp_path: Path) -> None:
    output = tmp_path / "empty.csv"
    write_csv(output, [])

    with output.open(encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle))

    assert header == CSV_FIELDS


class FakeResponse:
    status_code = 200
    content = b'{"elements": []}'

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"elements": [], "osm3s": {"timestamp_osm_base": "2026-11-04T00:00:00Z"}}


class FakeSession:
    def __init__(self) -> None:
        self.calls = 0

    def post(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
        self.calls += 1
        return FakeResponse()


def test_run_extraction_writes_query_raw_csv_and_metadata_for_zero_results(
    tmp_path: Path,
) -> None:
    session = FakeSession()
    metadata = run_extraction(project_root=tmp_path, session=session)  # type: ignore[arg-type]

    assert session.calls == 1
    assert metadata["http_status"] == 200
    assert metadata["raw_elements"] == 0
    assert metadata["unique_elements"] == 0
    assert (tmp_path / metadata["query_file"]).exists()
    assert (tmp_path / metadata["raw_response_file"]).exists()
    assert (tmp_path / metadata["processed_csv_file"]).exists()
    assert len(list((tmp_path / "data" / "metadata").glob("*.json"))) == 1
