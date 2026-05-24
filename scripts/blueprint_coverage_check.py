#!/usr/bin/env python3
"""blueprint_coverage_check.py — End-of-Track-A coverage check.

Verifies that every project folder passed in has a
<project>/transition-data/project-blueprint.md on disk. Surfaces any
missing blueprints so the user knows to regenerate them before
proceeding to Track B (the relink step) or deleting the source account.

Invoked by SKILL.md at the end of Track A: pass every project folder the
walk-through touched (Part 1 reconstructed-from-export at <outdir>/<name>,
plus Part 2 Cowork-native at their user-selected paths). Exit code 0 if
all present, 1 if any missing.

Usage:

    python3 blueprint_coverage_check.py <project-dir> [<project-dir> ...]
    python3 blueprint_coverage_check.py --folders-file <list.txt>

Where:
    <project-dir>      One or more project folders to check (positional).
    --folders-file     Optional path to a text file with one project
                       folder per line. Combined with any positional args.
                       Useful for batched orchestrator invocations.
"""

import argparse
import sys
from pathlib import Path


BLUEPRINT_REL_PATH = Path("transition-data") / "project-blueprint.md"


def check_folder(project_dir: Path):
    """Return (status, blueprint_path) for a single project folder.

    status is one of:
        'ok'              — folder exists and contains the blueprint
        'missing'         — folder exists but no blueprint inside
        'missing-folder'  — the project folder itself doesn't exist
    """
    if not project_dir.exists():
        return ("missing-folder", project_dir / BLUEPRINT_REL_PATH)
    if not project_dir.is_dir():
        return ("missing-folder", project_dir / BLUEPRINT_REL_PATH)
    blueprint = project_dir / BLUEPRINT_REL_PATH
    if blueprint.is_file():
        return ("ok", blueprint)
    return ("missing", blueprint)


def read_folders_file(path):
    """Read a list of project folders from a text file (one per line,
    blanks and # comments skipped)."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(Path(line))
    return out


def main():
    ap = argparse.ArgumentParser(
        description=("End-of-Track-A coverage check: verify each project "
                     "has transition-data/project-blueprint.md on disk."))
    ap.add_argument("project_dirs", nargs="*", type=Path,
                    help="Project folders to check (one or more).")
    ap.add_argument("--folders-file", type=Path, default=None,
                    help="Optional path to a text file with one project "
                         "folder per line; merged with positional args.")
    args = ap.parse_args()

    folders = list(args.project_dirs)
    if args.folders_file:
        if not args.folders_file.is_file():
            print(f"ERROR: --folders-file does not exist: {args.folders_file}",
                  file=sys.stderr)
            return 2
        folders.extend(read_folders_file(args.folders_file))

    if not folders:
        print("ERROR: no project folders provided (positional or "
              "--folders-file).", file=sys.stderr)
        return 2

    ok = []
    missing = []
    missing_folder = []
    for project_dir in folders:
        project_dir = project_dir.resolve()
        status, blueprint = check_folder(project_dir)
        if status == "ok":
            ok.append((project_dir, blueprint))
        elif status == "missing":
            missing.append((project_dir, blueprint))
        else:
            missing_folder.append((project_dir, blueprint))

    # Report summary.
    print(f"Blueprint coverage check — {len(folders)} folder(s) inspected")
    print()
    if ok:
        print(f"Present ({len(ok)}):")
        for p, _ in ok:
            print(f"  ✓ {p.name}")
        print()

    if missing or missing_folder:
        print(f"MISSING ({len(missing) + len(missing_folder)}):")
        for p, b in missing:
            print(f"  ✗ {p.name}  (blueprint not at {b})")
        for p, b in missing_folder:
            print(f"  ✗ {p.name}  (project folder itself not found at {p})")
        print()
        print("Before proceeding to Track B (or deleting the source account):")
        print("  - For each missing Part 1 project, re-run "
              "generate_blueprint.py --type part1 against its folder.")
        print("  - For each missing Part 2 project, dump that project's "
              "memory + session transcripts on the source side first, then "
              "re-run generate_blueprint.py --type part2 against its folder.")
        return 1

    print("All blueprints present. Ready for Track B.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
