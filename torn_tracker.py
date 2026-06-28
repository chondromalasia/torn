import requests
import os
import json
from datetime import datetime

API_KEY = os.environ.get("TORN_API_KEY") or input("Enter your Torn API key: ").strip()
FACTION_ID = os.environ.get("TORN_FACTION_ID") or input("Enter enemy faction ID: ").strip()
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "index.html")

BASE_URL = "https://api.torn.com"


def get_faction_members(api_key, faction_id):
    url = f"{BASE_URL}/faction/{faction_id}?selections=basic&key={api_key}"
    response = requests.get(url, timeout=15)
    data = response.json()

    if "error" in data:
        raise RuntimeError(f"API Error {data['error']['code']}: {data['error']['error']}")

    return data.get("name", "Unknown Faction"), data.get("members", {})


def build_member(member_id, member_data):
    status = member_data.get("status", {})
    last_action = member_data.get("last_action", {})
    state = status.get("state", "Unknown")
    description = status.get("description", "Unknown")
    until = status.get("until", 0)

    destination = "Torn"
    if state in ("Traveling", "Abroad"):
        desc_lower = description.lower()
        if "to torn" in desc_lower:
            destination = "Torn"
        elif desc_lower.startswith("traveling from torn to "):
            destination = description[len("traveling from torn to "):].strip()
        elif desc_lower.startswith("traveling to "):
            destination = description[len("traveling to "):].strip()
        elif desc_lower.startswith("in "):
            destination = description[len("in "):].strip()
        else:
            destination = description

    if state == "Traveling" and until:
        now = datetime.now().timestamp()
        time_left = max(0, int(until - now))
        mins, secs = divmod(time_left, 60)
        time_left_str = f"{mins}m {secs}s"
        eta_str = datetime.fromtimestamp(until).strftime("%H:%M:%S")
    else:
        time_left = 0
        time_left_str = "—"
        eta_str = "—"

    return {
        "id": member_id,
        "name": member_data.get("name", "Unknown"),
        "level": member_data.get("level", "?"),
        "state": state,
        "description": description,
        "destination": destination,
        "time_left": time_left,
        "time_left_str": time_left_str,
        "eta": eta_str,
        "online": last_action.get("status", "Unknown"),
        "last_action": last_action.get("relative", "Unknown"),
        "last_action_ts": last_action.get("timestamp", 0),
    }


def sort_key(m):
    state = m.get("state", "")
    if state == "Traveling":
        return (0, m.get("time_left", 9999999))
    elif state == "Abroad":
        return (1, m.get("name", ""))
    else:
        return (2, m.get("name", ""))


STATE_COLORS = {
    "Traveling": "#f59e0b",
    "Abroad":    "#3b82f6",
    "Hospital":  "#ef4444",
    "Jail":      "#8b5cf6",
    "Okay":      "#6b7280",
    "Unknown":   "#6b7280",
}

ONLINE_COLORS = {
    "Online": "#22c55e",
    "Idle":   "#f59e0b",
    "Offline":"#6b7280",
}


def render_html(faction_name, members, generated_at):
    rows = ""
    for m in members:
        state_color = STATE_COLORS.get(m["state"], "#6b7280")
        online_color = ONLINE_COLORS.get(m["online"], "#6b7280")
        rows += f"""
        <tr>
          <td><a href="https://www.torn.com/profiles.php?XID={m['id']}" target="_blank">{m['name']}</a></td>
          <td data-sort="{m['level']}">{m['level']}</td>
          <td><span class="badge" style="background:{state_color}">{m['state']}</span></td>
          <td>{m['destination']}</td>
          <td><span class="dot" style="background:{online_color}"></span>{m['online']}</td>
          <td data-sort="{m['last_action_ts']}">{m['last_action']}</td>
        </tr>"""

    traveling = sum(1 for m in members if m["state"] == "Traveling")
    abroad = sum(1 for m in members if m["state"] == "Abroad")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="300">
  <title>{faction_name} — Torn Tracker</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: 'Segoe UI', system-ui, sans-serif;
      font-size: 14px;
      padding: 24px;
    }}
    h1 {{ font-size: 1.4rem; font-weight: 600; margin-bottom: 4px; }}
    .meta {{ color: #94a3b8; font-size: 0.85rem; margin-bottom: 20px; }}
    .stats {{ display: flex; gap: 16px; margin-bottom: 20px; }}
    .stat {{
      background: #1e293b;
      border-radius: 8px;
      padding: 10px 18px;
      font-size: 0.85rem;
      color: #94a3b8;
    }}
    .stat strong {{ display: block; font-size: 1.3rem; color: #e2e8f0; }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{
      text-align: left;
      padding: 8px 12px;
      color: #64748b;
      font-weight: 600;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-bottom: 1px solid #1e293b;
      cursor: pointer;
      user-select: none;
    }}
    thead th:after {{ content: ''; margin-left: 6px; }}
    thead th[aria-sort="ascending"]:after {{ content: '▲'; }}
    thead th[aria-sort="descending"]:after {{ content: '▼'; }}
    thead th.no-sort {{ cursor: default; }}
    tbody tr {{ border-bottom: 1px solid #1e293b; }}
    tbody tr:hover {{ background: #1e293b; }}
    td {{ padding: 10px 12px; }}
    a {{ color: #93c5fd; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 0.75rem;
      font-weight: 600;
      color: #fff;
    }}
    .dot {{
      display: inline-block;
      width: 8px; height: 8px;
      border-radius: 50%;
      margin-right: 6px;
      vertical-align: middle;
    }}
  </style>
</head>
<body>
  <h1>{faction_name}</h1>
  <p class="meta">Updated: {generated_at} &nbsp;·&nbsp; Auto-refreshes every 5 minutes</p>
  <div class="stats">
    <div class="stat"><strong>{len(members)}</strong> Members</div>
    <div class="stat"><strong>{traveling}</strong> Traveling</div>
    <div class="stat"><strong>{abroad}</strong> Abroad</div>
  </div>
  <table id="members-table">
    <thead>
      <tr>
        <th>Name</th>
        <th>Level</th>
        <th>State</th>
        <th>Destination</th>
        <th>Online</th>
        <th>Last Action</th>
      </tr>
    </thead>
    <tbody>{rows}
    </tbody>
  </table>
  <script src="https://cdn.jsdelivr.net/npm/tablesort@5.3.0/dist/tablesort.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/tablesort@5.3.0/dist/sorts/tablesort.number.min.js"></script>
  <script>new Tablesort(document.getElementById('members-table'));</script>
</body>
</html>"""


faction_name, raw_members = get_faction_members(API_KEY, FACTION_ID)

members = [build_member(mid, mdata) for mid, mdata in raw_members.items()]
members.sort(key=sort_key)

generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
html = render_html(faction_name, members, generated_at)

with open(OUTPUT_FILE, "w") as f:
    f.write(html)

print(f"Written {OUTPUT_FILE}  ({len(members)} members, faction: {faction_name})")
