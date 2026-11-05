# Architecture

## Current extraction flow

~~~text
OpenStreetMap / Overpass API
          │
          ▼
  Raw JSON response ───────────────► data/raw/
          │
          ▼
  Normalize OSM elements
  - nodes and centered ways/relations
  - preserve source tags and identifiers
  - classify target, retail candidate, adjacent trade
          │
          ▼
  Deduplicate by (osm_type, osm_id)
          │
          ├────────────────────────► data/processed/*.csv
          │
          └────────────────────────► data/metadata/*.json

Exact Overpass QL query ───────────► queries/*.overpassql
~~~

## Current boundaries

The extraction is read-only and uses one Overpass endpoint. The Cairo search area is a rectangular bounding box (south, west, north, east), not an administrative boundary. OSM tags are discovery signals, not proof of an active business or a verified service offering.

Raw responses are saved before transformation. The CSV retains OSM IDs, feature URLs, primary tags, contact fields where publicly mapped, the source endpoint/license, query filename, and extraction timestamp. Missing city/country values remain blank rather than being inferred from coordinates.

## Planned architecture (not yet implemented)

~~~text
Approved public/API sources
          │
          ▼
 Source-specific adapters
          │
          ▼
 Raw snapshots + provenance
          │
          ▼
 Normalize / validate / classify
          │
          ▼
 Cross-source entity resolution
          │
          ▼
 Reviewable SQL store
          │
          ├── Data-quality reports
          └── Reviewed, permitted exports
~~~

Each future source adapter must document its terms, license, access method, refresh policy, fields collected, and limitations before being enabled. A source-specific record ID must be retained to make transformations reproducible.
