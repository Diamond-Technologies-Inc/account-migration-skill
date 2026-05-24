#!/usr/bin/env python3
"""render_recon_script.py — turn the recon-script template into a ready-to-run
script with the install root and output path baked in.

Inputs:
  --install-root  PATH    The host install root, e.g. (Windows)
                          C:\\Users\\<u>\\AppData\\Local\\Packages\\Claude_pzs8sxrjxfjjc\\
                          LocalCache\\Roaming\\Claude\\local-agent-mode-sessions\\
                          <account>\\<install>
                          (Get this from scripts/derive_install_root.py.)
  --host-os       OS      "windows" or "mac". Selects the template.
  --out-script    PATH    Where to write the rendered script (relative or
                          absolute; the parent dir must already exist).
  --csv-output    PATH    Optional. Where the rendered script should write its
                          CSV. Defaults to "next to the rendered script itself"
                          via $PSScriptRoot (Windows) / $(dirname "${BASH_SOURCE[0]}")
                          (Mac). This makes no assumptions about the user's
                          environment — no named folders, no cloud-sync product
                          assumptions, no install-style assumptions. The CSV
                          simply lands beside the script wherever the user
                          chose to save it. If that folder refuses writes, the
                          script surfaces a clean error and the user re-runs
                          from a different folder of their choice.

Output: writes the rendered script and prints a one-line summary on stderr.

Why a separate render step (vs. just printing the script in chat).
  The skill's SKILL.md flow needs to (1) compute the right install root from
  the mount table, (2) drop the user a ready-to-run file in their hub folder,
  (3) wait for the user to come back with the CSV. Writing the file from a
  template keeps the substitution mechanical and auditable, and means we
  don't have to inline the template text in SKILL.md.
"""

import argparse
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent     # skill-source/account-migration/
ASSETS = REPO / "assets"

TEMPLATES = {
    "windows": ASSETS / "recon-script-windows.ps1.template",
    "mac":     ASSETS / "recon-script-mac.sh.template",
}

# Default: write the CSV next to the rendered script itself. Works on both
# OSes and follows the script wherever the user copies it. NOTE: the templates
# already wrap these in quotes (`$out = "..."` in PowerShell, `OUT="..."` in
# bash), so the values below must NOT include outer quotes — they drop into
# the existing quoted assignment as-is.
DEFAULT_CSV_OUTPUT = {
    "windows": r"$PSScriptRoot\sessions-recon.csv",
    "mac":     r'$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sessions-recon.csv',
}


def render(template_text, install_root, csv_output):
    """Substitute the two placeholders. Hard error if either is left over."""
    rendered = (template_text
                .replace("{{BASE_PATH}}", install_root)
                .replace("{{OUTPUT_CSV}}", csv_output))
    if "{{BASE_PATH}}" in rendered or "{{OUTPUT_CSV}}" in rendered:
        raise RuntimeError("template still has unreplaced placeholders after "
                           "substitution — check the template file.")
    return rendered


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--install-root", required=True,
                    help="Host install root path (from derive_install_root.py).")
    ap.add_argument("--host-os", required=True, choices=sorted(TEMPLATES),
                    help="Selects which template to render.")
    ap.add_argument("--out-script", required=True,
                    help="Where to write the rendered script.")
    ap.add_argument("--csv-output", default=None,
                    help="Where the rendered script will write its CSV. "
                         "Defaults to a Downloads-folder path appropriate for "
                         "the host OS.")
    args = ap.parse_args()

    template_path = TEMPLATES[args.host_os]
    if not template_path.exists():
        print(f"ERROR: template not found: {template_path}", file=sys.stderr)
        return 2

    csv_output = args.csv_output or DEFAULT_CSV_OUTPUT[args.host_os]

    template_text = template_path.read_text(encoding="utf-8")
    try:
        rendered = render(template_text, args.install_root, csv_output)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    out_script = Path(args.out_script)
    out_script.parent.mkdir(parents=True, exist_ok=True)
    out_script.write_text(rendered, encoding="utf-8")

    # Best-effort chmod +x on the Mac template (Windows .ps1 doesn't need it).
    if args.host_os == "mac":
        try:
            out_script.chmod(0o755)
        except OSError:
            pass

    print(f"Rendered {args.host_os} recon script -> {out_script}",
          file=sys.stderr)
    print(f"  Install root baked in: {args.install_root}", file=sys.stderr)
    print(f"  CSV will land at     : {csv_output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
