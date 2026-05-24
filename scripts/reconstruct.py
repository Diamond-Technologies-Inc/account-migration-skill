#!/usr/bin/env python3
"""reconstruct.py — Build per-project layouts in destination folders from
extracted transcripts + export project JSONs.

Reads the routing dict (the orchestrator's per-project decisions from the
Track A walk-through) from a JSON file. The orchestrator writes that JSON
before invoking this script. All paths come in as CLI arguments — no
hardcoded scratch directories or project names live in this source.

Routing JSON schema (dict keyed by user-facing project name):

    {
      "Display Name of Project": {
        "action": "reconstruct_in_place" | "route_to_catchall",
        "folder_name": "destination folder name on disk",
        "export_name": "name as it appears in the export's projects_manifest.csv",
        "export_uuid": "uuid of the project's JSON in export-unzipped/projects/",
        "reason": "(route_to_catchall only) human-readable reason"
      }
    }

Per-action expectations:

    reconstruct_in_place — writes a full project layout to <outdir>/<folder_name>/.
        Requires: folder_name, export_name, export_uuid.
        Produces: knowledge/, conversation-history/, _PROJECT_BRIEF.md.

    route_to_catchall — writes transcripts to <outdir>/<catchall_name>/<folder_name>/.
        Requires: folder_name, reason.
        Produces: transcripts + INDEX.md + _MIGRATION_NOTE.md inside the subfolder.
        (The reshape_and_extract pass later moves the transcripts under
        conversation-history/ inside the subfolder.)

Usage:

    python3 reconstruct.py \\
        --extracted   <path>   \\
        --attribution <path>   \\
        --export      <path>   \\
        --routing     <path>   \\
        --outdir      <path>   \\
        [--catchall-name <name>]

Where:
    --extracted    The output dir produced by extract_export.py. Must
                   contain transcripts/, raw/, and
                   conversations_manifest.csv.
    --attribution  Path to attribution_map.csv (produced by
                   parse_allchats.py).
    --export       The unzipped export root. Must contain projects/
                   with one JSON per project.
    --routing      Path to the routing JSON file (schema above).
    --outdir       Destination root. Each reconstructed project lands at
                   <outdir>/<folder_name>/; catchall content lands at
                   <outdir>/<catchall_name>/.
    --catchall-name  Folder name for the catch-all project at the
                     destination. Default: "Migrated Conversation History".
"""

import argparse
import csv
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_CATCHALL_NAME = "Migrated Conversation History"

# Visible mojibake artifacts from double-UTF-8 encoding (export-side defect:
# UTF-8 bytes interpreted as Windows-1252, then re-encoded as UTF-8). When any
# of these sequences appears in a knowledge file's text, the file likely has
# encoding damage that the user may want to compare against the original.
MOJIBAKE_PATTERNS = (
    "Â ",       # nbsp mojibake (very common)
    "â€",       # em-dash, smart quotes, ellipsis mojibake leading
    "âœ",       # check / x emoji mojibake leading
    "âš",       # warning sign mojibake leading
    "âžž",      # arrow mojibake
    "Ã©",       # é mojibake
    "Ã¨",       # è mojibake
    "Ã¢",       # â mojibake (different from leading-â above)
)


def detect_mojibake(text):
    """Return True if the text contains visible mojibake patterns indicative
    of double-UTF-8 encoding in the source export."""
    for pat in MOJIBAKE_PATTERNS:
        if pat in text:
            return True
    return False


def safe_filename(name):
    """Sanitize for OS-safe filenames."""
    return re.sub(r"[^\w\-\.\[\] ]", "_", name)


def load_attribution(attribution_csv):
    """uuid -> project_name (or '' for unattributed)."""
    with open(attribution_csv, encoding="utf-8") as f:
        return {r["uuid"]: r["project_assignment"] for r in csv.DictReader(f)}


def load_attribution_full(attribution_csv):
    """Full per-uuid row (used to inspect in_allchats column for orphan filtering)."""
    with open(attribution_csv, encoding="utf-8") as f:
        return {r["uuid"]: r for r in csv.DictReader(f)}


def load_conv_manifest(conv_csv):
    """uuid -> manifest row."""
    with open(conv_csv, encoding="utf-8") as f:
        return {r["uuid"]: r for r in csv.DictReader(f)}


def load_routing(routing_json):
    """Load the routing decisions from JSON."""
    with open(routing_json, encoding="utf-8") as f:
        return json.load(f)


def load_project_json(export_projects_dir, uuid):
    """Load a project's full export JSON. Returns None if not present."""
    path = export_projects_dir / f"{uuid}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def find_transcript(extracted_dir, uuid, manifest):
    """Find the transcript path for a conv uuid."""
    m = manifest.get(uuid)
    if not m:
        return None
    return extracted_dir / m["transcript_file"]


def get_opener(raw_dir, uuid):
    """First ~100 chars of the first human message in a conv, for the INDEX."""
    raw_path = raw_dir / f"{uuid}.json"
    if not raw_path.exists():
        return ""
    try:
        d = json.loads(raw_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    for m in d.get("chat_messages", []):
        if m.get("sender") == "human":
            t = (m.get("text") or "").strip()
            if not t:
                # try content blocks
                for b in m.get("content", []) or []:
                    if isinstance(b, dict) and b.get("type") == "text":
                        t = (b.get("text") or "").strip()
                        if t:
                            break
            if t:
                return t.replace("\n", " ")[:100]
    return ""


def write_index(path, conv_rows):
    """Write a conversation-history INDEX.md."""
    lines = [
        "# Conversation history index",
        "",
        "| # | Time | Conversation | Msgs | Opens with |",
        "|---|------|--------------|-----:|------------|",
    ]
    for i, r in enumerate(conv_rows, 1):
        name = r["name"] or "(untitled)"
        ts = r["created_at"][:16].replace("T", " ") if r["created_at"] else ""
        opener = r["opener"][:80] + ("…" if len(r["opener"]) > 80 else "")
        # Escape pipes in table cells
        name_esc = name.replace("|", "\\|")
        opener_esc = opener.replace("|", "\\|")
        lines.append(
            f"| {i} | {ts} | [{name_esc}]({r['filename']}) | "
            f"{r['messages']} | {opener_esc} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_project_brief(path, project, conv_rows, action, mojibake_files=None):
    """Write _PROJECT_BRIEF.md for a reconstructed project."""
    mojibake_files = mojibake_files or []
    lines = [
        f"# {project.get('name', '')}",
        "",
        "## Provenance",
        f"- Source: Claude personal-account export (web project)",
        f"- Project UUID: `{project.get('uuid', '')}`",
        f"- Description: {project.get('description', '') or '(none)'}",
        f"- Reconstruction action: {action}",
        f"- Reconstructed: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Custom instructions (from claude.ai)",
        "",
    ]
    instr = (project.get("prompt_template") or "").strip()
    if instr:
        lines.append(instr)
    else:
        lines.append("_(none set on claude.ai)_")
    lines += [
        "",
        "## Knowledge inventory",
        "",
    ]
    docs = project.get("docs", []) or []
    if docs:
        lines.append(f"{len(docs)} knowledge doc(s) in `knowledge/`:")
        lines.append("")
        for d in docs:
            fn = d.get("filename", "(unnamed)")
            chars = len(d.get("content", "") or "")
            lines.append(f"- `{fn}` — {chars:,} chars (text content from export)")
    else:
        lines.append("_(no knowledge docs)_")
    lines += [
        "",
        "## Conversation history",
        "",
        f"{len(conv_rows)} conversation(s) in `conversation-history/`. "
        f"See `conversation-history/INDEX.md` for the table.",
        "",
        "## Resuming on the new account",
        "",
        "When you've imported this folder as a Cowork project on the new account",
        "(via **New project → Choose existing folder**):",
        "",
        "1. Open `transition-data/project-blueprint.md` and copy its **Custom",
        "   Instructions** section into the new project's settings.",
        "2. Start a conversation in the project. Paste this prompt:",
        "",
        "   ```",
        "   This is a project I'm migrating from my old Claude account.",
        "   Read `transition-data/project-blueprint.md` for full context, then",
        "   treat its **Recommended Starting Prompt** section as my first",
        "   directive — that's the project-tailored resumption point.",
        "   Knowledge files referenced in the blueprint are in `knowledge/`",
        "   (for reconstructed projects) or in this project's folder (for",
        "   Cowork projects).",
        "   ```",
        "",
        "Claude will read the blueprint and pick up where the old-account",
        "version left off — no further setup needed.",
        "",
        "## Notes",
        "",
    ]
    if mojibake_files:
        lines.append(
            f"- **Mojibake detected** in {len(mojibake_files)} knowledge "
            f"file(s): {', '.join(f'`{f}`' for f in mojibake_files)}. The "
            f"export-side double-UTF-8 encoding produced visible artifacts "
            f"(`Â`, `âœ…`, `â€`, etc.) in these files. Compare against the "
            f"original on-disk copies if available and replace as needed; "
            f"the migration cannot reliably round-trip the damage."
        )
    lines += [
        "- Binary knowledge docs (PDFs, .docx, etc.) come through as **extracted text** in the export.",
        "- Conversation-uploaded files are listed by name in the transcripts but their binaries are not preserved.",
        "- This brief is generated by the project-import skill. Edit freely after Track B relink.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_migration_note(path, project_name, reason, count):
    """Write _MIGRATION_NOTE.md for a catch-all per-project subfolder."""
    lines = [
        f"# {project_name} — migration note",
        "",
        f"Routed here because: **{reason}**.",
        "",
        f"Contains **{count} conversation(s)** that were attributed to this project on claude.ai.",
        "",
        "## Why this is in the catch-all",
        "",
        "During the project-import walk-through, you either:",
        "- Picked an existing folder you've been working in (so I left it alone to protect your work), or",
        "- Skipped this project (so it wasn't reconstructed as a project).",
        "",
        "Either way, the conversations themselves are preserved here for review.",
        "",
        "## Your options",
        "",
        "- **Keep this subfolder** as a permanent reference.",
        "- **Fold it into a project** later — pick a few transcripts that are still useful and copy them where you want.",
        "- **Delete it** if you don't need it.",
        "",
        f"Generated by the project-import skill, {datetime.now().strftime('%Y-%m-%d %H:%M')}.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_catchall_brief(path, catchall_name, totals):
    """Write the catch-all project's own _PROJECT_BRIEF.md."""
    lines = [
        f"# {catchall_name}",
        "",
        "## What this is",
        "",
        "A catch-all Cowork project created by the project-import skill to hold "
        "any conversation history that doesn't belong in a reconstructed project.",
        "",
        "## What's inside",
        "",
        f"- `unattributed-conversations/` — {totals['orphans']} conversations from "
        f"claude.ai that weren't in any project (loose chats).",
        "- One subfolder per source project you either skipped or picked into an "
        "existing folder:",
    ]
    for s in totals["subfolders"]:
        lines.append(f"  - `{s['name']}/` — {s['count']} conversation(s) ({s['reason']})")
    lines += [
        "",
        "## Track B (after you've relinked everything to your new account)",
        "",
        "Review each subfolder and keep, fold, or delete as you see fit. The "
        "`_MIGRATION_NOTE.md` in each subfolder explains its origin.",
        "",
        f"Generated by the project-import skill, {datetime.now().strftime('%Y-%m-%d %H:%M')}.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def reconstruct_in_place(project_name, route, paths):
    """Build the project layout inside the picked folder.

    paths is a dict containing resolved Path objects for: outdir,
    export_projects_dir, extracted_dir, raw_dir, attribution, manifest.
    """
    folder = paths["outdir"] / route["folder_name"]
    folder.mkdir(parents=True, exist_ok=True)

    project = load_project_json(paths["export_projects_dir"], route["export_uuid"])
    if project is None:
        print(f"  WARN: no export JSON for {project_name}")
        project = {"name": project_name, "uuid": route["export_uuid"]}

    # knowledge/
    knowledge_dir = folder / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    mojibake_files = []
    for d in project.get("docs", []) or []:
        fn = safe_filename(d.get("filename", "doc.txt"))
        content = d.get("content", "") or ""
        (knowledge_dir / fn).write_text(content, encoding="utf-8")
        if detect_mojibake(content):
            mojibake_files.append(fn)

    # conversation-history/
    convs_dir = folder / "conversation-history"
    convs_dir.mkdir(exist_ok=True)
    conv_uuids = [u for u, p in paths["attribution"].items() if p == project_name]
    conv_rows = []
    for u in conv_uuids:
        src = find_transcript(paths["extracted_dir"], u, paths["manifest"])
        m = paths["manifest"].get(u, {})
        if src and src.exists():
            dest = convs_dir / src.name
            shutil.copy2(src, dest)
            conv_rows.append({
                "name": m.get("name", ""),
                "created_at": m.get("created_at", ""),
                "messages": m.get("messages", ""),
                "filename": src.name,
                "opener": get_opener(paths["raw_dir"], u),
            })
    conv_rows.sort(key=lambda r: r["created_at"])

    write_index(convs_dir / "INDEX.md", conv_rows)
    write_project_brief(folder / "_PROJECT_BRIEF.md", project, conv_rows,
                        "reconstructed in place (empty folder picked)",
                        mojibake_files=mojibake_files)
    return len(conv_rows), len(project.get("docs", []) or [])


def route_to_catchall(project_name, route, paths):
    """Build a per-project subfolder in the catch-all."""
    subfolder = paths["catchall_dir"] / route["folder_name"]
    subfolder.mkdir(parents=True, exist_ok=True)

    conv_uuids = [u for u, p in paths["attribution"].items() if p == project_name]
    conv_rows = []
    for u in conv_uuids:
        src = find_transcript(paths["extracted_dir"], u, paths["manifest"])
        m = paths["manifest"].get(u, {})
        if src and src.exists():
            dest = subfolder / src.name
            shutil.copy2(src, dest)
            conv_rows.append({
                "name": m.get("name", ""),
                "created_at": m.get("created_at", ""),
                "messages": m.get("messages", ""),
                "filename": src.name,
                "opener": get_opener(paths["raw_dir"], u),
            })
    conv_rows.sort(key=lambda r: r["created_at"])
    write_index(subfolder / "INDEX.md", conv_rows)
    write_migration_note(subfolder / "_MIGRATION_NOTE.md",
                         project_name, route.get("reason", ""), len(conv_rows))
    return len(conv_rows)


def route_orphans(paths):
    """Build the unattributed-conversations folder in the catch-all."""
    folder = paths["catchall_dir"] / "unattributed-conversations"
    folder.mkdir(parents=True, exist_ok=True)

    # Orphans: in AllChats but no project AND have messages.
    # in_allchats column distinguishes "current on claude.ai" from
    # "in manifest only (deleted but still in the JSON)".
    attribution_full = paths["attribution_full"]
    orphan_uuids = []
    for u, row in attribution_full.items():
        if row.get("in_allchats") != "yes":
            continue
        if row.get("project_assignment"):
            continue
        m = paths["manifest"].get(u, {})
        if m.get("messages", "0") == "0":
            continue
        orphan_uuids.append(u)

    conv_rows = []
    for u in orphan_uuids:
        src = find_transcript(paths["extracted_dir"], u, paths["manifest"])
        m = paths["manifest"].get(u, {})
        if src and src.exists():
            dest = folder / src.name
            shutil.copy2(src, dest)
            conv_rows.append({
                "name": m.get("name", ""),
                "created_at": m.get("created_at", ""),
                "messages": m.get("messages", ""),
                "filename": src.name,
                "opener": get_opener(paths["raw_dir"], u),
            })
    conv_rows.sort(key=lambda r: r["created_at"])
    write_index(folder / "INDEX.md", conv_rows)
    return len(conv_rows)


def main():
    ap = argparse.ArgumentParser(
        description=("Build per-project destination layouts from extracted "
                     "transcripts + export project JSONs."))
    ap.add_argument("--extracted", required=True,
                    help="extract_export.py outdir (contains transcripts/, raw/, "
                         "conversations_manifest.csv).")
    ap.add_argument("--attribution", required=True,
                    help="Path to attribution_map.csv (output of parse_allchats.py).")
    ap.add_argument("--export", required=True,
                    help="Unzipped export root (contains projects/ with project JSONs).")
    ap.add_argument("--routing", required=True,
                    help="Path to the routing JSON file (see module docstring for schema).")
    ap.add_argument("--outdir", required=True,
                    help="Destination root for reconstructed projects.")
    ap.add_argument("--catchall-name", default=DEFAULT_CATCHALL_NAME,
                    help=f"Folder name for the catch-all project. "
                         f"Default: '{DEFAULT_CATCHALL_NAME}'.")
    args = ap.parse_args()

    extracted_dir = Path(args.extracted).resolve()
    attribution_csv = Path(args.attribution).resolve()
    export_root = Path(args.export).resolve()
    routing_json = Path(args.routing).resolve()
    outdir = Path(args.outdir).resolve()

    # Validate inputs exist.
    for p, label in [
        (extracted_dir, "--extracted"),
        (attribution_csv, "--attribution"),
        (export_root, "--export"),
        (routing_json, "--routing"),
    ]:
        if not p.exists():
            print(f"ERROR: {label} does not exist: {p}", file=sys.stderr)
            return 1

    conv_csv = extracted_dir / "conversations_manifest.csv"
    if not conv_csv.exists():
        print(f"ERROR: conversations_manifest.csv missing under --extracted: {conv_csv}",
              file=sys.stderr)
        return 1

    raw_dir = extracted_dir / "raw"
    export_projects_dir = export_root / "projects"

    outdir.mkdir(parents=True, exist_ok=True)
    catchall_dir = outdir / args.catchall_name
    catchall_dir.mkdir(parents=True, exist_ok=True)

    # Load data.
    attribution = load_attribution(attribution_csv)
    attribution_full = load_attribution_full(attribution_csv)
    manifest = load_conv_manifest(conv_csv)
    routing = load_routing(routing_json)

    print(f"Loaded {len(attribution)} attribution rows, "
          f"{len(manifest)} manifest rows, "
          f"{len(routing)} routing entries.\n")

    paths = {
        "outdir": outdir,
        "catchall_dir": catchall_dir,
        "extracted_dir": extracted_dir,
        "raw_dir": raw_dir,
        "export_projects_dir": export_projects_dir,
        "attribution": attribution,
        "attribution_full": attribution_full,
        "manifest": manifest,
    }

    results = []
    catchall_subfolders = []
    for name in sorted(routing.keys()):
        route = routing[name]
        action = route.get("action", "")
        if action == "reconstruct_in_place":
            convs, docs = reconstruct_in_place(name, route, paths)
            results.append(f"  ✓ {name}: reconstructed in place — "
                           f"{convs} convs, {docs} docs")
        elif action == "route_to_catchall":
            convs = route_to_catchall(name, route, paths)
            results.append(f"  → {name}: routed to catch-all "
                           f"({route.get('reason','')}) — {convs} convs")
            catchall_subfolders.append({
                "name": route["folder_name"],
                "count": convs,
                "reason": route.get("reason", ""),
            })
        else:
            print(f"  WARN: unknown action '{action}' for project '{name}', skipping",
                  file=sys.stderr)

    print("Per-project results:")
    for r in results:
        print(r)

    print()
    print("Orphan conversations:")
    orphans = route_orphans(paths)
    print(f"  → unattributed-conversations: {orphans} convs")

    # Catch-all _PROJECT_BRIEF.md
    write_catchall_brief(
        catchall_dir / "_PROJECT_BRIEF.md",
        args.catchall_name,
        {"orphans": orphans, "subfolders": catchall_subfolders},
    )
    print(f"  ✓ wrote catch-all _PROJECT_BRIEF.md")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
