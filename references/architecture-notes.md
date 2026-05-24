# Architecture notes — account-migration

Reference material for the skill. Read when `SKILL.md` points here or when you need to reason about something the orchestration doesn't directly cover.

## The three project categories

Every project the skill handles is one of three categories. The distinction drives where the data comes from and how routing works.

1. **Web project, imported into Cowork** — Part 1 territory. Knowledge from the export's `projects/<uuid>.json` `docs[]` array (text-extracted) or the cache. Conversations in the export's `conversations.json` (flat list with no project-linkage). Per-project attribution recovered via the saved Chats page.
2. **Web project, not imported** — same as #1 except no folder/cache yet. Deciding to migrate it means the user creates the project on Cowork side first.
3. **Cowork-native project** — Part 2 territory. Born on disk, never on the web. Knowledge already in the project folder (working files). Conversations in local JSONL session files that are walled off to skills.

Part 1 of the skill handles category 1 and 2. Part 2 handles category 3 (plus previously-imported projects the user has continued working in inside Cowork).

## The data export schema

- `conversations.json` — JSON array of conversation objects. Each conversation has `uuid`, `name`, `summary` (sometimes), `created_at`, `updated_at`, `account`, `chat_messages[]`.
- `projects/<uuid>.json` — one per project. Has `uuid`, `name`, `description`, `prompt_template` (custom instructions), `docs[]` (knowledge files with `filename` and `content` text), `is_starter_project` (boolean — filter this from user-visible counts).
- `memories.json` — account-level memory (not per-project; the skill doesn't depend on this).
- `users.json` — minimal account info.

**Critical:** `conversations.json` has NO project-linkage field. Attribution must be recovered from elsewhere. The skill recovers it from a saved copy of the user's Chats page (HTML), parsed by `parse_allchats.py`.

## The four artifact kinds

A conversation's `chat_messages[].content[]` can contain four patterns of assistant-produced content. Each requires different handling — `reshape_and_extract.py` implements all four.

1. **`tool_use: artifacts`** — Claude's web Artifacts panel. Inline content in `tool_use.input.content`. **Extract** to `<conv-slug>/artifacts/<safe-title>.<ext>` using `type` (and `language` for code) to pick the extension:
   - `text/markdown` → `.md`
   - `application/vnd.ant.code` with `language: javascript` → `.js` (and similar for other languages)
   - `image/svg+xml` → `.svg`
   - `application/vnd.ant.mermaid` → `.mermaid`
   - `application/vnd.ant.react` → `.jsx`
   - `text/html` → `.html`

2. **`tool_use: create_file`** — file written via Claude's web file tools (typically a build script later run via `bash_tool`). Inline in `tool_use.input.file_text`. The `path` field provides the basename. **Extract** to `<conv-slug>/artifacts/<basename-of-path>`.

3. **`tool_use: bash` heredoc / tee / redirect writes** (added in v1.5). A bash command may write file content inline via a heredoc (`cat << EOF > path` ... `EOF`), or write content from earlier in the pipeline via `tee path` or a `> path.ext` redirect. The conversation's transcript carries the bash command but only sometimes carries the file content:
   - **Intact heredoc** (`cat << DELIM > path` with the body and matching closing `DELIM` both inline): **extract** to `<conv-slug>/artifacts/<basename-of-path>`. Content is in the bash command itself.
   - **Truncated heredoc** (the renderer's `[Omitted long matching line]` marker is inside the heredoc body): **not extractable** — body got dropped during export rendering. List in `_ARTIFACTS_TO_RECOVER.md` with the destination path.
   - **`tee path` writes**: content was stdin to `tee`, not in the bash command. **Not extractable.** List in `_ARTIFACTS_TO_RECOVER.md`.
   - **Plain `> path.ext` redirects** that aren't part of a heredoc: content was a previous command's stdout. **Not extractable.** List in `_ARTIFACTS_TO_RECOVER.md`.

   Closes the v1.0–v1.4 silent-loss class where intact heredoc-written CSVs (and other text files) were discarded because only the `artifacts` and `create_file` patterns were scanned.

4. **`tool_use: present_files`** binary outputs — `.docx`, `.xlsx`, `.pdf`, `.pptx`, images, archives. Only the filepath reference is in the export; **no binary content**. **Not extractable.** Listed in `_ARTIFACTS_TO_RECOVER.md` at the catch-all root with checkboxes for the user to manually recover from claude.ai.

The recovery file groups by destination class (reconstructed projects first, then catch-all subfolders, then orphans) and within each by conversation. If the same filename was referenced multiple times within one conversation, the count is shown (e.g., "3× referenced") — usually indicating versioned drafts. Recovery entries include both the non-extractable bash-write paths and the binary present_files refs in a unified list.

## The three-bucket conversation rule

Every conversation in the export ends up in one of three buckets:

| Bucket | Condition | Destination |
|---|---|---|
| Attributed | In Chats save with project column populated | Per-project (if folder picked empty) OR catch-all per-project subfolder (if skipped / non-empty pick) |
| Catch-all (orphan) | In Chats save, project column empty | `<catchall_name>/unattributed-conversations/` |
| Dropped | In manifest but NOT in Chats save | Discarded — user deleted them; content is empty in export anyway |

**Why dropped is dropped:** deleted conversations are present in the export but every message has `text: ""`, `content: []`, `attachments: []`, `files: []`. The conversation `name` is cleared too. Skeleton only. Nothing meaningful to recover.

**Orphans are not filtered by message count.** An empty-named or zero-message orphan can still belong in the catch-all for review (it had a name once, the user knows what it was). The user can prune later if desired; the skill includes them.

## Per-project routing rules (Part 1)

After the user makes a pick/skip decision for each web project:

| User action | Project folder | Web-side conversations + cache binaries |
|---|---|---|
| Pick empty folder | Reconstructed in place | Folded into reconstruction |
| Pick non-empty folder | Untouched (user's work protected) | → catch-all per-project subfolder |
| Skip | Not reconstructed | → catch-all per-project subfolder |

Skip and non-empty-pick are mechanically identical (both route to catch-all). Only the framing in the post-pick confirmation differs:

- Non-empty pick → *"existing folder picked. Conversations will be stored in `<catchall_name>`."*
- Skip → *"project skipped. Its conversations will be stored in `<catchall_name>` for your final review."*

This matters because skip is *defer the decision*, not *delete the content*. If a user reconsiders later, the conversations are intact in the catch-all.

## Reconstructed folder layout

### Fresh-import case (Part 1, empty picked folder)

```
<project>/
  _PROJECT_BRIEF.md              factual brief (provenance + description + instructions + inventory)
  knowledge/                     project's knowledge docs (byte-faithful where text; PDFs etc. as extracted text)
    <filename>
    …
  conversation-history/
    INDEX.md                     table of contents (see "INDEX.md format" below)
    <conv-slug>.md               per-conversation transcript
    <conv-slug>/
      artifacts/                 inline artifacts extracted from the conversation
        <file>
    …
  transition-data/
    project-blueprint.md         auto-generated narrative blueprint
```

### Catch-all per-project subfolder (Part 1, skipped or non-empty pick)

```
<catchall_name>/<source project name>/
  _MIGRATION_NOTE.md             explains where these conversations came from
  conversation-history/
    INDEX.md
    <conv-slug>.md
    <conv-slug>/
      artifacts/
        <file>
```

### Cowork project (Part 2)

```
<cowork project folder>/
  <user's existing working files — UNTOUCHED>
  _PROJECT_BRIEF.md              factual brief (skill writes this next to the working files)
  transition-data/
    migration-prompt.md          prompt for the user to run in old-account Cowork session
    project-blueprint.md         user writes this themselves after running migration-prompt.md
```

### Migration hub root (the user's catch-all Cowork project plus the migration scaffold)

```
<migration hub folder>/
  tracker.html                   on-disk twin of the Cowork sidebar artifact
  README - Final Transition to New Account.md   written at end of Track A
  memory-capture-prompt.md       written at end of Track A
  memory-seed-prompt.md          written at end of Track A
  skills/
    account-migration.skill      and any other custom .skill installers
    …
  <intermediate artifacts>       export zip + Chats HTML during Track A, cleaned up at end
```

## INDEX.md format

Each `INDEX.md` (in any conversation-history folder) is a markdown table:

```
# Conversation history index

| # | Time | Conversation | Msgs | Artifacts | Opens with |
|---|------|--------------|-----:|-----------|------------|
| 1 | <date time> | [<conv title>](<conv-slug>.md) | <msg count> | [<artifact count>](<conv-slug>/artifacts/) | <first-message excerpt> |
| … |
```

The Artifacts cell links to the per-conversation `<slug>/artifacts/` folder when present, with the file count. Empty when the conv had no inline artifacts.

## Selective-pick is the only mode

The skill does **not** auto-match folders to web projects by name. The user makes an explicit pick decision per project via the picker. This is locked because:

1. There's no programmatic folder-path → web-uuid mapping available to skills (Cowork install-level storage is walled off).
2. Folder-name matching is unreliable — users rename folders freely. A user might have a Cowork folder with a slightly different name from the corresponding web project (e.g., a name appended at import time, or a deliberate rename on either side); pure-name matching would either miss the link or create false matches.
3. Picker mode of `request_cowork_directory` always works and gives least-privilege access automatically.

## Tracker (dual-render)

The tracker is rendered two ways and kept in sync:

1. **Cowork sidebar artifact** via `mcp__cowork__create_artifact` — in-session UX surface.
2. **`tracker.html`** in the migration hub on disk — cross-account handoff vehicle.

Both carry an embedded `<script type="application/json" id="handoff-state">…</script>` block with the full project roster, final names, source UUIDs, on-disk folder paths, per-project status, totals, and cross-track phase tracking. Track B reads this block to drive the destination-side walk-through.

**Columns in the rendered table:** Project · Docs · Convs · Export · Cache · Attached · Reconstructed · Relinked. Status indicators: ✓ done · pending · — n/a · ? unknown.

After every state transition during either track, update both representations. Each `mcp__cowork__update_artifact` call triggers a user approval — that's the cost of accurate state; pay it.

## Tracker JSON schema (handoff-state)

The embedded `<script type="application/json" id="handoff-state">` block carries the cross-account state. Track A writes it as the run progresses; Track B reads it to drive the relink walk-through.

```jsonc
{
  "schema_version": 1,
  "phase": "<phase-string>",       // see phase enum below
  "session": "<session-id>",        // identifier for the source-side run
  "cleanup_done": <true|false>,     // populated by Track B Phase 7. Absent in
                                    // pre-v1.6.1 trackers; the resume detector
                                    // treats absent as false (offer resume).
                                    // True only after `done` at cleanup wrap.
  "totals": {
    "conversations": <N>,
    "messages": <N>,
    "attributed": <N>,
    "catchall_orphans": <N>,
    "dropped": <N>,
    "projects_in_export": <N>,
    "projects_user_visible": <N>,
    "reconstructed_in_place": <N>,
    "routed_to_catchall": <N>
  },
  "catchall": {
    "name": "<user-chosen catch-all name>",
    "status": "<status string>",
    "folder_path": "<windows path on source machine>",
    "orphan_count": <N>,
    "subfolder_count": <N>,
    "subfolder_conv_total": <N>,
    "relink_pending_track": "B"
  },
  "projects": [
    {
      "order": <N>,
      "name_display": "...",        // display name for prompts
      "name_export": "...",         // name from projects/<uuid>.json
      "name_allchats": "...",       // name as it appeared in the Chats save
      "uuid": "<web project uuid>",
      "docs": <N>,
      "convs": <N>,
      "export": "done|skipped|...",
      "cache": "unknown|...",
      "attached": "done|...",
      "folder_path": "<windows path>|null",
      "disposition": "<human-readable description>",
      "reconstructed": "done_in_place|done_routed_to_catchall|skipped",
      "relinked": "pending|done|done_no_bootstrap|skipped"
    }
    // ... one per Part 1 project
  ],
  "cowork_projects": [
    {
      "name": "<folder name>",
      "folder_path": "<windows path>",
      "has_blueprint": <true|false>,
      "relinked": "pending|done|done_no_bootstrap|skipped"
    }
    // ... one per Part 2 picked folder
  ],
  "custom_skills": [
    {
      "filename": "<filename>.skill",
      "size_bytes": <N>,
      "installed": <true|false>   // set by Track B Step 8.7's pre-check
                                  // (reconciling tracker filenames against
                                  // the destination account's
                                  // .claude/skills/ mount), and refreshed
                                  // on user `done` after the user installs
                                  // skills via the Save-skill button.
                                  // Absent for fresh Track A writes —
                                  // treated as `false` by Track B.
    }
    // ... one per .skill file in the hub's skills/ subfolder
  ],
  "scheduled_tasks": [
    {
      "taskId": "<task-id>",
      "description": "<description>",
      "cronExpression": "<cron>",
      "enabled": <true|false>,
      "has_dependencies": <true|false>,
      "recreated_on_destination": <true|false>   // set by Track B Step 8.5 when the user
                                                  // says `recreate` (and the MCP call
                                                  // succeeds). false otherwise or after
                                                  // user `skip`. Absent for fresh
                                                  // Track A writes.
    }
    // ... one per active scheduled task at capture time; populated by Step 3.7
    // in multi-project Track A only (single-project skips Step 3.7). Track B's
    // Step 8.5 walks the user through recreating each on the new account.
  ]
}
```

### Phase string enum

Tracks where in the overall flow the migration is:

- `"track-a-part-1-complete"` — Part 1 (web/chat projects) finished; Part 2 not yet started.
- `"track-a-part-2-complete"` — Part 2 (Cowork projects) finished; custom-skills capture not yet started.
- `"track-a-complete"` — All of Track A done (including custom-skills capture). README and memory-capture-prompt written. Ready for Track B.
- `"track-b-walkthrough-complete"` — Track B's per-project walk-through finished. Scheduled-tasks recreation (Step 8.5) / binary recovery / validation / cleanup still ahead.
- `"track-b-scheduled-tasks-complete"` — Track B's scheduled-tasks recreation step (8.5) finished, whether tasks were recreated, skipped, or absent. Set in multi-project mode only; single-project Track B skips Step 8.5 and goes straight from walk-through to Step 9.
- `"track-b-custom-skills-complete"` — Track B's custom-skills installation step (8.7) finished, whether all skills were installed, some were skipped, or none were captured. Set in multi-project mode only; single-project Track B skips Step 8.7.
- `"track-b-complete"` — Full migration complete (whether cleanup was performed or skipped).

Track A advances the phase as each sub-phase completes. Track B reads `phase` to verify it's running against a valid handoff (must be at least `"track-a-complete"` to proceed) and updates it on completion. A future run can re-enter Track B at any point and resume from where the phase indicates.

### Writing the tracker

The skill writes both representations in lockstep. The on-disk write goes through the host-side Write tool, NEVER through a bash-read → host-write cycle (see the cloud-synced hub truncation gotcha below).

### Rendering the tracker — group-and-sort discipline

The visible HTML table is **always grouped by status and sorted alphabetically within each group**, regardless of what order the underlying JSON arrays have:

- **Status group order:** `pending` first → `done` (and `done_no_bootstrap`) → `skipped`. Pending-first because that's what's still actionable; skipped-last because it's the least actionable.
- **Within-group sort:** alphabetical by `name`, case-insensitive (Unicode `casefold`).

This is a presentation rule, not a data rule — the JSON's order is preserved as-written (it's a record of how Track A processed the projects). Track A's v1.6+ recon path sorts alphabetically at parse time, so for fresh runs the JSON order and HTML render order naturally agree; for older trackers (pre-v1.6, recency-first order) the render-side sort still gives a clean view. Both Track A and Track B apply this same group-and-sort on every dual-render, including state-transition updates that flip a project's status. A project moving from `pending` to `done` should physically move within the rendered table to the corresponding group's position, not stay in its prior row.

### Tracker HTML structure — what the user sees

The visible HTML carries three optional sections beyond the header / progress block:

1. **Projects table** — always present when `cowork_projects` and/or `projects` arrays are non-empty. Group-and-sort per the rule above. Columns: Project (name + folder hint) | Sessions | Transcripts | Memory | Blueprint | Status.

2. **Custom Cowork Skills section** — rendered when `custom_skills` array is non-empty. H2 + one-line user-facing note + table: skill filename | size | status badge. Status mapping: on Track A (no `installed` field present anywhere) → `ready to install` for every row; on Track B (Step 8.7's pre-check has run, so at least one entry has an `installed` field) → per-row `installed` when `installed: true`, `pending install` when `installed: false`. A small legend below names the bundled `anthropic-skills` plugin members that aren't captured (they re-install with Cowork on the new account). Step 8.7's pre-check sets `installed` by listing the destination account's read-only `.claude/skills/` mount and matching folder-name slugs against the tracker's filename minus `.skill`; user `done` triggers a re-read of the same mount.

3. **Scheduled Tasks section** — rendered when `scheduled_tasks` array is non-empty. H2 + one-line user-facing note + table: task ID + description | cron + human schedule | dependencies (folder names if any, otherwise "none — recreates cleanly") | status badge. Track A renders status as `pending recreate`; Track B's Step 8.5 flips to `done` per `recreated_on_destination: true`, or leaves `pending recreate` if the user `skip`ped that task.

Before v1.6.1, `custom_skills` and `scheduled_tasks` were JSON-only (invisible in the rendered HTML). Surfacing them as visible sections lets the user verify the capture at end of Track A AND see what Track B will handle without having to read the JSON or open `scheduled-tasks-export.md`.

### Track B re-render — preserve Track B framing

When the tracker is rendered or re-rendered during Track B (a common trigger is the `update_artifact` call when the orchestrator notices the Cowork sidebar artifact has fallen out of sync with the on-disk `tracker.html`), the renderer MUST use the on-disk JSON as the source of truth AND preserve Track B framing. Specifically:

- The **phase chip** reflects the actual `phase` field — e.g. `track-b-walkthrough-complete`, `track-b-scheduled-tasks-complete`, `track-b-custom-skills-complete`, `track-b-complete` — not the Track-A-final "Track A complete · ready for Track B" label.
- The **projects table** carries the relinked dimension that Track B is actively mutating, either as a dedicated RELINK column or merged into the STATUS badge per row.
- The **Custom Skills table** uses the Track B status mapping (per-row from `installed`), not Track A's blanket `ready to install` label.
- The **Scheduled Tasks table** reflects each task's `recreated_on_destination` per row.

This rule exists because the v1.6.2 dry run surfaced a regression where a mid-Track-B re-render fell back to Track A's rendering path. The on-disk JSON was correct; the render path lost the Track B framing. Naming the failure mode here so future render-rule changes don't repeat it.

## Inline reconstruction (not deferred)

Reconstruction happens immediately after each pick/skip is confirmed, before the next per-project prompt fires. Reasons:

1. The user wants to verify results as they go.
2. Decisions are already captured in the tracker JSON at pick time — no benefit to deferring.
3. If the session crashes mid-walk-through, deferred work is lost; inline work is preserved.

The Part 1 wrap describes what's already on disk (past tense), not what will be (future tense).

## Briefs are factual, not narrative

The `_PROJECT_BRIEF.md` files this skill writes contain:

- Provenance (source, UUID, action, date)
- Description (verbatim from export) — say `(none)` if empty
- Custom instructions (verbatim from export) — say `_(none set on claude.ai)_` if empty
- Knowledge inventory (filename + char count)
- Conversation count + pointer to `conversation-history/INDEX.md`
- A short "what to do next" paragraph aimed at the destination-side Claude

They do NOT contain a synthesized "what's important about this project" narrative. Reasons:

1. **Synthesis at rest goes stale.** The moment the user reopens the project on the destination side, a synthesized summary written today is already out of date.
2. **Different project shapes need different summaries.** Sequential workflow, framework-reused-across-iterations, heterogeneous bucket — each wants a different summary shape. The skill can't predict which.
3. **The transcripts are right there.** The next Claude that opens the project can read `conversation-history/INDEX.md` and any specific transcript on demand to synthesize.

Narrative synthesis lives in `project-blueprint.md` instead — auto-generated for Part 1 (the skill has the data), user-generated via `migration-prompt.md` for Part 2 (skill doesn't have the data).

## Per-project Cowork memory architecture (v1.5)

Cowork stores per-project space memory in an isolated per-project directory on disk (`<install>/spaces/<space-uuid>/memory/`). The `<space-uuid>` differs per Cowork project; only a session running INSIDE the project can read or write that project's memory. Folder access alone does NOT grant memory access — even with the hub's working folder mounted, a hub session cannot reach a different project's memory.

This forecloses any skill-autonomous design where the hub session reads each project's memory directly. The skill instead drives **paste-prompt operations**: the orchestrator writes a dump prompt asset into each project's `transition-data/` folder, instructs the user to open the project's own source-account Cowork session and paste the prompt, and waits for the user to confirm the dump is done. Claude in the per-project session does the actual memory read+write (it has the permissions the hub session lacks).

Two assets implement this pattern:

- **`assets/cowork-memory-dump-prompt.md`** (source side, written into each Part 2 project's `transition-data/`). Reads the project's per-project memory directory, writes each entry to `transition-data/cowork-space-memory/` as individual files (plus the index `MEMORY.md`). Cross-platform: uses whichever path syntax the host hands the receiving Claude.
- **`assets/cowork-memory-restore-prompt.md`** (destination side, embedded verbatim into each project blueprint's Section 7 by `generate_blueprint.py`). When the user pastes the blueprint's recommended starting prompt in a fresh destination-account project conversation, the restore preamble runs first — reads `transition-data/cowork-space-memory/` and writes each entry to the destination project's per-project memory directory. The Cowork memory-write handler engages on path match and enriches frontmatter with `node_type: memory` + `originSessionId`; expected behavior, not corruption.

Standalone `cowork-memory-restore-prompt.md` ships in the bundle for projects without blueprints or for debug re-runs.

## Unified blueprint generation (v1.5)

`scripts/generate_blueprint.py` handles both Part 1 (reconstructed-from-export) and Part 2 (Cowork-native) projects with the same logic — reads disk-resident data only, no Cowork-session-context dependency.

**Inputs (per project type):**

| Source | Part 1 | Part 2 |
|---|---|---|
| Custom instructions | from export project JSON's `prompt_template` field | from `<root>/custom-instructions.md` or similar at project root |
| Knowledge files | from `<project>/knowledge/` (written by `reconstruct.py`) | from working files at the project root |
| Conversations | from `<project>/conversation-history/` (`_chat_` filenames written by `reconstruct.py`) | from `<project>/conversation-history/` (`_sess_` filenames written by the transcript-dump paste prompt) |
| Memory | n/a (web chats don't have per-project memory) | from `<project>/transition-data/cowork-space-memory/` (written by the memory-dump paste prompt) |
| Project name | from export JSON's `name` field, or fallback to folder name | folder name |

**Outputs:**

- `<project>/transition-data/project-blueprint.md` with seven sections. Mechanical sections (2 Custom Instructions, 5 Knowledge Base, 7 Recommended Starting Prompt with the memory-restore preamble embedded verbatim) are filled in directly. Synthesis-required sections (1 Purpose, 3 Key Decisions, 4 WIP, 6 Recurring Context) get clear TODO markers pointing to the synthesis notes.
- `<project>/transition-data/_BLUEPRINT_SYNTHESIS_NOTES.md` — raw input excerpts: transcript opener+closer user messages (for sections 1 and 4), full memory entry bodies (for sections 3 and 6), knowledge/working file previews (for section 5). The hub Claude reads this file as context and writes the synthesis directly into the blueprint, producing a complete blueprint before moving on.
- For Part 2 only: `<project>/_PROJECT_BRIEF.md` at the project root — same brief structure `reconstruct.py` produces for Part 1, adapted for Cowork-native inputs (no export JSON, working files instead of knowledge docs).

**Why mechanical-fill + synthesis-via-notes** rather than full automated synthesis or full Claude-driven generation: synthesis from transcripts and memory genuinely requires LLM judgment, but it doesn't require LLM access to the Cowork project's session context. By having the script gather the inputs into a structured notes file and the hub Claude do synthesis from that, the work runs in the hub session (which has full project-folder access) without needing the user to paste anything inside the source-account project. Faster, more reliable, easier to iterate. The pre-v1.5 `migration-prompt-template.md` per-project paste flow stays in the bundle as a fallback for users running partial-manual orchestration.

## Mojibake detection (v1.5)

`reconstruct.py` scans each knowledge document it writes for visible double-UTF-8 mojibake patterns: `Â ` (nbsp artifact), `â€` (em-dash/smart-quotes leading), `âœ` (check/x emoji leading), `âš` (warning sign), `âžž` (arrow), `Ã©` / `Ã¨` / `Ã¢` (accented Latin). When any of these substrings appears in a doc's text, the filename is added to a list that surfaces as a Notes-section bullet at the top of the project's `_PROJECT_BRIEF.md`.

Detection only — no auto-correction. The damage results from the export pipeline interpreting some Unicode bytes as Windows-1252 between rounds of UTF-8 encoding; round-tripping the bytes back through `latin-1.decode().encode('utf-8')` recovers cleanly for some patterns but not all (depending on what the original Unicode codepoint was). The skill's job is to flag the issue so the user compares against their original on-disk copies and replaces affected files as needed.

## Script parameterization (v1.5)

`reconstruct.py` and `reshape_and_extract.py` are fully parameterized as of v1.5 — no hardcoded paths, no hardcoded project names. Both accept `--extracted / --attribution / --export / --routing / --outdir / --catchall-name` and read the per-project routing dict from a JSON file the orchestrator writes from walk-through state before invoking.

**Routing JSON schema** (dict keyed by user-facing project name):

```json
{
  "Display Name": {
    "action": "reconstruct_in_place" | "route_to_catchall",
    "folder_name": "destination folder name on disk",
    "export_name": "name as it appears in the export's projects_manifest.csv",
    "export_uuid": "uuid of the project's JSON in export-unzipped/projects/",
    "reason": "(route_to_catchall only) human-readable reason for the migration note"
  }
}
```

Per-action expectations:

- **`reconstruct_in_place`** — writes a full project layout to `<outdir>/<folder_name>/`. Requires `folder_name`, `export_name`, `export_uuid`. Produces `knowledge/`, `conversation-history/`, `_PROJECT_BRIEF.md`.
- **`route_to_catchall`** — writes transcripts to `<outdir>/<catchall_name>/<folder_name>/`. Requires `folder_name`, `reason`. Produces transcripts + INDEX.md + `_MIGRATION_NOTE.md` inside the subfolder. The reshape pass later moves the transcripts under `conversation-history/` inside the subfolder.

The orchestrator (SKILL.md Step 2) serializes the routing JSON to disk at the end of the per-project walk-through loop, then invokes reconstruct.py + reshape_and_extract.py against it. Both scripts run for any user's export without source edits.

## End-of-Track-A coverage gate (v1.5)

`scripts/blueprint_coverage_check.py` verifies that every project folder the walk-through touched has `transition-data/project-blueprint.md` on disk. SKILL.md Step 3.6 invokes it after Part 2 wraps and before the end-of-Track-A cleanup wrap. Exit code 0 → all present, proceed to Step 4. Exit code 1 → surface the gap to the user with the list of missing-blueprint projects; the user either regenerates inline (re-run `generate_blueprint.py` against each) or acknowledges and proceeds.

This catches gaps from interrupted runs, manual interventions where the orchestrator skipped a step, or projects added to the routing after blueprint generation ran. The gate is a ship-readiness check, not a hard block — the user can still proceed past it; the warning is informational.

## Cloud-synced hub truncation gotcha

Files inside the user's migration hub may sit inside a cloud-synced folder (any flavor — the same failure mode happens across cloud-sync products on Windows and macOS). Cloud-sync clients can leave files in a placeholder state where the directory entry exists but a read returns "no such file" or a truncated body. The sandbox's bash mount layer also keeps a per-path attribute cache that can serve stale views to bash after host-side writes. Three failure modes follow:

- **Bundled scripts read at rest may be truncated.** Always write fresh copies from the skill folder to a private scratch directory (inside the agent's session outputs, not the user's hub) at start of run. Don't trust `.py` files at rest in the hub.

- **Reading files at rest in the hub:** prefer the host-side `Read` tool over `mcp__workspace__bash`, since they use different code paths and the host-side often succeeds where bash fails on the same path. Host-side isn't iron-clad either; for high-stakes disagreements between bash and host-side reads, force a fresh attribute lookup via `mv X X.tmp && mv X.tmp X` in bash, then re-read.

- **Write-back cascade — never round-trip bash-read content through a host-side write.** The bash read may be returning a stale or truncated view of a hub-resident file; writing that content back via a host-side tool produces NTFS truncation of the source file. Most destructive failure mode. If a script needs to update a tracker or recovery file, source the existing state from process memory or regenerate from authoritative data (manifest, tracker JSON in memory) — never read-modify-write through bash.

## Install recon — spaceId attribution (v1.5)

Cowork's `list_sessions` returns sessions account-wide with no project membership in its output. To attribute sessions to projects, the skill reads the on-disk per-session JSON files — each contains `spaceId` (= project identity), `userSelectedFolders` (= the working-folder reattach list), `title`, timestamps, and `isArchived`. Sensitive fields (initial messages, system prompts, MCQ answers, enabled MCP tools) are deliberately not read.

The install root holding those JSONs isn't a sandbox mount, so the skill can't read them in-band. The recon mechanism splits the work:

- **Sandbox-side** (`scripts/derive_install_root.py`): runs `findmnt -n -o SOURCE --target <mount>` against `.auto-memory` and `outputs`. Each mount's source path embeds the install root + the four identifying UUIDs. The Windows translation rule (strip `/mnt/.virtiofs-root/shared/`, first segment becomes drive-letter `:`, join with backslashes) is verified. The Mac rule is theoretical and needs validation on a real macOS Cowork session — the principle (read mount source, translate to host path) is OS-agnostic but the exact source format on macOS isn't confirmed as of v1.5.

- **Native-shell-side** (`assets/recon-script-*.template`): the user runs a small script in their native shell. The script walks `<install_root>/local_*.json`, extracts the seven non-sensitive fields per session, sorts by `createdAt`, writes `sessions-recon.csv` next to itself (via `$PSScriptRoot` / `$BASH_SOURCE` — no hardcoded user-folder names or cloud-sync brand assumptions).

- **Bridge**: `scripts/render_recon_script.py` substitutes the derived install root into the OS-appropriate template. `scripts/parse_recon_csv.py` consumes the resulting CSV, groups rows by `spaceId`, applies the universal noise filter to `userSelectedFolders` (`.project-cache`, `/tmp/`, `\Temp\`, `/var/folders/`), and emits structured JSON. `--filter-space-id` mode drives single-project runs.

What this enables vs. what it doesn't:

- **Enabled.** Track A Part 2 enumerates projects from the recon JSON and pulls every session's transcript via `mcp__session_info__read_transcript` (works account-wide across spaceIds). Track B Phase 4 surfaces each project's noise-filtered `userSelectedFolders` union as informational reattach guidance.
- **Still walled.** Per-space memory dirs (`spaces/<spaceId>/memory/`) are only mounted into that space's own sandbox sessions — not into the hub session. Per-project Cowork memory still requires a per-project paste prompt (`assets/cowork-memory-dump-prompt.md`) run inside each project's source-account session.

**Blank-spaceId sessions.** Sessions with no `spaceId` decompose into (a) utility / scheduled-task runs that never belonged to any project (the majority — backup monitors, updates digests, etc.), and (b) "pre-spaceId-era" sessions whose topic later became a discrete Cowork project (early sessions in generic parent folders, before the project existed as a space). Blank and populated sessions overlap heavily in time — there is NO clean "field added on date X" boundary. The skill keeps blanks separate (parse_recon_csv's `blank_space_sessions` array) and the orchestrator decides whether/how to surface them. Pre-space lineage that matters needs title-level inspection; folder-matching can't recover it because pre-space sessions often used generic parent folders rather than the project folder.

## Adaptive detection — never hardcode scaffolding location

The skill must run correctly regardless of where the user invokes it from. A Side B user might:

- Invoke from inside the migration source (the multi-project hub, or a single-project folder with `transition-data/`).
- Invoke from a fresh empty Cowork project they just created.
- Invoke from an unrelated existing project (e.g., a working notebook they happened to have open).
- Invoke from a no-project conversation.

None of these scenarios are wrong, and the skill cannot assume any of them. The pattern is:

1. **Detect.** Check the current working folder for the signals that indicate migration scaffolding — `tracker.html` at root (multi-project hub), `transition-data/tracker.html` (single-project source). Use whichever you find.
2. **Prompt if not detected.** Surface a picker prompt that explicitly names both possible folder shapes ("hub folder" vs. "project folder with `transition-data/` inside") and asks the user which one they have. Do NOT default to either shape.
3. **Re-detect after picker.** Once the user picks, run the same detection logic inside the picked folder. Branch to the appropriate flow based on what's actually there.
4. **Surface a clean error if still not detected.** If the picked folder also has neither signal, the user picked something wrong — say so plainly, offer pick / hold / quit. Do NOT try to "make it work" with partial scaffolding.

**The bundled READMEs are supplementary, never load-bearing.** `README - Final Transition to New Account.md` (multi-project) and `_RESUME_ON_NEW_ACCOUNT.md` (single-project) are reference documents for the user to read if they want to understand the flow outside the skill. The skill itself walks the user through every step via prompts and does not require any READMEs to be read first. If a user hasn't opened either, the skill still works end-to-end. This is the operational meaning of Discipline rule #12.

This adaptive pattern applies to Track A as well, not just Track B. On the source side, a user might invoke the skill from the hub project they just created, from a no-project conversation, or from another folder entirely. Track A's hub-setup steps work the same way — detect what's available, ask for what's missing, never assume.

## Cowork session storage wall

`mcp__cowork__request_cowork_directory` refuses paths inside Cowork's install storage. This is intentional Anthropic behavior — the install root is private to the local install. The v1.5 install recon (above) extracts non-sensitive session metadata via a user-run native-shell script, but it does not bypass the wall — the user does the reading.

Implications after v1.5:

- Per-project Cowork memory still doesn't migrate via the hub. Per-project paste prompt remains the path.
- Session transcripts now migrate via the hub-driven `read_transcript` pull (recon path) — no more per-project paste prompt for transcripts. The legacy paste prompt (`assets/cowork-session-transcript-dump-prompt.md`) stays in the bundle for blank-spaceId fallback cases.
- Working-folder attachment paths are surfaced from recon as informational guidance for Track B; the user still reattaches via the picker per the always-picker discipline.

**User workaround (not part of the skill).** If the user copies Cowork's install storage outside the wall to a non-protected location, the skill could in principle read the JSONL transcripts and per-space memory tree from that copy. The recon mechanism makes most of this unnecessary; it's mentioned for completeness.

## Bipartite blueprint pattern (v1.5.1)

Every project blueprint splits its sections into two roles, made explicit by the "How to use this file" header at the top of the file:

- **Human-facing sections (the user acts on these directly):**
  - **Section 2 — Custom Instructions.** The user pastes the fenced block into the destination project's *Custom Instructions* settings field. If Section 2 has the empty-placeholder string, the source had no Custom Instructions and the user skips this step.
  - **Section 7 — Recommended Starting Prompt.** Section 7 is NOT what the user pastes — it is a directive *to Claude* that the user triggers by pasting the canonical short outer bootstrap prompt in chat.
- **AI-facing sections (Claude reads as context):** Sections 1 (Purpose), 3 (Key Decisions), 4 (Work in Progress), 5 (Knowledge Base inventory), 6 (Recurring Context).

This split is load-bearing for the Side B B-1c-bootstrap flow. The skill walks the user through **two action steps** in Step 5-single sub-steps 4 and 5: (1) Custom Instructions paste via Prompt B-1c-customs-present / B-1c-customs-empty, (2) bootstrap prompt paste via Prompt B-1c-bootstrap-in-place / B-1c-bootstrap-relocated. Before v1.5.1, the skill only walked through step 2 and Section 2's paste step was silently skipped — that was the bug §12 of the session-7 handoff identified.

### Canonical outer bootstrap prompt — one text, four places

The short outer prompt the user pastes in chat is canonical across the skill — same three-line text everywhere:

```
This is a project I'm migrating from my old Claude account. Read
`transition-data/project-blueprint.md` for the full project context,
then treat its Section 7 — Recommended Starting Prompt — as your
first directive.
```

This text appears verbatim in four places:

1. `skill-source/account-migration/references/skill-user-facing-text.md` — inside B-1c-bootstrap-in-place and B-1c-bootstrap-relocated locked copy (the skill-driven Side B path).
2. `skill-source/account-migration/assets/README-template.md` — Step 4's "paste this prompt" block (the multi-project manual-fallback path).
3. `<project>/transition-data/_RESUME_ON_NEW_ACCOUNT.md` — single-project manual-fallback path. Written at end of Track A for single-project migrations.
4. `<project>/_PROJECT_BRIEF.md` — "Resuming on the new account" section. Generated by `generate_blueprint.py` (Part 2 case).

If the text needs to change, update all four places. The skill's value is that this prompt is *short* — the rich content lives in the blueprint, where Claude reads it as a whole. Anything pushed into the outer prompt erodes that.

### On-demand conversation-archive registration

Section 7's directive Item 2 instructs Claude to write a memory entry that registers `conversation-history/` as on-demand reference — not preload. The memory-entry slug is datestamped at blueprint-generation time (`reference_pre_migration_archive_YYYYMMDD`) so the entry marks a specific point in time; future Cowork conversations grow forward from there as fresh history, distinct from the pre-migration archive.

Why this matters: a typical migrated project has 5+ session transcripts averaging 2-4k tokens each. Pre-loading them costs 10-20k tokens of context the destination session usually won't need. The memory-entry approach keeps the archive *discoverable* (Claude knows it exists and can pull specific transcripts when relevant) without burning context on speculative loading.

### Section 7 has-memory / has-history branching

`generate_blueprint.py`'s Section 7 emitter branches on two booleans:

- **has-memory** (`len(memory_entries) > 0`). When true, Section 7 opens with the memory-restore preamble (STEPS 1-5 verbatim from `cowork-memory-restore-prompt.md`), followed by a `---` separator and the lead-in "Once memory is restored, resume the project:". When false, Section 7 skips the preamble entirely and opens with "Resume the project:". No point making Claude run a 5-step procedure that will find nothing to restore.

- **has-history** (`len(transcript_files) > 0`). When true, the archive-registration item (Item 2 above) is emitted with the transcript count and datestamped slug substituted. When false, the archive-registration item is omitted entirely and the remaining items renumber.

This produces four shapes for Section 7's directive block:

| has-memory | has-history | Section 7 shape |
|---|---|---|
| Yes | Yes | Preamble + 4 items (reading list, archive register, Section 4 summary, confirm-memory-restored ack) |
| Yes | No | Preamble + 3 items (reading list, Section 4 summary, confirm-memory-restored ack) |
| No | Yes | 4 items (reading list, archive register, Section 4 summary, confirm-frame-loaded ack) |
| No | No | 3 items (reading list, Section 4 summary, confirm-frame-loaded ack) |

Item 4's acknowledgment text varies based on has-memory: "Confirm memory restored cleanly and the project frame is loaded" vs. "Confirm the project frame is loaded." Items 1 and 3 are TODO markers for synthesis-Claude; items 2 (when present) and 4 are templated and emitted directly by the generator with substitutions applied.

### Generator emits the final post-synthesis header directly

Pre-v1.5.1, `generate_blueprint.py` emitted a TODO-synthesis header ("Sections 1, 3, 4, and 6 are flagged for synthesis — see `_BLUEPRINT_SYNTHESIS_NOTES.md`"). Synthesis-Claude was implicitly expected to rewrite the header during the synthesis pass — fragile, because the rewrite had no explicit TODO marker, and synthesis-Claude could leave the synthesis-state header in the final blueprint.

v1.5.1: the generator emits the final "How to use this file" header directly. Synthesis-Claude's job is bounded to "fill the explicit TODO markers" — no implicit "and also rewrite the header" requirement. Reduces failure surface.

## Transcript archival mechanics — what the orchestrator should and shouldn't do (v1.6)

A pattern observed in real-data runs: when archiving session transcripts in the multi-project Track A recon-driven flow, the orchestrator was repeatedly going off-script — gauging sizes, investigating the inline-vs-diverted tool-result distinction, probing `.claude/projects/` mounts, surfacing "full-fidelity vs. condensed?" decisions to the user mid-loop, and using transcript content as input to subsequent steps (e.g., "I read in session 4 that memory was dumped — skipping memory step"). The single-project flow had picked up explicit anti-pattern guidance after the v1.4→v1.5 run, but the multi-project flow's Step 3 was abstract enough that the model improvised differently.

The mechanism the orchestrator should use is simple and bounded:

1. **Call `mcp__session_info__read_transcript(session_id=<id>, format='full')`.** No `limit` parameter — full fidelity by default.
2. **Take whatever the tool returns and Write it verbatim to disk** at `<picked-folder>/conversation-history/<filename>.md`. The Write tool accepts large content; both inline and diverted-to-file results land at disk via Write. If for some reason the tool returns a divert-file pointer instead of inline content, Read that file then Write the content — but in practice the tool result IS the content for the vast majority of transcripts.
3. **Emit one short progress line** (`"Session N of M done."`) after each save. Nothing else.

Things the orchestrator should NOT do:

- Read the first transcript to "gauge size" before processing the rest.
- Investigate where diverted transcripts land (`/sessions/.../mnt/.claude/projects/`, virtiofs mounts, advertised-vs-actual paths). The mechanism is opaque on purpose.
- Compare inline-vs-diverted behavior, hypothesize about "working memory consumed by reproducing inline content," or surface mid-loop fidelity decisions to the user.
- Condense, summarize, characterize, or edit transcript content. The transcript IS the archive; the title (already in `recon_data`) IS the description.
- Use anything observed inside transcript content as input to subsequent decisions (e.g., "the transcript mentioned a memory dump, so I'll skip the memory step"). The skip-if-already-done check for memory is a directory listing against disk, not transcript-content inference.

These are restatements of Discipline rules #10 (archive mechanically, don't synthesize) and #11 (stay on task — don't act on incidental content), made concrete at the step level so the orchestrator doesn't need to abstract from the general rule to the specific behavior.
