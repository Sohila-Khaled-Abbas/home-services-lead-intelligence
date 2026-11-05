# Contributing

Thank you for helping improve Home Services Lead Intelligence.

## Development setup

Python 3.11 or newer is required.

~~~powershell
python -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -e ".[dev]"
~~~

## Before making changes

1. Read the [README](README.md), [architecture](docs/architecture.md), and [data governance](docs/data-governance.md).
2. Create a short-lived branch from the latest \`main\`.
3. Keep changes focused and avoid committing local environments, credentials, or unreviewed extraction output.

Suggested branch names:

- \`feat/<short-description>\`
- \`fix/<short-description>\`
- \`docs/<short-description>\`
- \`chore/<short-description>\`

## Validation

Run the offline tests and lint checks before opening a pull request:

~~~powershell
& ".\.venv\Scripts\python.exe" -m pytest
& ".\.venv\Scripts\python.exe" -m ruff check .
~~~

Tests should not depend on a live third-party API. Use mocked responses for unit tests and keep live extraction as a deliberate manual or separately controlled integration step.

## Adding a data source

Before writing an adapter, document:

- Canonical source URL and source owner.
- API or page access method and applicable terms.
- License, attribution, and redistribution conditions.
- Fields required and why each is necessary.
- Source record identifier and provenance strategy.
- Refresh/rate limits and failure handling.
- Known coverage gaps and classification caveats.

Never bypass authentication, paywalls, CAPTCHAs, rate limits, or technical access controls. Do not assume public visibility means permission to collect, republish, or contact.

## Pull request checklist

- [ ] The change has a clear scope and rationale.
- [ ] Tests are added or updated where behavior changes.
- [ ] \`pytest\` and \`ruff check .\` pass.
- [ ] Documentation and project status reflect the actual implementation.
- [ ] Source provenance and licensing are documented for new data.
- [ ] No secrets, credentials, or unreviewed personal/contact data are included.
- [ ] Any limitations or unverified assumptions are stated explicitly.

Use descriptive commits, for example \`feat: add NREA source adapter\` or \`docs: clarify OSM attribution\`.
