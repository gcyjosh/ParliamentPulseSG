"""
One-off script to add source_url and year to existing hansard_full.json.
Run this ONCE before re-running summarise.py.

Usage:
  cd ~/Desktop/simple-parliament-v4
  /opt/homebrew/bin/python3 add_fields.py
"""
import json

INPUT  = "data/hansard_full.json"
OUTPUT = "data/hansard_full.json"  # overwrites in place

with open(INPUT) as f:
    records = json.load(f)

updated = 0
for record in records:
    # Add source_url from reportId
    report_id = record.get("reportId", "").rstrip("#")
    if report_id and "source_url" not in record:
        record["source_url"] = f"https://sprs.parl.gov.sg/search/#/topic?reportid={report_id}"
        updated += 1
    elif not report_id:
        record["source_url"] = ""

    # Add year from date string e.g. "25-2-2026" → 2026
    date = record.get("date", "")
    if date and "year" not in record:
        try:
            record["year"] = int(date.split("-")[2])
        except:
            record["year"] = None

with open(OUTPUT, "w") as f:
    json.dump(records, f, indent=2, ensure_ascii=False)

print(f"Done. Added source_url + year to {updated} records.")
print(f"Saved to {OUTPUT}")
