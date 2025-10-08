#!/usr/bin/env python3
"""
Photo Organizer Web Server
Browse, search, and manage your photo collection
"""

import json
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Photo Organizer")

# Add CORS middleware to allow Tauri app to access the API
# Only allow specific origins and methods for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",
        "http://localhost:1420",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Mount thumbnail directory
app.mount("/thumbnails", StaticFiles(directory="thumbnails"), name="thumbnails")
app.mount("/static", StaticFiles(directory="static"), name="static")

DB_PATH = "photos.db"
CONFIG_PATH = "scan_config.json"

# Pydantic models
class PhotoUpdate(BaseModel):
    category: str | None = None
    file_path: str | None = None
    hidden: bool | None = None

class ScanConfig(BaseModel):
    scan_paths: list[str]
    exclude_patterns: list[str]
    additional_excludes: list[str]

def get_db() -> sqlite3.Connection:
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/", response_class=HTMLResponse)
async def root() -> FileResponse | HTMLResponse:
    """Serve the main gallery page"""
    html_path = Path("static/index.html")
    if html_path.exists():
        return FileResponse(html_path)
    return HTMLResponse("<h1>Photo Organizer</h1><p>Run scanner first: python photo_scanner.py --scan ~</p>")

@app.get("/api/stats")
async def get_stats() -> dict[str, Any]:
    """Get database statistics"""
    conn = get_db()
    cursor = conn.cursor()

    # Total photos
    cursor.execute("SELECT COUNT(*) FROM photos")
    total = cursor.fetchone()[0]

    # Total size
    cursor.execute("SELECT SUM(file_size) FROM photos")
    total_size = cursor.fetchone()[0] or 0

    # Duplicates
    cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT file_hash, file_size, COUNT(*) as count
            FROM photos
            GROUP BY file_hash, file_size
            HAVING count > 1
        )
    """)
    duplicate_groups = cursor.fetchone()[0]

    # Format breakdown
    cursor.execute("""
        SELECT format, COUNT(*) as count
        FROM photos
        GROUP BY format
        ORDER BY count DESC
    """)
    formats = [{"format": row[0], "count": row[1]} for row in cursor.fetchall()]

    conn.close()

    return {
        "total": total,
        "total_size_gb": round(total_size / (1024**3), 2),
        "duplicate_groups": duplicate_groups,
        "formats": formats
    }

@app.get("/api/photos")
async def get_photos(
    limit: int = 100,
    offset: int = 0,
    format: str | None = None,
    category: str | None = None,
    search: str | None = None,
    sort_by: str = "date_modified",
    order: str = "DESC",
    show_hidden: bool = False
) -> dict[str, Any]:
    """Get photos with filtering and pagination"""
    # Validate pagination parameters
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 1000")
    if offset < 0:
        raise HTTPException(status_code=400, detail="Offset must be non-negative")

    # Validate and sanitize search input
    if search and len(search) > 500:
        raise HTTPException(status_code=400, detail="Search query too long (max 500 characters)")

    conn = get_db()
    cursor = conn.cursor()

    # Build query
    where_clauses = []
    params = []

    # Hide hidden photos by default
    if not show_hidden:
        where_clauses.append("(hidden = 0 OR hidden IS NULL)")

    if format:
        # Sanitize format input
        format_clean = format.strip()
        if format_clean:
            where_clauses.append("format = ?")
            params.append(format_clean)

    if category:
        # Sanitize category input
        category_clean = category.strip()
        if category_clean:
            where_clauses.append("category = ?")
            params.append(category_clean)

    if search:
        # Sanitize search input
        search_clean = search.strip()
        if search_clean:
            where_clauses.append("file_path LIKE ?")
            params.append(f"%{search_clean}%")

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Valid sort columns (whitelist to prevent SQL injection)
    valid_sorts = ["date_modified", "date_taken", "file_size", "width", "height"]
    if sort_by not in valid_sorts:
        sort_by = "date_modified"

    # Validate order direction
    order = "DESC" if order.upper() == "DESC" else "ASC"

    # Get total count
    cursor.execute(f"SELECT COUNT(*) FROM photos WHERE {where_sql}", params)
    total = cursor.fetchone()[0]

    # Get photos
    query = f"""
        SELECT id, file_path, file_hash, file_size, width, height, format,
               date_taken, date_modified, thumbnail_path, category, hidden
        FROM photos
        WHERE {where_sql}
        ORDER BY {sort_by} {order}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    cursor.execute(query, params)
    photos = []
    for row in cursor.fetchall():
        photos.append({
            "id": row["id"],
            "path": row["file_path"],
            "hash": row["file_hash"],
            "size": row["file_size"],
            "size_mb": round(row["file_size"] / (1024**2), 2),
            "width": row["width"],
            "height": row["height"],
            "format": row["format"],
            "date_taken": row["date_taken"],
            "date_modified": row["date_modified"],
            "thumbnail": f"/thumbnails/{Path(row['thumbnail_path']).name}" if row["thumbnail_path"] else None,
            "category": row["category"],
            "hidden": bool(row["hidden"]) if row["hidden"] else False
        })

    conn.close()

    return {
        "photos": photos,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@app.get("/api/duplicates")
async def get_duplicates() -> dict[str, list[dict[str, Any]]]:
    """Get all duplicate photo groups"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file_hash, file_size, COUNT(*) as count
        FROM photos
        GROUP BY file_hash, file_size
        HAVING count > 1
        ORDER BY file_size DESC
    """)

    duplicate_groups = []
    for row in cursor.fetchall():
        file_hash, file_size, count = row["file_hash"], row["file_size"], row["count"]

        # Get all photos in this group
        cursor.execute("""
            SELECT id, file_path, thumbnail_path, date_modified
            FROM photos
            WHERE file_hash = ? AND file_size = ?
            ORDER BY date_modified
        """, (file_hash, file_size))

        photos = []
        for photo_row in cursor.fetchall():
            photos.append({
                "id": photo_row["id"],
                "path": photo_row["file_path"],
                "thumbnail": f"/thumbnails/{Path(photo_row['thumbnail_path']).name}" if photo_row["thumbnail_path"] else None,
                "date_modified": photo_row["date_modified"]
            })

        duplicate_groups.append({
            "hash": file_hash,
            "size": file_size,
            "size_mb": round(file_size / (1024**2), 2),
            "count": count,
            "photos": photos
        })

    conn.close()

    return {"duplicates": duplicate_groups}

@app.post("/api/open/{photo_id}")
async def open_photo(photo_id: int) -> dict[str, Any]:
    """Open photo in Finder"""
    # Validate photo ID
    if photo_id < 1:
        raise HTTPException(status_code=400, detail="Invalid photo ID")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT file_path FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")

    file_path = row["file_path"]

    # Validate file still exists
    if not Path(file_path).exists():
        raise HTTPException(status_code=404, detail=f"File no longer exists: {file_path}")

    # Open in Finder (macOS) - check platform first
    import sys
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", file_path], check=True, timeout=5)
        elif sys.platform == "win32":
            subprocess.run(["explorer", "/select,", file_path], check=True, timeout=5)
        else:  # Linux and others
            subprocess.run(["xdg-open", Path(file_path).parent], check=True, timeout=5)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="File manager command timed out") from None
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to open file manager: {e}") from e
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="File manager not found on this system") from None

    return {"success": True, "path": file_path}

@app.delete("/api/photo/{photo_id}")
async def delete_photo(photo_id: int) -> dict[str, Any]:
    """Remove photo from database (doesn't delete file)"""
    # Validate photo ID
    if photo_id < 1:
        raise HTTPException(status_code=400, detail="Invalid photo ID")

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
        deleted = cursor.rowcount
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e
    finally:
        conn.close()

    if deleted:
        return {"success": True, "message": f"Photo {photo_id} removed from index"}
    else:
        raise HTTPException(status_code=404, detail="Photo not found")

@app.get("/api/photo/{photo_id}")
async def get_photo_details(photo_id: int) -> dict[str, Any]:
    """Get detailed information for a single photo"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, file_path, file_hash, file_size, width, height, format,
               date_taken, date_modified, thumbnail_path, category, storage_location, volume_name, hidden
        FROM photos
        WHERE id = ?
    """, (photo_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")

    return {
        "id": row["id"],
        "path": row["file_path"],
        "hash": row["file_hash"],
        "size": row["file_size"],
        "size_mb": round(row["file_size"] / (1024**2), 2),
        "width": row["width"],
        "height": row["height"],
        "format": row["format"],
        "date_taken": row["date_taken"],
        "date_modified": row["date_modified"],
        "thumbnail": f"/thumbnails/{Path(row['thumbnail_path']).name}" if row["thumbnail_path"] else None,
        "category": row["category"],
        "storage_location": row["storage_location"],
        "volume_name": row["volume_name"],
        "hidden": bool(row["hidden"]) if row["hidden"] else False
    }

@app.patch("/api/photo/{photo_id}")
async def update_photo(photo_id: int, update: PhotoUpdate) -> dict[str, Any]:
    """Update photo metadata"""
    # Validate photo ID
    if photo_id < 1:
        raise HTTPException(status_code=400, detail="Invalid photo ID")

    # Validate category length if provided
    if update.category and len(update.category) > 100:
        raise HTTPException(status_code=400, detail="Category name too long (max 100 characters)")

    # Validate file path if provided
    if update.file_path and len(update.file_path) > 1000:
        raise HTTPException(status_code=400, detail="File path too long (max 1000 characters)")

    conn = get_db()
    cursor = conn.cursor()

    # Get current photo info
    cursor.execute("SELECT file_path, category FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Photo not found")

    old_path = row["file_path"]
    updates = {}

    # Handle category update
    if update.category is not None:
        category_clean = update.category.strip() if update.category else None
        updates["category"] = category_clean

    # Handle hidden flag update
    if update.hidden is not None:
        updates["hidden"] = 1 if update.hidden else 0

    # Handle file rename
    if update.file_path and update.file_path != old_path:
        old_file = Path(old_path)
        new_file = Path(update.file_path)

        # Validate new path
        if new_file.exists():
            conn.close()
            raise HTTPException(status_code=400, detail="File already exists at new path")

        # Rename the actual file
        try:
            old_file.rename(new_file)
            updates["file_path"] = str(new_file)
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=500, detail=f"Failed to rename file: {str(e)}") from e

    # Update database
    if updates:
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [photo_id]
        cursor.execute(f"UPDATE photos SET {set_clause} WHERE id = ?", values)
        conn.commit()

    conn.close()
    return {"success": True, "message": "Photo updated", "updates": updates}

@app.get("/api/categories")
async def get_categories() -> dict[str, list[str]]:
    """Get list of all unique categories"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT category
        FROM photos
        WHERE category IS NOT NULL
        ORDER BY category
    """)

    categories = [row["category"] for row in cursor.fetchall()]
    conn.close()

    return {"categories": categories}

@app.get("/api/scan-config")
async def get_scan_config() -> dict[str, Any]:
    """Get scan configuration"""
    if not os.path.exists(CONFIG_PATH):
        # Return default config
        return {
            "scan_paths": ["~/Desktop", "~/Documents", "~/Pictures"],
            "exclude_patterns": [],
            "additional_excludes": []
        }

    with open(CONFIG_PATH) as f:
        config = json.load(f)
    return config

@app.post("/api/scan-config")
async def update_scan_config(config: ScanConfig) -> dict[str, Any]:
    """Update scan configuration"""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config.dict(), f, indent=2)
    return {"success": True, "message": "Scan configuration updated"}


if __name__ == "__main__":
    print("""
    🖼️  Photo Organizer Server
    ========================
    Starting server at http://localhost:3000

    First time? Run the scanner:
      python photo_scanner.py --scan ~

    """)
    uvicorn.run(app, host="0.0.0.0", port=3000)
