#!/usr/bin/env python3
"""parse_recon_csv.py — load the sessions-recon CSV, group by spaceId, apply
the userSelectedFolders noise filter, and emit a structured JSON view that
the SKILL.md flow consumes downstream.

Inputs (CLI):
  --csv PATH                Path to the sessions-recon.csv the user produced
                            with the native-shell recon script.
  --own-space-id UUID       Optional. Marks the project with this spaceId as
                            `is_own_space: true` in the output. The skill uses
                            this to identify and (typically) exclude the
                            migration hub itself from the to-migrate list. Get
                            this from derive_install_root.py.
  --filter-space-id UUID    Optional. Return data for just this spaceId. Used
                            in single-project mode after the user has picked a
                            specific project.
  --out PATH                Optional. Write JSON to this file. Default: stdout.

Output: JSON with this shape:
  {
    "scan_info": {
      "source_csv": "...",
      "total_rows": N,
      "rows_with_space_id": N,
      "rows_without_space_id": N
    },
    "projects": [
      {
        "space_id": "...",
        "is_own_space": false,
        "session_count": N,
        "earliest_created_at": <epoch_ms>,
        "latest_activity_at": <epoch_ms>,
        "session_titles": ["..."],          # all titles, chronological
        "reattach_folders": ["..."],        # filtered userSelectedFolders union
        "noise_folders_filtered": ["..."],  # what we excluded, for transparency
        "name_hint": "...",                 # basename of first reattach_folder; sort key
        "sessions": [
          {
            "session_id": "...",
            "title": "...",
            "created_at": <epoch_ms>,
            "last_activity_at": <epoch_ms>,
            "is_archived": <bool>,
            "user_selected_folders": ["..."]
          },
          ...
        ]
      },
      ...
    ],
    "blank_space_sessions": [
      # session-level view for rows with no spaceId — pre-space-era sessions
      # plus orphan/utility sessions. The skill decides whether and how to
      # surface these to the user (most are utility-noise; some are early
      # project-precursor sessions that need title-level inspection).
      { ...same shape as session... },
      ...
    ]
  }

Sort order. `projects` are emitted in this order:
  1. `is_own_space: true` first (the migration hub itself, if recognized).
  2. Then alphabetical by `name_hint`, case-insensitive. `name_hint` is the
     basename of the first reattach_folder — typically the on-disk project
     folder name, which matches the Cowork project name in the vast majority
     of cases. Alphabetical sort gives the user a predictable, on-disk-like
     walk-through order; previously projects were sorted by recency, which
     was confusing run-to-run.
  3. `latest_activity_at` desc as a final tiebreaker (rarely matters; only
     when two projects share a name_hint or both have empty hints).

Noise filter for userSelectedFolders. We strip categories that are
universally not-a-project-folder:
  - empty strings
  - paths whose POSIX-or-native basename starts with `.project-cache` or
    sits below a `.project-cache` segment (Cowork's internal cache)
  - well-known scratch roots: `/tmp/...`, `\temp\...`, `\Temp\...`,
    `C:\Windows\Temp\...`, `/var/folders/...` (macOS per-user temp)
We do NOT try to filter user-environment-specific "parent of all projects"
folders (like "...\Documents\Claude\Projects" on the dev's machine) — those
vary per user. The skill surfaces both filtered and excluded folders so the
user can review in Track B before reattaching.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path


# Substrings (case-insensitive) that mark a path as definitively not a project
# folder. These are deliberately universal — no user-environment-specific
# brands or relocatable folder names.
NOISE_SUBSTRINGS = (
    ".project-cache",
    "/tmp/",
    "\\temp\\",       # Windows ...\Temp\... (any case)
    "\\windows\\temp",
    "/var/folders/",  # macOS per-user temp
)


def is_noise_folder(path):
    if not path:
        return True
    p = path.lower()
    return any(needle in p for needle in NOISE_SUBSTRINGS)


def split_folders(field):
    """The recon CSV joins userSelectedFolders with ` | `. Reverse that."""
    if not field:
        return []
    return [s.strip() for s in field.split("|") if s.strip()]


def coerce_int(val):
    if val in (None, "", "null"):
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def coerce_bool(val):
    if isinstance(val, bool):
        return val
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in {"true", "1", "yes"}:
        return True
    if s in {"false", "0", "no"}:
        return False
    return None


def row_to_session(row):
    folders = split_folders(row.get("userSelectedFolders", ""))
    return {
        "session_id":           row.get("sessionId", ""),
        "title":                row.get("title", "") or "",
        "created_at":           coerce_int(row.get("createdAt")),
        "last_activity_at":     coerce_int(row.get("lastActivityAt")),
        "is_archived":          coerce_bool(row.get("isArchived")),
        "user_selected_folders": folders,
    }


def build_project(space_id, rows, own_space_id):
    sessions = [row_to_session(r) for r in rows]
    sessions.sort(key=lambda s: s["created_at"] or 0)

    folder_union = []
    folder_seen = set()
    noise = []
    noise_seen = set()
    for s in sessions:
        for f in s["user_selected_folders"]:
            target_list, seen = (
                (noise, noise_seen) if is_noise_folder(f)
                else (folder_union, folder_seen)
            )
            if f not in seen:
                seen.add(f)
                target_list.append(f)

    earliest = min((s["created_at"] for s in sessions
                    if s["created_at"] is not None), default=None)
    latest = max((s["last_activity_at"] for s in sessions
                  if s["last_activity_at"] is not None), default=None)

    # Derive a name hint. Priority order:
    #   1. Last path component of the first non-noise reattach folder (the
    #      strongest signal — on-disk project folder name usually matches the
    #      Cowork project name).
    #   2. The first session title (a weaker signal — often the user's first
    #      question rather than the project name, but at least it's
    #      distinctive enough for the user to recognize the project in the
    #      opener list).
    #   3. "(folder unknown)" placeholder. Project still appears in the list;
    #      the orchestrator must NOT silently drop projects whose name_hint
    #      couldn't be derived — the user needs to see every project the
    #      recon found, even if Claude has to ask which one is which.
    # The name_hint also drives alphabetical sort (with the "(folder unknown)"
    # placeholder sorting to the end via leading parenthesis being late in
    # casefold order... actually leading "(" sorts BEFORE letters; that's fine,
    # it puts unknowns at the top where they're visible rather than buried).
    name_hint = ""
    if folder_union:
        first = folder_union[0]
        # Last path component, OS-agnostic — split on both backslash and forward slash.
        for sep in ("\\", "/"):
            if sep in first:
                name_hint = first.rsplit(sep, 1)[-1].strip()
                break
        if not name_hint:
            name_hint = first.strip()
    if not name_hint and sessions:
        # Fall back to first session title.
        first_title = (sessions[0].get("title") or "").strip()
        if first_title:
            name_hint = first_title
    if not name_hint:
        name_hint = "(folder unknown)"

    return {
        "space_id":              space_id,
        "is_own_space":          bool(own_space_id) and space_id == own_space_id,
        "session_count":         len(sessions),
        "earliest_created_at":   earliest,
        "latest_activity_at":    latest,
        "session_titles":        [s["title"] for s in sessions],
        "reattach_folders":      folder_union,
        "noise_folders_filtered": noise,
        "name_hint":             name_hint,
        "sessions":              sessions,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--csv", required=True, help="Path to sessions-recon.csv.")
    ap.add_argument("--own-space-id", default=None,
                    help="spaceId of the migration hub itself; the matching "
                         "project will be flagged is_own_space=true.")
    ap.add_argument("--filter-space-id", default=None,
                    help="Return data only for this spaceId.")
    ap.add_argument("--out", default=None,
                    help="Write JSON to this file. Default: stdout.")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.is_file():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        return 2

    rows = []
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(r)

    # Group by spaceId. Blank spaceId rows go into blank_space_sessions.
    by_space = {}
    blank_rows = []
    for r in rows:
        sid = (r.get("spaceId") or "").strip()
        if sid:
            by_space.setdefault(sid, []).append(r)
        else:
            blank_rows.append(r)

    # Build per-project structs.
    projects = []
    for sid, sid_rows in by_space.items():
        if args.filter_space_id and sid != args.filter_space_id:
            continue
        projects.append(build_project(sid, sid_rows, args.own_space_id))

    # Sort: own space first (if present), then alphabetically by name_hint
    # (case-insensitive). Alphabetical order makes the walk-through predictable
    # for the user — it matches the on-disk order a typical file explorer shows
    # and gives stable run-to-run expectations. latest_activity_at is preserved
    # as a final tiebreaker (descending — most recently active wins) for the
    # rare case of identical name_hints (e.g., empty hints).
    def sort_key(p):
        return (0 if p["is_own_space"] else 1,
                (p["name_hint"] or "").casefold(),
                -(p["latest_activity_at"] or 0))
    projects.sort(key=sort_key)

    # Blank-space sessions: emit unfiltered for the skill to handle. Only
    # include if no filter is in effect (single-project mode doesn't want
    # this noise).
    blank_session_view = []
    if not args.filter_space_id:
        for r in blank_rows:
            blank_session_view.append(row_to_session(r))
        blank_session_view.sort(key=lambda s: s["created_at"] or 0)

    result = {
        "scan_info": {
            "source_csv":            str(csv_path),
            "total_rows":            len(rows),
            "rows_with_space_id":    sum(1 for r in rows if (r.get("spaceId") or "").strip()),
            "rows_without_space_id": len(blank_rows),
            "filter_applied":        args.filter_space_id,
            "own_space_id":          args.own_space_id,
        },
        "projects":             projects,
        "blank_space_sessions": blank_session_view,
    }

    output = json.dumps(result, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Wrote {out_path}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
