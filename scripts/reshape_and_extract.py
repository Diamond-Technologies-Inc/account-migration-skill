#!/usr/bin/env python3
"""reshape_and_extract.py — post-reconstruction polish for the per-project
destination layouts.

Runs after reconstruct.py. Does four things:

1. Reshape catch-all per-project subfolders so transcripts live under
   conversation-history/ (mirrors the reconstructed-project layout).
2. Extract inline artifacts (tool_use:artifacts + tool_use:create_file)
   from each conversation into per-conversation <conv-slug>/artifacts/
   folders.
3. Build _ARTIFACTS_TO_RECOVER.md at the catch-all root listing binary
   present_files references whose contents are not in the export
   (.docx, .xlsx, .pdf, .pptx, .png, .jpg, .zip, .tar, .gz, .xml).
4. Regenerate INDEX.md files for every destination folder so they pick
   up the new artifact subfolders and any other layout updates.

Like reconstruct.py, this script accepts all paths as CLI arguments and
reads its routing decisions from a JSON file. The same routing JSON
schema as reconstruct.py — see that module's docstring for the schema.
The 'action' values must be 'reconstruct_in_place' or 'route_to_catchall'.

Usage:

    python3 reshape_and_extract.py \\
        --extracted   <path>   \\
        --attribution <path>   \\
        --export      <path>   \\
        --routing     <path>   \\
        --outdir      <path>   \\
        [--catchall-name <name>]

Where:
    --extracted    extract_export.py outdir (for conversations_manifest.csv).
    --attribution  Path to attribution_map.csv (from parse_allchats.py).
    --export       Unzipped export root (must contain conversations.json).
    --routing      Path to the routing JSON file.
    --outdir       Destination root (where reconstruct.py wrote projects).
    --catchall-name  Folder name for the catch-all project at the destination.
                     Default: "Migrated Conversation History".
"""

import argparse
import csv
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


DEFAULT_CATCHALL_NAME = "Migrated Conversation History"

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
BINARY_EXTS = {".docx", ".xlsx", ".pdf", ".pptx", ".png", ".jpg",
               ".jpeg", ".zip", ".tar", ".gz", ".xml"}

# Heredoc pattern: matches `cat <<[-]['"]DELIM['"] > path` followed by the
# heredoc body and a line containing only the matching DELIM. Quoted and
# unquoted delimiters are both supported; the optional `-` indents.
# Group 1: delimiter; Group 2: output path; Group 3: heredoc body.
HEREDOC_RE = re.compile(
    r"cat\s*<<-?\s*['\"]?(\w+)['\"]?\s*>\s*(\S+)[^\n]*\n(.*?)\n\s*\1\s*$",
    re.DOTALL | re.MULTILINE,
)

# `tee path` (or `tee -a path`) — content was written but lives in the
# command's stdin, not inline. Capture the output path only.
TEE_RE = re.compile(
    r"\btee\s+(?:-a\s+)?(\S+\.[a-zA-Z0-9]+)\b",
)

# Plain `> path.ext` redirect that isn't part of a heredoc — captured for
# the recovery manifest. The lookbehind avoids matching `<<` openers and
# `2>` / `&>` style redirects.
REDIRECT_RE = re.compile(
    r"(?<![<>&\d])>\s+(\S+\.[a-zA-Z0-9]+)\b",
)

# Marker the transcript renderer inserts when content was truncated.
TRUNCATION_MARKER = "[Omitted long matching line]"


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
    """Return list of (basename, conversation_filepath, count) for binary
    present_files references not backed by inline extraction."""
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


def collect_bash_heredoc_artifacts(conv):
    """Return list of (basename, content) for bash heredoc patterns that
    wrote content to a file inline (cat <<EOF > path ... EOF).

    Truncated heredocs (where the renderer inserted the truncation marker
    inside the bash command) are NOT returned here — they go through
    collect_bash_non_heredoc_refs as recovery entries instead.
    """
    out = []
    seen_basenames = {}
    for m in conv.get("chat_messages", []) or []:
        for b in m.get("content", []) or []:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            if b.get("name") != "bash":
                continue
            inp = b.get("input", {}) or {}
            command = inp.get("command", "") or ""
            if not command:
                continue
            for match in HEREDOC_RE.finditer(command):
                output_path = match.group(2)
                body = match.group(3)
                if TRUNCATION_MARKER in body:
                    # Truncated — skip; the non-heredoc collector will flag it.
                    continue
                basename = safe_name(
                    output_path.split("/")[-1].split("\\")[-1])
                if not basename:
                    basename = "bash-heredoc-output"
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
                out.append((basename, body))
    return out


def collect_bash_non_heredoc_refs(conv, inline_basenames):
    """Return list of (basename, command_excerpt, count) for bash patterns
    that wrote content to a file but the content isn't recoverable from the
    transcript:
        - `tee path` (content was stdin, not in the bash command itself)
        - `> path.ext` redirects (content was a previous command's stdout)
        - heredocs whose body was truncated in the transcript

    These go into _ARTIFACTS_TO_RECOVER.md so the user knows what to retrieve
    manually from claude.ai before the source account is deleted.
    """
    counts = defaultdict(int)
    commands_seen = {}
    for m in conv.get("chat_messages", []) or []:
        for b in m.get("content", []) or []:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            if b.get("name") != "bash":
                continue
            inp = b.get("input", {}) or {}
            command = inp.get("command", "") or ""
            if not command:
                continue

            # Heredocs whose body was truncated.
            for match in HEREDOC_RE.finditer(command):
                output_path = match.group(2)
                body = match.group(3)
                if TRUNCATION_MARKER not in body:
                    continue
                basename = safe_name(
                    output_path.split("/")[-1].split("\\")[-1])
                if basename and basename not in inline_basenames:
                    counts[basename] += 1
                    commands_seen[basename] = (
                        f"truncated heredoc -> {output_path}")

            # `tee` writes — content lives in stdin, never in the command.
            for match in TEE_RE.finditer(command):
                output_path = match.group(1)
                basename = safe_name(
                    output_path.split("/")[-1].split("\\")[-1])
                if basename and basename not in inline_basenames:
                    counts[basename] += 1
                    commands_seen[basename] = f"tee -> {output_path}"

            # Plain `> path.ext` redirects — only flag if we haven't already
            # captured this path as an intact heredoc (heredoc match would
            # have produced an `inline_basenames` entry covering it).
            # Skip lines inside fenced heredoc bodies to avoid false positives
            # (heredoc bodies often contain redirects of their own).
            command_without_heredocs = HEREDOC_RE.sub("", command)
            for match in REDIRECT_RE.finditer(command_without_heredocs):
                output_path = match.group(1)
                basename = safe_name(
                    output_path.split("/")[-1].split("\\")[-1])
                if basename and basename not in inline_basenames:
                    counts[basename] += 1
                    commands_seen.setdefault(
                        basename, f"redirect -> {output_path}")

    return [(b, commands_seen[b], counts[b]) for b in counts]


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


def reshape_catchall_subfolder(catchall_dir, subfolder_name):
    """Move existing transcripts + INDEX.md into a conversation-history/ subfolder."""
    folder = catchall_dir / subfolder_name
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


def build_recovery_md(catchall_dir, entries, routing):
    """Write the recovery manifest grouped by destination class then conversation."""
    # Dedup: same (conv_uuid, basename) -> one row
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
    in_place_classes = sorted(
        k for k in by_dest if k != "(orphan)"
        and routing.get(k, {}).get("action") == "reconstruct_in_place"
    )
    catchall_classes = sorted(
        k for k in by_dest if k != "(orphan)"
        and routing.get(k, {}).get("action") == "route_to_catchall"
    )
    orphan_class = ["(orphan)"] if "(orphan)" in by_dest else []
    ordered = in_place_classes + catchall_classes + orphan_class

    catchall_name = catchall_dir.name

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
            lines.append(f"`{catchall_name}/unattributed-conversations/`.")
        elif routing.get(cls, {}).get("action") == "reconstruct_in_place":
            folder_name = routing[cls].get("folder_name", cls)
            lines.append(f"## {cls} — {len(rows)} files")
            lines.append("")
            lines.append(f"Reconstructed project folder: `{folder_name}/`. "
                         f"Each file's transcript lives in `conversation-history/`.")
        else:
            folder_name = routing.get(cls, {}).get("folder_name", cls)
            lines.append(f"## {cls} — {len(rows)} files")
            lines.append("")
            lines.append(f"Catch-all subfolder: "
                         f"`{catchall_name}/{folder_name}/conversation-history/`.")
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

    (catchall_dir / "_ARTIFACTS_TO_RECOVER.md").write_text(
        "\n".join(lines), encoding="utf-8")


def write_index_with_artifacts(path, conv_rows):
    """Write an INDEX.md including an Artifacts column reflecting per-conv extraction."""
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


def regenerate_all_indexes(routing, paths):
    """Rewrite every INDEX.md in the reconstructed projects + catch-all subfolders + orphans."""
    manifest = paths["manifest"]
    all_convs = paths["all_convs"]
    attribution_full = paths["attribution_full"]
    outdir = paths["outdir"]
    catchall_dir = paths["catchall_dir"]

    # Group conv_uuids by destination
    dest_uuids = defaultdict(list)
    for cuuid, attr in attribution_full.items():
        if attr.get("in_allchats") != "yes":
            continue
        project = attr.get("project_assignment", "")
        if project and project in routing:
            r = routing[project]
            if r.get("action") == "reconstruct_in_place":
                dest = ("in_place", outdir / r["folder_name"])
            else:
                dest = ("catchall", catchall_dir / r["folder_name"])
            dest_uuids[dest].append(cuuid)
        elif not project:
            dest_uuids[("orphan",
                        catchall_dir / "unattributed-conversations")].append(cuuid)

    for (kind, base_dir), uuids in dest_uuids.items():
        if kind in ("in_place", "catchall"):
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
        write_index_with_artifacts(ch / "INDEX.md", rows)
        print(f"  wrote {ch / 'INDEX.md'}  ({len(rows)} rows)")


def main():
    ap = argparse.ArgumentParser(
        description=("Post-reconstruction polish: reshape catch-all subfolders, "
                     "extract inline artifacts, build recovery manifest, "
                     "regenerate indexes."))
    ap.add_argument("--extracted", required=True,
                    help="extract_export.py outdir (for conversations_manifest.csv).")
    ap.add_argument("--attribution", required=True,
                    help="Path to attribution_map.csv (output of parse_allchats.py).")
    ap.add_argument("--export", required=True,
                    help="Unzipped export root (must contain conversations.json).")
    ap.add_argument("--routing", required=True,
                    help="Path to the routing JSON file (same schema as reconstruct.py).")
    ap.add_argument("--outdir", required=True,
                    help="Destination root (where reconstruct.py wrote projects).")
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
        (outdir, "--outdir"),
    ]:
        if not p.exists():
            print(f"ERROR: {label} does not exist: {p}", file=sys.stderr)
            return 1

    conv_csv = extracted_dir / "conversations_manifest.csv"
    if not conv_csv.exists():
        print(f"ERROR: conversations_manifest.csv missing under --extracted: {conv_csv}",
              file=sys.stderr)
        return 1

    export_conv = export_root / "conversations.json"
    if not export_conv.exists():
        print(f"ERROR: conversations.json missing under --export: {export_conv}",
              file=sys.stderr)
        return 1

    catchall_dir = outdir / args.catchall_name

    # Load data.
    with open(conv_csv, encoding="utf-8") as f:
        manifest = {r["uuid"]: r for r in csv.DictReader(f)}
    with open(attribution_csv, encoding="utf-8") as f:
        attribution_full = {r["uuid"]: r for r in csv.DictReader(f)}
    with open(export_conv, encoding="utf-8") as f:
        all_convs = {c["uuid"]: c for c in json.load(f)}
    with open(routing_json, encoding="utf-8") as f:
        routing = json.load(f)

    paths = {
        "outdir": outdir,
        "catchall_dir": catchall_dir,
        "extracted_dir": extracted_dir,
        "manifest": manifest,
        "attribution_full": attribution_full,
        "all_convs": all_convs,
    }

    # Step 1: reshape catch-all subfolders
    print("=== Step 1: reshape catch-all subfolders ===")
    for project_name, route in routing.items():
        if route.get("action") == "route_to_catchall":
            reshape_catchall_subfolder(catchall_dir, route["folder_name"])

    # Step 2: extract artifacts per conversation
    print()
    print("=== Step 2: extract artifacts per conversation ===")
    recovery_entries = []
    artifact_summary = defaultdict(lambda: {"convs": 0, "files": 0})

    for cuuid, conv in all_convs.items():
        m = manifest.get(cuuid)
        if not m:
            continue
        attr = attribution_full.get(cuuid, {})
        project = attr.get("project_assignment", "")
        in_allchats = attr.get("in_allchats", "no")

        # Determine destination conversation-history/ folder
        if in_allchats != "yes":
            continue  # dropped — skip
        if project and project in routing:
            route = routing[project]
            if route.get("action") == "reconstruct_in_place":
                dest_ch = outdir / route["folder_name"] / "conversation-history"
            else:
                dest_ch = catchall_dir / route["folder_name"] / "conversation-history"
            dest_class = project
        elif not project:
            dest_ch = catchall_dir / "unattributed-conversations"
            dest_class = "(orphan)"
        else:
            continue  # unknown attribution; skip

        # Collect artifacts + binary refs.
        # Inline artifacts (tool_use:artifacts + tool_use:create_file) plus
        # bash heredocs that wrote their content inline (cat <<EOF > path) all
        # get extracted to the conv-slug/artifacts/ folder.
        inline_arts = collect_inline_artifacts(conv)
        bash_heredoc_arts = collect_bash_heredoc_artifacts(conv)
        # Heredoc basenames could collide with inline-artifact basenames; dedup
        # by appending _v<n> when they clash.
        existing_basenames = {b for b, _ in inline_arts}
        for basename, body in bash_heredoc_arts:
            if basename in existing_basenames:
                name_root, _, ext = basename.rpartition(".")
                n = 2
                while True:
                    candidate = (f"{name_root}_v{n}.{ext}" if name_root
                                 else f"{basename}_v{n}")
                    if candidate not in existing_basenames:
                        basename = candidate
                        break
                    n += 1
            existing_basenames.add(basename)
            inline_arts.append((basename, body))
        inline_basenames = existing_basenames

        # Recovery references: binary present_files plus bash tee/redirect/
        # truncated-heredoc cases (content not in the transcript).
        binary_refs = collect_binary_refs(conv, inline_basenames)
        bash_non_heredoc_refs = collect_bash_non_heredoc_refs(
            conv, inline_basenames)

        if not inline_arts and not binary_refs and not bash_non_heredoc_refs:
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

        for basename, command_excerpt, count in bash_non_heredoc_refs:
            recovery_entries.append({
                "conv_uuid": cuuid,
                "conv_name": conv.get("name", "") or "(untitled)",
                "transcript_file": transcript_file,
                "dest_class": dest_class,
                "basename": basename,
                "src_path": command_excerpt,
                "ref_count": count,
            })

    print("  Inline artifact extraction by destination:")
    for k, v in sorted(artifact_summary.items()):
        print(f"    {k:50s}  {v['convs']} convs, {v['files']} files")
    print(f"  Binary refs for manual recovery: {len(recovery_entries)}")

    # Step 3: build _ARTIFACTS_TO_RECOVER.md
    print()
    print("=== Step 3: build _ARTIFACTS_TO_RECOVER.md ===")
    catchall_dir.mkdir(parents=True, exist_ok=True)
    build_recovery_md(catchall_dir, recovery_entries, routing)
    print(f"  wrote {catchall_dir / '_ARTIFACTS_TO_RECOVER.md'}")

    # Step 4: regenerate INDEX.md files
    print()
    print("=== Step 4: regenerate INDEX.md for catch-all subfolders + reconstructed projects ===")
    regenerate_all_indexes(routing, paths)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
