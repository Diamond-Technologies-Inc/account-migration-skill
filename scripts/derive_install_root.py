#!/usr/bin/env python3
"""derive_install_root.py — self-determine the Cowork install root and the four
identifying UUIDs (account / install / space / session) by reading the sandbox
mount table.

Background. Cowork sessions run inside a Linux sandbox; the host filesystem is
exposed through virtiofs mounts. Each mounted folder's SOURCE (visible via
`findmnt`) spells out the real host path, including all the UUIDs that the
session JSON files live under. That makes the install root self-discoverable
without asking the user for any UUID and without depending on canonical
install-path conventions — the mount table tells us where the install
actually lives on this user's machine, whatever shape that takes.

Two stable mounts carry the data we need:
  - `.auto-memory` → `.../local-agent-mode-sessions/<account>/<install>/spaces/<space>/memory`
  - `outputs`      → `.../local-agent-mode-sessions/<account>/<install>/local_<session>/outputs`

Together these yield account, install, space, AND the current session id.

Path translation rules:
  - Windows:  /mnt/.virtiofs-root/shared/c/Users/...        → C:\\Users\\...
  - Mac:      (TBD — Mac mount source format unconfirmed on a real Cowork
              session as of v1.5; this script will detect "no drive letter" and
              attempt the Mac translation; downstream code should treat the
              host_os field with caution until a Mac run validates the rule.)

Usage:
    python3 derive_install_root.py                       # prints JSON
    python3 derive_install_root.py --pretty              # human-readable
    python3 derive_install_root.py --memory-mount PATH   # override (default: auto)
    python3 derive_install_root.py --outputs-mount PATH  # override (default: auto)

Exits non-zero (with a stderr message) when:
  - findmnt isn't available (not in a Linux sandbox with virtiofs).
  - One of the two required mounts isn't present.
  - The translated path doesn't match the expected install-root shape.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import PurePosixPath


VIRTIOFS_PREFIX = "/mnt/.virtiofs-root/shared/"

# Expected install-root shape after the install UUID:
#   <base>/local-agent-mode-sessions/<account>/<install>/spaces/<space>/memory
#   <base>/local-agent-mode-sessions/<account>/<install>/local_<session>/outputs
SESSIONS_SEGMENT = "local-agent-mode-sessions"

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SESSION_DIR_RE = re.compile(r"^local_([0-9a-f-]+)$")


def find_default_mount(suffix):
    """Walk /sessions/*/mnt/<suffix> looking for an existing directory.

    Sandbox mount roots look like /sessions/<sandbox-name>/mnt/<suffix>. The
    sandbox-name is the three-word "adjective-adjective-scientist" string and
    is per-session, so we don't hardcode it.
    """
    base = "/sessions"
    if not os.path.isdir(base):
        return None
    for entry in os.listdir(base):
        candidate = os.path.join(base, entry, "mnt", suffix)
        if os.path.isdir(candidate):
            return candidate
    return None


def run_findmnt(target):
    if not shutil.which("findmnt"):
        raise RuntimeError("findmnt not available on PATH — not running inside "
                           "the Cowork sandbox?")
    try:
        out = subprocess.check_output(
            ["findmnt", "-n", "-o", "SOURCE", "--target", target],
            stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"findmnt failed for {target}: "
                           f"{e.output.strip()}") from e
    src = out.strip()
    if not src:
        raise RuntimeError(f"findmnt returned no SOURCE for {target}")
    return src


def detect_host_os(source):
    """Return 'windows', 'mac', or 'unknown' based on the virtiofs source shape.

    Windows mount sources start with /mnt/.virtiofs-root/shared/<drive-letter>/...
    where <drive-letter> is a single ASCII letter. Mac is TBD but expected to
    use /Users/... (no drive-letter segment).
    """
    if not source.startswith(VIRTIOFS_PREFIX):
        return "unknown"
    tail = source[len(VIRTIOFS_PREFIX):]
    first_segment = tail.split("/", 1)[0]
    if len(first_segment) == 1 and first_segment.isalpha():
        return "windows"
    # Tentative Mac heuristic: typical real-host paths begin with Users/
    # (the macOS user home root). Will need a real Mac session to confirm.
    if first_segment in {"Users", "Volumes"} or tail.startswith("Users/"):
        return "mac"
    return "unknown"


def translate_to_host(source, host_os):
    """Translate a virtiofs SOURCE to a host-native path.

    Windows: strip prefix, first segment becomes 'C:', join rest with backslashes.
    Mac:     strip prefix, join with forward slashes (no drive letter).
    Unknown: return the stripped sandbox tail as-is; caller decides what to do.
    """
    if not source.startswith(VIRTIOFS_PREFIX):
        return source
    tail = source[len(VIRTIOFS_PREFIX):]
    parts = tail.split("/")

    if host_os == "windows":
        drive = parts[0].upper() + ":"
        rest = parts[1:]
        return drive + "\\" + "\\".join(rest)

    if host_os == "mac":
        return "/" + "/".join(parts)

    return tail  # unknown — return the stripped form, no translation


def parse_uuids_from_paths(memory_src, outputs_src):
    """Parse account/install/space UUIDs and the session id from the two mount
    sources. Validate that both sources agree on account+install."""

    def split(src):
        if not src.startswith(VIRTIOFS_PREFIX):
            raise RuntimeError(f"unexpected mount source (no virtiofs prefix): {src}")
        return src[len(VIRTIOFS_PREFIX):].split("/")

    mem_parts = split(memory_src)
    out_parts = split(outputs_src)

    # Find SESSIONS_SEGMENT in each.
    def locate(parts):
        try:
            i = parts.index(SESSIONS_SEGMENT)
        except ValueError:
            raise RuntimeError(
                f"path does not contain {SESSIONS_SEGMENT!r}: {'/'.join(parts)}")
        # After SESSIONS_SEGMENT we expect: <account>/<install>/<rest...>
        if len(parts) < i + 3:
            raise RuntimeError(
                f"path truncated after {SESSIONS_SEGMENT!r}: {'/'.join(parts)}")
        account = parts[i + 1]
        install = parts[i + 2]
        rest = parts[i + 3:]
        if not UUID_RE.match(account):
            raise RuntimeError(f"account segment doesn't look like a UUID: {account}")
        if not UUID_RE.match(install):
            raise RuntimeError(f"install segment doesn't look like a UUID: {install}")
        return account, install, rest

    mem_account, mem_install, mem_rest = locate(mem_parts)
    out_account, out_install, out_rest = locate(out_parts)

    if (mem_account, mem_install) != (out_account, out_install):
        raise RuntimeError(
            "memory and outputs mounts disagree on account/install: "
            f"memory=({mem_account},{mem_install}) outputs=({out_account},{out_install})")

    # memory rest should be: spaces/<space>/memory
    space = None
    if len(mem_rest) >= 2 and mem_rest[0] == "spaces":
        if UUID_RE.match(mem_rest[1]):
            space = mem_rest[1]
    if not space:
        raise RuntimeError(f"could not extract space UUID from memory rest: {mem_rest}")

    # outputs rest should be: local_<session>/outputs
    session_uuid = None
    session_id = None
    if len(out_rest) >= 1:
        m = SESSION_DIR_RE.match(out_rest[0])
        if m:
            session_id = out_rest[0]            # local_<...>
            session_uuid = m.group(1)           # <...> (no prefix)
    if not session_id:
        raise RuntimeError(f"could not extract session id from outputs rest: {out_rest}")

    return {
        "account_uuid": mem_account,
        "install_uuid": mem_install,
        "space_uuid": space,
        "session_uuid": session_uuid,
        "session_id": session_id,
    }


def install_root_from_memory_source(memory_src, host_os):
    """Trim a memory mount source down to .../local-agent-mode-sessions/<account>/<install>
    and translate to a host-native path."""
    tail = memory_src[len(VIRTIOFS_PREFIX):]
    parts = tail.split("/")
    try:
        i = parts.index(SESSIONS_SEGMENT)
    except ValueError:
        raise RuntimeError(f"no {SESSIONS_SEGMENT!r} in memory source: {memory_src}")
    # install-root ends at parts[i+2] (the install UUID)
    root_parts = parts[: i + 3]
    rebuilt = VIRTIOFS_PREFIX + "/".join(root_parts)
    return translate_to_host(rebuilt, host_os)


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--memory-mount", default=None,
                    help="Override the .auto-memory mount path "
                         "(default: auto-discovered via /sessions/*/mnt/.auto-memory).")
    ap.add_argument("--outputs-mount", default=None,
                    help="Override the outputs mount path "
                         "(default: auto-discovered via /sessions/*/mnt/outputs).")
    ap.add_argument("--pretty", action="store_true",
                    help="Print a human-readable summary instead of JSON.")
    args = ap.parse_args()

    memory_mount = args.memory_mount or find_default_mount(".auto-memory")
    outputs_mount = args.outputs_mount or find_default_mount("outputs")

    if not memory_mount:
        print("ERROR: could not find an .auto-memory mount under /sessions/*/mnt/.",
              file=sys.stderr)
        return 2
    if not outputs_mount:
        print("ERROR: could not find an outputs mount under /sessions/*/mnt/.",
              file=sys.stderr)
        return 2

    try:
        memory_src = run_findmnt(memory_mount)
        outputs_src = run_findmnt(outputs_mount)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    host_os = detect_host_os(memory_src)
    if detect_host_os(outputs_src) != host_os:
        print(f"WARN: memory and outputs mount sources disagree on host OS "
              f"detection — using {host_os!r} from memory source.",
              file=sys.stderr)

    try:
        ids = parse_uuids_from_paths(memory_src, outputs_src)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    install_root_host = install_root_from_memory_source(memory_src, host_os)
    install_root_sandbox = VIRTIOFS_PREFIX + "/".join(
        memory_src[len(VIRTIOFS_PREFIX):].split("/")[
            : memory_src[len(VIRTIOFS_PREFIX):].split("/").index(SESSIONS_SEGMENT) + 3
        ])

    result = {
        "host_os": host_os,
        "install_root_host": install_root_host,
        "install_root_sandbox": install_root_sandbox,
        "memory_mount_source": memory_src,
        "outputs_mount_source": outputs_src,
        **ids,
    }

    if args.pretty:
        print("Install root (host)   :", result["install_root_host"])
        print("Host OS               :", result["host_os"])
        print("Account UUID          :", result["account_uuid"])
        print("Install UUID          :", result["install_uuid"])
        print("Space UUID            :", result["space_uuid"])
        print("Session id            :", result["session_id"])
        print()
        print("Sandbox source paths (for debugging):")
        print("  memory  :", result["memory_mount_source"])
        print("  outputs :", result["outputs_mount_source"])
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
