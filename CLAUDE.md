# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Photo Organizer is a photo indexing and management tool that scans your Mac for photos (TIF, JPG, PNG, HEIC, RAW formats, etc.), detects duplicates using content hashing, generates thumbnails, and provides a web interface to browse and search your collection. Photos are never moved or modified - only indexed.

## Architecture

The project has three components:

1. **Scanner** (`photo_scanner.py`) - CLI tool that walks directories, calculates SHA256 hashes, extracts EXIF metadata, generates thumbnails, and stores everything in SQLite
2. **Web Server** (`server.py`) - FastAPI backend serving photo metadata and thumbnails via REST API
3. **Desktop App** (`desktop/`) - Tauri-based desktop wrapper (in development)

## Commands

### Scanner Operations

```bash
# Scan home directory for photos
python3 photo_scanner.py --scan ~

# Scan specific folder
python3 photo_scanner.py --scan ~/Pictures

# Show database statistics
python3 photo_scanner.py --stats

# List duplicate photos
python3 photo_scanner.py --duplicates

# Categorize all photos (screenshot, photo, wallpaper, etc.)
python3 photo_scanner.py --categorize
```

### Web Server

```bash
# Start web gallery at http://localhost:3000
python3 server.py
```

### Desktop App

```bash
cd desktop
npm install
npm run dev       # Development mode
npm run build     # Build production bundle
npm run tauri dev # Run Tauri desktop app
```

## Key Implementation Details

### Database Schema

SQLite database (`photos.db`) with single table:

```sql
photos (
    id INTEGER PRIMARY KEY,
    file_path TEXT UNIQUE,        -- Full path to original file
    file_hash TEXT,                -- SHA256 for duplicate detection
    file_size INTEGER,             -- Bytes
    storage_location TEXT,         -- "Local HD", "External Drive", "iCloud"
    volume_name TEXT,              -- Volume/drive name
    width INTEGER, height INTEGER, -- Dimensions
    format TEXT,                   -- TIFF, JPEG, PNG, etc.
    date_taken TIMESTAMP,          -- From EXIF if available
    date_modified TIMESTAMP,       -- File mtime
    thumbnail_path TEXT,           -- Path in thumbnails/
    category TEXT,                 -- Auto-categorized: photo, screenshot, wallpaper, etc.
    hidden BOOLEAN                 -- Hide from gallery
)
```

Indexes on `file_hash`, `date_taken`, `file_size` for fast queries.

### Duplicate Detection

Uses SHA256 content hash + file size comparison. Two files are duplicates if both hash AND size match. All duplicate file locations are stored in database - scanner never deletes anything.

### Thumbnail Generation

- 300px max dimension, JPEG format, quality 85
- Thumbnails named by first 16 chars of file hash (reused for duplicates)
- Stored in `thumbnails/` directory
- Handles large TIF files efficiently

### Directory Exclusions

Scanner skips system/app directories to avoid noise and performance issues. Configured in `scan_config.json`:
- System: `Library`, `System`, `.Trash`
- Cloud: `Library/CloudStorage`, `Dropbox`
- Development: `node_modules`, `.git`, `__pycache__`
- Photos.app library (contains internal duplicates)

### Auto-Categorization

Photos are categorized based on:
- Filename patterns (e.g., "screenshot" → screenshot)
- Dimensions (screen resolutions → screenshot, wide high-res → wallpaper)
- EXIF data (has date_taken → photo)
- Aspect ratios (square → social, camera ratios → photo)

Categories: `photo`, `screenshot`, `wallpaper`, `social`, `icon`, `graphic`, `image`

## API Endpoints

**Core endpoints:**
- `GET /api/photos` - List photos with filtering (category, format, search), pagination, sorting
- `GET /api/duplicates` - Get duplicate groups
- `GET /api/stats` - Database statistics
- `GET /api/categories` - List all unique categories
- `POST /api/open/{photo_id}` - Open photo in Finder
- `PATCH /api/photo/{photo_id}` - Update category, hide photo, or rename file
- `DELETE /api/photo/{photo_id}` - Remove from database (doesn't delete file)

**Configuration:**
- `GET /api/scan-config` - Get scan paths and exclusions
- `POST /api/scan-config` - Update scan configuration

## File Safety

- Scanner NEVER moves, modifies, or deletes original photos
- All operations are read-only except database writes
- File renames only happen via explicit API call (`PATCH /api/photo/{id}`)
- Deletion removes database entry only, not the actual file

## Development Notes

- FastAPI runs on port 3000 by default
- CORS enabled for Tauri app (`tauri://localhost`, `http://localhost:1420`)
- Logging configured in scanner for scan progress tracking
- Scanner processes ~10-20 photos/second depending on file sizes
- Subsequent scans are fast (skips already-indexed photos via UNIQUE constraint)
