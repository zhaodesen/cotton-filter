# Cotton Filter

A cross-platform desktop tool for filtering, scoring, and exporting cotton-resource Excel workbooks.

[English](./README.md) | [简体中文](./README.zh-CN.md)

## Overview

Cotton Filter combines a Tauri desktop shell with a React interface and a local Python service. Tauri manages native windows, file selection, packaging, and updates; Python handles Excel parsing, header matching, rule-based scoring, filtering, and result generation.

```text
Tauri desktop app
  └── React + Vite UI
        └── Local FastAPI sidecar
              └── pandas / openpyxl / xlrd
```

## Features

- Process single or multiple Excel workbooks
- Match varying column names through maintainable alias rules
- Configure scoring and filtering rules in a local SQLite database
- Export filtered results with Chinese logs and output columns
- Package for macOS and Windows with Tauri 2
- Generate updater artifacts for GitHub Releases

## Requirements

- Node.js 24 or a compatible release
- Rust stable
- Python 3.10
- [uv](https://docs.astral.sh/uv/)
- Platform-specific Tauri prerequisites

## Getting Started

```bash
uv sync
npm install
npm run dev
```

The development command builds the Python sidecar, starts Vite, and opens the Tauri application. The local API listens only on `127.0.0.1` and uses a dynamically selected port.

## Development Commands

| Command | Description |
| --- | --- |
| `npm run dev` | Run the complete desktop app |
| `npm run build:backend` | Build the Python sidecar |
| `npm run build:frontend` | Build the sidecar and frontend assets |
| `npm run build` | Create platform installers with Tauri |
| `uv run --with pytest python -m pytest` | Run Python tests |
| `cargo check --manifest-path src-tauri/Cargo.toml` | Check the Rust project |

## Project Structure

```text
backend/             # FastAPI sidecar entry point
cotton_filter_app/   # Excel processing and rule engine
src/                 # React user interface
src-tauri/           # Tauri configuration and Rust entry point
scripts/             # Sidecar build, versioning, and updater scripts
```

## Packaging and Updates

```bash
npm run build
```

Release builds that publish updater artifacts require `TAURI_SIGNING_PRIVATE_KEY` and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` in the environment or GitHub Actions secrets. Never commit signing keys to the repository.

## Design Notes

- Keep Excel-processing logic in `cotton_filter_app/`.
- Add customer-specific column names through alias rules instead of hard-coding them.
- Prefer SQLite-backed rules for recognition, scoring ranges, and filters.
- Keep the backend local and preserve Chinese logs and exported column names.
