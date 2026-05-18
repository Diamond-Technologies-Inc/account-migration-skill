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

## The three artifact kinds

A conversation's `chat_messages[].content[]` can contain three patterns of assistant-produced content. Each requires different handling — `reshape_and_extract.py` implements all three.

1. **`tool_use: artifacts`** — Claude's web Artifacts panel. Inline content in `tool_use.input.content`. **Extract** to `<conv-slug>/artifacts/<safe-title>.<ext>` using `type` (and `language` for code) to pick the extension:
   - `text/markdown` → `.md`
   - `application/vnd.ant.code` with `language: javascript` → `.js` (and similar for other languages)
   - `image/svg+xml` → `.svg`
   - `application/vnd.ant.mermaid` → `.mermaid`
   - `application/vnd.ant.react` → `.jsx`
   - `text/html` → `.html`

2. **`tool_use: create_file`** — file written via Claude's web file tools (typically a build script later run via `bash_tool`). Inline in `tool_use.input.file_text`. The `path` field provides the basename. **Extract** to `<conv-slug>/artifacts/<basename-of-path>`.

3. **`tool_use: present_files`** binary outputs — `.docx`, `.xlsx`, `.pdf`, `.pptx`, images, archives. Only the filepath reference is in the export; **no binary content**. **Not extractable.** Listed in `_ARTIFACTS_TO_RECOVER.md` at the catch-all root with checkboxes for the user to manually recover from claude.ai.

The recovery file groups by destination class (reconstructed projects first, then catch-all subfolders, then orphans) and within each by conversation. If the same filename was referenced multiple times by `present_files` within one conversation, the count is shown (e.g., "3× referenced") — usually indicating versioned drafts.

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
      "size_bytes": <N>
    }
    // ... one per .skill file in the hub's skills/ subfolder
  ]
}
```

### Phase string enum

Tracks where in the overall flow the migration is:

- `"track-a-part-1-complete"` — Part 1 (web/chat projects) finished; Part 2 not yet started.
- `"track-a-part-2-complete"` — Part 2 (Cowork projects) finished; custom-skills capture not yet started.
- `"track-a-complete"` — All of Track A done (including custom-skills capture). README and memory-capture-prompt written. Ready for Track B.
- `"track-b-walkthrough-complete"` — Track B's per-project walk-through finished. Binary recovery / validation / cleanup still ahead.
- `"track-b-complete"` — Full migration complete (whether cleanup was performed or skipped).

Track A advances the phase as each sub-phase completes. Track B reads `phase` to verify it's running against a valid handoff (must be at least `"track-a-complete"` to proceed) and updates it on completion. A future run can re-enter Track B at any point and resume from where the phase indicates.

### Writing the tracker

The skill writes both representations in lockstep. The on-disk write goes through the host-side Write tool, NEVER through a bash-read → host-write cycle (see the OneDrive truncation gotcha below).

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

## OneDrive truncation gotcha

Files inside the user's migration hub may be OneDrive-synced. OneDrive can leave files in a placeholder state where the directory entry exists but a read returns "no such file" or a truncated body. The sandbox's bash mount layer also keeps a per-path attribute cache that can serve stale views to bash after host-side writes. Three failure modes follow:

- **Bundled scripts read at rest may be truncated.** Always write fresh copies from the skill folder to a non-cloud-synced scratch directory at start of run. Don't trust `.py` files at rest in the hub.

- **Reading files at rest in the hub:** prefer the host-side `Read` tool over `mcp__workspace__bash`, since they use different code paths and the host-side often succeeds where bash fails on the same path. Host-side isn't iron-clad either; for high-stakes disagreements between bash and host-side reads, force a fresh attribute lookup via `mv X X.tmp && mv X.tmp X` in bash, then re-read.

- **Write-back cascade — never round-trip bash-read content through a host-side write.** The bash read may be returning a stale or truncated view of an OneDrive-resident file; writing that content back via a host-side tool produces NTFS truncation of the source file. Most destructive failure mode. If a script needs to update a tracker or recovery file, source the existing state from process memory or regenerate from authoritative data (manifest, tracker JSON in memory) — never read-modify-write through bash.

## Cowork session storage wall

`mcp__cowork__request_cowork_directory` refuses paths inside Cowork's install storage. This is intentional Anthropic behavior — Cowork session content (JSONL transcripts, project memory.md, working-folder attachments metadata) is private to the local install.

Implications:

- Part 2 reconstruction is fundamentally less rich than Part 1. The skill writes only `_PROJECT_BRIEF.md` and `migration-prompt.md`; the user runs the migration-prompt themselves to produce a blueprint.
- Working-folder attachments don't migrate. The skill instructs the user to note them manually before deleting the old account.
- Cowork memory.md doesn't migrate. Same constraint.

**User workaround (not part of the skill).** If the user copies Cowork's install storage outside the wall to a non-protected location, the skill can read the JSONL transcripts and the per-space memory tree from that copy. This is outside the skill's normal flow and requires user-side action; the skill doesn't automate it.
