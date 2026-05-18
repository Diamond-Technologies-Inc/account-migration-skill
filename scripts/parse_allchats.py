#!/usr/bin/env python3
"""parse_allchats.py - content-detect AllChats save, build attribution_map.csv."""
import re, csv, os, sys, glob
from bs4 import BeautifulSoup
from collections import defaultdict

UUID_RE = re.compile(r"/chat/([0-9a-f-]{36})")

def parse_allchats(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("main table")
    out = []
    if not table:
        return out
    for tr in table.select("tbody tr"):
        a = tr.find("a", href=UUID_RE)
        if not a:
            continue
        uuid = UUID_RE.search(a["href"]).group(1)
        td = a.find_parent("td")
        if not td:
            continue
        parts = [p.strip() for p in td.get_text(separator="|||", strip=True).split("|||") if p.strip()]
        title = parts[0] if parts else ""
        time_s = parts[1] if len(parts) >= 2 else ""
        project = parts[2] if len(parts) >= 3 else ""
        out.append(dict(uuid=uuid, title=title, time=time_s, project=project))
    return out

def load_manifest(path):
    with open(path, encoding="utf-8") as f:
        return {r["uuid"]: r for r in csv.DictReader(f)}

def find_allchats(hub):
    best = (None, 0)
    candidates = sorted(glob.glob(os.path.join(hub, "*.html")))
    for path in candidates:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                html = f.read()
        except OSError:
            continue
        if "/chat/" not in html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("main table tbody tr")
        count = sum(1 for tr in rows if tr.find("a", href=UUID_RE))
        if count > best[1]:
            best = (path, count)
    return best

def main():
    hub = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))

    webarchives = sorted(glob.glob(os.path.join(hub, "*.webarchive")))
    if webarchives:
        print("WARNING: .webarchive file(s) found:")
        for w in webarchives:
            print(f"   {w}")
        print("  Safari's Web Archive format is binary and cannot be parsed here.")
        print("  Re-save the page as 'Page Source' (HTML) instead.\n")

    allchats_path, row_count = find_allchats(hub)
    if not allchats_path:
        sys.exit(f"No AllChats-shaped HTML found in {hub}.")
    print(f"Detected AllChats file: {os.path.basename(allchats_path)}  ({row_count} rows)\n")

    manifest_path = os.path.join(hub, "conversations_manifest.csv")
    if not os.path.exists(manifest_path):
        sys.exit(f"conversations_manifest.csv not found in {hub}")

    manifest = load_manifest(manifest_path)
    html = open(allchats_path, encoding="utf-8", errors="replace").read()
    rows = parse_allchats(html)

    by_proj = defaultdict(list)
    for r in rows:
        by_proj[r["project"]].append(r)

    print(f"AllChats: {len(rows)} rows parsed")
    print(f"Manifest: {len(manifest)} conversations")
    print()
    print("Project assignments:")
    for k, v in sorted(by_proj.items(), key=lambda x: -len(x[1])):
        print(f"  {len(v):>4}  {k or '(unattributed)'}")
    print()

    ac_uuids = {r["uuid"] for r in rows}
    missing = set(manifest) - ac_uuids
    if missing:
        print(f"In manifest but not in AllChats ({len(missing)}):")
        for u in sorted(missing):
            m = manifest[u]
            print(f"  {u}  name='{m['name']}'  messages={m['messages']}  updated={m['updated_at'][:10]}")
        print()

    out_path = os.path.join(hub, "attribution_map.csv")
    attribution = {r["uuid"]: r["project"] for r in rows}
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["uuid", "name", "project_assignment", "updated_at", "messages", "in_allchats"])
        for u, m in manifest.items():
            w.writerow([u, m["name"], attribution.get(u, ""), m["updated_at"], m["messages"],
                        "yes" if u in ac_uuids else "no"])
    print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()
