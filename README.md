# 🖼️ Photo Organizer

Find, organize, and manage all your photos in one place. Perfect for photographers with large TIF files scattered across your Mac.

## Features

- ✅ **Scan entire machine** for photos (TIF, JPG, PNG, HEIC, RAW, etc.)
- ✅ **Duplicate detection** using content hashing
- ✅ **Thumbnail generation** for fast browsing (even huge TIF files)
- ✅ **Web gallery** to browse and search
- ✅ **No file moving** - indexes photos where they are
- ✅ **Click to open** in Finder
- ✅ **Filter & search** by date, size, format

## Quick Start

### 1. Install Dependencies

```bash
cd /Users/danielchayes/Workspace/photo-organizer
pip3 install -r requirements.txt
```

### 2. Scan Your Photos

Scan your entire home directory:
```bash
python3 photo_scanner.py --scan ~
```

Or scan a specific folder:
```bash
python3 photo_scanner.py --scan ~/Pictures
```

This will:
- Find all image files
- Calculate hashes for duplicate detection
- Generate thumbnails
- Store metadata in SQLite database

**Note**: First scan can take a while depending on how many photos you have. It processes ~10-20 photos per second.

### 3. Start the Web Gallery

```bash
python3 server.py
```

Then open http://localhost:3000 in your browser!

## Usage

### Command Line

**Show statistics:**
```bash
python3 photo_scanner.py --stats
```

**List duplicates:**
```bash
python3 photo_scanner.py --duplicates
```

**Re-scan to find new photos:**
```bash
python3 photo_scanner.py --scan ~
```

### Web Gallery

The web interface lets you:
- Browse all photos as thumbnails
- Search by filename/path
- Sort by date, size, or dimensions
- View duplicates grouped together
- Click any photo to open it in Finder

## How It Works

### Scanner (`photo_scanner.py`)
1. Walks through directories finding image files
2. Skips system/cache directories automatically
3. Calculates SHA256 hash of each file for duplicate detection
4. Extracts EXIF metadata (dimensions, date taken)
5. Generates 300px thumbnails (JPEG, optimized)
6. Stores everything in SQLite database

### Web Server (`server.py`)
- FastAPI backend serving thumbnails and metadata
- Simple, clean web UI built with Tailwind CSS
- No React/build step needed - just open and browse

### Database Schema
```sql
photos (
    file_path,      -- Full path to original file
    file_hash,      -- SHA256 hash for duplicate detection
    file_size,      -- Size in bytes
    width, height,  -- Image dimensions
    format,         -- Image format (TIFF, JPEG, etc.)
    date_taken,     -- From EXIF if available
    date_modified,  -- File modification date
    thumbnail_path  -- Path to generated thumbnail
)
```

## Directory Structure

```
photo-organizer/
├── photo_scanner.py      # Scanner script
├── server.py             # Web server
├── photos.db             # SQLite database (created on first scan)
├── thumbnails/           # Generated thumbnails (created automatically)
├── static/
│   └── index.html        # Web gallery UI
└── requirements.txt      # Python dependencies
```

## Tips

**Large Collections:**
- First scan takes time but subsequent scans are fast
- Scanner skips already-indexed photos
- Database is indexed for fast queries

**Duplicate Detection:**
- Uses content hashing (not just filename)
- Catches exact duplicates even with different names
- Groups shown in "Show Duplicates" view

**File Safety:**
- Never moves or modifies your original photos
- Only creates read-only index and thumbnails
- Click "Open in Finder" to manage files

**Thumbnails:**
- Generated at 300px max dimension
- Stored as optimized JPEGs (~50-100KB each)
- Created only once, reused on subsequent visits

## Next Steps

Want to add:
- [ ] Tag/label photos
- [ ] Export duplicate list
- [ ] Bulk operations
- [ ] EXIF editor
- [ ] Electron app wrapper

## Troubleshooting

**"No photos found"**
- Check the directory you're scanning has images
- Check file permissions
- Try running with `sudo` if permission errors

**"Thumbnails not showing"**
- Check `thumbnails/` directory was created
- Verify Pillow is installed: `pip3 install Pillow`

**"Server won't start"**
- Check port 3000 is available
- Try different port: Edit `server.py` line with `port=3000`

---

Built Oct 6, 2024 for organizing photography workflow
