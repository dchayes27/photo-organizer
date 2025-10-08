#!/usr/bin/env python3
"""
Photo Organizer - Scan and index all photos on your Mac
Finds duplicates, generates thumbnails, provides searchable interface
"""

import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Image extensions to scan
IMAGE_EXTENSIONS = {
    # Standard formats
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.avif',
    # TIFF formats (tif and tiff are the same, different extensions)
    '.tif', '.tiff',
    # Apple/Mobile
    '.heic', '.heif',
    # RAW formats - Canon
    '.cr2', '.cr3', '.crw',
    # RAW formats - Nikon
    '.nef', '.nrw',
    # RAW formats - Sony
    '.arw', '.srf', '.sr2',
    # RAW formats - Other manufacturers
    '.dng',  # Adobe Digital Negative (universal)
    '.orf',  # Olympus
    '.rw2',  # Panasonic
    '.pef',  # Pentax
    '.raf',  # Fujifilm
    '.raw',  # Generic RAW
    '.rwl',  # Leica
    '.mrw',  # Minolta
    '.dcr',  # Kodak
    '.kdc',  # Kodak
    '.erf',  # Epson
    '.mef',  # Mamiya
    '.mos',  # Leaf
    '.x3f',  # Sigma
}

# Directories to skip (system and app dirs)
SKIP_DIRS = {
    # System directories
    'Library',  # Skip ALL Library folders (Messages, Caches, Application Support, Developer, etc.)
    'System',
    'private',
    '.Trash',

    # Cloud storage (causes timeouts)
    'Library/CloudStorage',
    'Dropbox',
    'dropboxa',

    # Photos app library (contains internal cached duplicates)
    'Photos Library.photoslibrary',
    '.photoslibrary',

    # Development directories
    'node_modules',
    '.git',
    '.vscode',
    '.cursor',
    'vendor',
    'build',
    'dist',
    '__pycache__',
    '.pytest_cache',

    # Hidden app directories
    '.local',
    '.config',
    '.cache',
    '.npm',
    '.nvm',
    '.pyenv',
    '.conda',

    # Our own generated files
    'thumbnails',  # Don't scan our own thumbnails!
    'waveforms',  # Don't scan audio waveform images!
}

class PhotoOrganizer:
    def __init__(
        self,
        db_path: str = 'photos.db',
        thumbnail_dir: str = 'thumbnails',
        config_path: str = 'scan_config.json'
    ) -> None:
        self.db_path: str = db_path
        self.thumbnail_dir: Path = Path(thumbnail_dir)
        self.thumbnail_dir.mkdir(exist_ok=True)
        self.config_path: str = config_path
        self.exclude_patterns: set[str] = set()
        self.load_config()
        self.init_database()

    def load_config(self) -> None:
        """Load scan configuration from JSON file"""
        if os.path.exists(self.config_path):
            with open(self.config_path) as f:
                config: dict[str, Any] = json.load(f)
                self.exclude_patterns = set(config.get('exclude_patterns', [])) | set(
                    config.get('additional_excludes', [])
                )
        else:
            # Fall back to hardcoded SKIP_DIRS
            self.exclude_patterns = SKIP_DIRS
        logger.info(f"Loaded {len(self.exclude_patterns)} exclude patterns")

    def init_database(self) -> None:
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                storage_location TEXT,
                volume_name TEXT,
                width INTEGER,
                height INTEGER,
                format TEXT,
                date_taken TIMESTAMP,
                date_modified TIMESTAMP,
                thumbnail_path TEXT,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index for fast duplicate detection
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON photos(file_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_date_taken ON photos(date_taken)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_size ON photos(file_size)")

        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

    def calculate_hash(self, file_path: Path, chunk_size: int = 8192) -> str | None:
        """Calculate SHA256 hash of file"""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error hashing {file_path}: {e}")
            return None

    def generate_thumbnail(self, image_path: Path, max_size: int = 300) -> str | None:
        """Generate thumbnail for image"""
        try:
            # Create thumbnail filename based on hash
            file_hash = self.calculate_hash(image_path)
            if not file_hash:
                return None

            thumb_name = f"{file_hash[:16]}.jpg"
            thumb_path = self.thumbnail_dir / thumb_name

            # Skip if thumbnail already exists
            if thumb_path.exists():
                return str(thumb_path)

            # Open and resize image
            with Image.open(image_path) as img:
                # Convert to RGB if needed (handles RGBA, L, etc.)
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')

                # Calculate thumbnail size maintaining aspect ratio
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                # Save thumbnail
                img.save(thumb_path, 'JPEG', quality=85, optimize=True)
                logger.debug(f"Generated thumbnail: {thumb_path}")
                return str(thumb_path)

        except Exception as e:
            logger.error(f"Error generating thumbnail for {image_path}: {e}")
            return None

    def extract_metadata(self, image_path: Path) -> dict[str, Any] | None:
        """Extract image metadata"""
        try:
            with Image.open(image_path) as img:
                # Get EXIF data if available
                exif = img.getexif()
                date_taken: datetime | None = None

                if exif:
                    # Try to get DateTimeOriginal (tag 36867)
                    date_taken_str = exif.get(36867)
                    if date_taken_str:
                        try:
                            date_taken = datetime.strptime(date_taken_str, '%Y:%m:%d %H:%M:%S')
                        except Exception:
                            pass

                return {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'date_taken': date_taken
                }
        except Exception as e:
            logger.error(f"Error extracting metadata from {image_path}: {e}")
            return None

    def detect_storage_location(self, file_path: Path) -> tuple[str, str]:
        """Detect where the file is stored"""
        path_str = str(file_path)

        # External drives (mounted volumes)
        if path_str.startswith('/Volumes/'):
            volume_name = path_str.split('/')[2] if len(path_str.split('/')) > 2 else 'Unknown'
            return 'External Drive', volume_name

        # iCloud Drive
        if 'Library/Mobile Documents' in path_str or 'iCloud' in path_str:
            return 'iCloud', 'iCloud Drive'

        # Local HD (main system drive)
        if path_str.startswith('/Users/'):
            return 'Local HD', 'Macintosh HD'

        # Other locations
        return 'Other', 'System'

    def categorize_photo(
        self,
        file_path: Path,
        width: int | None = None,
        height: int | None = None,
        date_taken: datetime | None = None
    ) -> str:
        """Categorize photo based on filename, dimensions, and metadata"""
        filename = file_path.name.lower()

        # Screenshot detection
        screenshot_patterns = [
            'screenshot', 'screen shot', 'screen_shot',
            'scr_', 'capture', 'screen capture',
            'shot_', 'snap_'
        ]
        if any(pattern in filename for pattern in screenshot_patterns):
            return 'screenshot'

        # Check for common screen resolutions (screenshots)
        if width and height:
            common_screen_resolutions = [
                (1920, 1080), (2560, 1440), (3840, 2160),  # 16:9
                (1920, 1200), (2560, 1600),  # 16:10
                (1440, 900), (1680, 1050),   # 16:10
                (2880, 1800), (3456, 2234),  # Retina
                (1366, 768), (1280, 720)     # Common laptop
            ]
            # Allow small variance for screenshots with status bars
            for screen_w, screen_h in common_screen_resolutions:
                if abs(width - screen_w) < 50 and abs(height - screen_h) < 50:
                    return 'screenshot'

        # Wallpaper/background detection
        wallpaper_patterns = ['wallpaper', 'background', 'bg_', 'desktop']
        if any(pattern in filename for pattern in wallpaper_patterns):
            return 'wallpaper'

        # Large high-res images with common wallpaper aspect ratios
        if width and height and width >= 1920:
            aspect_ratio = width / height
            # Common wallpaper ratios: 16:9, 16:10, 21:9
            if 1.7 < aspect_ratio < 2.4:  # Wide wallpapers
                if width >= 2560:  # High res wallpaper
                    return 'wallpaper'

        # Photo detection (has EXIF date_taken, common photo aspect ratios)
        if date_taken:
            if width and height:
                aspect_ratio = width / height
                # Typical camera ratios: 3:2, 4:3, 16:9
                if 1.3 < aspect_ratio < 1.8 or 0.55 < aspect_ratio < 0.77:  # Include portrait
                    return 'photo'
            return 'photo'  # Has camera metadata

        # Social/meme detection (square or Instagram-like ratios)
        if width and height:
            aspect_ratio = width / height
            # Square or near-square
            if 0.95 < aspect_ratio < 1.05:
                if width >= 400:  # Not an icon
                    return 'social'

        # Icon detection (very small)
        if width and height and width <= 512 and height <= 512:
            if width == height:  # Square icons
                return 'icon'

        # Graphic/design detection
        if file_path.suffix.lower() in ['.png', '.gif', '.svg']:
            if 'logo' in filename or 'icon' in filename or 'badge' in filename:
                return 'graphic'

        # Default to 'image' if can't categorize
        return 'image'

    def should_skip_directory(self, dir_path: Path) -> bool:
        """Check if directory should be skipped"""
        dir_str = str(dir_path)
        return any(skip_dir in dir_str for skip_dir in self.exclude_patterns)

    def scan_directory(self, root_dir: str, max_depth: int = 10) -> None:
        """Scan directory for images"""
        root_path = Path(root_dir).expanduser()
        logger.info(f"Scanning {root_path}...")

        found_count = 0
        processed_count = 0
        duplicate_count = 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Use os.walk instead of glob to skip directories during traversal
        for dirpath, dirnames, filenames in os.walk(root_path, topdown=True):
            # Skip excluded directories (modifying dirnames in-place skips them)
            dirnames[:] = [d for d in dirnames if not self.should_skip_directory(Path(dirpath) / d)]

            for filename in filenames:
                file_path = Path(dirpath) / filename

                # Skip if wrong extension
                if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue

                found_count += 1

                # Check if already indexed
                cursor.execute("SELECT id FROM photos WHERE file_path = ?", (str(file_path),))
                if cursor.fetchone():
                    continue

                # Calculate hash
                file_hash = self.calculate_hash(file_path)
                if not file_hash:
                    continue

                # Get file stats
                stat = file_path.stat()
                file_size = stat.st_size
                date_modified = datetime.fromtimestamp(stat.st_mtime)

                # Check for duplicate by hash and size
                cursor.execute(
                    "SELECT file_path FROM photos WHERE file_hash = ? AND file_size = ?",
                    (file_hash, file_size)
                )
                existing = cursor.fetchone()

                # Extract metadata
                metadata = self.extract_metadata(file_path)

                # Detect storage location
                storage_location, volume_name = self.detect_storage_location(file_path)

                # Categorize photo
                category = self.categorize_photo(
                    file_path,
                    width=metadata['width'] if metadata else None,
                    height=metadata['height'] if metadata else None,
                    date_taken=metadata['date_taken'] if metadata else None
                )

                # Generate thumbnail (reuse existing if duplicate)
                thumbnail_path = self.generate_thumbnail(file_path)

                # Always insert (stores all file locations, even duplicates)
                # The UNIQUE constraint on file_path prevents re-scanning same file
                try:
                    cursor.execute("""
                        INSERT INTO photos
                        (file_path, file_hash, file_size, storage_location, volume_name, width, height, format, date_taken, date_modified, thumbnail_path, category)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(file_path),
                        file_hash,
                        file_size,
                        storage_location,
                        volume_name,
                        metadata['width'] if metadata else None,
                        metadata['height'] if metadata else None,
                        metadata['format'] if metadata else None,
                        metadata['date_taken'] if metadata else None,
                        date_modified,
                        thumbnail_path,
                        category
                    ))

                    # Log duplicate after successful insert
                    if existing:
                        duplicate_count += 1
                        logger.info(f"DUPLICATE: {file_path} (same content as {existing[0]})")

                    processed_count += 1

                except sqlite3.IntegrityError:
                    # File path already exists, skip
                    logger.debug(f"Already indexed: {file_path}")

                if processed_count % 10 == 0:
                    conn.commit()
                    logger.info(f"Processed {processed_count} photos (found {found_count}, {duplicate_count} duplicates) - Last: {storage_location}/{volume_name}")

        conn.commit()
        conn.close()

        logger.info("✅ Scan complete!")
        logger.info(f"   Found: {found_count} images")
        logger.info(f"   Indexed: {processed_count} new photos")
        logger.info(f"   Duplicates: {duplicate_count}")

    def get_stats(self) -> dict[str, Any]:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
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
        formats = cursor.fetchall()

        # Storage location breakdown
        cursor.execute("""
            SELECT storage_location, volume_name, COUNT(*) as count, SUM(file_size) as size
            FROM photos
            GROUP BY storage_location, volume_name
            ORDER BY count DESC
        """)
        storage_locations = cursor.fetchall()

        conn.close()

        return {
            'total': total,
            'total_size_gb': total_size / (1024**3),
            'duplicate_groups': duplicate_groups,
            'formats': formats,
            'storage_locations': storage_locations
        }

    def find_duplicates(self) -> list[dict[str, Any]]:
        """Find all duplicate photos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT file_hash, file_size, GROUP_CONCAT(file_path, '|||') as paths, COUNT(*) as count
            FROM photos
            GROUP BY file_hash, file_size
            HAVING count > 1
            ORDER BY file_size DESC
        """)

        duplicates = []
        for row in cursor.fetchall():
            file_hash, file_size, paths, count = row
            paths_list = paths.split('|||')
            duplicates.append({
                'hash': file_hash,
                'size': file_size,
                'size_mb': file_size / (1024**2),
                'count': count,
                'paths': paths_list
            })

        conn.close()
        return duplicates


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Photo Organizer - Scan and index photos')
    parser.add_argument('--scan', type=str, help='Directory to scan (default: ~)')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--duplicates', action='store_true', help='List duplicate photos')
    parser.add_argument('--categorize', action='store_true', help='Categorize all existing photos')

    args = parser.parse_args()

    organizer = PhotoOrganizer()

    if args.categorize:
        print("\n📸 Categorizing all photos...")
        print("   (Analyzing filename patterns, dimensions, and metadata)")
        conn = sqlite3.connect(organizer.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_path, width, height, date_taken FROM photos")
        rows = cursor.fetchall()

        categorized = 0
        categories_count = {}

        for row in rows:
            photo_id, file_path, width, height, date_taken = row

            # Categorize
            category = organizer.categorize_photo(
                Path(file_path),
                width=width,
                height=height,
                date_taken=date_taken
            )

            cursor.execute("UPDATE photos SET category = ? WHERE id = ?", (category, photo_id))
            categorized += 1

            # Count categories
            categories_count[category] = categories_count.get(category, 0) + 1

            if categorized % 100 == 0:
                conn.commit()
                print(f"   Categorized {categorized} photos...")

        conn.commit()
        conn.close()

        print(f"\n✅ Categorized {categorized} photos!")
        print("\n📊 Category Breakdown:")
        for category, count in sorted(categories_count.items(), key=lambda x: x[1], reverse=True):
            print(f"   {category}: {count:,} photos")

    elif args.stats:
        stats = organizer.get_stats()
        print("\n📊 Photo Database Statistics:")
        print(f"   Total photos: {stats['total']:,}")
        print(f"   Total size: {stats['total_size_gb']:.2f} GB")
        print(f"   Duplicate groups: {stats['duplicate_groups']}")

        print("\n   📍 Storage Locations:")
        for location, volume, count, size in stats['storage_locations']:
            size_gb = size / (1024**3) if size else 0
            print(f"      {location} ({volume}): {count:,} photos, {size_gb:.2f} GB")

        print("\n   Formats:")
        for fmt, count in stats['formats']:
            print(f"      {fmt}: {count:,}")

    elif args.duplicates:
        duplicates = organizer.find_duplicates()
        print(f"\n🔄 Found {len(duplicates)} duplicate groups:")
        for dup in duplicates:
            print(f"\n   {dup['count']} copies ({dup['size_mb']:.1f} MB each):")
            for path in dup['paths']:
                print(f"      - {path}")

    elif args.scan:
        organizer.scan_directory(args.scan)

    else:
        print("Photo Organizer")
        print("Usage:")
        print("  python photo_scanner.py --scan ~        # Scan home directory")
        print("  python photo_scanner.py --stats         # Show statistics")
        print("  python photo_scanner.py --duplicates    # List duplicates")
