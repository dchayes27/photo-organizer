# 📸 Photo Scanning Guide

The photo scanner now **excludes heavily** to avoid scanning app data, system files, and internal photo library caches.

## ⚠️ What's Now Excluded:

- **Library/** - All system libraries (Messages, Caches, Developer, etc.)
- **Photos Library.photoslibrary** - macOS Photos app internal structure
- **.local/**, **.config/**, **.cache/** - Hidden app directories
- **node_modules/**, **vendor/**, **build/** - Development directories
- **Dropbox/**, **CloudStorage/** - Cloud sync folders (to avoid timeouts)
- All our generated files (thumbnails, waveforms)

## ✅ Recommended: Scan Specific Folders

Instead of scanning your entire home directory (`~`), scan specific known photo locations:

### Common Photo Locations:

```bash
# Desktop (quick test)
python3 photo_scanner.py --scan ~/Desktop

# Pictures folder (excluding Photos Library)
python3 photo_scanner.py --scan ~/Pictures

# Documents folder
python3 photo_scanner.py --scan ~/Documents

# Downloads folder
python3 photo_scanner.py --scan ~/Downloads

# Specific project folders
python3 photo_scanner.py --scan ~/Workspace/my-photo-project

# External drives
python3 photo_scanner.py --scan /Volumes/MyBackupDrive
```

### Scan Multiple Folders:

Run multiple scans - the scanner remembers what it's indexed:

```bash
# Scan Desktop
python3 photo_scanner.py --scan ~/Desktop

# Then scan Pictures
python3 photo_scanner.py --scan ~/Pictures

# Then scan Documents
python3 photo_scanner.py --scan ~/Documents

# Check what you have so far
python3 photo_scanner.py --stats
```

## 🔍 Finding Where Your Photos Are

Not sure where your photos are? Use these commands:

```bash
# Find directories with lots of photos (excluding system dirs)
find ~ -type f \( -name "*.jpg" -o -name "*.png" -o -name "*.tif" \) 2>/dev/null |
  grep -v Library |
  grep -v ".local" |
  grep -v ".config" |
  grep -v "node_modules" |
  xargs -n1 dirname |
  sort |
  uniq -c |
  sort -rn |
  head -20

# Or use Spotlight to find photo-heavy directories
mdfind "kMDItemKind == 'JPEG image'" |
  grep -v Library |
  xargs -n1 dirname |
  sort |
  uniq -c |
  sort -rn |
  head -20
```

## 🎯 Suggested Workflow:

1. **Start small** - Scan Desktop first to test:
   ```bash
   python3 photo_scanner.py --scan ~/Desktop
   python3 photo_scanner.py --stats
   python3 server.py  # Check results at http://localhost:3000
   ```

2. **Find your photo folders** - Use the find commands above

3. **Scan each known folder**:
   ```bash
   python3 photo_scanner.py --scan ~/Pictures
   python3 photo_scanner.py --scan ~/Documents/Photography
   python3 photo_scanner.py --scan /Volumes/ExternalDrive/Photos
   ```

4. **Check results** after each scan:
   ```bash
   python3 photo_scanner.py --stats
   ```

## 📊 What Gets Indexed:

- ✅ Your actual photo files (JPG, PNG, TIFF, RAW, HEIC, etc.)
- ✅ Photos in Desktop, Documents, Pictures (outside Photos Library)
- ✅ Photos on external drives
- ✅ Organized project folders

## ❌ What Gets Skipped:

- ❌ macOS Photos Library internal files (42,000+ cached duplicates)
- ❌ iMessage attachments in Library/Messages
- ❌ App data and caches
- ❌ Browser downloaded favicons/icons
- ❌ IDE/editor resources
- ❌ System thumbnails and previews
- ❌ Cloud storage sync folders (timeout prevention)

## 💡 Pro Tips:

- **Don't scan `~`** - Too broad, picks up everything
- **Scan specific folders** - Desktop, Documents, specific projects
- **Multiple scans are fine** - Scanner skips already-indexed files
- **Check stats often** - See what you're getting as you go
- **External drives** - Scan mounted volumes explicitly

## 🚀 Example Session:

```bash
# Test with Desktop
python3 photo_scanner.py --scan ~/Desktop
# Found 50 photos

# Add Pictures folder
python3 photo_scanner.py --scan ~/Pictures
# Found 200 more photos

# Add Documents
python3 photo_scanner.py --scan ~/Documents
# Found 100 more photos

# Check total
python3 photo_scanner.py --stats
# Total: 350 photos, 5 GB

# Scan external drive
python3 photo_scanner.py --scan /Volumes/Photos2023
# Found 5,000 more photos

# Final stats
python3 photo_scanner.py --stats
# Total: 5,350 photos, 75 GB
```

Now you have a curated photo library without app data!
