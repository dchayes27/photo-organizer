# Photo Organizer - Tauri Mac App Guide

Your Photo Organizer is now a native Mac app built with Tauri! 🎉

## 🚀 Quick Start

### Development Mode (with hot-reload)

```bash
cd /Users/danielchayes/Workspace/photo-organizer/desktop
npm run tauri dev
```

This will:
- Open the app in a Tauri window
- Show a splash screen while the Python server starts  
- Automatically navigate to your photo gallery when ready
- Auto-reload when you make changes to Python or frontend code
- Kill the Python server when you close the app

### Build Production App

```bash
cd /Users/danielchayes/Workspace/photo-organizer/desktop
npm run tauri build
```

The final `.app` will be at:
```
desktop/src-tauri/target/release/bundle/macos/Photo Organizer.app
```

Drag it to your Applications folder and launch like any other Mac app!

## 📁 What Changed

**Nothing in your Python code!** The Tauri wrapper lives in the `desktop/` folder:

```
photo-organizer/
├── server.py              ← Unchanged!
├── photo_scanner.py       ← Unchanged!
├── static/                ← Unchanged!
├── photos.db              ← Unchanged!
│
└── desktop/               ← NEW
    ├── index.html         ← Splash screen
    ├── src/main.ts        ← Server startup logic
    └── src-tauri/
        └── tauri.conf.json  ← Config
```

## 🛠️ Development Workflow

You can still develop exactly as before:

### Option 1: Browser (Fastest)
```bash
python3 server.py
# Open http://localhost:3000
```

### Option 2: Tauri App
```bash
cd desktop
npm run tauri dev
```

Both work identically! Your Python code doesn't change.

## ✨ Adding Features

### File Operations (Delete/Move)

Add to `server.py`:

```python
from send2trash import send2trash

@app.post("/api/files/trash")
async def move_to_trash(photo_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()
    
    if row:
        send2trash(row["file_path"])
        cursor.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
        conn.commit()
    conn.close()
    return {"success": True}
```

Call from frontend (works in both browser and Tauri):
```javascript
await fetch('http://localhost:3000/api/files/trash', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({ photo_id: 123 })
});
```

## 🐛 Troubleshooting

**Server won't start:**
- Check Python path in `desktop/src-tauri/tauri.conf.json`
- Current: `/Users/danielchayes/.pyenv/versions/3.11.7/bin/python3`

**Port 3000 in use:**
```bash
lsof -i :3000
kill -9 <PID>
```

**See logs:**
Press Cmd+Option+I in dev mode to open DevTools

## 🎯 Key Benefits

- ✅ Native Mac app - no terminal needed
- ✅ Auto-starts/stops Python server
- ✅ Small (~5-10MB vs 50-100MB Electron)
- ✅ Fast (uses system WebKit)
- ✅ **Your Python code unchanged!**

---

Need more help? Check the detailed comments in `desktop/src/main.ts`!
