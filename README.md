# CircuitPedal Reference Importer

A research importer for building a structured reference library of analogue guitar-effects circuits for the CircuitPedal project.

The importer is intentionally separate from the main CircuitPedal application. Its job is to collect and normalize source evidence; it does **not** attempt to generate DSP models.

## Phase 1 goals

- Discover every post from Effects Layouts using Blogger's public post feed.
- Open each individual post rather than collecting images alone.
- Capture title, URL, date, labels and Verified/Unverified status.
- Capture post text for local research.
- Classify links, including likely schematic/reference links.
- Record layout/reference image URLs without downloading binaries by default.
- Record iframe/embed URLs used by older posts for circuit material.
- Capture comments and identify replies by the blog author where possible.
- Cache fetched HTML locally and resume safely on later runs.
- Produce JSONL records plus a crawl summary.
- Provide a mixed-sample validation report before a full crawl.
- Be polite to the source site with explicit request throttling.

## Important source-use boundary

Effects Layouts states that its layouts are intended for hobbyists and that commercial use requires permission. This repository is therefore designed as a **research/indexing tool**. Cached HTML, images and full scraped datasets are local-only and gitignored by default.

CircuitPedal should ultimately use independently implemented circuit models and retain source provenance rather than redistributing source layout artwork.

## Requirements

- Python 3.11+

## Setup

```bash
python3 -m venv .venv
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Validate before a full crawl

Run:

```bash
circuitpedal-importer validate
```

The validation command discovers the catalogue, inspects a distributed candidate pool, and selects a mixed set of representative posts where available, including:

- Verified and Unverified posts
- posts with schematic links
- posts with iframe/embed references
- posts with community comments
- posts with Effects Layouts author replies
- posts with richer reference-link sets
- older and recent catalogue entries

It prints a readable report to the terminal and also writes:

```text
data/validation-report.txt
data/validation-report.json
```

For a larger validation sample:

```bash
circuitpedal-importer validate --sample-size 12 --candidate-pool 40
```

Use `--refresh` if you deliberately want to bypass cached pages.

The report includes each selected post's source URL so it can be manually compared with the original page.

## Crawl

A small test crawl:

```bash
circuitpedal-importer crawl --limit 5
```

Full crawl:

```bash
circuitpedal-importer crawl
```

Force a refresh of cached pages:

```bash
circuitpedal-importer crawl --refresh
```

Skip comment extraction:

```bash
circuitpedal-importer crawl --no-comments
```

Outputs are written under `data/` and page cache files under `cache/`. Both are ignored by Git apart from placeholder files.

## Output record

Each JSONL line represents one blog post and includes:

- source URL
- title
- published timestamp
- labels
- verification status
- normalized post text
- outgoing links with a basic classification
- likely schematic links
- image URLs
- iframe/embed URLs
- comments/replies
- fetch timestamp
- content hash

This is deliberately evidence-oriented. Circuit interpretation and model generation belong in later phases.

## Development

```bash
pytest
```

The unit tests use local HTML fixtures/strings and do not require network access.
