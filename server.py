#!/usr/bin/env python3
"""
Photo Organizer Web Server
Browse, search, and manage your photo collection
"""

import sqlite3
import subprocess
import os
import shutil
import json
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Photo Organizer")

# Add CORS middleware to allow Tauri app to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["tauri://localhost", "http://localhost:1420", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount thumbnail directory
app.mount("/thumbnails", StaticFiles(directory="thumbnails"), name="thumbnails")
app.mount("/static", StaticFiles(directory="static"), name="static")

DB_PATH = "photos.db"
CONFIG_PATH = "scan_config.json"

# Pydantic models
class PhotoUpdate(BaseModel):
    category: Optional[str] = None
    file_path: Optional[str] = None
    hidden: Optional[bool] = None

class ScanConfig(BaseModel):
    scan_paths: List[str]
    exclude_patterns: List[str]
    additional_excludes: List[str]

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main gallery page"""
    html_path = Path("static/index.html")
    if html_path.exists():
        return FileResponse(html_path)
    return HTMLResponse("<h1>Photo Organizer</h1><p>Run scanner first: python photo_scanner.py --scan ~</p>")

@app.get("/api/stats")
async def get_stats():
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
    format: str = None,
    category: str = None,
    search: str = None,
    sort_by: str = "date_modified",
    order: str = "DESC",
    show_hidden: bool = False
):
    """Get photos with filtering and pagination"""
    conn = get_db()
    cursor = conn.cursor()

    # Build query
    where_clauses = []
    params = []

    # Hide hidden photos by default
    if not show_hidden:
        where_clauses.append("(hidden = 0 OR hidden IS NULL)")

    if format:
        where_clauses.append("format = ?")
        params.append(format)

    if category:
        where_clauses.append("category = ?")
        params.append(category)

    if search:
        where_clauses.append("file_path LIKE ?")
        params.append(f"%{search}%")

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Valid sort columns
    valid_sorts = ["date_modified", "date_taken", "file_size", "width", "height"]
    if sort_by not in valid_sorts:
        sort_by = "date_modified"

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
async def get_duplicates():
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
async def open_photo(photo_id: int):
    """Open photo in Finder"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT file_path FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")

    file_path = row["file_path"]

    # Open in Finder (macOS)
    subprocess.run(["open", "-R", file_path])

    return {"success": True, "path": file_path}

@app.delete("/api/photo/{photo_id}")
async def delete_photo(photo_id: int):
    """Remove photo from database (doesn't delete file)"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted:
        return {"success": True, "message": f"Photo {photo_id} removed from index"}
    else:
        raise HTTPException(status_code=404, detail="Photo not found")

@app.get("/api/photo/{photo_id}")
async def get_photo_details(photo_id: int):
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
async def update_photo(photo_id: int, update: PhotoUpdate):
    """Update photo metadata"""
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
        updates["category"] = update.category

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
            raise HTTPException(status_code=500, detail=f"Failed to rename file: {str(e)}")

    # Update database
    if updates:
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [photo_id]
        cursor.execute(f"UPDATE photos SET {set_clause} WHERE id = ?", values)
        conn.commit()

    conn.close()
    return {"success": True, "message": "Photo updated", "updates": updates}

@app.get("/api/categories")
async def get_categories():
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
async def get_scan_config():
    """Get scan configuration"""
    if not os.path.exists(CONFIG_PATH):
        # Return default config
        return {
            "scan_paths": ["~/Desktop", "~/Documents", "~/Pictures"],
            "exclude_patterns": [],
            "additional_excludes": []
        }

    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    return config

@app.post("/api/scan-config")
async def update_scan_config(config: ScanConfig):
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
