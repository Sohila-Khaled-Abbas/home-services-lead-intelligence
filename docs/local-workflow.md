# Local-device workflow and checkpoints

This guide starts from the local project state **before pulling the GitHub professionalization changes**. It is deliberately read-first: do not reset, clean, hard-reset, or overwrite local files as a shortcut.

## Local project path

~~~text
D:\courses\Data Analysis 26-27\Projects\home-services-lead-intelligence
~~~

## Checkpoint 0 — inspect before changing anything

Open PowerShell:

~~~powershell
Set-Location "D:\courses\Data Analysis 26-27\Projects\home-services-lead-intelligence"

git status --short --branch
git branch --show-current
git remote -v
git log --oneline --decorate -5
~~~

**Stop and inspect** if `git status` shows modified, deleted, staged, or untracked files you care about. Do not use `git reset --hard`, `git clean -fd`, or force-push to make the output look clean.

Save a local inventory of the project files:

~~~powershell
Get-ChildItem -Force
Get-ChildItem -Recurse -File |
    Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]|[\\/]\.venv[\\/]|[\\/]__pycache__[\\/]' } | |
    Select-Object FullName, Length, LastWriteTime
~~~

If the working tree contains important uncommitted changes, make a normal backup copy outside the repository before continuing, or commit them on a separate local branch after reviewing the diff.

## Checkpoint 1 — confirm the remote and fetch

Confirm that `origin` points to:

~~~text
https://github.com/Sohila-Khaled-Abbas/home-services-lead-intelligence.git
~~~

Then fetch remote history without changing your working files:

~~~powershell
git fetch origin
git branch -avv
git log --oneline --decorate --all -10
~~~

The professionalized repository is now on `origin/main`. Do not assume that your local `main` is current.

## Checkpoint 2 — synchronize safely

First confirm that the working tree is clean:

~~~powershell
git status --short
~~~

If it is clean and you are on `main`, fast-forward it:

~~~powershell
git switch main
git pull --ff-only origin main
~~~

If you are not on `main`, or the tree is not clean, stop before switching branches. Review the status and diffs, preserve your work on a separate branch or backup, then synchronize deliberately. Do not merge unrelated local changes blindly.

Verify the professionalization commit is now present:

~~~powershell
git log --oneline --decorate -8
Test-Path .\README.md
Test-Path .\src\home_services_lead_intelligence\osm.py
Test-Path .\tests\test_osm.py
~~~

## Checkpoint 3 — activate and validate the environment

Use the project virtual environment already created on this device:

~~~powershell
& ".\.venv\Scripts\python.exe" --version
& ".\.venv\Scripts\python.exe" -m pip check
& ".\.venv\Scripts\python.exe" -m pytest -q
& ".\.venv\Scripts\python.exe" -m ruff check .
~~~

If Ruff is not installed in the existing environment, install the project's development dependencies:

~~~powershell
& ".\.venv\Scripts\python.exe" -m pip install -e ".[dev]"
~~~

Do not run a new live extraction merely to test setup. Unit tests are offline; your existing November 4 raw response, CSV, metadata, and query remain the reference baseline.

## Checkpoint 4 — create a working branch for the next project milestone

Once tests and lint pass:

~~~powershell
git switch -c feat/nrea-solar-source
~~~

The next implementation should evaluate NREA's published Solar/PV company information, document its reuse conditions, and only then build a source adapter. Keep the national list's source geography separate from a verified company operating location.

## Checkpoint 5 — implementation and evidence

For each future source adapter:

1. Record the source URL, publisher, terms, license, attribution, access method, and rate limits.
2. Save a raw snapshot locally before transformation.
3. Add a source-specific parser and unit tests using saved, sanitized fixtures.
4. Normalize fields without inventing missing names, locations, contacts, or dates.
5. Preserve original source IDs and extraction timestamps.
6. Keep `contact_permission_status = unknown` and `campaign_eligible = false` unless separately reviewed and documented.
7. Update the README and project status only after the implementation is tested.

Do not commit new raw contact-bearing files until you have reviewed source reuse rights and the content for privacy and suitability.

## Checkpoint 6 — commit and publish

Inspect the change:

~~~powershell
git status --short
git diff --check
git diff
~~~

Run tests again, then commit focused changes:

~~~powershell
git add <reviewed-files>
git commit -m "feat: add NREA solar source adapter"
git push -u origin feat/nrea-solar-source
~~~

Open a pull request from the feature branch to `main`. Review the diff and CI checks before merging.

## Recovery rules

- If Git reports a merge conflict, do not delete conflict markers blindly. Inspect both versions and reconcile each file.
- If a pull fails because local changes would be overwritten, stop and preserve those changes first.
- Never use `git push --force` on `main`.
- Never commit `.venv`, API tokens, passwords, local environment files, or unreviewed extraction files.
