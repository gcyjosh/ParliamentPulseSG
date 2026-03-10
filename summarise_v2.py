import json
import os
import time
import requests
from datetime import datetime

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

INPUT_FILE  = "data/hansard_full.json"
OUTPUT_FILE = "output/summaries.html"
JSON_OUTPUT = "data/summaries.json"
API_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")

HEADERS = {
    "x-api-key": API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}

CONCERNS = [
    "Cost of Living", "Housing & HDB", "Healthcare", "Jobs & Retrenchment",
    "Education", "Mental Health", "Public Transport", "Climate & Environment",
    "Aging & Elderly", "Immigration & Foreign Workers", "Income Inequality",
    "Scams & Cybersecurity", "CPF & Retirement", "Racial Harmony",
    "Youth, Families & Childcare", "Crime & Safety", "Free Speech & POFMA",
    "Inflation & Prices",
]

# ─────────────────────────────────────────
# CLASSIFY + SUMMARISE
# ─────────────────────────────────────────

def classify_and_summarise(record):
    text = record.get("text", "").strip()
    if not text:
        return [], "No speech text available."

    if len(text) > 12000:
        text = text[:12000] + "..."

    concerns_list = "\n".join(f"- {c}" for c in CONCERNS)

    prompt = f"""You are analysing a Singapore Parliament speech for a political literacy website aimed at young Singaporeans.

Title: {record.get('title', '')}
Date: {record.get('date', '')}

Speech:
{text}

Do two things:

1. CLASSIFY: Which of these 18 public concerns does this speech relate to? Pick ALL that apply:
{concerns_list}

2. SUMMARISE: Write ONE paragraph of UNDER 100 WORDS in plain English. Cover what was discussed, the government's position, and how it affects ordinary Singaporeans. No bullet points, no headers.

Respond in this exact JSON format and nothing else:
{{
  "concerns": ["Concern 1", "Concern 2"],
  "summary": "Your summary here."
}}"""

    body = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        resp = requests.post("https://api.anthropic.com/v1/messages",
            headers=HEADERS, json=body, timeout=60)
        if resp.status_code != 200:
            print(f"  API ERROR {resp.status_code}: {resp.text[:200]}")
            return [record.get("concern_keyword", "Cost of Living")], "API error."
        raw = resp.json()["content"][0]["text"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)
        concerns = [c for c in parsed.get("concerns", []) if c in CONCERNS]
        summary  = parsed.get("summary", "").strip()
        if not concerns:
            concerns = [record.get("concern_keyword", "Cost of Living")]
        if not summary:
            summary = "Summary unavailable."
        return concerns, summary
    except json.JSONDecodeError:
        return [record.get("concern_keyword", "Cost of Living")], "Summary unavailable."
    except requests.exceptions.Timeout:
        return [record.get("concern_keyword", "Cost of Living")], "Request timed out."
    except Exception as e:
        return [record.get("concern_keyword", "Cost of Living")], f"Error: {str(e)[:80]}"

# ─────────────────────────────────────────
# GENERATE HTML
# ─────────────────────────────────────────

def concern_to_key(c):
    return c.replace(" ", "-").replace("&", "and").replace(",", "")

def format_date(date_str):
    """Convert '25-2-2026' to '25 Feb 2026'"""
    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    try:
        parts = date_str.split("-")
        return f"{parts[0]} {months[int(parts[1])]} {parts[2]}"
    except:
        return date_str

def generate_html(records):
    # Collect unique years and dates
    years   = sorted(set(r.get("year") for r in records if r.get("year")))
    dates   = sorted(set(r.get("date") for r in records if r.get("date")), reverse=True)

    # Concern filter buttons
    concern_buttons = '<button class="filter-btn active" data-filter="concern" data-value="all" onclick="setFilter(\'concern\',\'all\',this)">All Topics</button>\n'
    for c in CONCERNS:
        key  = concern_to_key(c)
        safe = c.replace("&", "&amp;")
        concern_buttons += f'<button class="filter-btn" data-filter="concern" data-value="{key}" onclick="setFilter(\'concern\',\'{key}\',this)">{safe}</button>\n'

    # Year filter buttons
    year_buttons = '<button class="year-btn active" data-value="all" onclick="setFilter(\'year\',\'all\',this)">All Years</button>\n'
    for y in years:
        year_buttons += f'<button class="year-btn" data-value="{y}" onclick="setFilter(\'year\',\'{y}\',this)">{y}</button>\n'

    # Date dropdown options
    date_options = '<option value="all">All sitting dates</option>\n'
    for d in dates:
        date_options += f'<option value="{d}">{format_date(d)}</option>\n'

    # Cards
    cards = ""
    for r in records:
        concern_keys = " ".join(concern_to_key(c) for c in r.get("concerns", []))
        concern_tags = "".join(f'<span class="tag">{c}</span>' for c in r.get("concerns", []))
        source_link  = f'<a href="{r["source_url"]}" target="_blank" class="source-link">Read full speech &#8594;</a>' if r.get("source_url") else ""
        title   = r.get("title", "").replace("<","&lt;").replace(">","&gt;")
        summary = r.get("summary", "").replace("<","&lt;").replace(">","&gt;")
        year    = r.get("year", "")
        date    = format_date(r.get("date", ""))
        raw_date = r.get("date", "")

        cards += f"""<div class="card" data-concerns="{concern_keys}" data-year="{year}" data-date="{raw_date}">
  <div class="meta"><span class="date">{date}</span></div>
  <h2>{title}</h2>
  <div class="tags">{concern_tags}</div>
  <p class="summary">{summary}</p>
  {source_link}
</div>\n"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ParliamentPulse SG</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f4f4f4; color: #333; }}

  header {{ background: #c0392b; color: white; padding: 1.8rem 1rem; text-align: center; }}
  header h1 {{ font-size: 1.9rem; font-weight: 700; }}
  header p {{ opacity: 0.85; margin-top: 0.4rem; font-size: 0.95rem; }}

  /* STICKY FILTER BAR */
  .filters {{ position: sticky; top: 0; z-index: 100; background: white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.10); padding: 0.75rem 1rem; }}

  .search-row {{ margin-bottom: 0.6rem; position: relative; }}
  .search-row input {{ width: 100%; padding: 8px 36px 8px 12px; border: 1px solid #ddd;
    border-radius: 20px; font-size: 0.9rem; outline: none; }}
  .search-row input:focus {{ border-color: #c0392b; }}
  .clear-btn {{ position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
    background: none; border: none; cursor: pointer; color: #aaa; font-size: 1rem; }}

  .filter-row {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.5rem; align-items: center; }}
  .filter-label {{ font-size: 0.75rem; font-weight: 700; color: #888; text-transform: uppercase;
    letter-spacing: 0.05em; margin-right: 0.3rem; white-space: nowrap; }}

  .filter-btn, .year-btn {{ background: #f0f0f0; border: none; padding: 5px 12px;
    border-radius: 16px; cursor: pointer; font-size: 0.78rem; white-space: nowrap; }}
  .filter-btn.active, .filter-btn:hover, .year-btn.active, .year-btn:hover
    {{ background: #c0392b; color: white; }}

  .date-select {{ padding: 6px 10px; border: 1px solid #ddd; border-radius: 16px;
    font-size: 0.82rem; cursor: pointer; outline: none; background: #f0f0f0; }}
  .date-select:focus {{ border-color: #c0392b; }}

  /* CARDS */
  .container {{ max-width: 820px; margin: 1.5rem auto; padding: 0 1rem; }}
  #result-count {{ font-size: 0.82rem; color: #888; margin-bottom: 1rem; }}

  .card {{ background: white; border-radius: 8px; padding: 1.4rem; margin-bottom: 1.2rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07); }}
  .card.hidden {{ display: none; }}
  .date {{ color: #999; font-size: 0.8rem; display: block; margin-bottom: 0.4rem; }}
  h2 {{ font-size: 0.97rem; font-weight: 600; margin-bottom: 0.55rem; line-height: 1.45; }}
  .tags {{ display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.7rem; }}
  .tag {{ background: #fef3cd; color: #856404; font-size: 0.7rem; padding: 2px 8px;
    border-radius: 10px; font-weight: 600; }}
  .summary {{ font-size: 0.9rem; line-height: 1.65; color: #444; margin-bottom: 0.6rem; }}
  .source-link {{ font-size: 0.8rem; color: #c0392b; text-decoration: none; font-weight: 600; }}
  .source-link:hover {{ text-decoration: underline; }}

  footer {{ text-align: center; padding: 2rem; color: #aaa; font-size: 0.82rem; }}
</style>
</head>
<body>

<header>
  <h1>ParliamentPulse SG</h1>
  <p>What Parliament said about the issues that matter to you</p>
</header>

<div class="filters">

  <div class="search-row">
    <input type="text" id="search-input" placeholder="Search speeches..." oninput="applyFilters()">
    <button class="clear-btn" onclick="clearSearch()" title="Clear search">&#x2715;</button>
  </div>

  <div class="filter-row">
    <span class="filter-label">Topic</span>
    {concern_buttons}
  </div>

  <div class="filter-row">
    <span class="filter-label">Year</span>
    {year_buttons}
  </div>

  <div class="filter-row">
    <span class="filter-label">Sitting Date</span>
    <select class="date-select" id="date-select" onchange="setFilter('date', this.value, null)">
      {date_options}
    </select>
  </div>

</div>

<div class="container">
  <p id="result-count"></p>
  <div id="cards">{cards}</div>
</div>

<footer>Generated {datetime.now().strftime('%d %B %Y')} &middot; {len(records)} speeches</footer>

<script>
const state = {{ concern: 'all', year: 'all', date: 'all', search: '' }};

function setFilter(type, value, btn) {{
  state[type] = value;
  // Clicking a year resets the date dropdown
  if (type === 'year') {{
    state.date = 'all';
    document.getElementById('date-select').value = 'all';
  }}
  // Update button active states
  if (btn) {{
    const selector = type === 'concern' ? '.filter-btn' : '.year-btn';
    document.querySelectorAll(selector).forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }}
  applyFilters();
}}

function applyFilters() {{
  state.search = document.getElementById('search-input').value.toLowerCase();
  state.date   = document.getElementById('date-select').value;
  let visible  = 0;
  document.querySelectorAll('.card').forEach(card => {{
    const matchConcern = state.concern === 'all' || card.dataset.concerns.includes(state.concern);
    const matchYear    = state.year === 'all'    || card.dataset.year === state.year;
    const matchDate    = state.date === 'all'    || card.dataset.date === state.date;
    const text         = card.innerText.toLowerCase();
    const matchSearch  = state.search === ''     || text.includes(state.search);
    const show = matchConcern && matchYear && matchDate && matchSearch;
    card.classList.toggle('hidden', !show);
    if (show) visible++;
  }});
  const total = document.querySelectorAll('.card').length;
  document.getElementById('result-count').textContent = visible + ' of ' + total + ' speeches shown';
}}

window.onload = () => applyFilters();

function clearSearch() {{
  document.getElementById('search-input').value = '';
  applyFilters();
}}
</script>
</body>
</html>"""

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    if not API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        print("Run: export ANTHROPIC_API_KEY=sk-ant-...")
        return

    os.makedirs("output", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    with open(INPUT_FILE) as f:
        records = json.load(f)

    records = [r for r in records if r.get("text", "").strip()]
    print(f"Processing {len(records)} speeches...\n")

    results = []
    for i, record in enumerate(records):
        # Add year field
        date = record.get("date", "")
        try:
            record["year"] = int(date.split("-")[2])
        except:
            record["year"] = None

        # Add source_url field
        report_id = record.get("reportId", "").rstrip("#")
        record["source_url"] = f"https://sprs.parl.gov.sg/search/#/topic?reportid={report_id}" if report_id else ""

        print(f"[{i+1}/{len(records)}] {record['date']} | {record['title'][:55]}")
        concerns, summary = classify_and_summarise(record)
        record["concerns"] = concerns
        record["summary"]  = summary
        results.append(record)
        print(f"  Concerns: {', '.join(concerns)}")
        print(f"  Summary:  {summary[:80]}...")
        time.sleep(0.5)

        if (i + 1) % 20 == 0:
            with open(JSON_OUTPUT, "w") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            html = generate_html(results)
            with open(OUTPUT_FILE, "w") as f:
                f.write(html)
            print(f"  --- Progress saved ({i+1} done) ---\n")

    with open(JSON_OUTPUT, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    html = generate_html(results)
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    print(f"\nDone!")
    print(f"  Open: output/summaries.html")
    print(f"  Data: data/summaries.json")

if __name__ == "__main__":
    main()
