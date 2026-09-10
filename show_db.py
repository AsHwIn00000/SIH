"""Quick viewer for the HEXA SQLite database — run from d:\HEXA\HEXA"""
import sqlite3
import os

DB_PATH = os.path.join("data", "app.db")

if not os.path.exists(DB_PATH):
    print("ERROR: Database not found at", os.path.abspath(DB_PATH))
    exit(1)

print("Database:", os.path.abspath(DB_PATH))
print("Size:", round(os.path.getsize(DB_PATH) / 1024, 1), "KB")
print()

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# List all tables with row counts
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print(f"{'TABLE':<35} {'ROWS':>8}")
print("-" * 45)
for t in tables:
    name = t[0]
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
    except Exception:
        count = "?"
    print(f"  {name:<33} {count:>8}")

print()

# Show recent chat sessions
print("=" * 60)
print("RECENT CHAT SESSIONS (last 5)")
print("=" * 60)
try:
    rows = conn.execute("""
        SELECT id, name, model, message_count, created_at
        FROM sessions
        ORDER BY last_accessed DESC
        LIMIT 5
    """).fetchall()
    for r in rows:
        print(f"  ID:      {r['id']}")
        print(f"  Name:    {r['name']}")
        print(f"  Model:   {r['model']}")
        print(f"  Msgs:    {r['message_count']}")
        print(f"  Created: {r['created_at']}")
        print()
except Exception as e:
    print("  (no sessions yet or error:", e, ")")

# Show total messages
print("=" * 60)
print("CHAT MESSAGES")
print("=" * 60)
try:
    total = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
    user_msgs = conn.execute("SELECT COUNT(*) FROM chat_messages WHERE role='user'").fetchone()[0]
    ai_msgs = conn.execute("SELECT COUNT(*) FROM chat_messages WHERE role='assistant'").fetchone()[0]
    print(f"  Total messages  : {total}")
    print(f"  User messages   : {user_msgs}")
    print(f"  AI messages     : {ai_msgs}")
    print()

    print("  Last 3 messages:")
    last = conn.execute("""
        SELECT role, substr(content, 1, 120) as preview, timestamp
        FROM chat_messages ORDER BY timestamp DESC LIMIT 3
    """).fetchall()
    for m in last:
        print(f"    [{m['role'].upper()}] {m['timestamp']}")
        print(f"    {m['preview']}...")
        print()
except Exception as e:
    print("  (error:", e, ")")

# Show uploaded files
print("=" * 60)
print("UPLOADED FILES (from uploads.json)")
print("=" * 60)
import json
uploads_json = os.path.join("data", "uploads", "uploads.json")
if os.path.exists(uploads_json):
    with open(uploads_json) as f:
        uploads = json.load(f)
    entries = list(uploads.items()) if isinstance(uploads, dict) else uploads
    print(f"  Total uploads: {len(entries)}")
    for uid, info in list(entries)[-5:]:
        if isinstance(info, dict):
            print(f"  - {info.get('original_name', uid)} | {round(info.get('size',0)/1024,1)} KB | {info.get('uploaded_at','?')}")
else:
    print("  No uploads found")

conn.close()
print()
print("To open visually: download 'DB Browser for SQLite' from https://sqlitebrowser.org")
print("Then open: ", os.path.abspath(DB_PATH))
