#!/usr/bin/env python3
"""export_custom_skills.py — Repackage user-installed custom skills as `.skill`
files so they travel with the migration hub.

Reads installed-skill source folders from a Cowork installed-skills root
(typically the read-only `.claude/skills/` mount in the sandbox; the user's
actual installed-skill source lives there), filters out the bundled
`anthropic-skills` plugin members and the migration skill itself, and writes
one `.skill` (zip) archive per remaining custom skill into the specified
output folder.

The installed-skill source is read-only on disk, but Python's `zipfile`
module can copy file contents through to a sandbox-writable destination — no
permission concern; we don't modify the source.

Usage:

    python3 export_custom_skills.py \\
        --skills-root <path-to-installed-skills>   (required)
        --out-dir     <hub-skills-folder>          (where to place .skill files)
        [--exclude    <name>]                      (additional names to skip; repeatable)
        [--include-bundled]                        (rare; include anthropic-skills members)

Bundled `anthropic-skills` plugin members that are always excluded (these
re-install automatically with Cowork on the new account — no need to migrate):

    docx, pdf, pptx, xlsx, schedule, setup-cowork, skill-creator,
    consolidate-memory

The `account-migration` skill is also always excluded — it's exported
separately by `package_self.py` in SKILL.md Step 3.5 sub-step 1, against the
hub's source tree rather than the installed copy, to ensure a byte-faithful
rebuild.

Output:

    <out-dir>/<skill-name>.skill   (zip archive containing SKILL.md plus any
                                    subfolders like assets/, references/,
                                    scripts/, with the skill-name as the root
                                    folder inside the zip)

Returns a brief summary on stdout:

    Exported <N> custom skill(s) to <out-dir>:
      - <name>.skill (<size> bytes)
      - ...

    Skipped <N> bundled/excluded skill(s): <comma-list>
"""

import argparse
import os
import sys
import zipfile
from pathlib import Path


# Known anthropic-skills plugin members. These ship with Cowork and are
# re-installed automatically on the new account — no need to export. If this
# list goes stale (Anthropic adds new bundled skills), the export will
# unnecessarily include them — harmless but worth knowing.
ANTHROPIC_BUNDLED_SKILLS = {
    "docx",
    "pdf",
    "pptx",
    "xlsx",
    "schedule",
    "setup-cowork",
    "skill-creator",
    "consolidate-memory",
}

# The migration skill is exported separately by package_self.py against the
# hub source tree (Step 3.5 sub-step 1), so skip it here even though it's
# installed and visible in the skills root.
ALWAYS_EXCLUDE = {"account-migration"}


def package_skill_to_zip(skill_dir, out_path):
    """Walk skill_dir recursively and zip every file into out_path.

    The archive's internal root is `<skill_name>/...`, matching what Cowork's
    skill installer expects.
    """
    skill_name = skill_dir.name
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(skill_dir):
            for f in files:
                full = Path(root) / f
                rel = full.relative_to(skill_dir)
                arcname = f"{skill_name}/{rel.as_posix()}"
                try:
                    zf.write(full, arcname)
                except (OSError, PermissionError) as e:
                    # Skip individual unreadable files but don't fail the
                    # whole skill export.
                    print(f"  WARN: could not include {arcname}: {e}",
                          file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(
        description=("Export user-installed custom Cowork skills as `.skill` "
                     "files so they can be re-installed on a new account."))
    ap.add_argument("--skills-root", required=True,
                    help=("Path to the installed-skills root. In a Cowork "
                          "sandbox session, this is typically the read-only "
                          "mount at `/sessions/<sandbox>/mnt/.claude/skills/`. "
                          "Each subdirectory is one installed skill."))
    ap.add_argument("--out-dir", required=True,
                    help=("Folder to write `.skill` archives into. Typically "
                          "the hub's `skills/` subfolder."))
    ap.add_argument("--exclude", action="append", default=[],
                    help=("Additional skill names to skip. Repeatable. "
                          "Bundled `anthropic-skills` members and the "
                          "`account-migration` skill itself are excluded "
                          "automatically."))
    ap.add_argument("--include-bundled", action="store_true",
                    help=("Include `anthropic-skills` bundled members in the "
                          "export. Rare; only useful if the user customized "
                          "a bundled skill and wants to carry the customization "
                          "across."))
    args = ap.parse_args()

    skills_root = Path(args.skills_root).resolve()
    if not skills_root.is_dir():
        print(f"ERROR: --skills-root is not a directory: {skills_root}",
              file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    exclusion = set(ALWAYS_EXCLUDE) | set(args.exclude)
    if not args.include_bundled:
        exclusion |= ANTHROPIC_BUNDLED_SKILLS

    exported = []
    skipped = []
    not_a_skill = []

    for entry in sorted(skills_root.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        if name in exclusion:
            skipped.append(name)
            continue
        # A real skill folder has SKILL.md at the root. Skip anything else
        # (in case the installer leaves auxiliary folders around).
        if not (entry / "SKILL.md").is_file():
            not_a_skill.append(name)
            continue
        out_path = out_dir / f"{name}.skill"
        try:
            package_skill_to_zip(entry, out_path)
        except Exception as e:
            print(f"ERROR exporting {name}: {e}", file=sys.stderr)
            continue
        exported.append({"name": name, "size_bytes": out_path.stat().st_size})

    # Summary.
    print(f"Exported {len(exported)} custom skill(s) to {out_dir}:")
    for e in exported:
        print(f"  - {e['name']}.skill ({e['size_bytes']} bytes)")
    print()
    if skipped:
        print(f"Skipped {len(skipped)} bundled/excluded skill(s): "
              f"{', '.join(skipped)}")
    if not_a_skill:
        print(f"Skipped {len(not_a_skill)} entr(y/ies) without SKILL.md: "
              f"{', '.join(not_a_skill)}")
    if not exported:
        print("No custom skills found to export. (Bundled `anthropic-skills` "
              "members re-install automatically on the new account.)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
