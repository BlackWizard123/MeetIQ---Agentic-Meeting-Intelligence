"""
Run once to fix existing history.json entries that have no project.
python fix_history.py
"""
import json, os, sys

DATA_DIR     = os.path.join(os.path.dirname(__file__), "data")
MEETINGS_DIR = os.path.join(DATA_DIR, "meetings")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

with open(HISTORY_FILE) as f:
    history = json.load(f)

fixed = 0
for item in history:
    if not item.get("project") or item["project"] == "Unknown Project":
        # Try to read the project from the full meeting JSON
        fp = os.path.join(MEETINGS_DIR, f"{item['id']}.json")
        if os.path.exists(fp):
            with open(fp) as f:
                record = json.load(f)
            proj = (record.get("memo") or {}).get("project", "")
            if proj and proj != "Unknown":
                item["project"] = proj
                fixed += 1
                print(f"  Fixed {item['id']}: {item['title']} → {proj}")

with open(HISTORY_FILE, "w") as f:
    json.dump(history, f, indent=2)

print(f"\n✅ Fixed {fixed} entries in history.json")
print("Note: entries with no project in memo will still show 'Unknown Project'")
print("Re-process those transcripts with a project selected to fix them properly.")