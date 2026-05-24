# Cowork memory dump prompt (source account, per project)

Run this prompt inside each project on the source account whose accumulated Cowork memory you want to carry to the destination account.

**Where this fits in the migration flow.** Cowork's per-project space memory (the rules and context Claude has accumulated about how you work in that project) is isolated per project on disk — a session running outside a project cannot reach that project's memory. The account-migration skill drives the broader migration from a hub project, but it can't reach into other projects' memories on its own. This standalone prompt is the per-project hand-off: you open each project's own Cowork session, paste the prompt, and Claude there writes the project's memory entries as individual files in the project's working folder. The destination account picks them up when you relink the project there.

**Workflow per project.**

1. Open the project's Cowork conversation on the source account.
2. Confirm Claude has access to the project's working folder. If a fresh conversation hasn't been granted access yet, grant it before continuing.
3. Paste the prompt below.
4. Claude does the dump and reports a short summary — typically 5-15 seconds.
5. Confirm the `transition-data/cowork-space-memory/` subfolder exists in the project's working folder and contains one `.md` per memory entry plus `MEMORY.md`.
6. Move to the next project.

If a project has no accumulated memory, Claude will report "No memory entries to dump" and exit cleanly. No file is written. That's a normal outcome — most projects without active multi-session work won't have anything to migrate.

If a project's working folder isn't accessible on this machine (for example, the folder lives on a different computer), Claude will report the limitation and output the entries inline in chat for you to save manually.

---

## Prompt to paste

```
Please dump this Cowork project's space memory to disk for migration
to a new account. Mechanical task — locate the memory directory,
copy each entry as an individual file, report when done.

STEP 1 — Locate the memory directory.

Use the memory directory path your environment advertises (your
system prompt's auto-memory section is the usual source). Call this
MEMORY_DIR.

If that path doesn't look right (the directory doesn't exist, or
enumerates as empty when you have reason to expect entries), fall
back: run `grep auto-memory /proc/mounts` and use the first
whitespace-delimited field of the output as the actual on-disk path.
This fallback handles rare sessions whose advertised path is stale.

Use the path syntax appropriate for your host — Windows-style for
Windows, POSIX-style for macOS or Linux. Don't translate or
reconstruct; just use what your environment hands you.

STEP 2 — Enumerate the .md files in MEMORY_DIR.

Use whatever method works in your environment (shell `ls`, file-tool
directory listing, etc.). If MEMORY_DIR contains no .md files, or
contains no MEMORY.md, report "No memory entries to dump" and stop.

STEP 3 — Copy every .md file.

For each .md file in MEMORY_DIR (including MEMORY.md itself):
  - Read it
  - Write its content verbatim to:
      <working-folder>/transition-data/cowork-space-memory/<filename>

The Write tool creates intermediate directories as needed. Capture
every .md file present, not only those listed in MEMORY.md —
orphan entries (on disk but not in the index) are migrated too.

If you don't have access to the working folder, output each entry
inline in chat (one fenced block per entry, labeled with the
filename) and report that the user needs to save them manually.

STEP 4 — Report.

Reply with a short summary, no narrative:
  - MEMORY_DIR
  - Working folder
  - **Entries copied (count)** — count of `.md` files copied EXCLUDING
    `MEMORY.md`. The blueprint uses this same definition, so reporting
    it this way keeps the count consistent across the skill flow.
  - `MEMORY.md` index — was it present and copied? (yes/no)
  - Orphans — any entries that were on disk but not listed in
    `MEMORY.md` (subset of the entries above)
  - Output directory (or "displayed inline" if no folder access)
  - Any read or write failures

For example, if `MEMORY_DIR` had `MEMORY.md` plus two entry files
(`feedback_x.md`, `project_y.md`), the report should say
**"Entries copied: 2"** and **"MEMORY.md index: yes"**, not
"3 entries copied." Three .md files were copied, but the entry-count
semantic is 2.
```
