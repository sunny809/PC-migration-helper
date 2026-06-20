# PC Migration Helper

> **迁移助手** — Scan, review, and migrate your personal files when switching to a new Windows PC.

[![Build](https://github.com/your-username/PC-migration-helper/actions/workflows/build.yml/badge.svg)](https://github.com/your-username/PC-migration-helper/actions/workflows/build.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## What it does

When you get a new computer, you need to move your files from the old one. This tool helps you:

1. **Scan** drives to find your personal files (documents, photos, music, browser bookmarks, etc.)
2. **Review** what was found and select what to keep
3. **Package** them into a ZIP/7z archive or copy to a USB drive
4. **Verify** every file was written correctly (xxHash / SHA-256)

Everything runs locally. No cloud, no accounts, no uploads.

---

## Features

| | Feature | Description |
|--|---------|-------------|
| 📂 | **Smart scan** | Scans your drives, excludes system/application files automatically |
| 🏷️ | **File classification** | Groups files into Documents, Photos, Videos, Music, Archives, Browser Data |
| 🔍 | **Search & filter** | Find files by name, extension, category, or path |
| 📦 | **ZIP / 7z / Copy** | Package files with compression, or copy them as-is |
| ✅ | **Post-migration verification** | Every file is checksummed (xxHash) and verified after writing |
| 🌐 | **Bilingual UI** | 中文 / English — switch at any time |
| 🧩 | **Browser bookmarks** | Automatically detects Chrome, Edge, Firefox, Brave, Vivaldi, Opera bookmarks |

---

## Quick start

### Option 1: Download the latest build

Go to the [Releases](https://github.com/your-username/PC-migration-helper/releases) page and download the latest `PC迁移助手-Windows-x64.zip`. Extract and run `PC迁移助手.exe`.

### Option 2: Run from source

```bash
# Requires Python 3.11+
git clone https://github.com/your-username/PC-migration-helper.git
cd PC-migration-helper
pip install -r requirements.txt
python main.py
```

---

## How to use (4-step wizard)

```
Step 1                Step 2                 Step 3              Step 4
Scan                  Review                 Target              Execute
────                  ──────                 ──────              ───────
Select drives →       Browse files by        Choose a USB →      Choose format →
Start scan             category →             drive or path →    Start migration →
                      Check/uncheck files    Check free space   Watch progress →
                                                                 Verify files →
                                                                 Read report
```

### Reports

After each scan, a preview report (`report.html`) is generated automatically. Open it in your browser to see what was found — file counts, sizes by category, and a browseable file tree.

After migration, a final report including verification results is saved alongside your backup.

---

## Build from source

```bash
pip install pyinstaller
python scripts/build.py
# Output: dist/PC迁移助手/
```

Or use the pre-configured GitHub Actions CI — push to `main` and download the artifact.

---

## Project structure

```
src/
├── scanners/         # Disk scanning and file classification
│   ├── disk_scanner.py
│   └── file_classifier.py
├── migration/        # Compression (ZIP/7z) and copy engine
│   ├── compressor.py
│   └── copier.py
├── targets/          # USB/drive detection
├── utils/            # Browser detection, checksum, human-size formatting
│   ├── browser_detector.py
│   └── checksum.py
├── ui/               # PySide6 interface — 4-step wizard
├── models/           # Data classes (FileEntry, ScanResult, MigrationConfig)
└── constants.py      # Enums and app metadata
```

---

## Tech stack

| Component | Choice |
|-----------|--------|
| GUI | PySide6 (Qt for Python) |
| Packaging | PyInstaller (--onedir) |
| Compression | ZIP (built-in) + 7z (py7zr) |
| Verification | xxHash (default), SHA-256 (optional) |
| Config | YAML (`config/default_rules.yaml`) |

---

## License

MIT
