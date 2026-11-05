# Data governance and responsible use

## Source provenance

Every collected record should retain, where available:

- Source name and canonical source URL or API endpoint.
- Source record identifier and record URL.
- Source license or terms reference.
- Exact query, endpoint parameters, or extraction method.
- UTC extraction timestamp and source update timestamp.
- Any transformation, validation, or manual-review decision.

Do not merge records from different sources in a way that discards their individual provenance.

## Contact data and campaign eligibility

A publicly visible phone number, email address, or website is not evidence of consent or legal permission for outbound marketing. New records must default to:

- **contact_permission_status = unknown**
- **campaign_eligible = false**

Do not change these fields automatically because a contact field exists. Any later approval requires a documented review of the source terms, applicable Egyptian legal requirements, the intended purpose, and the organization's contact policy. This repository does not provide legal advice.

## Collection boundaries

- Use public APIs or pages where the access method and reuse conditions permit the intended collection.
- Do not bypass authentication, paywalls, CAPTCHAs, rate limits, or technical access controls.
- Respect source terms, robots guidance where applicable, API usage policies, attribution, and request limits.
- Collect only business-relevant fields needed for the stated project purpose.
- Do not intentionally collect sensitive personal data.
- Keep source snapshots private/local until reviewed for licensing, relevance, and third-party contact information.

## OpenStreetMap

OSM data is available under ODbL 1.0. Attribute OpenStreetMap contributors and review share-alike obligations before redistributing substantial extracts or a derived database. A source's public visibility does not remove its license conditions.

## Repository hygiene

New raw and processed extraction outputs are ignored by Git by default. The two existing baseline snapshots are allow-listed for project traceability. This is not legal approval to reuse, redistribute, or market the records.
