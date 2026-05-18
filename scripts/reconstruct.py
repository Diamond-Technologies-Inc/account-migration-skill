#!/usr/bin/env python3
"""reconstruct.py - Build per-project layouts in destination folders from
extracted transcripts + export project JSONs. Routes per the user's
walk-through decisions captured in the routing dict below."""

import csv, json, os, shutil, sys, re
from datetime import datetime
from pathlib import Path

SCRATCH = Path("/sessions/elegant-dazzling-cerf/mnt/outputs/run")
EXPORT_PROJECTS = SCRATCH / "export-unzipped" / "projects"
TRANSCRIPTS = SCRATCH / "run2-extracted" / "transcripts"
RAW = SCRATCH / "run2-extracted" / "raw"
ATTR_CSV = SCRATCH / "run2-hub-stage" / "attribution_map.csv"
CONV_CSV = SCRATCH / "run2-extracted" / "conversations_manifest.csv"

MNT = Path("/sessions/elegant-dazzling-cerf/mnt")
CATCHALL = MNT / "Migrated Conversation History"

# Routing decisions captured from the walk-through. Keyed by AllChats name.
ROUTING = {
    "CAT to CSF Transition [imported-archive]": {
        "action": "route_to_catchall",
        "subfolder_name": "CAT to CSF Transition [imported-archive]",
        "reason": "existing folder picked (CSF 2.0) — protected, conversations routed",
        "export_name": "CAT to CSF Transition [imported-archive]",
        "export_uuid": "019ced86-e1b7-718a-baee-866af833e4d0",
    },
    "CB - GPO Review": {
        "action": "reconstruct_in_place",
        "folder": MNT / "CB - GPO Review",
        "export_name": "CB - GPO Review",
        "export_uuid": "019bb78b-96e3-720c-86ec-12fcceac97b2",
    },
    "Corporate AI Policy Transition": {
        "action": "route_to_catchall",
        "subfolder_name": "Corporate AI Policy Transition",
        "reason": "skipped — renamed on web from 'Corporate AI Policy'",
        "export_name": "Corporate AI Policy",
        "export_uuid": "019e0889-3698-7093-9653-f88d0aa0521c",
    },
    "Developing a Work Voice": {
        "action": "reconstruct_in_place",
        "folder": MNT / "Developing a Work Voice",
        "export_name": "Developing a Work Voice",
        "export_uuid": "019deab8-fb8a-71b3-a744-6703bf34aab2",
    },
    "OCSP Study": {
        "action": "reconstruct_in_place",
        "folder": MNT / "OCSP Study",
        "export_name": "OCSP Study",
        "export_uuid": "019af510-c482-7759-a6b5-77f4c226a0f5",
    },
    "Personal - Workspace": {
        "action": "reconstruct_in_place",
        "folder": MNT / "Personal - Workspace",
        "export_name": "Personal - Workspace",
        "export_uuid": "019deb7f-1a62-727a-b730-a9411e5c0b2a",
    },
    "Vendor Setup for Heaven on earth": {
        "action": "reconstruct_in_place",
        "folder": MNT / "Vendor Setup for Heaven on earth",
        "export_name": "Vendor Setup for Heaven on earth",
        "export_uuid": "019d10c9-7107-70f4-ba3d-077a7da09778",
    },
    "VulScan Analysis [imported-archive]": {
        "action": "route_to_catchall",
        "subfolder_name": "VulScan Analysis [imported-archive]",
        "reason": "skipped",
        "export_name": "VulScan Analysis [imported-archive]",
        "export_uuid": "019bb321-acec-7009-bb0c-053f4ddd2c74",
    },
}


def safe_filename(name):
    """Sanitize for OS-safe filenames."""
    return re.sub(r"[^\w\-\.\[\] ]", "_", name)


def load_attribution():
    """uuid -> project_name (or '' for unattributed)."""
    with open(ATTR_CSV, encoding="utf-8") as f:
        return {r["uuid"]: r["project_assignment"] for r in csv.DictReader(f)}


def load_conv_manifest():
    """uuid -> manifest row."""
    with open(CONV_CSV, encoding="utf-8") as f:
        return {r["uuid"]: r for r in csv.DictReader(f)}


def load_project_json(uuid):
    """Load a project's full export JSON."""
    path = EXPORT_PROJECTS / f"{uuid}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def find_transcript(uuid, manifest):
    """Find the transcript path for a conv uuid."""
    m = manifest.get(uuid)
    if not m:
        return None
    return SCRATCH / "run2-extracted" / m["transcript_file"]


def get_opener(uuid):
    """First ~100 chars of the first human message in a conv, for the INDEX."""
    raw_path = RAW / f"{uuid}.json"
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


def write_project_brief(path, project, conv_rows, action):
    """Write _PROJECT_BRIEF.md for a reconstructed project."""
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
        "## Notes",
        "",
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


def write_catchall_brief(path, totals):
    """Write the catch-all project's own _PROJECT_BRIEF.md."""
    lines = [
        "# Migrated Conversation History",
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


def reconstruct_in_place(project_name, route, attribution, manifest):
    """Build the project layout inside the picked folder."""
    folder = route["folder"]
    project = load_project_json(route["export_uuid"])
    if project is None:
        print(f"  WARN: no export JSON for {project_name}")
        project = {"name": project_name, "uuid": route["export_uuid"]}

    # knowledge/
    knowledge_dir = folder / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    for d in project.get("docs", []) or []:
        fn = safe_filename(d.get("filename", "doc.txt"))
        (knowledge_dir / fn).write_text(d.get("content", "") or "", encoding="utf-8")

    # conversation-history/
    convs_dir = folder / "conversation-history"
    convs_dir.mkdir(exist_ok=True)
    conv_uuids = [u for u, p in attribution.items() if p == project_name]
    conv_rows = []
    for u in conv_uuids:
        src = find_transcript(u, manifest)
        m = manifest.get(u, {})
        if src and src.exists():
            dest = convs_dir / src.name
            shutil.copy2(src, dest)
            conv_rows.append({
                "name": m.get("name", ""),
                "created_at": m.get("created_at", ""),
                "messages": m.get("messages", ""),
                "filename": src.name,
                "opener": get_opener(u),
            })
    conv_rows.sort(key=lambda r: r["created_at"])

    write_index(convs_dir / "INDEX.md", conv_rows)
    write_project_brief(folder / "_PROJECT_BRIEF.md", project, conv_rows,
                        "reconstructed in place (empty folder picked)")
    return len(conv_rows), len(project.get("docs", []) or [])


def route_to_catchall(project_name, route, attribution, manifest):
    """Build a per-project subfolder in the catch-all."""
    subfolder = CATCHALL / route["subfolder_name"]
    subfolder.mkdir(exist_ok=True)
    conv_uuids = [u for u, p in attribution.items() if p == project_name]
    conv_rows = []
    for u in conv_uuids:
        src = find_transcript(u, manifest)
        m = manifest.get(u, {})
        if src and src.exists():
            dest = subfolder / src.name
            shutil.copy2(src, dest)
            conv_rows.append({
                "name": m.get("name", ""),
                "created_at": m.get("created_at", ""),
                "messages": m.get("messages", ""),
                "filename": src.name,
                "opener": get_opener(u),
            })
    conv_rows.sort(key=lambda r: r["created_at"])
    write_index(subfolder / "INDEX.md", conv_rows)
    write_migration_note(subfolder / "_MIGRATION_NOTE.md",
                         project_name, route["reason"], len(conv_rows))
    return len(conv_rows)


def route_orphans(attribution, manifest):
    """Build the unattributed-conversations folder in the catch-all."""
    folder = CATCHALL / "unattributed-conversations"
    folder.mkdir(exist_ok=True)
    orphan_uuids = [u for u, p in attribution.items() if not p and manifest.get(u, {}).get("messages", "0") != "0"]
    # Note: filter to orphans that are in AllChats but have no project AND have messages
    # (deleted conversations are the in-manifest-not-in-AllChats set; we don't want those)
    # But attribution_map.csv has in_allchats column to check
    with open(ATTR_CSV, encoding="utf-8") as f:
        in_allchats = {r["uuid"]: r["in_allchats"] for r in csv.DictReader(f)}
    orphan_uuids = [u for u in orphan_uuids if in_allchats.get(u) == "yes"]

    conv_rows = []
    for u in orphan_uuids:
        src = find_transcript(u, manifest)
        m = manifest.get(u, {})
        if src and src.exists():
            dest = folder / src.name
            shutil.copy2(src, dest)
            conv_rows.append({
                "name": m.get("name", ""),
                "created_at": m.get("created_at", ""),
                "messages": m.get("messages", ""),
                "filename": src.name,
                "opener": get_opener(u),
            })
    conv_rows.sort(key=lambda r: r["created_at"])
    write_index(folder / "INDEX.md", conv_rows)
    return len(conv_rows)


def main():
    attribution = load_attribution()
    manifest = load_conv_manifest()

    print(f"Loaded {len(attribution)} attribution rows, {len(manifest)} manifest rows.\n")

    results = []
    catchall_subfolders = []
    for name, route in sorted(ROUTING.items()):
        if route["action"] == "reconstruct_in_place":
            convs, docs = reconstruct_in_place(name, route, attribution, manifest)
            results.append(f"  ✓ {name}: reconstructed in place — {convs} convs, {docs} docs")
        elif route["action"] == "route_to_catchall":
            convs = route_to_catchall(name, route, attribution, manifest)
            results.append(f"  → {name}: routed to catch-all ({route['reason']}) — {convs} convs")
            catchall_subfolders.append({"name": name, "count": convs, "reason": route["reason"]})

    print("Per-project results:")
    for r in results:
        print(r)

    print()
    print("Orphan conversations:")
    orphans = route_orphans(attribution, manifest)
    print(f"  → unattributed-conversations: {orphans} convs")

    # Catch-all _PROJECT_BRIEF.md
    write_catchall_brief(
        CATCHALL / "_PROJECT_BRIEF.md",
        {"orphans": orphans, "subfolders": catchall_subfolders}
    )
    print("  ✓ wrote catch-all _PROJECT_BRIEF.md")
    print("\nDone.")


if __name__ == '__main__':
    main()
