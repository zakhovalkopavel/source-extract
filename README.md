# source-extract

**One library + single entry point:** take a **source** (tabular handbooks, diagram figures, or mixed papers) and **save structured results** — via console CLI, REST API (Swagger), and React GUI.

| Surface | Entry |
| --- | --- |
| Library | `source_extract.tables` / `.diagrams` / `.papers` / `.pipeline` |
| CLI | `source-extract …` or `python -m source_extract.cli` |
| API | FastAPI `/api/v1`, docs at `/docs` |
| GUI | `frontend/` (React 19 + MUI + Vite) |

Host apps keep **source adapters** only (paths, catalogs, quirks). SE discovers them through entry points (`source_extract.adapters`) and/or `SE_ADAPTER_MODULES`.

Depends on **`page-ocr`** for recognition (local or Modal).

## Layout

```text
src/source_extract/
  adapters/     SourceAdapter protocol + registry
  commands/     CommandSpec catalog
  params/       ParamSpec + validation
  jobs/         async job runner
  models/       LLM + OCR
  assist/       assistant tools
  review/       review sessions (spine)
  versioning/   current/history + manifests
  api/          FastAPI
  cli/          console entry
  diagrams/ tables/ papers/ pipeline.py
frontend/       React GUI
docker/         SE-local Dockerfile + compose
```

## Quick start (inside thermal-software compose)

```bash
docker compose up -d source-extractor source-extractor-ui
curl -s http://localhost/source-extractor/api/v1/health
docker compose run --rm --no-deps source-extractor python -m source_extract.cli --help
```

## Tests

```bash
docker compose run --rm --no-deps source-extractor \
  bash -c "pip install -q pytest httpx && pip install -q -e /app/vendor/source-extract && pytest /app/vendor/source-extract/tests -q"
```

This directory is its **own git repository** (submodule path `vendor/source-extract`).
