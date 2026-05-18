#!/usr/bin/env python3
"""reshape_and_extract.py — apply the post-feedback fixes:

1. Reshape catch-all per-project subfolders so transcripts live under
   conversation-history/ (mirrors the reconstructed-project layout).
2. Extract inline artifacts (tool_use:artifacts + tool_use:create_file)
   into per-conversation <conv-slug>/artifacts/ folders.
3. Build _ARTIFACTS_TO_RECOVER.md at the catch-all root.
4. Regenerate INDEX.md files to reference the new layout.
"""

import csv, json, os, re, shutil
from collections import defaultdict
from pathlib import Path
from datetime import datetime

SCRATCH = Path("/sessions/elegant-dazzling-cerf/mnt/outputs/run")
MNT = Path("/sessions/elegant-dazzling-cerf/mnt")
CATCHALL = MNT / "Migrated Conversation History"
CONV_CSV = SCRATCH / "run2-extracted" / "conversations_manifest.csv"
ATTR_CSV = SCRATCH / "run2-hub-stage" / "attribution_map.csv"
EXPORT_CONV = SCRATCH / "export-unzipped" / "conversations.json"

ROUTING = {
    "CAT to CSF Transition [imported-archive]": {"action": "catchall_subfolder", "folder_name": "CAT to CSF Transition [imported-archive]"},
    "CB - GPO Review": {"action": "in_place", "folder": MNT / "CB - GPO Review"},
    "Corporate AI Policy Transition": {"action": "catchall_subfolder", "folder_name": "Corporate AI Policy Transition"},
    "Developing a Work Voice": {"action": "in_place", "folder": MNT / "Developing a Work Voice"},
    "OCSP Study": {"action": "in_place", "folder": MNT / "OCSP Study"},
    "Personal - Workspace": {"action": "in_place", "folder": MNT / "Personal - Workspace"},
    "Vendor Setup for Heaven on earth": {"action": "in_place", "folder": MNT / "Vendor Setup for Heaven on earth"},
    "VulScan Analysis [imported-archive]": {"action": "catchall_subfolder", "folder_name": "VulScan Analysis [imported-archive]"},
}

EXT_MAP = {
    "text/markdown": ".md",
    "text/html": ".html",
    "image/svg+xml": ".svg",
    "application/vnd.ant.mermaid": ".mermaid",
    "application/vnd.ant.react": ".jsx",
}
LANG_EXT_MAP = {
    "javascript": ".js", "typescript": ".ts", "python": ".py",
    "powershell": ".ps1", "bash": ".sh", "html": ".html", "css": ".css",
    "json": ".json", "yaml": ".yml", "xml": ".xml", "sql": ".sql",
    "go": ".go", "rust": ".rs", "c": ".c", "cpp": ".cpp", "java": ".java",
}
BINARY_EXTS = {".docx", ".xlsx", ".pdf", ".pptx", ".png", ".jpg", ".jpeg", ".zip", ".tar", ".gz", ".xml"}


def safe_name(s, maxlen=80):
    s = re.sub(r"[^\w\-\.\[\] ]", "_", s or "")
    return s[:maxlen].strip()


def conv_slug_from_transcript(transcript_filename):
    """Get the slug (filename minus .md extension)."""
    return Path(transcript_filename).stem


def artifact_ext(atype, language=""):
    """Pick an extension for an inline artifact."""
    if atype in EXT_MAP:
        return EXT_MAP[atype]
    if atype == "application/vnd.ant.code":
        return LANG_EXT_MAP.get((language or "").lower(), ".code")
    return ".txt"


def collect_inline_artifacts(conv):
    """Return list of (basename, content) tuples for one conversation.
    Combines tool_use:artifacts + tool_use:create_file inline content."""
    out = []
    seen_basenames = {}  # basename -> count, for dedup
    for m in conv.get("chat_messages", []) or []:
        for b in m.get("content", []) or []:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            nm = b.get("name", "")
            inp = b.get("input", {}) or {}
            content = None
            basename = None
            if nm == "artifacts":
                content = inp.get("content", "") or ""
                if not content:
                    continue
                title = inp.get("title", "") or "untitled-artifact"
                ext = artifact_ext(inp.get("type", ""), inp.get("language", ""))
                basename = safe_name(title) + ext
            elif nm == "create_file":
                content = inp.get("file_text", "") or ""
                if not content:
                    continue
                path = inp.get("path", "") or ""
                if path:
                    basename = safe_name(path.split("/")[-1].split("\\")[-1])
                else:
                    basename = "untitled-file.txt"
            else:
                continue
            # Dedup
            if basename in seen_basenames:
                seen_basenames[basename] += 1
                name_root, _, ext = basename.rpartition(".")
                if name_root:
                    basename = f"{name_root}_v{seen_basenames[basename]}.{ext}"
                else:
                    basename = f"{basename}_v{seen_basenames[basename]}"
            else:
                seen_basenames[basename] = 1
            out.append((basename, content))
    return out


def collect_binary_refs(conv, inline_basenames):
    """Return list of (basename, conversation_filepath, count) for binary present_files
    references not backed by inline extraction."""
    counts = defaultdict(int)
    paths_seen = {}
    for m in conv.get("chat_messages", []) or []:
        for b in m.get("content", []) or []:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            if b.get("name") != "present_files":
                continue
            inp = b.get("input", {}) or {}
            for p in inp.get("filepaths", []) or []:
                if not p:
                    continue
                basename = p.split("/")[-1].split("\\")[-1]
                ext = "." + basename.rsplit(".", 1)[-1].lower() if "." in basename else ""
                if ext not in BINARY_EXTS:
                    continue
                if basename in inline_basenames:
                    continue
                counts[basename] += 1
                paths_seen[basename] = p
    return [(b, paths_seen[b], counts[b]) for b in counts]


def write_artifacts(conv_dest_folder, conv_slug, inline_arts):
    """Write inline artifacts into conv-slug/artifacts/ under the destination folder."""
    if not inline_arts:
        return None
    artifacts_dir = conv_dest_folder / conv_slug / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    for basename, content in inline_arts:
        (artifacts_dir / basename).write_text(content, encoding="utf-8")
    return artifacts_dir


def get_opener(conv):
    for m in conv.get("chat_messages", []):
        if m.get("sender") == "human":
            t = (m.get("text") or "").strip()
            if not t:
                for b in m.get("content", []) or []:
                    if isinstance(b, dict) and b.get("type") == "text":
                        t = (b.get("text") or "").strip()
                        if t:
                            break
            if t:
                return t.replace("\n", " ")[:100]
    return ""


# ---- Step 1: reshape catch-all subfolders ----
def reshape_catchall_subfolder(subfolder_name):
    """Move existing transcripts + INDEX.md into a conversation-history/ subfolder."""
    folder = CATCHALL / subfolder_name
    if not folder.exists():
        print(f"  skipping (not found): {folder}")
        return
    ch = folder / "conversation-history"
    ch.mkdir(exist_ok=True)
    moved = 0
    for f in folder.iterdir():
        if f.is_dir():
            continue
        if f.name == "_MIGRATION_NOTE.md":
            continue
        # transcripts and INDEX.md go into conversation-history/
        dest = ch / f.name
        if dest.exists():
            # Already there; remove src duplicate (try)
            try:
                f.unlink()
            except OSError:
                pass
        else:
            try:
                shutil.move(str(f), str(dest))
                moved += 1
            except OSError:
                # Can't move? copy + best-effort unlink
                shutil.copy2(str(f), str(dest))
                try:
                    f.unlink()
                except OSError:
                    pass
                moved += 1
    print(f"  {subfolder_name}: moved {moved} files into conversation-history/")


# ---- Step 2-4: main flow ----
def main():
    # Load data
    manifest = {r["uuid"]: r for r in csv.DictReader(open(CONV_CSV, encoding="utf-8"))}
    attribution = {r["uuid"]: r for r in csv.DictReader(open(ATTR_CSV, encoding="utf-8"))}
    with open(EXPORT_CONV, encoding="utf-8") as f:
        all_convs = {c["uuid"]: c for c in json.load(f)}

    print("=== Step 1: reshape catch-all subfolders ===")
    for project_name, route in ROUTING.items():
        if route["action"] == "catchall_subfolder":
            reshape_catchall_subfolder(route["folder_name"])

    print()
    print("=== Step 2: extract artifacts per conversation ===")
    recovery_entries = []  # list of dicts for the _ARTIFACTS_TO_RECOVER.md
    artifact_summary = defaultdict(lambda: {"convs": 0, "files": 0})

    for cuuid, conv in all_convs.items():
        m = manifest.get(cuuid)
        if not m:
            continue
        attr = attribution.get(cuuid, {})
        project = attr.get("project_assignment", "")
        in_allchats = attr.get("in_allchats", "no")

        # Determine destination conversation-history/ folder
        if in_allchats != "yes":
            continue  # dropped — skip
        if project and project in ROUTING:
            route = ROUTING[project]
            if route["action"] == "in_place":
                dest_ch = route["folder"] / "conversation-history"
            else:
                dest_ch = CATCHALL / route["folder_name"] / "conversation-history"
            dest_class = project
        elif not project:
            dest_ch = CATCHALL / "unattributed-conversations"
            dest_class = "(orphan)"
        else:
            continue  # unknown attribution; skip

        # Collect artifacts + binary refs
        inline_arts = collect_inline_artifacts(conv)
        inline_basenames = {b for b, _ in inline_arts}
        binary_refs = collect_binary_refs(conv, inline_basenames)

        if not inline_arts and not binary_refs:
            continue

        transcript_file = Path(m["transcript_file"]).name
        conv_slug = conv_slug_from_transcript(transcript_file)

        if inline_arts:
            write_artifacts(dest_ch, conv_slug, inline_arts)
            artifact_summary[dest_class]["convs"] += 1
            artifact_summary[dest_class]["files"] += len(inline_arts)

        for basename, src_path, count in binary_refs:
            recovery_entries.append({
                "conv_uuid": cuuid,
                "conv_name": conv.get("name", "") or "(untitled)",
                "transcript_file": transcript_file,
                "dest_class": dest_class,
                "basename": basename,
                "src_path": src_path,
                "ref_count": count,
            })

    print(f"  Inline artifact extraction by destination:")
    for k, v in sorted(artifact_summary.items()):
        print(f"    {k:50s}  {v['convs']} convs, {v['files']} files")
    print(f"  Binary refs for manual recovery: {len(recovery_entries)}")

    # ---- Step 3: build _ARTIFACTS_TO_RECOVER.md ----
    print()
    print("=== Step 3: build _ARTIFACTS_TO_RECOVER.md ===")
    build_recovery_md(recovery_entries)
    print(f"  wrote {CATCHALL / '_ARTIFACTS_TO_RECOVER.md'}")

    # ---- Step 4: regenerate INDEX.md files for catch-all subfolders ----
    print()
    print("=== Step 4: regenerate INDEX.md for catch-all subfolders + reconstructed projects ===")
    regenerate_all_indexes(manifest, all_convs, attribution)


def build_recovery_md(entries):
    """Write the recovery manifest grouped by destination class then conversation."""
    # Dedup: same (conv_uuid, basename) → one row
    seen = set()
    unique = []
    for e in entries:
        k = (e["conv_uuid"], e["basename"])
        if k in seen:
            continue
        seen.add(k)
        unique.append(e)

    # Group by dest_class
    by_dest = defaultdict(list)
    for e in unique:
        by_dest[e["dest_class"]].append(e)

    # Order: reconstructed projects (alphabetical), catch-all subfolders (alphabetical), orphans last
    in_place_classes = sorted(k for k, v in by_dest.items() if k != "(orphan)" and ROUTING.get(k, {}).get("action") == "in_place")
    catchall_classes = sorted(k for k, v in by_dest.items() if k != "(orphan)" and ROUTING.get(k, {}).get("action") == "catchall_subfolder")
    orphan_class = ["(orphan)"] if "(orphan)" in by_dest else []
    ordered = in_place_classes + catchall_classes + orphan_class

    lines = [
        "# Artifacts to recover manually",
        "",
        "These files were produced by Claude during your conversations on claude.ai,",
        "but their **binary contents are not in your data export** — only the",
        "references to them are. To preserve them:",
        "",
        "1. Open each conversation on claude.ai while your old account still exists.",
        "2. Find the file in the conversation's file panel and download it.",
        "3. Save it next to the conversation's transcript on disk and tick the box.",
        "",
        "If you don't recover them before your old account is deleted, **they will",
        "be lost permanently**. If a build script for the file is included in the",
        "transcript (typical for `.docx` / `.xlsx` generated by `create_file` +",
        "`bash_tool`), you can regenerate the file by running that script locally.",
        "",
        f"Total files to recover: **{len(unique)}**",
        "",
    ]

    for cls in ordered:
        rows = sorted(by_dest[cls], key=lambda e: (e["conv_name"], e["basename"]))
        if cls == "(orphan)":
            lines.append(f"## Orphan conversations (unattributed) — {len(rows)} files")
            lines.append("")
            lines.append("Each lives next to its transcript in")
            lines.append("`Migrated Conversation History/unattributed-conversations/`.")
        elif ROUTING.get(cls, {}).get("action") == "in_place":
            lines.append(f"## {cls} — {len(rows)} files")
            lines.append("")
            lines.append(f"Reconstructed project folder: `{cls}/`. Each file's transcript lives in `conversation-history/`.")
        else:
            lines.append(f"## {cls} — {len(rows)} files")
            lines.append("")
            lines.append(f"Catch-all subfolder: `Migrated Conversation History/{cls}/conversation-history/`.")
        lines.append("")
        # Group by conversation
        by_conv = defaultdict(list)
        for r in rows:
            by_conv[(r["conv_name"], r["transcript_file"])].append(r)
        for (conv_name, tfile), files in sorted(by_conv.items()):
            lines.append(f"### {conv_name}")
            lines.append(f"  Transcript: `{tfile}`")
            lines.append("")
            for r in files:
                ref_note = f" ({r['ref_count']}× referenced)" if r["ref_count"] > 1 else ""
                lines.append(f"- [ ] `{r['basename']}`{ref_note}")
            lines.append("")
        lines.append("")

    (CATCHALL / "_ARTIFACTS_TO_RECOVER.md").write_text("\n".join(lines), encoding="utf-8")


def write_index(path, conv_rows, manifest, all_convs):
    lines = [
        "# Conversation history index",
        "",
        "| # | Time | Conversation | Msgs | Artifacts | Opens with |",
        "|---|------|--------------|-----:|-----------|------------|",
    ]
    for i, r in enumerate(conv_rows, 1):
        name = r["name"] or "(untitled)"
        ts = r["created_at"][:16].replace("T", " ") if r["created_at"] else ""
        # Check if conv has an artifacts subfolder
        conv_slug = Path(r["filename"]).stem
        artifacts_marker = ""
        artifact_subfolder = path.parent / conv_slug / "artifacts"
        if artifact_subfolder.exists():
            n = len(list(artifact_subfolder.iterdir()))
            artifacts_marker = f"[{n}]({conv_slug}/artifacts/)"
        opener = r.get("opener", "")
        opener_disp = opener[:80] + ("…" if len(opener) > 80 else "")
        name_esc = name.replace("|", "\\|")
        opener_esc = opener_disp.replace("|", "\\|")
        lines.append(
            f"| {i} | {ts} | [{name_esc}]({r['filename']}) | "
            f"{r['messages']} | {artifacts_marker} | {opener_esc} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def regenerate_all_indexes(manifest, all_convs, attribution):
    """Rewrite every INDEX.md in the reconstructed projects + catch-all subfolders + orphans."""
    # Group conv_uuids by destination
    dest_uuids = defaultdict(list)
    for cuuid, attr in attribution.items():
        if attr["in_allchats"] != "yes":
            continue
        project = attr["project_assignment"]
        if project and project in ROUTING:
            r = ROUTING[project]
            if r["action"] == "in_place":
                dest = ("in_place", r["folder"])
            else:
                dest = ("catchall", CATCHALL / r["folder_name"])
            dest_uuids[dest].append(cuuid)
        elif not project:
            dest_uuids[("orphan", CATCHALL / "unattributed-conversations")].append(cuuid)

    for (kind, base_dir), uuids in dest_uuids.items():
        if kind == "in_place":
            ch = base_dir / "conversation-history"
        elif kind == "catchall":
            ch = base_dir / "conversation-history"
        else:
            ch = base_dir
        ch.mkdir(parents=True, exist_ok=True)
        rows = []
        for u in uuids:
            m = manifest.get(u)
            if not m:
                continue
            tfile = Path(m["transcript_file"]).name
            rows.append({
                "name": m.get("name", ""),
                "created_at": m.get("created_at", ""),
                "messages": m.get("messages", ""),
                "filename": tfile,
                "opener": get_opener(all_convs.get(u, {})),
            })
        rows.sort(key=lambda r: r["created_at"])
        write_index(ch / "INDEX.md", rows, manifest, all_convs)
        print(f"  wrote {ch / 'INDEX.md'}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
    print("\nDone.")
