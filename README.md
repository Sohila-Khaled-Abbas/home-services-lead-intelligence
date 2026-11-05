# Home Services Lead Intelligence

**A provenance-first public business-data discovery project for Egypt's home-services market.**

> **Current phase:** source discovery and extraction foundations. This repository is an in-progress portfolio project—not a production lead database and not a consent-cleared outbound list.

## Project objective

Build a reproducible data pipeline that discovers publicly documented home-services businesses, records where each field came from, standardizes the data, evaluates record quality, and produces reviewable datasets for downstream analytics.

The initial market is Egypt. The first geographic test is a broad Cairo-metro bounding box. Target segments are:

- Solar and photovoltaic service providers
- HVAC and air-conditioning service providers
- Roofing contractors

Plumbing and electrical records are retained as **adjacent-trade discovery results**, not counted as target-segment leads.

## Verified implementation status

The latest committed live extraction was run on **November 4, 2026** against the OpenStreetMap Overpass API. The API returned HTTP 200 and four unique OSM elements:

| Classification | Records |
|---|---:|
| Adjacent plumbing | 2 |
| Adjacent electrical | 2 |
| Solar / HVAC / roofing target matches | 0 |
| **Total** | **4** |

All four records had a name tag; one had at least one public contact field (phone, email, or website). These are mapped OSM features, not independently verified active businesses. None is approved for campaign use. The exact raw response, processed CSV, query, and run metadata are retained in the repository for auditability.

The earlier, narrower HVAC/roofing query also completed successfully but returned zero records. The broader discovery query did not find a target-segment match in the configured area. This is evidence of limited OSM coverage for this query—not evidence that Cairo has no such businesses.

## Implemented now

- Read-only extraction from the Overpass API using Python requests.
- Eight explicit OSM tag selectors for target, retail-candidate, and adjacent-trade discovery.
- Node and way/relation-center coordinate handling.
- Conservative classification that keeps retailers and adjacent trades distinct.
- Stable deduplication on (osm_type, osm_id).
- Raw JSON preservation before transformation.
- UTF-8 CSV output with a stable schema, including an empty-result header.
- Run metadata containing endpoint, query path, bounding box, OSM base timestamp, counts, output paths, and known limitations.
- Contact permission defaults to unknown; campaign_eligible defaults to false.
- Unit tests that use a fake HTTP response and do not call the live API.

## Not implemented yet

BeautifulSoup or Scrapy website collection, Selenium or Playwright browser automation, NREA or directory ingestion, business-website enrichment, SQL storage, automated entity resolution across sources, a campaign export, and a Power BI quality dashboard are planned work. They are not represented as completed capabilities.

## Repository structure

~~~text
home-services-lead-intelligence/
├── data/
│   ├── metadata/       # Committed extraction-run metadata
│   ├── processed/      # Committed discovery CSV snapshots
│   └── raw/            # Committed original OSM JSON responses
├── docs/
│   ├── architecture.md
│   ├── data-governance.md
│   └── project-status.md
├── queries/            # Reproducible Overpass QL query
├── scripts/            # Human-friendly extraction entry point
├── src/
│   └── home_services_lead_intelligence/
│       └── osm.py      # Reusable extraction and normalization logic
├── tests/              # Offline unit tests
├── .gitignore
├── pyproject.toml
└── README.md
~~~

## Quick start (Windows PowerShell)

Python 3.11 or newer is required. From the repository root:

~~~powershell
# Create the virtual environment once
python -m venv .venv

# Install the project and development tools
& ".\.venv\Scripts\python.exe" -m pip install -e ".[dev]"

# Run the Cairo discovery extraction (makes one read-only API request)
& ".\.venv\Scripts\python.exe" ".\scripts\extract_osm_cairo_v2.py"

# Run the offline test suite
& ".\.venv\Scripts\python.exe" -m pytest
~~~

The extraction uses a bounded request timeout and retries temporary HTTP errors. Overpass is a shared public service; avoid repeated rapid requests. A successful HTTP response with zero matches is a valid **zero-result extraction**, not evidence of source coverage completeness.

## Output files

Each run writes a timestamped set of files:

- data/raw/: unmodified JSON response returned by Overpass.
- data/processed/: normalized CSV for analysis.
- data/metadata/: run metadata and source provenance.
- queries/: the exact Overpass QL query used for the run.

Generated live outputs are ignored by Git by default. The two existing November 4, 2026 baseline snapshots remain tracked for traceability; they are not consent-cleared or approved for campaign use. Review new output for licensing, relevance, and third-party contact information before deciding whether any artifact should be committed.

## Data model and quality boundaries

Every normalized row carries its OSM element type and ID, OSM feature URL, source name, API endpoint, source license, query file, extraction timestamp, and source object timestamp/version when supplied. The source's own location fields are retained; the pipeline does not invent a city or country when OSM does not provide it.

A mapped feature is not automatically a qualified lead. Records still require checks for name quality, service fit, active status, location, duplicate identity across sources, and permitted use. Publicly visible contact details do **not** establish permission for direct marketing. The pipeline therefore keeps campaign eligibility false until a separate, documented review is performed.

See [Data governance](docs/data-governance.md) and [Project status](docs/project-status.md) for the rules and evidence boundary.

## Roadmap

1. Validate additional Egyptian source options and their access/reuse conditions before automating collection.
2. Add a separately tested source adapter for official Solar/PV company information, preserving source-specific tier and provenance fields.
3. Add permitted HVAC and roofing source adapters; keep directory candidates separate from confirmed service providers.
4. Build field-level cleaning, validation, and cross-source deduplication with auditable decisions.
5. Persist reviewed records in SQLite first, then evaluate PostgreSQL when the data model stabilizes.
6. Add quality reporting and a Power BI view only after the source and entity model are reliable.

## Source attribution and licensing

OpenStreetMap data is © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) and is made available under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Attribution is retained in the run metadata and outputs. Review ODbL obligations before redistributing derived databases or substantial extracts.

No separate license is currently granted for this project's source code. Do not assume that the code is MIT- or Apache-licensed; request permission before reuse until a code license is intentionally selected.
