# Photo Organizer Usage Guide

## ✅ Storage Location Tracking - NEW!

The scanner now clearly shows WHERE your photos are stored:

### Storage Types Detected:
- **Local HD** (Macintosh HD) - Photos on your main drive (`/Users/...`)
- **iCloud** (iCloud Drive) - Photos synced to iCloud
- **External Drive** - Photos on USB/SSD drives (`/Volumes/...`)

### Example Output:
```
📍 Storage Locations:
   Local HD (Macintosh HD): 1,234 photos, 15.6 GB
   iCloud (iCloud Drive): 456 photos, 8.2 GB
   External Drive (My Backup SSD): 789 photos, 45.3 GB
```

This helps you:
- Know where your photos actually are
- Identify photos on drives that might not always be connected
- See which storage is taking up space

## 🔄 Incremental Scanning (Smart Re-Scans!)

### **First Scan:**
```bash
python3 photo_scanner.py --scan ~
# Takes hours - scans EVERYTHING
```

### **Subsequent Scans:**
```bash
python3 photo_scanner.py --scan ~
# Fast - only indexes NEW photos!
```

### How It Works:
1. **Checks database first** - If photo path already exists, SKIPS it
2. **Only processes new files** - Dramatically faster
3. **Updates are safe** - Won't re-process thousands of photos

### What Gets Skipped:
- Photos already in database (by file path)
- Even if you stop mid-scan, it won't re-scan those photos

### What Gets Added:
- New photos since last scan
- Photos from newly connected external drives
- Photos moved to different locations

### Example Scenario:

**Monday - First Scan:**
```
Scanning ~/Pictures...
Found 10,000 photos
Processed 10,000 photos (12 hours)
```

**Tuesday - After Photoshoot:**
```
Scanning ~/Pictures...
Found 10,200 photos
Already indexed: 10,000
Processed 200 NEW photos (2 minutes!)
```

## 📁 Recommended Scan Strategy

### Option 1: Scan Everything Once
```bash
# Let it run overnight
nohup python3 photo_scanner.py --scan ~ > scan.log 2>&1 &

# Check progress
tail -f scan.log

# See results
python3 photo_scanner.py --stats
```

### Option 2: Scan Incrementally
```bash
# Day 1: Scan Pictures folder
python3 photo_scanner.py --scan ~/Pictures

# Day 2: Scan Downloads
python3 photo_scanner.py --scan ~/Downloads

# Day 3: Scan Documents
python3 photo_scanner.py --scan ~/Documents

# Combine all scans in one database!
```

### Option 3: External Drives
```bash
# Scan drive when connected
python3 photo_scanner.py --scan /Volumes/MyExternalDrive

# Stats will show:
#   External Drive (MyExternalDrive): X photos

# Re-scan when drive reconnected later
# Only NEW photos will be indexed!
```

## 🔍 Monitoring Long Scans

### Start Background Scan:
```bash
nohup python3 photo_scanner.py --scan ~ > scan.log 2>&1 &
```

### Monitor Progress (Live):
```bash
tail -f scan.log
```

### Check Stats While Scanning:
```bash
# Open new terminal
python3 photo_scanner.py --stats

# Shows current database state
# Even while scan is running!
```

### View in Browser While Scanning:
```bash
python3 server.py
# Open http://localhost:3000
# Browse photos already indexed
# Refresh to see new photos appear!
```

## 💡 Pro Tips

### Handling External Drives

**Problem:** External drive gets disconnected

**Solution:** Photos stay in database! You can still see them, just can't open them until drive reconnects.

### Handling iCloud Photos

**Problem:** iCloud photos aren't fully downloaded

**Solution:** Scanner will see placeholder files but may fail to generate thumbnails. That's okay - they'll still be indexed!

### Finding New Photos

```bash
# Before photoshoot
python3 photo_scanner.py --stats
# Total: 10,000 photos

# After photoshoot + import
python3 photo_scanner.py --scan ~/Pictures
# Processed 150 NEW photos

# View just the new ones
python3 server.py
# Sort by "Date Modified" to see newest first
```

### Full Re-Index (Rarely Needed)

If you want to start completely fresh:
```bash
# Backup old database
mv photos.db photos_backup.db

# Start fresh scan
python3 photo_scanner.py --scan ~
```

## 🎯 Common Workflows

### Workflow 1: Initial Setup
```bash
# 1. Install
pip3 install -r requirements.txt

# 2. Quick test
python3 photo_scanner.py --scan ~/Pictures

# 3. View results
python3 server.py
# Open localhost:3000

# 4. Full scan overnight
nohup python3 photo_scanner.py --scan ~ > scan.log 2>&1 &
```

### Workflow 2: Weekly Maintenance
```bash
# Quick re-scan for new photos
python3 photo_scanner.py --scan ~/Pictures

# Check duplicates
python3 photo_scanner.py --duplicates

# View in browser
python3 server.py
```

### Workflow 3: External Drive Backup
```bash
# Scan external drive
python3 photo_scanner.py --scan /Volumes/PhotoBackup

# Find duplicates between local and backup
python3 photo_scanner.py --duplicates

# Stats show both locations
python3 photo_scanner.py --stats
```

## ⚡ Performance Notes

**Scanning Speed:**
- ~10-20 photos/second (depends on file size)
- TIF files: slower (larger files to hash)
- JPG files: faster

**Thumbnail Generation:**
- First time: ~0.5-1 second per photo
- Subsequent views: instant (thumbnail cached)

**Database Updates:**
- Commits every 10 photos (won't lose progress)
- Can safely Ctrl+C anytime

**Memory Usage:**
- Very low (~100MB RAM)
- Database grows ~1KB per photo

---

**Questions?** Check README.md for more info!
