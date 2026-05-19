#!/usr/bin/env python3
"""
package_self.py — re-package the account-migration skill from its source
folder into a fresh .skill (zip) file the user can install on the new
account.

Used by Track A's Step 3.5 (custom-skills capture) so the user doesn't
have to locate the original installer — the skill drops a fresh copy of
itself into the hub's skills/ subfolder.

Usage:
    python3 package_self.py <skill-source-folder> <output-skill-path>

Example:
    python3 package_self.py /path/to/account-migration /hub/skills/account-migration.skill

The skill-source-folder is the folder containing SKILL.md, assets/,
references/, and scripts/. The output is a .skill file (a zip archive)
with a single top-level folder named "account-migration" containing the
source files.

Exits non-zero on error and prints a diagnostic message.
"""

import os
import sys
import zipfile
from pathlib import Path


# Patterns to exclude when packaging (matches skill-creator's package_skill.py).
EXCLUDE_DIRS = {"__pycache__", "node_modules", ".git"}
EXCLUDE_GLOBS = {"*.pyc", "*.pyo"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}


def should_exclude(rel_path: Path) -> bool:
    """Return True if a path should be excluded from packaging."""
    parts = rel_path.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    name = rel_path.name
    if name in EXCLUDE_FILES:
        return True
    for pat in EXCLUDE_GLOBS:
        if Path(name).match(pat):
            return True
    return False


def package(skill_source: Path, output_path: Path) -> int:
    """Zip the skill source folder into output_path.

    The zip's top-level folder is named after skill_source.name, matching
    the .skill format Cowork expects (the skill's name is the top-level
    folder inside the zip).
    """
    if not skill_source.is_dir():
        print(f"ERROR: skill source not a directory: {skill_source}", file=sys.stderr)
        return 1

    skill_md = skill_source / "SKILL.md"
    if not skill_md.is_file():
        print(f"ERROR: no SKILL.md at {skill_md} — does not look like a skill source folder", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    top_folder = skill_source.name  # e.g., "account-migration"

    count = 0
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(skill_source):
            root_path = Path(root)
            # Filter excluded dirs in-place (os.walk respects this)
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fname in files:
                full = root_path / fname
                rel = full.relative_to(skill_source)
                if should_exclude(rel):
                    continue
                arcname = f"{top_folder}/{rel.as_posix()}"
                zf.write(full, arcname)
                count += 1

    if count == 0:
        print(f"ERROR: no files written to {output_path}", file=sys.stderr)
        return 1

    print(f"Packaged {count} file(s) from {skill_source} → {output_path}")
    return 0


def main(argv):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    skill_source = Path(argv[1]).resolve()
    output_path = Path(argv[2]).resolve()
    return package(skill_source, output_path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
