# Cowork memory restore prompt (destination account, per project) — fallback / reference form

**Primary use is via blueprints.** The account-migration skill embeds this restore logic into the "Recommended Starting Prompt" section of every project blueprint it generates. When you paste a project's blueprint bootstrap on the destination account, the memory restore happens automatically as the first step — you don't paste anything else. This standalone prompt file exists for two cases:

1. **Projects without a blueprint** — for example, a Cowork project you're migrating by hand without using the skill's full flow.
2. **Debugging or re-running the restore** — if a project's restore was skipped or failed and you want to re-run it without re-pasting the whole blueprint.

If the project does have a blueprint with the embedded restore preamble, you don't need this file at all — just paste the blueprint's recommended starting prompt and it handles everything.

**Workflow when used standalone.**

1. Open the destination-account Cowork project (folder already relinked, project already set up).
2. Paste the prompt below.
3. Claude reads `<working-folder>/transition-data/cowork-space-memory/`, copies each `.md` file into the project's memory directory, and reports a short summary.
4. Future sessions in this project will see the restored memory in their context automatically.

If `transition-data/cowork-space-memory/` doesn't exist for the project, Claude reports "No memory to restore" and exits cleanly. Normal outcome for projects that had no source-account memory.

---

## Prompt to paste

```
Please restore this Cowork project's space memory from the migration
data in the working folder. Mechanical task — locate the destination
directory, copy each migration file into it, report.

STEP 1 — Confirm there's something to restore.

Check whether <working-folder>/transition-data/cowork-space-memory/
exists and contains any .md files. If not, report "No memory to
restore — proceeding" and stop.

STEP 2 — Locate the destination memory directory.

Use the memory directory path your environment advertises (your
system prompt's auto-memory section is the usual source). Call this
MEMORY_DIR.

If that path doesn't look right, fall back: run
`grep auto-memory /proc/mounts` and use the first whitespace-delimited
field of the output as the actual on-disk path. This fallback handles
rare sessions whose advertised path is stale.

Use the path syntax appropriate for your host — Windows-style for
Windows, POSIX-style for macOS or Linux. Don't translate or
reconstruct; just use what your environment hands you.

STEP 3 — Copy each migration file into MEMORY_DIR.

List every .md file under
<working-folder>/transition-data/cowork-space-memory/. For each:
  - Read the file
  - Write the same content to MEMORY_DIR/<filename>

This includes MEMORY.md alongside the entry files.

STEP 4 — Verify.

  - Read MEMORY_DIR/MEMORY.md to confirm the index landed.
  - Read one non-MEMORY.md entry to confirm content is intact.
  - The Cowork memory-write handler may enrich each entry's
    frontmatter with an `originSessionId` field (and `node_type:
    memory` if the source entry didn't already have it under a
    `metadata:` block). This is expected behavior, not corruption.

STEP 5 — Report.

Reply with a short summary, no narrative:
  - Source path (the transition-data subfolder)
  - MEMORY_DIR
  - **Number of entries restored** — count of `.md` files restored
    EXCLUDING `MEMORY.md`. (`MEMORY.md` is the index file, not a
    memory entry; keeping the entry-count consistent across dump and
    restore reports avoids off-by-one confusion.)
  - `MEMORY.md` index — was it present and restored? (yes/no)
  - Sample frontmatter from one restored entry (to confirm handler
    enrichment was applied)
  - Any failures
```

---

## Note for skill authors / blueprint authors

The blueprint generator (`generate_blueprint.py`) embeds a verbatim copy of STEPS 1-5 above into Section 7 ("Recommended Starting Prompt") of every blueprint it produces, ahead of the project-specific bootstrap directives. The user-side prompt the migration-prompt-template asks Claude to write also includes the same preamble. Both paths produce blueprints whose recommended starting prompt handles memory restore automatically without any separate paste.

If the restore mechanism ever changes (e.g., the path-discovery step or the directory layout evolves), update three places: this file, the blueprint generator's Section 7 template, and the migration-prompt-template's Section 7 instructions. Regenerate existing blueprints if the change is breaking.
