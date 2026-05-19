---
name: account-migration
description: Walk the user through migrating their projects, conversations, and accumulated context between two Claude accounts. Use this skill whenever the user mentions migrating to a new Claude account, switching from a personal account to a corporate/Teams account, exporting projects, transferring Cowork projects, or any account-transition scenario — including when they don't say "migration" but describe the underlying need ("I'm getting a Teams account", "I need to move my work projects somewhere new", "help me get my projects off this account", "we're switching to a corporate plan"). Anthropic provides a data export but no import; this skill bridges that gap with a tracked, decision-driven walk-through across both source and destination accounts.
---

# Claude Account Migration

## When to invoke

Use this skill whenever the user wants to move data between two Claude accounts. The trigger is the account-transition intent, not specific keywords — the user may say "migrate," "switch," "move," "transfer," or describe the situation in their own words. Common phrasings include:

- "I'm getting a corporate Claude account, need to move stuff over"
- "We're switching to a Teams plan, how do I bring my projects?"
- "I want to consolidate two Claude accounts"
- "Can you help me export everything from my personal Claude account?"

Direction is metadata, not mechanics. Personal→corporate, corporate→personal, personal→personal — the flow is the same. The skill handles which side the user is currently on via its opening question.

## What this skill does

Anthropic exports your Claude data but doesn't import it. Claude.ai conversations are flat and unattributed in the export; Cowork session storage is intentionally walled off from skills. The general migration story is therefore: extract what's portable from the source account, hand the user the manual checklist for everything that's not, and drive a full interactive walk-through across both source and destination accounts.

Concretely, this skill drives a three-phase flow split across two tracks:

- **Track A (source account):**
  - **Part 1 (web/chat projects)** — process the user's data export, recover per-project attribution from a saved copy of their Chats page, walk the user through a pick/skip decision per project, and reconstruct picked projects as on-disk folders with a `_PROJECT_BRIEF.md`, `knowledge/`, and `conversation-history/`. Inline artifacts (code, scripts, markdown produced by Claude) are extracted to per-conversation `artifacts/` subfolders. Binary files referenced but not in the export get listed in `_ARTIFACTS_TO_RECOVER.md` for manual recovery.
  - **Part 2 (Cowork projects)** — collect existing Cowork project folders from the user via a picker loop. Write a `_PROJECT_BRIEF.md` next to each one's working files (folder contents are not touched). Also write a `transition-data/migration-prompt.md` carrying the per-project blueprint prompt the user runs in each Cowork session on the old account before deletion.
  - **Custom-skills capture** — user collects their custom `.skill` installer files into a `skills/` subfolder in the hub (including this migration skill itself, so the new account can run Track B).
  - **End-of-Track-A wrap** — write `README - Final Transition to New Account.md`, `memory-capture-prompt.md`, and the `tracker.html` handoff file to the hub. Tell the user how to start Track B on the new account.

- **Track B (destination account)** — full interactive walk-through that drives the new-account setup. Reads the tracker the source side left, then: seeds global memory from `memory-capture.md`, sets up the catch-all as a Cowork project on this account, walks through each project to relink (Part 1 reconstructed + Part 2 Cowork), walks through binary recovery from the recovery checklist, runs validation, walks through hub cleanup. The same skill drives both tracks via the **"old" / "new"** branch at Prompt 0.

A **migration hub** Cowork project (the user creates this themselves at the start of Track A; default suggestion is "Migrated Conversation History" but the user can name it anything) is the catch-all for orphan conversations and any project the user chose to skip. It's also where the tracker, the README, the memory-capture prompt, and the `skills/` subfolder live. On the new account during Track B, the user re-imports this same hub folder as a Cowork project so the skill runs in its context.

## Files in this skill

This skill uses progressive disclosure — `SKILL.md` orchestrates; longer content lives in subfolders. Read them when prompted by the flow below.

### `scripts/`

Run these via `mcp__workspace__bash`. Stage them into a non-OneDrive scratch directory at session start before invoking (see "OneDrive truncation gotcha" below).

- `extract_export.py` — splits the export's `conversations.json` into per-conversation transcripts + a manifest. Run after the user uploads the export to the hub.
- `parse_allchats.py` — content-detects the user's saved Chats page (any `.html` in the hub) and produces `attribution_map.csv`. Run after `extract_export.py`.
- `reconstruct.py` — given the manifests, attribution map, export-unzipped data, and per-project routing decisions, writes the per-project folder layouts (`_PROJECT_BRIEF.md`, `knowledge/`, `conversation-history/INDEX.md`, transcripts). Drives Part 1 reconstruction in place + catch-all routing.
- `reshape_and_extract.py` — extracts inline artifacts (`tool_use:artifacts` + `tool_use:create_file`) into per-conversation subfolders and builds `_ARTIFACTS_TO_RECOVER.md` for non-inline binaries. Runs after reconstruction.
- `package_self.py` — re-packages the skill's source folder into a fresh `.skill` (zip) file. Used by Step 3.5 (custom-skills capture) to drop `account-migration.skill` into the hub's `skills/` subfolder so the user doesn't have to find the original installer.

### `assets/` (templates and canonical prompts)

These are deliverables the skill writes to the user's disk verbatim (or with minor substitution). Read each one and write to the appropriate location when the flow indicates.

- `README-template.md` — full content of `README - Final Transition to New Account.md`. Written to the migration hub at end of Track A. Two sections: skill-assisted Track B (at the top, primary path) and manual fallback (below). Substitution markers (`<N_projects>`, `<N_reconstructed>`, `<N_routed>`, `<N_unattributed>`, `<N_recover>`, `<catchall_name>`) get filled in from the run's actual counts.
- `migration-prompt-template.md` — the per-Cowork-project blueprint prompt. Written to `<project>/transition-data/migration-prompt.md` for each Part 2 folder the user picks. Substitution: replace `<PROJECT NAME>` with the picked folder's name.
- `memory-capture-prompt.md` — the global memory-capture prompt the user runs on the old account, no project selected. Written to the hub root at end of Track A as a standalone file. Produces `memory-capture.md`, consumed by Track B's memory-seed phase.
- `memory-seed-prompt.md` — the memory-seed prompt the user runs on the new account in a no-project conversation, with `memory-capture.md` attached. Written to the hub root at end of Track A so it's available when Track B starts.
- `validation-prompt.md` — the validation prompt the user runs on the new account at end of Track B. Embedded in Track B Phase 6.

### `references/` (read as needed)

Longer reference material that doesn't need to be in context all the time. Read selectively based on what the flow is doing.

- `skill-user-facing-text.md` — the canonical locked copy of every user-facing prompt the skill speaks. **When the flow says "display Prompt N," find Prompt N in this file and display the fenced block verbatim.** Wording is deliberate — do not paraphrase, do not embellish.
- `architecture-notes.md` — key architectural decisions, the three project categories, the three artifact kinds, the tracker JSON schema, the layout schemas. Read when you need to understand *why* the flow looks the way it does or when you're about to make a structural decision not covered in SKILL.md.

## The flow

### Discipline rules — read before invoking

These are baked-in operational rules. They apply to every interaction during the skill run; don't drop them.

1. **Stay in frame between prompts.** Display each user-facing prompt verbatim from `references/skill-user-facing-text.md` in a code-fenced block. Don't weave meta-commentary into the same response. If something is worth saying that the locked copy doesn't say, save it for an end-of-session notes file, not the live chat.
2. **Don't re-litigate locked architecture.** The skill has settled decisions (selective-pick replaces name-matching; skip routes to catch-all not drop; catch-all setup is first; memory seed before walk-through in Track B; etc.). Act on them; don't surface them to the user as decisions to re-make.
3. **Folder access is always the picker.** Every `mcp__cowork__request_cowork_directory` call uses no `path` argument (picker mode). Never guess a path from a suggested name; never ask the user to type a path. Precede the call with a brief "I'm going to have you select the folder for X" message.
4. **Picker cancel after "pick" is a possible mistake.** Don't silently treat picker-cancel as skip. Re-ask with pick / skip / quit. (Quit ends the whole skill cleanly; tracker stays on disk for resumption.)
5. **Tracker reflects current state.** After every state transition (catch-all created, project picked, project skipped, folder granted, reconstruction done, relink done), update both the on-disk `tracker.html` AND the Cowork sidebar artifact. Never write "to be created" for something the user is about to create on the next turn.
6. **Artifact descriptions and update summaries are user-facing copy.** The `description` and `update_summary` fields passed to `mcp__cowork__create_artifact` / `update_artifact` show in the approval prompt. Write them in plain English from the user's perspective, not as implementation notes.
7. **Briefs are factual, not narrative.** The `_PROJECT_BRIEF.md` files this skill writes contain provenance, custom instructions (verbatim from export), knowledge inventory, conversation count, a "Resuming on the new account" section with the bootstrap instructions verbatim, and a short notes block. They do not synthesize "what's important about this project" — that's the destination-side Claude's job on demand, driven by the blueprint. (Project blueprints, written separately, are the place for narrative synthesis when appropriate.)
8. **Reconstruction happens inline, not deferred.** As each per-project pick/skip is made, immediately run the reconstruction work for that project before the next prompt fires. Don't batch to end of Track A.

### Step 0 — Stage scripts to non-OneDrive scratch

**Why this exists:** the user's Cowork install may sync the migration hub through OneDrive. OneDrive can leave file copies in a placeholder state at rest (a real failure mode). The four `.py` scripts bundled here must be written fresh into a non-synced scratch directory at session start, then run from there.

At session start, before displaying any user-facing prompt:

```python
# Read each script from this skill folder and write to scratch
# Scratch location should be inside the agent's session outputs/, not the user's hub
SKILL_PATH = "<path-to-this-skill-folder>"
SCRATCH = "<session>/outputs/migration-scratch"
# Copy: extract_export.py, parse_allchats.py, reconstruct.py, reshape_and_extract.py
```

Do this silently — the user does not need to know.

### Step 1 — Opener and side selection

Display the opener from `references/skill-user-facing-text.md` (section "Prompt 0 — skill opener + Track A/B branch") verbatim. Wait for user response.

- **"old"** → display the Part 1 banner: `▶ Part 1: Preparing Claude Chat and Chat Projects (Old Account) ◀`. Then proceed to Step 2 (Track A).
- **"new"** → display the Part 3 banner: `▶ Part 3: Setting Up Claude Cowork (New Account) ◀`. Then proceed to Step 5 (Track B).

### Step 2 — Track A, Part 1 (web/chat projects)

The full Part 1 flow lives in `references/skill-user-facing-text.md` under "Prompt 1" through "Prompt N+1.5". Display each in turn, executing the implementation actions between them.

High-level orchestration:

1. **Prompt 1**: ask the user to drop two files (export zip + saved Chats HTML) into the migration hub folder. Wait for "ready."
2. **Prompt 2**: display the "Got it, in the folder I see X, hang tight" inventory message with the real filename + size of both inputs.
3. **Execute** (silent during the "hang tight" pause):
   - Unzip the export to `<scratch>/export-unzipped/`.
   - Run `extract_export.py` with `--export <scratch>/export-unzipped --outdir <scratch>/extracted`.
   - Stage the AllChats HTML + the conversation manifest together; run `parse_allchats.py` against them to produce `attribution_map.csv`.
4. **Prompt 2.5**: display the headline counts (total convs, attributed, catch-all, dropped). Substitute the real numbers from the manifest + attribution map.
5. **Build the tracker** (dual-render): write `tracker.html` to the hub, and call `mcp__cowork__create_artifact` with the same HTML. Use plain-English descriptions for the artifact. Architecture in `references/architecture-notes.md` covers the columns and embedded handoff-state JSON schema.
6. **Prompt 3**: display the "I've opened your tracker. Set up the catch-all" message. Wait for the user to create the catch-all Cowork project and say "ready."
7. **Prompt 3.5** (post-ready bridge): display "Bringing up the folder picker so you can select <catchall_name>'s folder." Then call `mcp__cowork__request_cowork_directory` with no path (picker mode).
8. **Per-project walk-through**: alphabetical order. Filter built-in starter projects (marked `is_starter_project: true` in the export) silently. For project 1, display the verbose Prompt 4 (full rules). For projects 2–N, display the terse Pattern 5–N (import-prompt → ready / skip / quit). After "ready," display Prompt 4.5. After "pick," display the post-pick folder-picker bridge, then fire the picker.
9. **On each pick** (empty or non-empty) **or skip**: run the per-project reconstruction inline via `reconstruct.py` for that single project + run `reshape_and_extract.py` for artifact extraction. Update the tracker row + JSON state + Cowork artifact. Display the post-pick confirmation line. Then fire the next per-project prompt.
10. **Cancel handling**: if `request_cowork_directory` returns "Directory selection was cancelled by the user" after the user said "pick," do NOT silently fall through. Display the cancel re-ask: pick (re-fire) / skip (route to catch-all) / quit (end skill).
11. **End of Part 1**: display the Part 1 boundary wrap (substituting actual counts), then auto-generate `transition-data/project-blueprint.md` for each reconstructed (empty-pick) project from the extracted data. Update tracker. Continue to Part 2.

### Step 3 — Track A, Part 2 (Cowork projects)

The Part 2 flow lives in `references/skill-user-facing-text.md` under "Part 2 — preparing Cowork projects (source account)."

1. Display the Part 2 banner: `▶ Part 2: Preparing Claude Cowork (Old Account) ◀`.
2. **Part 2 Prompt 1**: display the opener with continue / skip and the heads-up about what doesn't migrate (working-folder attachments, session history, project memory).
3. **On "continue"**: enter the folder-picker loop. Each iteration:
   - Display the folder-picker bridge.
   - Call `mcp__cowork__request_cowork_directory` with no path.
   - On successful pick: display the per-folder processing confirmation. Write `_PROJECT_BRIEF.md` to the folder root — same brief structure `reconstruct.py` produces for Part 1 projects (provenance, custom instructions where available, knowledge inventory, conversation count, **"Resuming on the new account"** section with the bootstrap prompt verbatim, notes). Write `migration-prompt.md` to `transition-data/` using `assets/migration-prompt-template.md` with `<PROJECT NAME>` substituted. **Append an entry to the tracker's `cowork_projects` array** with the picked folder name and path.
   - On picker cancel: display the cancel-confirmation prompt (done / continue / quit).
4. **On "skip" at opener** or "done" at cancel-confirmation: advance the tracker `phase` field to `"track-a-part-2-complete"`. Display the Part 2 wrap.

### Step 3.5 — Custom-skills capture (Track A)

Fires after Part 2 wraps and before the end-of-Track-A cleanup wrap. The Track B README's Step 1.5 (manual fallback) documents the same flow as a checklist; this step makes it an in-session prompt so users actually do it before deletion of the old account.

The full user-facing copy lives in `references/skill-user-facing-text.md` under "Custom-skills capture".

Orchestration:

1. **Auto-create `skills/` and package the skill into it.** Before displaying the opener, create the hub's `skills/` subfolder if it doesn't exist, then run `scripts/package_self.py` (via `mcp__workspace__bash`) to write a fresh `account-migration.skill` into it:
   ```sh
   python3 <SKILL_PATH>/scripts/package_self.py <SKILL_PATH> <HUB>/skills/account-migration.skill
   ```
   Pass the skill's original source path (not the scratch staging copy) so the packaged .skill is byte-faithful to what's installed. If the script fails (non-zero exit), log and continue — the user can still add the file manually via Step 1.5 of the README.
2. Display the **custom-skills opener** prompt. The opener mentions that the migration skill has already been put in `skills/`. Wait for user response.
3. **On "ready"**: check the hub's `skills/` subfolder for `.skill` or `.zip` files. At minimum, the auto-packaged `account-migration.skill` is there.
   - **Found additional files beyond the auto-packaged skill** (or just the auto-packaged skill and the user is done): display the **custom-skills confirmation — files found** prompt with a sized listing. Append a `custom_skills` array to the tracker's handoff-state JSON listing all captured filenames. Proceed to Step 4.
   - **Only the auto-packaged skill is there, user said "ready" anyway**: same as above. The auto-packaged skill is the minimum viable state.
   - **Soft re-ask edge case**: if for some reason the auto-package failed AND the user added nothing, display the **soft re-ask** with the user-added context only.
4. **On "skip"**: display the **skip confirmation** one-liner. Set the tracker's `custom_skills` array to contain just the auto-packaged migration skill entry. Proceed to Step 4.
5. **On "quit"**: end the skill cleanly. Tracker stays on disk; user can resume later.

The tracker's `<script type="application/json" id="handoff-state">` block carries `custom_skills` as `[{"filename": "...", "size_bytes": N}, ...]`. The auto-packaged migration skill is always in this list when Step 3.5 has run.

### Step 4 — End-of-Track-A wrap

1. Write `README - Final Transition to New Account.md` to the migration hub by reading `assets/README-template.md` and substituting the run's counts and the actual `<catchall_name>`. Also write `memory-capture-prompt.md` and `memory-seed-prompt.md` to the hub root as standalone files (the user pastes the former on the old account to produce `memory-capture.md`; the latter is referenced by Track B's memory seed phase).
2. Advance the tracker's `phase` field to `"track-a-complete"`. Update both representations (file + artifact).
3. Display the Track A wrap message from `references/skill-user-facing-text.md` ("Prompt N+2 — Track A wrap"). The prompt enumerates the 4-step new-account bootstrap (get hub onto new machine, install skill, import hub as Cowork project, invoke skill and pick "new").
4. Skill exits cleanly. Tracker stays on disk for Track B.

---

### Step 5 — Track B Phase 1 (opener + hub access + inventory)

Fires after the user picks "new" at Prompt 0 and the Part 3 banner displays. The full Track B flow lives in `references/skill-user-facing-text.md` under "Track B — destination-account relink".

Orchestration:

1. **Hub detection.** Inspect the current Cowork project's working folder for `tracker.html`. If present, the skill is already running inside the migration hub → take the B-1a branch (no picker needed for hub access). If absent, take the B-1b branch.
   - **B-1a**: display the B-1a opener. Wait for "ready" / "hold" / "quit".
   - **B-1b**: display the B-1b opener. Wait for "ready" / "hold" / "quit". On "ready", display **Prompt B-2** (hub picker bridge), then call `mcp__cowork__request_cowork_directory` with no path.
2. **Tracker parse.** Read `tracker.html`, extract the embedded `<script type="application/json" id="handoff-state">` block, parse the JSON. Validate `schema_version`.
   - **Happy path**: silent, proceed to inventory.
   - **JSON unparseable but rendered HTML table readable**: display **Prompt B-3b** (partial corruption). Reconstruct counts from the HTML rows. Folder paths are lost — per-project picker will be by name only. Continue.
   - **Nothing parseable**: display **Prompt B-3c** (disaster). Wait for "pick" (re-pick hub via picker), "quit", or any unrecognized response treated as quit.
3. **Inventory display.** Display **Prompt B-4** with the counts computed from the tracker state:
   - `<N_part1_reconstructed>` = count of projects where `reconstructed == "done_in_place"`
   - `<N_part2_cowork>` = length of `cowork_projects` array
   - `<catchall_name>`, `<N_orphans>`, `<N_part1_catchall>` = from the `catchall` block
   - `<N_recover>` = count of unchecked items in `_ARTIFACTS_TO_RECOVER.md` (read from the catch-all once it's accessible; see Step 7's catch-all pick)
   - `<N_custom_skills>` = length of `custom_skills` array
   - Conditionally drop any bullet whose count is 0.

### Step 6 — Track B Phase 2 (memory seed)

Fires after Step 5's inventory display. Memory seeds Claude's account-level memory on the new account from `memory-capture.md` so per-project conversations later in Track B inherit the global context.

Orchestration:

1. Display **Prompt B-MS-1** (memory seed opener).
2. Wait for user response:
   - **"done"** → display **Prompt B-MS-2** (done confirmation). Mark memory-seed-phase as `done` in the tracker. Proceed to Step 7.
   - **"skip"** → display **Prompt B-MS-3** (skip confirmation). Mark memory-seed-phase as `skipped` in the tracker. Proceed to Step 7.
   - **"quit"** → end the skill cleanly.

### Step 7 — Track B Phase 3 (catch-all setup)

Fires after memory seed. User creates the catch-all as a Cowork project on the new account, grants the skill access via picker so it can verify orphan count + per-project subfolders.

Orchestration:

1. Display **Prompt B-5** (catch-all setup) using `<catchall_name>` and `<catchall_folder_path>` from the tracker's `catchall` block.
2. Wait for "ready" / "quit".
3. On "ready", display **Prompt B-5.5** (catch-all picker bridge), then call `mcp__cowork__request_cowork_directory` with no path.
4. After folder access is granted: verify the folder has the expected structure (`unattributed-conversations/` subfolder + per-project subfolders matching tracker entries with `reconstructed == "done_routed_to_catchall"`). Read `_ARTIFACTS_TO_RECOVER.md` to compute the unchecked count for use in Step 9.
5. Display **Prompt B-5.6** (post-pick confirmation). Proceed to Step 8.

### Step 8 — Track B Phase 4 (walk-through)

Fires after catch-all setup. Iterates over Part 1 reconstructed + Part 2 Cowork projects (skipping Part 1 catch-all-routed entries — those review inside the catch-all).

Orchestration:

1. Display **Prompt B-6** (walk-through verbose intro). Use `<N_walkthrough>` = `<N_part1_reconstructed> + <N_part2_cowork>`.
2. Iterate, in tracker order, over the projects to walk:
   - From `projects` array: entries where `reconstructed == "done_in_place"`. `<source_kind>` = `"reconstructed from web/chat"`.
   - From `cowork_projects` array (all entries). `<source_kind>` = `"Cowork from old account"`.
3. For each project, display the **per-project pattern** prompt with substitutions filled in from the tracker entry (`<project_name>`, `<source_kind>`, `<N_convs>`, `<N_docs>`, `<folder_path>`).
4. Wait for "ready" / "skip" / "quit":
   - **"ready"** → display the **per-project picker bridge**, call `mcp__cowork__request_cowork_directory` with no path.
   - **"skip"** → display **per-project skip confirmation**. Mark `relinked = "skipped"` in the tracker for this project. Next project's prompt fires.
   - **"quit"** → end the skill cleanly. Current project + remaining projects stay `relinked = "pending"`.
5. After folder access is granted, verify the folder's structure:
   - **Blueprint found at `transition-data/project-blueprint.md`** → display the **happy-path post-pick** prompt. Wait for "done" / "skip ahead". Mark `relinked = "done"` (on "done") or `relinked = "done_no_bootstrap"` (on "skip ahead").
   - **Blueprint missing (Part 2 only)** → display the **blueprint-missing branch**. Wait for "continue" / "go back" / "skip". Handle each as appropriate.
   - **Folder structure unexpected** → display the **folder-wrong branch**. Wait for "pick" (re-fire picker) / "skip" / "quit".
6. Cancel handling: if `request_cowork_directory` returns "Directory selection was cancelled by the user" after the user said "ready"-then-implicit-pick, re-ask with pick / skip / quit (same as Track A's cancel pattern).
7. After all projects walked: advance tracker `phase` to `"track-b-walkthrough-complete"`. Proceed to Step 9.

### Step 9 — Track B Phases 5–7 (binary recovery, validation, cleanup)

Fires after walk-through.

#### Phase 5 — Binary recovery

1. Read `_ARTIFACTS_TO_RECOVER.md` from the catch-all. Parse the unchecked items, grouped by conversation. If zero unchecked, display the silent one-liner ("No binaries to recover — moving on.") and proceed to Phase 6.
2. Display **Prompt B-BR-1** (binary recovery opener).
3. Wait for "ready" / "skip" / "quit".
4. On "ready", iterate per-conversation. For each conversation with unrecovered files:
   - Display the **per-conversation pattern** prompt with `<conversation_title>`, `<destination_label>`, `<transcript_relative_path>`, `<N_files>`, the filename list, the `https://claude.ai/chat/<conv_uuid>` URL, and `<artifacts_folder_relative_path>`.
   - Wait for "done" / "skip" / "quit".
   - On "done": tick the checkboxes in `_ARTIFACTS_TO_RECOVER.md` for this conversation's files. Move to next.
   - On "skip": leave checkboxes unchecked. Move to next.
   - On "quit": end the skill cleanly.
5. Display **Prompt B-BR-wrap** with the recovered/remaining counts.

#### Phase 6 — Validation

1. Display **Prompt B-V-1** (validation opener).
2. Wait for "done" / "skip" / "quit".
3. Display **Prompt B-V-2** (done) or **Prompt B-V-3** (skip) accordingly. Proceed to Phase 7.

#### Phase 7 — Cleanup wrap

1. Display **Prompt B-C-1** (cleanup opener).
2. Wait for "done" / "skip" / "quit".
3. Display **Prompt B-C-2** (done) or **Prompt B-C-3** (skip) accordingly. On quit, just exit.
4. Advance tracker `phase` to `"track-b-complete"` (whether cleanup was done or skipped — the tracker entry tracks intent, not external state).
5. Display **Prompt B-X-1** (Track B closing). Assemble conditional reminders based on which phases were skipped during this Track B run.
6. Skill exits cleanly.

## The artifact taxonomy (operational reference)

A Claude data export's `chat_messages[].content[]` carries three distinct `tool_use` patterns for assistant-produced content. The skill handles each differently — `reshape_and_extract.py` implements all three. Detail in `references/architecture-notes.md`.

1. **`tool_use: artifacts`** — Claude's web Artifacts panel. Content inline. **Extract** to `<conv-slug>/artifacts/<title>.<ext>` using `type` (and `language` for code) for extension.
2. **`tool_use: create_file`** — file written via Claude's web file tools (typically build scripts). Content inline in `input.file_text`. **Extract** to `<conv-slug>/artifacts/<basename-of-path>`.
3. **`tool_use: present_files`** binary outputs (`.docx`, `.xlsx`, etc.) — only the filepath reference is in the export, no binary. **Not extractable.** List in `_ARTIFACTS_TO_RECOVER.md` at the catch-all root.

## Tracker JSON schema (handoff-state)

`tracker.html` carries an embedded `<script type="application/json" id="handoff-state">` block. Track A writes it; Track B reads it. Full schema in `references/architecture-notes.md`. Key fields:

- `schema_version` — currently `1`.
- `phase` — string enum: `"track-a-part-1-complete"`, `"track-a-part-2-complete"`, `"track-a-complete"`, `"track-b-walkthrough-complete"`, `"track-b-complete"`.
- `catchall` — `{name, folder_path, orphan_count, subfolder_count, ...}` for the catch-all.
- `projects` — array of Part 1 web/chat projects. Each entry: `{order, name, uuid, docs, convs, folder_path, disposition, reconstructed, relinked}`.
- `cowork_projects` — array of Part 2 Cowork projects (added during Track A Step 3 per-folder). Each entry: `{name, folder_path, has_blueprint, relinked}`.
- `custom_skills` — array of captured custom skills (populated by Step 3.5). Each entry: `{filename, size_bytes}`.

When writing the tracker, the skill writes both `tracker.html` (file on disk) and the Cowork sidebar artifact in lockstep. After every state transition during either track, update both representations.

## OneDrive truncation gotcha

The user's migration hub will frequently sit inside OneDrive (or another cloud-synced location). OneDrive can leave files in a partially-synced state where the directory entry exists but a read returns "no such file" or a truncated body. The sandbox's bash mount also keeps a per-path attribute cache that can serve stale views after host-side writes — see the discipline rules below.

**Three failure modes to avoid:**

- **Bundled scripts read at rest in the hub may be truncated.** Always write fresh copies from this skill folder to a non-cloud-synced scratch directory at start of run (Step 0 above). Don't trust `.py` files at rest in the hub.
- **Reading files at rest in the hub** for verification — prefer the host-side `Read` tool over `mcp__workspace__bash`, since they use different code paths and the host-side often succeeds where bash fails on the same path. Note: the host-side Read isn't iron-clad either; for high-stakes disagreements between bash and host-side Read, do a per-file rename (`mv X X.tmp && mv X.tmp X` in bash) to force a fresh attribute lookup, then re-read both.
- **Write-back cascade** — never write back to disk content that was sourced from a bash read of a pre-existing OneDrive-resident file. The bash read may be returning a stale or truncated view; writing that content back via a host-side tool produces NTFS truncation of the source file. This is the most destructive failure mode. If a script needs to update part of a tracker or a recovery-checklist file, source the existing state from process memory or regenerate from authoritative data (tracker JSON, manifest CSV, etc.) — never round-trip through bash-read-then-write.

## Cowork session storage is walled off — by design

`mcp__cowork__request_cowork_directory` will refuse paths inside Cowork's install storage. This is intentional Anthropic behavior — Cowork session content (conversation transcripts, working-folder attachments metadata, project `memory.md`) is private to the local install and does not migrate via skills. Part 2 of this skill writes a `_PROJECT_BRIEF.md` for each Cowork project the user picks, but does **not** attempt to access session storage. The user handles working-folder re-attachment manually on the destination account.

## Operational discipline reminders

These are the durable operational rules for any run. The patterns are locked — apply them, don't re-derive:

- **Stay in frame** — don't weave meta-answers into roleplay frames.
- **No preemptive reassurance** — don't preempt unraised privacy concerns in skill copy.
- **Architecture is settled, don't re-litigate** — selective-pick / catch-all-first / skip-routes-to-catch-all / memory-seed-before-walkthrough are decisions; act on them.
- **Artifact descriptions are user-facing** — the `description` / `update_summary` parameters show in approval prompts; plain English.
- **Folder access is always the picker** — no path guessing, no user-typed paths.
- **Tracker reflects current state** — update both representations (file + Cowork artifact) after every state transition.
- **Every fix is two parts** — immediate symptom fix AND permanent rule capture in the locked copy or decision blocks.
- **Picker cancel after "pick" is a re-ask** — pick / skip / quit, never silent skip.
- **Three artifact kinds, three different handlers** — inline `artifacts`, inline `create_file`, recovery-only `present_files` binary refs.
- **Never round-trip bash-read content through a host-side write.** See "OneDrive truncation gotcha" above for the cascade this prevents.

## What's NOT in this version

- **Auto-tagging of conversation content as work vs. personal.** Some users want to migrate only work content from a comingled personal account. The skill provides selective-pick at the project level but does not classify individual conversations. Manual review inside the catch-all serves this purpose.
- **Per-file granularity in binary recovery.** Recovery is per-conversation (user opens each conversation once, downloads all its referenced files). If a single conversation has many files, the user takes care of them in one pass.
- **Automated validation of new-account memory state.** The validation phase asks the user to compare Claude's response to `memory-capture.md` themselves rather than diffing automatically.
- **Cross-machine path translation in the tracker.** Folder paths in the tracker are the source-account machine's paths. On the new account at the same workstation, they remain valid; on a different machine, the user navigates via the picker. The skill does not attempt to translate paths.
