---
name: account-migration
description: Walk the user through migrating projects, conversations, and accumulated context between two Claude accounts. Supports both whole-account migrations (every project) and single-project transfers (just one named project — a re-do, a one-off transfer, validating a specific project). Use whenever the user mentions migrating, switching, or transferring between Claude accounts — whether they say "everything" or name a specific project — including phrasings like "I'm getting a Teams account," "transfer my project to my new account," "move just one project over," "switching from personal to corporate," "consolidate two Claude accounts." Anthropic provides a data export but no import; this skill bridges that gap with a tracked, decision-driven walk-through across both source and destination accounts.
---

# Claude Account Migration

## When to invoke

Use this skill whenever the user wants to move data between two Claude accounts. The trigger is the account-transition intent, not specific keywords — the user may say "migrate," "switch," "move," "transfer," or describe the situation in their own words. Two scopes are supported:

**Whole-account migration** — every project goes. Typical phrasings:

- "I'm getting a corporate Claude account, need to move stuff over"
- "We're switching to a Teams plan, how do I bring my projects?"
- "I want to consolidate two Claude accounts"
- "Can you help me export everything from my personal Claude account?"

**Single-project transfer** — just one specific project. Typical phrasings:

- "Transfer my <project name> to my new account"
- "Move just one project — <project name> — to my work account"
- "I want to re-migrate the <project name> project after a fix"
- "Bring over just my <project name> repo to here"

The two scopes share the same flow primitives but the single-project flow short-circuits steps that don't apply (no catch-all setup, no global memory seed by default, no hub-vs-project distinction — the project folder IS the hub).

Direction is metadata, not mechanics. Personal→corporate, corporate→personal, personal→personal — the flow is the same. The skill handles which side the user is currently on via its opening question (Prompt 0), and which scope they want via the scope-selection step (Step 1.5 on Track A, Step 5.5 on Track B). If the user's invocation message already specifies side and/or scope (e.g., "transfer this project to a new account" → side=new, scope=single), Prompt 0 pre-inference (see "Step 1 — Opener" below) skips the matching prompts.

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

Run these via `mcp__workspace__bash`. Stage them into a private scratch directory (inside the agent's session outputs — not the user's hub) at session start before invoking (see the "Cloud-synced hub truncation gotcha" section below for why).

- `extract_export.py` — splits the export's `conversations.json` into per-conversation transcripts + a manifest. Run after the user uploads the export to the hub. Accepts `--export <path>` and `--outdir <path>`.
- `parse_allchats.py` — content-detects the user's saved Chats page (any `.html` in the hub) and produces `attribution_map.csv`. Run after `extract_export.py`. Accepts the hub folder as a positional arg.
- `reconstruct.py` — given the manifests, attribution map, export-unzipped data, and per-project routing decisions, writes the per-project folder layouts (`_PROJECT_BRIEF.md`, `knowledge/`, `conversation-history/INDEX.md`, transcripts). Drives Part 1 reconstruction in place + catch-all routing. **Parameterized** — accepts `--extracted / --attribution / --export / --routing / --outdir / --catchall-name` (no hardcoded paths or project names). The orchestrator writes the routing JSON from walk-through state before invoking. Also detects mojibake (visible double-UTF-8 artifacts) in knowledge files and surfaces affected filenames in the project's `_PROJECT_BRIEF.md` Notes section.
- `reshape_and_extract.py` — extracts artifacts (four categories: `tool_use:artifacts`, `tool_use:create_file`, bash heredoc/tee/redirect writes, plus `_ARTIFACTS_TO_RECOVER.md` for non-inline binaries) into per-conversation subfolders. Runs after reconstruction. Same parameterized CLI shape as `reconstruct.py` (same routing JSON, same `--outdir`).
- `generate_blueprint.py` — unified blueprint generator for both Part 1 and Part 2 projects. Reads disk-resident data only (no Cowork-session-context dependency). Accepts `--project-dir <path> --type {part1|part2} [--export-project-json <path>] [--name <display>]`. Writes `transition-data/project-blueprint.md` with mechanical sections filled (Section 2 verbatim Custom Instructions, Section 5 inventory, Section 7 with the memory-restore preamble embedded verbatim from `assets/cowork-memory-restore-prompt.md`) and clear TODO markers in synthesis-required sections (1 Purpose, 3 Key Decisions, 4 WIP, 6 Recurring Context). Writes `transition-data/_BLUEPRINT_SYNTHESIS_NOTES.md` sibling with raw input excerpts (transcript opener/closer messages, full memory entry bodies, file previews) the hub Claude reads as context to write the final synthesis. For Part 2 projects, also writes `_PROJECT_BRIEF.md` at project root (symmetric with what `reconstruct.py` produces for Part 1).
- `blueprint_coverage_check.py` — end-of-Track-A ship-readiness check. Takes one or more project folders (positional, or via `--folders-file`) and verifies each has `transition-data/project-blueprint.md` on disk. Exits non-zero if any missing — orchestrator gates the user's "delete source account" step on a clean coverage check.
- `derive_install_root.py` — self-determines the Cowork install root + account/install/space/session UUIDs by reading the sandbox mount table (`findmnt -n -o SOURCE --target ...`). No user input, no path guessing. OS-aware: translates the virtiofs source to a Windows or Mac host path. Emits JSON. Used at the start of Track A to feed `render_recon_script.py`.
- `render_recon_script.py` — substitutes the derived install root into the OS-appropriate recon-script template (Windows PowerShell or macOS bash+python3) and writes a ready-to-run script into the hub folder. CLI: `--install-root --host-os {windows|mac} --out-script [--csv-output]`. Default CSV output path uses `$PSScriptRoot` / `$BASH_SOURCE` so the CSV always lands next to the script wherever the user saves it — zero assumptions about Downloads folders or cloud-sync products.
- `parse_recon_csv.py` — reads the sessions-recon CSV the user produced with the native-shell recon script, groups rows by `spaceId`, applies the universal noise filter (`.project-cache`, `/tmp/`, `\Temp\`, `/var/folders/`) to `userSelectedFolders`, and emits structured JSON. CLI: `--csv --own-space-id [--filter-space-id] [--out]`. The `--filter-space-id` mode drives single-project runs (Step 2.0 gate).
- `package_self.py` — re-packages the skill's source folder into a fresh `.skill` (zip) file. Used by Step 3.5 (custom-skills capture) to drop `account-migration.skill` into the hub's `skills/` subfolder so the user doesn't have to find the original installer.

### `assets/` (templates and canonical prompts)

These are deliverables the skill writes to the user's disk verbatim (or with minor substitution). Read each one and write to the appropriate location when the flow indicates.

- `README-template.md` — full content of `README - Final Transition to New Account.md`. Written to the migration hub at end of Track A. Two sections: skill-assisted Track B (at the top, primary path) and manual fallback (below). Substitution markers (`<N_projects>`, `<N_reconstructed>`, `<N_routed>`, `<N_unattributed>`, `<N_recover>`, `<catchall_name>`) get filled in from the run's actual counts. **Substitution mechanics** are explicit in Step 4 below; the orchestrator does the find/replace, not a separate script.
- `migration-prompt-template.md` — the per-Cowork-project blueprint prompt. **Fallback path only as of v1.5** — the primary flow uses `generate_blueprint.py` invoked from the hub. This template stays in the bundle for users who run Track A by hand without the full skill flow. Substitution: replace `<PROJECT NAME>` with the picked folder's name.
- `memory-capture-prompt.md` — the global memory-capture prompt the user runs on the old account, no project selected. Written to the hub root at end of Track A as a standalone file. Produces `memory-capture.md`, consumed by Track B's memory-seed phase. **Note:** this is global / account-level memory (Chat-side). Per-project Cowork memory is handled separately by `cowork-memory-dump-prompt.md` (one paste per source-account project).
- `memory-seed-prompt.md` — the memory-seed prompt the user runs on the new account in a no-project conversation, with `memory-capture.md` attached. Written to the hub root at end of Track A so it's available when Track B starts. Global / account-level memory only; per-project Cowork memory restore is folded into each project blueprint's Section 7.
- `cowork-memory-dump-prompt.md` — per-project source-side prompt. Written to each Part 2 (Cowork-native) project's `transition-data/` folder by the orchestrator during Step 3. User pastes it in that project's own source-account Cowork session; Claude there writes the project's Cowork memory entries to `<project>/transition-data/cowork-space-memory/`. Mechanical / no analysis.
- `recon-script-windows.ps1.template` — Windows PowerShell recon script template. Contains `{{BASE_PATH}}` and `{{OUTPUT_CSV}}` placeholders that `render_recon_script.py` substitutes. Walks every per-session JSON file under the install root and writes a CSV of seven non-sensitive fields per session (sessionId, spaceId, title, createdAt, lastActivityAt, isArchived, userSelectedFolders). Run by the user in their native PowerShell — the sandbox can't read these JSONs (the install root isn't mounted). Output defaults to `$PSScriptRoot\sessions-recon.csv` (next to the script wherever the user saved it).
- `recon-script-mac.sh.template` — macOS bash+python3 equivalent of the Windows recon template. Same placeholders, same CSV shape, same script-relative output default via `$BASH_SOURCE`. Status: the path-translation rule that fills `{{BASE_PATH}}` on macOS is theoretical as of v1.5 — needs validation on a real macOS Cowork session. The recon mechanism itself (read mount source, derive host path, walk session JSONs) is OS-agnostic at the principle level.
- `cowork-session-transcript-dump-prompt.md` — **fallback path only** in v1.5. The primary transcript-archive path uses the spaceId recon (Step 2.0): the hub session iterates `read_transcript` over the session IDs from each in-scope project's recon entry, writes to `<project>/conversation-history/` directly. This paste prompt remains for the narrow case where a project's pre-spaceId-era sessions need manual attribution (blank-spaceId sessions from before a Cowork project existed as a discrete space — see architecture-notes for the blank-spaceId interpretation).
- `cowork-memory-restore-prompt.md` — destination-side fallback. The primary path is via blueprint Section 7 (which embeds this prompt's STEPS 1-5 verbatim). This standalone file in the bundle covers projects without blueprints or debug re-runs of the restore.
- `validation-prompt.md` — the validation prompt the user runs on the new account at end of Track B. Embedded in Track B Phase 6.

### `references/` (read as needed)

Longer reference material that doesn't need to be in context all the time. Read selectively based on what the flow is doing.

- `skill-user-facing-text.md` — the canonical locked copy of every user-facing prompt the skill speaks. **When the flow says "display Prompt N," find Prompt N in this file and display the fenced block verbatim.** Wording is deliberate — do not paraphrase, do not embellish.
- `architecture-notes.md` — key architectural decisions, the three project categories, the three artifact kinds, the tracker JSON schema, the layout schemas. Read when you need to understand *why* the flow looks the way it does or when you're about to make a structural decision not covered in SKILL.md.

## The flow

### Discipline rules — read before invoking

These are baked-in operational rules. They apply to every interaction during the skill run; don't drop them.

1. **Stay in frame between prompts.** Display each user-facing prompt verbatim from `references/skill-user-facing-text.md`. The locked copy is formatted as a `### ▶ Skill speaking ◀` header followed by markdown blockquote paragraphs separated by REAL blank lines (not `>` blank-line separators) — the format renders as adjacent blockquote blocks with visible vertical space between paragraphs. Reproduce that format exactly when displaying — the banner is the visual lock-in that distinguishes skill content from agent prose, the blockquote lets inline markdown (`**bold**`, lists, links) render properly, and the blank-line separators preserve paragraph spacing so the content doesn't render as one run-on blob. If you ever IMPROVISE or paraphrase prompt content (combining multiple prompts in a single display, extending with project-specific personalization, etc.), preserve the SAME paragraph-break pattern: real blank line between blockquote paragraphs, not `>` separators. Don't weave meta-commentary into the same response. If something is worth saying that the locked copy doesn't say, save it for an end-of-session notes file, not the live chat.
2. **Don't re-litigate locked architecture.** The skill has settled decisions (selective-pick replaces name-matching; skip routes to catch-all not drop; catch-all setup is first; memory seed before walk-through in Track B; etc.). Act on them; don't surface them to the user as decisions to re-make.
3. **Folder access is always the picker.** Every `mcp__cowork__request_cowork_directory` call uses no `path` argument (picker mode). Never guess a path from a suggested name; never ask the user to type a path. Precede the call with a brief "I'm going to have you select the folder for X" message.
4. **Picker cancel after "pick" is a possible mistake.** Don't silently treat picker-cancel as skip. Re-ask with pick / skip / quit. (Quit ends the whole skill cleanly; tracker stays on disk for resumption.)
5. **Tracker reflects current state.** After every state transition (catch-all created, project picked, project skipped, folder granted, reconstruction done, relink done), update both the on-disk `tracker.html` AND the Cowork sidebar artifact. Never write "to be created" for something the user is about to create on the next turn.
6. **Artifact descriptions and update summaries are user-facing copy.** The `description` and `update_summary` fields passed to `mcp__cowork__create_artifact` / `update_artifact` show in the approval prompt. Write them in plain English from the user's perspective, not as implementation notes.
7. **Briefs are factual, not narrative.** The `_PROJECT_BRIEF.md` files this skill writes contain provenance, custom instructions (verbatim from export), knowledge inventory, conversation count, a "Resuming on the new account" section with the bootstrap instructions verbatim, and a short notes block. They do not synthesize "what's important about this project" — that's the destination-side Claude's job on demand, driven by the blueprint. (Project blueprints, written separately, are the place for narrative synthesis when appropriate.)
8. **Reconstruction happens inline, not deferred.** As each per-project pick/skip is made, immediately run the reconstruction work for that project before the next prompt fires. Don't batch to end of Track A.
9. **Auto-advance between prompts.** When a prompt is informational only (no waiting on user input), advance immediately to the next prompt in the flow. Don't pause silently between informational prompts and the prompt that follows them. The intent of each prompt in `references/skill-user-facing-text.md` is signaled by whether the locked copy ends with a wait-state question; if there's no question, advance.
10. **Archive mechanically — don't synthesize.** When the flow archives or copies user data (session transcripts, memory dumps, working files), the progress reporting is mechanical: "session N of M done" / "N files written." Don't read what's being archived to summarize or characterize it. Don't qualify the archive with words like "faithful," "condensed," "key takeaway," "the big one." The existing title IS the description. If genuine per-item synthesis is needed (rare — usually only for blueprint generation), it happens in the blueprint's TODO sections via `_BLUEPRINT_SYNTHESIS_NOTES.md`, not inline during the archive step.
11. **Stay on task — don't act on incidental content.** Information surfaced while reading data for an archival/copy step is NOT input to the next step. If a transcript mentions an earlier dump, a prior fix, or a sidecar file, do not propose a recovery detour or shortcut based on that observation — proceed to the next mechanical step. The user is following a structured flow; helpful detours are off-task. Save observations for the end-of-flow wrap, not mid-flow.
12. **Adaptive detection over fixed-location assumptions.** Never hardcode "the scaffolding lives at path X." Always *detect* — check the working folder for known signals (tracker file at root, tracker file under `transition-data/`, etc.); if found, branch to the matching flow; if not found, *prompt the user to point you at the right folder* via the picker, then re-detect inside the picked folder and branch accordingly. The skill must work whether the user invokes from inside the migration source, from a fresh empty Cowork project, or from an unrelated project — without depending on the user having read any external instructions. The bundled `README - Final Transition to New Account.md` (multi-project) and `_RESUME_ON_NEW_ACCOUNT.md` (single-project) are **supplementary reference documents only** — never load-bearing for the flow. If a user hasn't opened either, the skill still walks them through end-to-end via prompts.

### Step 0 — Stage scripts to a private scratch directory

**Why this exists:** the user's migration hub may sit in a cloud-synced or otherwise permission-restricted folder, and files at rest there may be in a placeholder state where reads return truncated or empty bodies. The bundled `.py` scripts must be written fresh into a private scratch directory (inside the agent's session outputs, not the user's hub) at session start, then run from there.

At session start, before displaying any user-facing prompt:

```python
# Read each script from this skill folder and write to scratch
# Scratch location should be inside the agent's session outputs/, not the user's hub
SKILL_PATH = "<path-to-this-skill-folder>"
SCRATCH = "<session>/outputs/migration-scratch"
# Copy all nine scripts: extract_export.py, parse_allchats.py, reconstruct.py,
# reshape_and_extract.py, generate_blueprint.py, blueprint_coverage_check.py,
# derive_install_root.py, render_recon_script.py, parse_recon_csv.py
```

Do this silently — the user does not need to know.

### Step 1 — Opener and side selection

**Pre-inference (silent — before any prompt display).** Parse the user's invocation message for clear side and scope hints. Skip the matching prompts when intent is unambiguous.

Side hints:
- "old account," "source," "from this account," "migrating from," "preparing for transfer" → set `side = "old"`.
- "new account," "destination," "this one" (when the user is invoking ON the new account and refers to current), "to here," "import," "relink," "restore" → set `side = "new"`.
- Ambiguous ("starting the migration," "help me migrate") → leave unset, display Prompt 0.

Scope hints (collected at the same time):
- A specific project name, "just one," "this one project," "transfer X" where X names a project → set `scope = "single"`, capture the name as `scope_target` / `restore_target`.
- "everything," "all my projects," "whole account," "consolidate" → set `scope = "all"`.
- Ambiguous → leave unset, display Step 1.5 / 5.5 scope-selection prompt at the appropriate point.

When inferring, briefly acknowledge in plain English what you understood from the user's invocation BEFORE displaying any prompt — e.g., `"Got it — single-project transfer to this (new) account, project name '<name>'. Skipping the side and scope questions."` Then advance directly to the next relevant prompt for that branch. If pre-inference yields `side = "old"` AND `scope = "single"` AND `scope_target` is set, skip both Prompt 0 and Prompt 1.5; advance to Step 2.0 (install recon). If only side is clear, skip Prompt 0 but still ask scope at Step 1.5. Etc.

**When side is NOT inferable**: display the opener from `references/skill-user-facing-text.md` (section "Prompt 0 — skill opener + Track A/B branch") verbatim. Wait for user response.

- **"old"** → display the Part 1 banner: `▶ Part 1: Preparing Claude Chat and Chat Projects (Old Account) ◀`. Then proceed to Step 1.5 (scope gate) before Step 2 (Track A Part 1).
- **"new"** → display the Part 3 banner: `▶ Part 3: Setting Up Claude Cowork (New Account) ◀`. Then proceed to Step 5 (Track B).

### Step 1.5 — Migration scope (single-project vs. all-projects)

Display the **scope-selection** prompt from `references/skill-user-facing-text.md`. Ask whether the user is migrating their whole account or just one specific project this run. Wait for response.

- **"all"** → set `migration_scope = "all"` in run state. Proceed to Step 2.0 (install recon).
- **"one"** → display the **single-project-name** prompt; wait for the user to type a project name (free-form). Store as `migration_scope = "single"`, `scope_target = "<typed-name>"`. Proceed to Step 2.0.
- **"quit"** → end the skill cleanly.

Scope filtering is applied at every per-project loop downstream:

- Part 1 (Step 2): filter the export's `projects_manifest.csv` candidates by case-insensitive substring match against `scope_target` before the walk-through loop. If zero matches, Part 1 processes zero projects (no error — the chosen project may be Cowork-native only).
- Part 2 (Step 3): pass `--filter-space-id <space>` to `parse_recon_csv.py` where `<space>` is the recon-CSV spaceId whose project name matches `scope_target`. If zero matches, Part 2 processes zero projects (no error — the chosen project may be web/chat only).

If both Part 1 and Part 2 process zero projects in single-project mode, surface the **no-match** prompt (lists the names found on each side so the user can spot a typo) and offer pick / retry / quit.

### Step 2.0 — Install recon (project-membership map)

Fires once per Track A invocation, before Part 1's per-project walk-through. Produces the authoritative session-to-project attribution map that Steps 2 and 3 read.

**Why this exists.** `list_sessions` returns sessions account-wide with no project membership in its output. The on-disk per-session JSON files DO carry `spaceId` (= project identity) and `userSelectedFolders` (= the working-folder reattach list), but they live outside any sandbox mount. The user runs a small recon script in their native shell to extract that data into a CSV the skill can read.

Orchestration:

1. **Derive the install root + own spaceId.** Run `derive_install_root.py --pretty` (or capture JSON). Extract `install_root_host`, `host_os`, and `space_uuid` (this is the migration hub's own spaceId — used later to flag the hub's own project as `is_own_space` so the walk-through can exclude it).
2. **Render the OS-appropriate recon script — scratch first, then verified copy to hub.** Cloud-synced hub folders can serve a partially-uploaded file to the user when they click the `present_files` link; the rendered PowerShell case has hit this in practice (the user received a truncated script and had to hand-patch the closing block). Follow this pattern:
   1. Render into the private scratch directory first:
      ```sh
      python3 <SCRATCH>/render_recon_script.py \
        --install-root '<install_root_host>' \
        --host-os <host_os> \
        --out-script '<SCRATCH>/recon-<host_os>.<ps1|sh>'
      ```
   2. Read the scratch file via host-side `Read` to confirm it's complete (no `{{...}}` placeholders left, and the closing `Write-Host "Next step:"` / `echo "Next step:"` block is present).
   3. Copy into the hub via host-side `Write` (not bash, not `cp` — host-side write avoids the bash-mount cache and gives the cloud-sync client a clean fresh-write to start syncing).
   4. Read back from the hub via host-side `Read` and verify the byte length matches the scratch version, AND that the closing block is present in the hub copy. If they don't match, retry the host-side write once; if still mismatched, surface a clean error and offer the user the scratch path directly (they can copy it themselves).
   5. The rendered script writes its CSV next to itself wherever the user runs it (`$PSScriptRoot` / `$BASH_SOURCE` — no hardcoded user folders, no environment-specific defaults).
3. **Present the script to the user via `mcp__cowork__present_files`.** Only after the verification in step 2 succeeds. Pass the hub-resident path as a single file entry. This surfaces a `computer://` link the user can click; from there they save/copy the file to whichever folder on their machine they prefer to run it from.
4. **Display the recon-explainer prompt** from `references/skill-user-facing-text.md` (section "Install recon"). Tell the user: save the script, run it in native shell, drop the resulting `sessions-recon.csv` into the hub folder when it's done. Wait for "ready" / "skip" / "quit".
   - **"ready"** → poll the hub folder for `sessions-recon.csv`. If absent, re-ask "still not seeing it — drop in / skip / quit". On found, proceed.
   - **"skip"** → set `recon_csv = None` in run state; flow continues without the recon map. Part 2 falls back to the legacy paste-prompt path (`cowork-session-transcript-dump-prompt.md`) for transcript dumps; Track B reattach lists become user-recall instead of recon-derived. This is the v1.5 fallback path for users who can't or won't run the native script.
   - **"quit"** → end the skill cleanly.
5. **Parse the CSV into structured JSON.** With the user's own spaceId from step 1:
   ```sh
   python3 <SCRATCH>/parse_recon_csv.py \
     --csv '<hub>/sessions-recon.csv' \
     --own-space-id '<space_uuid>' \
     --out '<scratch>/recon.json'
   ```
   Cache the resulting structure (project list, per-project session IDs + reattach folders + noise-folder-filtered list) in run state for downstream steps. The hub's own project will have `is_own_space: true` and is excluded from the migrate-this list by default; the user can still pick to migrate it explicitly if desired.
6. **Display the recon-summary prompt**: project count, session count, total folders identified. If single-project mode is active, also display the matched project (or the no-match list).

After Step 2.0, the run state holds:
- `recon_csv_path` — path to the user's CSV (or `None` if skipped).
- `recon_data` — the parsed JSON from `parse_recon_csv.py` (or `None`).
- `own_space_id` — the hub's own spaceId.
- `host_os` — `"windows"` or `"mac"`.

### Step 2 — Track A, Part 1 (web/chat projects)

The full Part 1 flow lives in `references/skill-user-facing-text.md` under "Prompt 1" through "Prompt N+1.5". Display each in turn, executing the implementation actions between them.

High-level orchestration:

1. **Prompt 1**: ask the user to drop two files (export zip + saved Chats HTML) into the migration hub folder. Wait for "ready."
2. **Prompt 2**: display the "Got it, in the folder I see X, hang tight" inventory message with the real filename + size of both inputs.
3. **Execute** (silent during the "hang tight" pause):
   - Unzip the export to `<scratch>/export-unzipped/`.
   - Run `extract_export.py` with `--export <scratch>/export-unzipped --outdir <scratch>/extracted`. Produces `<scratch>/extracted/transcripts/`, `<scratch>/extracted/raw/`, `<scratch>/extracted/conversations_manifest.csv`, `<scratch>/extracted/projects_manifest.csv`.
   - Stage the AllChats HTML + the conversation manifest together; run `parse_allchats.py <hub-folder>` against them to produce `attribution_map.csv`.
   - **Filter starter projects.** Read `projects_manifest.csv`; drop any row where `is_starter == "yes"`. The remaining rows are the candidates for the per-project walk-through. (This is the "filter built-in starter projects silently" rule made explicit per v1.5's manual-intervention audit.)
   - **Apply single-project scope (if active).** If `migration_scope == "single"`, further filter the candidate list to rows whose name matches `scope_target` (case-insensitive substring). Zero matches is a clean "no Part 1 work for this run" — the chosen project may live only on the Cowork side; proceed to Part 1 wrap with `<N_walkthrough> = 0` and skip the per-project loop.
4. **Prompt 2.5**: display the headline counts (total convs, attributed, catch-all, dropped). Substitute the real numbers from the manifest + attribution map.
5. **Build the tracker** (dual-render): write `tracker.html` to the hub, and call `mcp__cowork__create_artifact` with the same HTML. **Group-and-sort the visible projects table by `(status_group, name ASC case-insensitive)`** — `pending` first, then `done` / `done_no_bootstrap`, then `skipped`; alphabetical by name within each group. The embedded handoff-state JSON preserves whatever order the underlying arrays have (the v1.6+ recon path sorts alphabetically at parse time, so JSON order and HTML render order naturally agree for fresh runs). Re-apply the same group-and-sort on every state-transition update so a project flipping status moves to the appropriate row position.

   **The tracker HTML must also render visible sections for custom skills + scheduled tasks** when those arrays are non-empty in the handoff-state JSON. These were previously JSON-only (invisible to the user); v1.6.1 surfaces them so the user can verify the capture and see what Track B will handle. Render after the projects table:

   - **Custom Skills section** (when `custom_skills` array is non-empty). H2 + a one-line "what to do" note ("Repackaged from the old account. On the new account, install each via *Cowork → Customize → the + button → Skills tab*. The migration skill is the first row; Track B uses it."). Then a table: skill filename | size | status badge. Status mapping: on Track A (no `installed` field present) → `ready to install`; on Track B (Step 8.7's pre-check has run) → `installed` when `installed: true`, `pending install` when `installed: false`. Bundled `anthropic-skills` members get a one-line legend below: "Bundled anthropic-skills members re-install automatically with Cowork — not captured here." **Re-render rule (Track B):** whenever this section is re-rendered mid-Track-B (artifact stale-sync, manual write-back, etc.), preserve the Track B framing — never revert to the Track A "ready to install" blanket label. The `installed` field on each entry is the source of truth; if it's set on any entry, use the Track B status mapping for the whole table.

   - **Scheduled Tasks section** (when `scheduled_tasks` array is non-empty). H2 + a one-line "what to do" note ("Captured from the old account. Track B Step 8.5 walks through recreating each on the new account using the captured cron + prompt. Full specs in `scheduled-tasks-export.md`."). Then a table: task ID + description | cron + human schedule | dependencies (folder names if `has_dependencies`, otherwise "none — recreates cleanly") | status badge. Status: `pending recreate` for fresh Track A; flips to `done` per `recreated_on_destination: true` set by Track B Step 8.5.

   Use plain-English descriptions for the artifact. Architecture in `references/architecture-notes.md` covers the columns and embedded handoff-state JSON schema.

   **Track B re-render preserves Track B framing.** When the tracker is rendered or re-rendered during Track B (artifact stale-sync, manual write-back, mid-walk state update, etc.), YOU WILL NOT regress to Track A framing. Specifically:

   - The **phase chip / top label** reflects the actual `phase` field — `"track-b-walkthrough-complete"`, `"track-b-scheduled-tasks-complete"`, `"track-b-custom-skills-complete"`, `"track-b-complete"` — not the generic "Track A complete · ready for Track B" Track-A-end label.
   - The **projects table includes a RELINK column** (or merges relinked-state into a STATUS badge per row). Each project's row reflects its `relinked` field: `pending` / `done` / `done_no_bootstrap` / `skipped`. Don't drop the relinked dimension when re-rendering mid-Track-B — that's the dimension Track B is actively mutating.
   - The **Custom Skills table uses Track B status mapping** (see the custom-skills rendering rule above) — `installed` / `pending install`, not the Track A blanket "ready to install."
   - The **Scheduled Tasks table** reflects each task's `recreated_on_destination` field: `done` for true, `pending recreate` for false/absent.

   A stale-artifact-detected re-render (the `update_artifact` call after the orchestrator notices the Cowork sidebar disagrees with the on-disk `tracker.html`) is the most common re-render trigger mid-Track-B. Use the on-disk tracker as the source of truth, but render it with Track B framing — never a Track A snapshot of the same data.
6. **Prompt 3**: display the "I've opened your tracker. Set up the catch-all" message. Wait for the user to create the catch-all Cowork project and say "ready."
7. **Prompt 3.5** (post-ready bridge): display "Bringing up the folder picker so you can select <catchall_name>'s folder." Then call `mcp__cowork__request_cowork_directory` with no path (picker mode).
8. **Per-project walk-through**: alphabetical order over the filtered candidates from step 3. For project 1, display the verbose Prompt 4 (full rules). For projects 2–N, display the terse Pattern 5–N (import-prompt → ready / skip / quit). After "ready," display Prompt 4.5. After "pick," display the post-pick folder-picker bridge, then fire the picker.
9. **On each pick** (empty or non-empty) **or skip**: update the in-memory routing state for that project (action: `reconstruct_in_place` or `route_to_catchall`, with folder name + export uuid). The routing JSON gets serialized to disk in step 11 just before reconstruct/reshape run. Update the tracker row + JSON state + Cowork artifact immediately. Display the post-pick confirmation line. Then fire the next per-project prompt.
10. **Cancel handling**: if `request_cowork_directory` returns "Directory selection was cancelled by the user" after the user said "pick," do NOT silently fall through. Display the cancel re-ask: pick (re-fire) / skip (route to catch-all) / quit (end skill).
11. **End of per-project loop — write routing JSON and run reconstruct/reshape.** Serialize the in-memory routing state to `<scratch>/routing.json`. Each entry: `{"action": "reconstruct_in_place" | "route_to_catchall", "folder_name": "...", "export_name": "...", "export_uuid": "...", "reason": "..."}` (reason only on route_to_catchall). Then run:
    ```sh
    python3 <SCRATCH>/reconstruct.py \
      --extracted   <scratch>/extracted \
      --attribution <hub>/attribution_map.csv \
      --export      <scratch>/export-unzipped \
      --routing     <scratch>/routing.json \
      --outdir      <user-chosen-dest-root> \
      --catchall-name "<catchall_name>"
    python3 <SCRATCH>/reshape_and_extract.py \
      --extracted   <scratch>/extracted \
      --attribution <hub>/attribution_map.csv \
      --export      <scratch>/export-unzipped \
      --routing     <scratch>/routing.json \
      --outdir      <user-chosen-dest-root> \
      --catchall-name "<catchall_name>"
    ```
    These two scripts now take all paths and routing as CLI args / JSON; no hardcoded source state lives in them.
12. **Generate Part 1 blueprints.** For each `reconstruct_in_place` entry in the routing JSON, invoke:
    ```sh
    python3 <SCRATCH>/generate_blueprint.py \
      --project-dir            <user-chosen-dest-root>/<folder_name> \
      --type                   part1 \
      --export-project-json    <scratch>/export-unzipped/projects/<export_uuid>.json
    ```
    The script writes `transition-data/project-blueprint.md` (with mechanical sections filled and TODO markers for synthesis-required sections) and `transition-data/_BLUEPRINT_SYNTHESIS_NOTES.md` (raw input excerpts the hub Claude reads to write the final synthesis). **The orchestrator then reads the notes file and synthesizes the TODO sections into the blueprint directly**, producing a complete blueprint before moving on. **After synthesis lands in the blueprint, delete `transition-data/_BLUEPRINT_SYNTHESIS_NOTES.md`** — it was a staging artifact, no longer needed once the blueprint is complete. **When requesting delete permission, name the specific file in the user-facing narration.** Example phrasing: *"The blueprint is complete. I need permission to delete the staging file `transition-data/_BLUEPRINT_SYNTHESIS_NOTES.md` — it's no longer needed."* Do NOT say "the tool to delete files" or anything vague — naming the file makes the scope unambiguous (one file, not a folder, not a batch). Same rule applies any time the skill requests file-delete permission.
13. **End of Part 1**: display the Part 1 boundary wrap (substituting actual counts). Update tracker. Continue to Part 2.

### Step 3 — Track A, Part 2 (Cowork projects)

The Part 2 flow lives in `references/skill-user-facing-text.md` under "Part 2 — preparing Cowork projects (source account)."

Two paths in v1.5:
- **Recon-driven (primary)** — if Step 2.0 produced `recon_data`, enumerate Cowork projects from the recon JSON. The hub session pulls session transcripts directly via `read_transcript` for every session ID attributed to each project's spaceId. The user still pastes the memory-dump prompt per project (memory is per-space and the hub session can't reach other spaces' memory).
- **Paste-prompt fallback (legacy)** — if the user skipped recon in Step 2.0 (or recon failed), fall back to the v1.4-era flow: pick each folder via picker, write the legacy paste prompt into `transition-data/`, user runs it in that project's source-account Cowork session to dump transcripts there.

#### Recon-driven path

1. Display the Part 2 banner: `▶ Part 2: Preparing Claude Cowork (Old Account) ◀`.
2. **Part 2 Prompt 1 (recon variant)**: display the opener that explains the recon-driven path and lists the in-scope projects pulled from `recon_data`. Filtering rules:
   - Exclude any project with `is_own_space == true` (the migration hub itself) — unless the user explicitly opts to migrate the hub.
   - If `migration_scope == "single"`, filter further to the project(s) whose name matches `scope_target` (case-insensitive substring against each project's session titles — pick the project with the most matching sessions).
   - For every remaining project, show: its `name_hint` from `recon_data` (the generator's pre-computed name; falls back to first session title then to `"(folder unknown)"`), session count, latest activity date, and the first reattach-folder path when available.
   - **Never silently drop a project.** Display every project in `recon_data.projects` that passed the filters above. If a project has empty `reattach_folders`, still list it — show "(no working folder attached)" instead of omitting. If `name_hint` is `"(folder unknown)"`, surface the first 2-3 session titles in the listing so the user can identify the project. The opener's project count MUST equal the count of in-scope projects in `recon_data.projects` minus excluded ones (own_space, scope filter); if those don't match, the orchestrator has a bug — surface it rather than papering over it.
3. Wait for "continue" / "skip" / "quit".
4. **On "continue"**: iterate over in-scope projects from `recon_data` **in the exact order they appear in the array** (v1.6+'s `parse_recon_csv.py` already sorts them alphabetically by `name_hint` with own-space first, so array order IS the display order in the tracker and the natural ABC order users expect). YOU WILL NOT reorder, skip ahead, or interleave projects — process each one fully (transcripts → memory → blueprint → tracker entry) before advancing to the next. If you skip a project (user denies the picker and says `skip`), record the skip in the tracker and advance to the NEXT project in array order — YOU WILL NOT come back to it later in the same run unless the user explicitly invokes Step 5-resume on a future re-invocation. The user reads the tracker top-to-bottom; the processing order should match. For each:
   - Display the per-project header with the project's display name, session count, and first reattach-folder path (informational only).
   - **Grant folder access via picker.** Display the folder-picker bridge, call `mcp__cowork__request_cowork_directory` with no path. (We have the folder path from recon, but the discipline rule is always-picker — never guess paths.) On cancel, re-ask pick / skip / quit. **On `skip`**: append an entry to the tracker's `cowork_projects` array for this project with `relinked: "skipped"` (plus `name` from recon, `space_id` from recon, `session_count` from recon, `reattach_folders` from recon — informational only, even though we didn't process this one). **Do not leave a skipped project as 'pending' or omit it entirely** — both produce confusing tracker state. Update both `tracker.html` and the Cowork sidebar artifact. Then advance to the next project in the iteration. On `quit`: end the skill cleanly; tracker stays on disk reflecting whatever's been processed so far.
   - **Pull transcripts directly. This is a strictly mechanical save-to-disk loop. YOU WILL NOT investigate, gauge, summarize, condense, characterize, or narrate. You will just save.** For each `session_id` in this project's `recon_data.projects[i].sessions`:
     ```
     result = mcp__session_info__read_transcript(
         session_id=<id>,
         format='full',
         limit=2000      # <-- MANDATORY. The tool's DEFAULT limit is 20.
                         # Without an explicit high limit you get only the last
                         # 20 messages, NOT the full transcript. Always pass
                         # a high limit (2000 covers every transcript size
                         # observed in real-data runs to date).
     )
     # Then write the entire tool result content verbatim to:
     #   <picked-folder>/conversation-history/<YYYY-MM-DD>_NN_<slug>_sess_<short-id>.md
     # via the Write tool, with the tool result as the content. That's it.
     ```
     Filename mirrors the legacy paste-prompt convention so dumps from either path coexist in the same folder. Date = today (the dump date), NN = ordinal in chronological order within this project's set, slug = derived from session title (lowercased, hyphens, special chars stripped, length-capped), short-id = first 8 chars of the session UUID after the `local_` prefix.
     - **No size gauging.** YOU WILL NOT read the first transcript to "gauge size before doing the rest." YOU WILL NOT worry about whether the tool result comes back inline or attached to a file — the Write tool handles both cases. If `read_transcript` returns content that mentions a saved-to-file divert path, just use that path with the Read tool to bring the content in for Write — but it's typically not needed; the tool result IS the content you save. **YOU WILL NOT investigate the divert mechanism, probe `/sessions/` paths, compare advertised vs. actual mounts, or re-pull a session with a different limit to "verify completeness."** The tool gives you bytes; you write the bytes to disk. End of step.
     - **Progress reporting is mechanical only** (per Discipline rule #10). After each session write, emit **ONE line, and ONLY one line**: `"Session N of M done."` Nothing else. YOU WILL NOT add commentary like "writing it in full," "session 2 — substantial," "important catch — the default truncates to last 20," "let me verify I'm getting the complete transcript," "comparing the tool result," "session captured." YOU WILL NOT explain what the tool is doing, what you discovered about its parameters, or what your strategy is for the remaining sessions. The user has read SKILL.md and knows the mechanism. Save the file. Print one line. Move to the next session. **If you find yourself wanting to be helpful by explaining or verifying mid-loop, that is the exact failure mode this rule forbids.** Do not use words like "faithful," "condensed," "key takeaway," "the big one," "rich," "substantial," "text-heavy," "large," "complete," "verify," "compare," "important catch," "writing it full." The transcript IS the archive; the session title IS the description. Save it as-returned by the tool — no editing, no collapsing of repeated tool-call markers, no tightening of long analysis blocks.
     - **Stay on the flow** (per Discipline rule #11). Anything you happen to notice in transcript content while writing it is NOT input to the next step — YOU WILL NOT propose recovery detours, sidecar reads, "I noticed memory was dumped earlier so let me skip the memory step," or shortcuts based on incidental observations. The presence-or-absence check for `cowork-space-memory/` happens against the disk in the next sub-step, NOT against transcript content. Proceed to the next session, then to the memory-dump step.
     - **No fidelity-mode prompts mid-loop.** YOU WILL NOT surface a "full fidelity vs. condensed?" decision to the user mid-archive. The default is full fidelity; the tool returns full content (when you pass `limit=2000` as mandated above); you save it. If a real blocker emerges (e.g., the tool throws an error), surface that one specific blocker — YOU WILL NOT reframe the situation as a fidelity decision the user has to make.
     - **Parameter-discovery comments are forbidden mid-loop.** If you discover something about the `read_transcript` tool's behavior (default limit, divert behavior, response format), YOU WILL NOT narrate that discovery to the user. The user does not need to know about parameter defaults during a save-to-disk loop. This is a load-bearing instruction: prior real-data runs failed this rule by emitting messages like "the default pull truncates to the last 20 messages — with an explicit high limit I get the complete transcript." That kind of mid-loop narration is exactly what Discipline rule #10 forbids, even when it sounds "informative" or "helpful." Pass `limit=2000` from the first call onward, save the result, print `"Session N of M done."`, advance.
   - **Write `<picked-folder>/conversation-history/INDEX.md`** after all transcripts land. **Mechanical only** — header line `"# Conversation history — <project name>"`, one-sentence provenance line (`"Migrated via the account-migration skill on <date>. Chronological order."`), then the catalog table (`#` / `Date` / `Title` / `File`). NO curation language ("condensed faithful archive," "verbose tool-call lists are summarized," etc.). The catalog table IS the index; nothing else belongs.
   - **Memory dump (per-project paste, with skip-if-already-done).** The skip-if-already-done check is grounded **only** in the on-disk presence of `<picked-folder>/transition-data/cowork-space-memory/` and `.md` files inside it. Use a directory listing — `ls` via bash or equivalent. **Do NOT infer skip-eligibility from anything you happened to read in a transcript** (per Discipline rule #11). If you saw something like "memory was dumped earlier" while saving transcripts in the previous sub-step, that observation is irrelevant — go to disk, check the folder, decide from what's actually there. If the folder exists and contains `.md` files: skip the paste step, report `"Cowork memory already present (<N> entries) — skipping the paste step."`, proceed. If the folder is absent or empty: copy `assets/cowork-memory-dump-prompt.md` to `<picked-folder>/transition-data/`, display the memory-dump instruction (open a fresh Cowork conversation IN that project on the source account, paste the prompt, wait for "done"). When the user comes back, wait for a single keyword — **`done`** (either case: memory was dumped successfully, OR there was nothing to dump and the prompt reported empty — both lead to the same next step) or **`quit`**. Don't ask the user to distinguish the two success cases; the next step is the same regardless. (Reason: per-project Cowork memory lives at `spaces/<that-project's-spaceId>/memory/` and is only mounted into that project's own sandbox sessions — the hub session can read other spaces' transcripts via `read_transcript` but not their on-disk memory directories.)
   - **Run `generate_blueprint.py` against the project.**
     ```sh
     python3 <SCRATCH>/generate_blueprint.py \
       --project-dir <picked-folder-path> \
       --type        part2
     ```
     Reads the dumped memory + transcripts + working files; writes `transition-data/project-blueprint.md` + `transition-data/_BLUEPRINT_SYNTHESIS_NOTES.md` + `_PROJECT_BRIEF.md`.
   - **Synthesize the blueprint's TODO sections.** Same pattern as Part 1: read `_BLUEPRINT_SYNTHESIS_NOTES.md`, fill in Sections 1, 3, 4, 6. **Delete the notes file once synthesis lands** — staging artifact, no longer needed.
   - **Append an entry to the tracker's `cowork_projects` array** with: picked folder name, path, `has_blueprint: true`, `space_id` (from recon), `session_count` (from recon), `reattach_folders` (the filtered list from `recon_data` — used by Track B's reattach step). Update both `tracker.html` and the Cowork sidebar artifact.
5. **On "skip"** at the opener or after any per-project cancel-loop: advance tracker `phase` to `"track-a-part-2-complete"`. Display the Part 2 wrap.

#### Paste-prompt fallback path (when recon was skipped or failed)

Used when `recon_data` is `None`. This is the v1.4-era flow; preserved verbatim so users without native-shell access can still run Track A.

1. Display the Part 2 banner.
2. **Part 2 Prompt 1 (fallback variant)**: display the legacy opener — "we'll do this folder by folder, you'll paste two prompts per project on the source account."
3. **On "continue"**: enter the folder-picker loop. Each iteration:
   - Display the folder-picker bridge.
   - Call `mcp__cowork__request_cowork_directory` with no path.
   - On successful pick:
     - Display the per-folder processing confirmation.
     - **Write the two source-side paste prompts into the project's `transition-data/` folder.** Copy `assets/cowork-memory-dump-prompt.md` and `assets/cowork-session-transcript-dump-prompt.md` into `<project>/transition-data/`. Display the **per-project paste-prompt instruction** message: open a fresh Cowork conversation in that project on the source account, paste the memory-dump prompt first, wait for confirmation, then paste the transcript-dump prompt.
     - Wait for confirmation both dumps are done.
     - Run `generate_blueprint.py` as above.
     - Synthesize blueprint TODO sections. Delete `_BLUEPRINT_SYNTHESIS_NOTES.md` after synthesis lands.
     - Append to tracker's `cowork_projects` array (no `space_id`/`session_count`/`reattach_folders` fields in the fallback path).
   - On picker cancel: display the cancel-confirmation prompt (done / continue / quit).
4. **On "skip" at opener** or "done" at cancel-confirmation: advance tracker `phase` to `"track-a-part-2-complete"`. Display the Part 2 wrap.

**On `migration-prompt-template.md`.** This template stays in the bundle as a documented fallback path — if a user runs Track A by hand without the full skill flow, they can paste this template's content in each Part 2 project's Cowork session to drive blueprint generation inside that session. The primary flow uses `generate_blueprint.py` from the hub (per the recon-driven path above), which is faster and doesn't require Claude in the per-project session to do synthesis.

### Step 3.5 — Custom-skills capture (Track A)

Fires after Part 2 wraps and before the end-of-Track-A cleanup wrap. The Track B README's Step 1.5 (manual fallback) documents the same flow as a checklist; this step makes it an in-session prompt so users actually do it before deletion of the old account.

The full user-facing copy lives in `references/skill-user-facing-text.md` under "Custom-skills capture".

**Single-project short-circuit.** When `migration_scope == "single"`, skip the opener prompt and the user-asked-for-other-skills loop entirely. Just auto-package the migration skill into `<project>/transition-data/skills/` (not a hub `skills/` subfolder — there is no hub in single-project) and advance to Step 4. The single-project Track A wrap explicitly surfaces `transition-data/skills/account-migration.skill` in its file inventory so the user knows the migration skill traveled with the project. Single-project users don't get asked about other custom skills because (a) they're doing a focused one-project transfer, not a whole-account move, and (b) packaging other skills can be done separately if they want; it's not in this skill's scope.

Orchestration (multi-project — `migration_scope == "all"` or unset):

1. **Auto-create `skills/` and package the migration skill into it.** Before anything else, create the hub's `skills/` subfolder if it doesn't exist, then run `scripts/package_self.py` (via `mcp__workspace__bash`) to write a fresh `account-migration.skill` into it:
   ```sh
   python3 <SKILL_PATH>/scripts/package_self.py <SKILL_PATH> <HUB>/skills/account-migration.skill
   ```
   Pass the skill's original source path (not the scratch staging copy) so the packaged .skill is byte-faithful to what's installed. If the script fails (non-zero exit), log and continue — the user can still add the file manually.
2. **Auto-export the user's other custom skills.** Run `scripts/export_custom_skills.py` against the installed-skills root (the read-only `.claude/skills/` mount in this sandbox):
   ```sh
   python3 <SKILL_PATH>/scripts/export_custom_skills.py \
       --skills-root /sessions/<sandbox>/mnt/.claude/skills/ \
       --out-dir     <HUB>/skills/
   ```
   The script filters out the bundled `anthropic-skills` plugin members (those re-install automatically with Cowork on the new account) and the `account-migration` skill itself (Step 3.5 sub-step 1 handled it). Every remaining installed-skill folder gets repackaged into a `.skill` zip in the hub's `skills/`. The sandbox path can be derived from `mcp__workspace__bash`'s available paths (look for `.claude/skills` in the mount table or `findmnt` output — same pattern as `derive_install_root.py`). If the script fails or returns zero custom skills, log and continue.
3. Display the **custom-skills confirmation — auto-export complete** prompt with the listing of what landed in `skills/` (the migration skill + each auto-exported custom skill, sized). Wait for the user's response: **`done`** (most common — every custom skill was exported), **`hold`** (the user wants to add another `.skill` file by hand into `skills/` that wasn't captured — e.g., a skill they downloaded but never installed, or a skill from another machine; the soft re-ask handles this), or **`quit`**.
4. **On "hold"**: display the **add-by-hand soft re-ask** prompt. User drops the additional `.skill` file(s) into `<HUB>/skills/` and says `ready`. Re-scan `<HUB>/skills/`, append any new files to the listing, return to step 3.
5. **On "done"**: append a `custom_skills` array to the tracker's handoff-state JSON listing every `.skill` filename + size in `<HUB>/skills/`. Update both `tracker.html` and the Cowork sidebar artifact. Proceed to Step 3.7.
6. **On "quit"**: end the skill cleanly. Tracker stays on disk; user can resume later.

The tracker's `<script type="application/json" id="handoff-state">` block carries `custom_skills` as `[{"filename": "...", "size_bytes": N}, ...]`. The auto-packaged migration skill is always in this list when Step 3.5 has run.

### Step 3.7 — Scheduled-tasks capture (Track A, multi-project only)

Fires after Step 3.5 (custom-skills capture) and before Step 3.6 (blueprint coverage check). **Single-project mode SKIPS this step entirely** — scheduled tasks are account-level resources, out of scope for a one-project transfer.

The full user-facing copy lives in `references/skill-user-facing-text.md` under "Scheduled-tasks capture".

Why this step exists: Cowork's scheduled tasks (cron-style recurring prompts) don't migrate automatically between accounts. They're stored under `Documents\Claude\Scheduled\<taskId>\SKILL.md` per task with a manifest. Recreating them on the new account is mechanical given the cron + prompt, but the user has to know what existed. This step captures that as a self-contained export file so the user can recreate each task on the new account using the `schedule` skill.

Orchestration:

1. **List existing scheduled tasks.** Call `mcp__scheduled-tasks__list_scheduled_tasks`. Returns each task's `taskId`, `description`, `cronExpression`, human-readable `schedule`, `fireAt` (one-time tasks), `enabled` state, and a `path` to the task's `SKILL.md` (containing the prompt body).

2. **If zero tasks**: display the **zero-tasks confirmation** one-liner — "No scheduled tasks active. Nothing to export." — and proceed to Step 3.6. Tracker's `scheduled_tasks` array stays empty.

3. **For each task, Read the prompt `SKILL.md`** via the `path` field. Capture the full prompt body. **Do not edit, summarize, or analyze the prompt content** (Discipline rule #10) — just capture it verbatim for the export.

4. **Write `<hub>/scheduled-tasks-export.md`**. Structure:
   - H1 title + capture-date header paragraph explaining the file is for new-account recreation.
   - For each task: H2 with `<N>. <taskId>`, bullets for `Description / Cron / Enabled / Dependencies`. The Dependencies bullet calls out attached working folders or external state the task assumes (Windows Task Scheduler entries, mounted backup folders, etc.) — derive from the prompt body if it references specific paths or external systems; if the prompt is fully self-contained (e.g., just web access), say "web access only — recreates cleanly anywhere."
   - The verbatim prompt inside a fenced code block.
   - A closing "Recreating on the new account" section explaining the user invokes the `schedule` skill on the new account and feeds it each cron + prompt. For tasks with folder dependencies, the user re-attaches those folders to the task. Note that original prompt files remain at `Documents\Claude\Scheduled\<taskId>\SKILL.md` on the source machine if the user prefers to copy directly.

5. **Append a `scheduled_tasks` array to the tracker's handoff-state JSON**. Each entry: `{taskId, description, cronExpression, enabled, has_dependencies}`. `has_dependencies` is a boolean — true when the prompt body references mounted working folders or external Windows-side state (i.e., the task isn't trivially self-contained).

6. **Display the done confirmation** with the count of tasks exported and the export file path.

The export file is referenced from `README - Final Transition to New Account.md` (Step 4) so the user sees it during the new-account walk-through.

### Step 3.6 — Blueprint coverage check (end-of-Track-A gate)

Fires after Part 2 wraps and before the end-of-Track-A cleanup wrap.

Run `blueprint_coverage_check.py` against every project the walk-through touched. Build the folders list from the tracker:

- For each `projects[]` entry where `reconstructed == "done_in_place"`: `<outdir>/<folder_name>`
- For each `cowork_projects[]` entry: that entry's `folder_path`

Invoke:
```sh
python3 <SCRATCH>/blueprint_coverage_check.py <folder1> <folder2> ...
```

Or write the list to a file and pass `--folders-file`. Exit code 0 = all present, proceed to Step 4. Exit code 1 = some missing — display the missing-blueprint warning prompt with the list (the script's own output is suitable to surface). The user has two paths:
- Regenerate the missing blueprints inline (re-run `generate_blueprint.py` against each) and re-run the coverage check.
- Acknowledge the gap and proceed anyway (with explicit warning that those projects won't have a bootstrap on the destination side).

### Step 4 — End-of-Track-A wrap

The wrap branches on scope. Single-project Track A wraps very differently from multi-project: there's no hub, no catch-all, no global memory capture, no project list to summarize. Everything is contained within the one project's folder.

#### Multi-project (`migration_scope == "all"` or unset)

1. **Write `README - Final Transition to New Account.md` to the hub** by reading `assets/README-template.md` and doing a find/replace pass on its substitution markers. **Explicit mechanics:** read the template file, then for each of `<N_projects>`, `<N_reconstructed>`, `<N_routed>`, `<N_unattributed>`, `<N_recover>`, `<catchall_name>`: replace every occurrence in the loaded text with the corresponding count or string from the tracker's handoff-state JSON. Write the substituted text to `<hub>/README - Final Transition to New Account.md`. (This makes the previously-implicit "substitution happens here" step explicit per v1.5's manual-intervention audit.)
2. **Also write `memory-capture-prompt.md` and `memory-seed-prompt.md`** to the hub root as standalone files (the user pastes the former on the old account to produce `memory-capture.md`; the latter is referenced by Track B's memory seed phase).
3. Advance the tracker's `phase` field to `"track-a-complete"`. Update both representations (file + artifact).
4. **Surface any per-project notes.** For each project folder, check whether `<folder>/_MIGRATION_NOTE.md` exists. If yes, include the note's filename + path + summary line in the wrap message so the user knows where to look.
5. Display the Track A wrap message from `references/skill-user-facing-text.md` ("Prompt N+2 — Track A wrap"). The prompt enumerates the 4-step new-account bootstrap (get hub onto new machine, install skill, import hub as Cowork project, invoke skill and pick "new").
6. Skill exits cleanly. Tracker stays on disk for Track B.

#### Single-project (`migration_scope == "single"`)

1. **Write `<project>/transition-data/tracker.html`** — a minimal tracker file scoped to this one project. The hidden `<script type="application/json" id="handoff-state">` block carries `schema_version: 1`, `phase: "track-a-complete"`, `scope: "single"`, and a one-entry `cowork_projects` array (for a Part 2 project) or one-entry `projects` array (for a Part 1 project) with the standard fields. No `catchall` block, no `custom_skills` array beyond the auto-packaged migration skill (already in `<project>/transition-data/skills/`). Visible HTML can be a tiny table summarizing just this one project's state, or a one-line "Single-project migration of <name> — see project-blueprint.md."
2. **Write `<project>/transition-data/_RESUME_ON_NEW_ACCOUNT.md`** — single-project equivalent of the multi-project README. Short: explain that this folder contains everything needed to bootstrap on the new account, list the destination-side steps (create a Cowork project pointing at this folder, invoke the migration skill, the skill detects the single-project tracker and walks the rest), and **include a manual-fallback section for users without the skill** that gives them two things: (a) the Custom Instructions paste step ("if Section 2 of `transition-data/project-blueprint.md` has a non-empty fenced block, paste it into the new project's *Custom Instructions* field"), and (b) the canonical outer bootstrap prompt verbatim:

```
This is a project I'm migrating from my old Claude account. Read
`transition-data/project-blueprint.md` for the full project context,
then treat its Section 7 — Recommended Starting Prompt — as your
first directive.
```

Do NOT tell the user to paste Section 7 directly — Section 7 is a directive *to Claude*, not a paste target for the user. **Also include a closing "Cleanup after verification" note** stating that once the user has confirmed the project bootstrapped cleanly on the new account, both `transition-data/` (the whole folder) AND `_PROJECT_BRIEF.md` (at the project root) are safe to delete — they are migration scaffolding only. The user's working files, `conversation-history/`, and the restored per-project memory are what's load-bearing going forward.
3. **DO NOT write `README - Final Transition to New Account.md`.** That file is for multi-project migrations; single-project doesn't need it. Also don't write `memory-capture-prompt.md` or `memory-seed-prompt.md` (global memory is not a single-project concern — the user either has it from a prior whole-account migration or doesn't need it for this one project).
4. **Surface notes.** Check whether `<project>/_MIGRATION_NOTE.md` exists; if yes, include in wrap.
5. Display the **Track A single-project wrap** message (locked-copy section, parallel to N+2). The message enumerates everything that landed in the project folder (`conversation-history/`, `transition-data/cowork-space-memory/`, `transition-data/project-blueprint.md`, `transition-data/skills/account-migration.skill`, `_PROJECT_BRIEF.md`, `transition-data/tracker.html`, `transition-data/_RESUME_ON_NEW_ACCOUNT.md`) and tells the user the 3-step new-account bootstrap (sync project folder to the new-account machine, create a Cowork project pointing at it, invoke the migration skill — it auto-detects single-project mode and walks the rest).
6. Skill exits cleanly. The project's `transition-data/tracker.html` stays on disk for Track B.

---

### Step 5 — Track B Phase 1 (opener + hub access + inventory)

Fires after the user picks "new" at Prompt 0 and the Part 3 banner displays. The full Track B flow lives in `references/skill-user-facing-text.md` under "Track B — destination-account relink".

Orchestration:

1. **Source detection.** Inspect the current Cowork project's working folder for three possible signals, in priority order:
   - **`transition-data/tracker.html` exists at working-folder/transition-data/** → this is a **single-project migration source**. The current project IS the migrated project; no hub picker needed. Read the tracker, parse the handoff-state JSON, confirm `scope == "single"`. Take the **B-1c branch** (single-project Track B flow — see Step 5-single below). Skip Steps 5.5 (scope gate redundant — tracker says single), 6 (memory seed — not in single-project scope), 7 (catch-all — not in single-project scope), and the multi-project version of 8.
   - **`tracker.html` exists at working-folder root** → this is a **multi-project migration hub**. Take the **B-1a branch** (no picker needed for hub access). Display the B-1a opener. Wait for "ready" / "hold" / "quit".
   - **Neither tracker is present** → take the **B-1b branch** (no hub detected). Display the B-1b opener. Wait for "ready" / "hold" / "quit". On "ready", display **Prompt B-2** (hub picker bridge), then call `mcp__cowork__request_cowork_directory` with no path. After the user picks, re-check for both tracker locations in the picked folder and branch accordingly (a user may point the picker at either a multi-project hub OR a single-project folder — handle either).
2. **Tracker parse.** Read `tracker.html`, extract the embedded `<script type="application/json" id="handoff-state">` block, parse the JSON. Validate `schema_version`.
   - **Happy path**: silent, proceed to phase routing (sub-step 2b) then inventory.
   - **JSON unparseable but rendered HTML table readable**: display **Prompt B-3b** (partial corruption). Reconstruct counts from the HTML rows. Folder paths are lost — per-project picker will be by name only. Continue.
   - **Nothing parseable**: display **Prompt B-3c** (disaster). Wait for "pick" (re-pick hub via picker), "quit", or any unrecognized response treated as quit.
2b. **Phase routing — handle re-entry on a completed migration.** Look at the parsed `phase` and `cleanup_done` fields:
   - `phase != "track-b-complete"` → normal Track B flow. Proceed to sub-step 2a (render artifact) then inventory.
   - `phase == "track-b-complete"` AND `cleanup_done == true` → migration is fully closed. Display **Prompt B-Resume-closed** (one-liner: "This migration is already complete and the hub was cleaned up on a prior run. Nothing left to do — pick a different project to work in.") and exit cleanly. The tracker stays on disk as a record.
   - `phase == "track-b-complete"` AND `cleanup_done == false` (or `cleanup_done` absent in pre-v1.6.1 trackers — treat absent as false to preserve resume capability) → **branch to Step 5-resume.** The user previously chose `later` at the cleanup wrap (or the tracker was written by a pre-v1.6.1 build that didn't track this) and the skill should offer to walk through any deferred items + close out cleanup.
2a. **Render the tracker as a Cowork sidebar artifact, grouped + sorted.** Call `mcp__cowork__create_artifact` with the tracker HTML so the user has the same at-a-glance view on the destination side that they had during Track A. **Sort the projects in the rendered HTML table by `(status_group, name ASC case-insensitive)`** — status_group order is `pending` first, then `done` (and `done_no_bootstrap`), then `skipped`. Within each status group, **sort projects alphabetically by name (case-insensitive)**. This gives a predictable, scannable view regardless of what order the underlying `cowork_projects` JSON has (Track A's recon-driven path sorts alphabetically at parse time, but trackers from older bundles may have recency-first ordering — sort defensively at render time so the user sees the same view either way). The underlying JSON order in `tracker.html` is preserved as-written (it's a record of how Track A processed the projects, not a presentation concern). Use plain-English description for the artifact (e.g., "Live migration tracker — projects, phase, and what's left"). Every state transition during Track B updates both the on-disk `tracker.html` AND this Cowork artifact via `update_artifact` (mirroring Track A's dual-render discipline). On every re-render, re-apply the same group-and-sort ordering — a project flipping from `pending` to `done` should move within the table, not stay in its prior row position. [Bug #41 — Track B tracker artifact display.]
3. **Inventory display.** Display **Prompt B-4** with the counts computed from the tracker state:
   - `<N_part1_reconstructed>` = count of projects where `reconstructed == "done_in_place"`
   - `<N_part2_cowork>` = length of `cowork_projects` array
   - `<catchall_name>`, `<N_orphans>`, `<N_part1_catchall>` = from the `catchall` block
   - `<N_scheduled_tasks>` = length of `scheduled_tasks` array
   - `<N_custom_skills>` = length of `custom_skills` array
   - `<N_recover>` = count of unchecked items in `_ARTIFACTS_TO_RECOVER.md` (read from the catch-all once it's accessible; see Step 7's catch-all pick)
   - Conditionally drop any bullet whose count is 0.

### Step 5-resume — Track B re-entry on a deferred-cleanup migration (B-1a/B-1b multi-project only)

Fires when Step 5's phase routing (sub-step 2b) finds `phase == "track-b-complete"` AND `cleanup_done` is false or absent. The user previously chose `later` at the Phase 7 cleanup wrap (or is running v1.6.1 against a pre-v1.6.1 tracker). The skill offers to walk through any items they deferred + close out cleanup. Single-project Track B (B-1c branch) doesn't go through this — single-project has no cleanup wrap and no `cleanup_done` flag; if the user re-invokes on a single-project tracker the existing B-1c flow handles re-entry by re-detecting the source and re-offering the bootstrap.

Orchestration:

1. **Tally deferred items** from the parsed tracker state:
   - `<N_skipped_projects>` = count of `cowork_projects[]` entries where `relinked == "skipped"` (plus `projects[]` entries where `reconstructed == "skipped"` if any).
   - `<N_skipped_tasks>` = count of `scheduled_tasks[]` entries where `recreated_on_destination` is false or absent.
   - `<N_pending_skills>` = count of `custom_skills[]` entries where `installed` is false or absent. (Re-check by listing the destination account's `.claude/skills/` mount — a skill that wasn't installed last round may have been installed in the meantime. Apply the same slug-reconciliation logic as Step 8.7 sub-step 1+2 before tallying.)
   - `<N_unchecked_binaries>` = count of unchecked items in `_ARTIFACTS_TO_RECOVER.md` (requires catch-all access; defer the actual count until catch-all is picked, or use the value from the tracker's `totals.catchall_orphans` minus checked count if cached).

2. **Render the tracker** as a Cowork sidebar artifact (same as Step 5 sub-step 2a — group-and-sort, projects + status). Skips this if the artifact already exists from this same conversation.

3. **Display Prompt B-Resume-1** (resume opener) with the deferred-item counts. Ask **`review`** / **`cleanup-now`** / **`leave`**:
   - `review` → walk through deferred items per sub-step 4 below.
   - `cleanup-now` → skip directly to Phase 7 cleanup wrap. The deferred items stay deferred; the user is just choosing to finalize the cleanup without revisiting them.
   - `leave` → exit cleanly. Tracker state unchanged. User can re-invoke later.

4. **On `review`**: walk through the deferred items, re-firing the relevant steps. Set a run-state flag `resume_mode = True` (in skill memory for this run, not in the tracker JSON) so the relevant steps know they're in resume mode.

   - **Sub-step 4a — Skipped projects.** If `<N_skipped_projects> > 0`:
     - Display **Prompt B-Resume-2-projects** with the list (project names + last-action notes from tracker). Ask **`re-walk`** / **`skip-projects-section`** / **`quit`**.
     - On `re-walk`: flip every `relinked == "skipped"` entry to `relinked == "pending"` in the tracker JSON, write `tracker.html`, update the Cowork sidebar artifact (per the group-and-sort rule, the projects now sort into the pending group). Re-fire **Step 8** (Track B walk-through). The existing Step 8 iterates pending projects normally; the user re-decides per project (`done` / `skip` / `quit`). Items they re-skip flip back to `relinked == "skipped"` as normal.
     - On `skip-projects-section`: advance to sub-step 4b without changes.

   - **Sub-step 4b — Skipped scheduled tasks.** If `<N_skipped_tasks> > 0` AND the multi-project Track A wrote a `scheduled_tasks` array:
     - Display **Prompt B-Resume-2-tasks** with the list. Ask **`re-walk`** / **`skip-tasks-section`** / **`quit`**.
     - On `re-walk`: re-fire **Step 8.5** for the non-recreated tasks only. Step 8.5's existing iteration filters by `recreated_on_destination != true`, so this works without tracker mutation. User re-decides per task (`recreate` / `skip` / `quit`).
     - On `skip-tasks-section`: advance to sub-step 4c without changes.

   - **Sub-step 4c — Pending custom skills.** If `<N_pending_skills> > 0`:
     - Display **Prompt B-Resume-2-skills** with the list (filename + size for each pending skill). Ask **`re-walk`** / **`skip-skills-section`** / **`quit`**.
     - On `re-walk`: re-fire **Step 8.7** (custom-skills walk-through). Step 8.7's pre-check already reconciles tracker state with the live `.claude/skills/` listing, so this works without additional tracker mutation. User re-decides per batch (`done` / `skip-all` / `quit`).
     - On `skip-skills-section`: advance to sub-step 4d without changes.

   - **Sub-step 4d — Unchecked binaries.** If `<N_unchecked_binaries> > 0`:
     - Display **Prompt B-Resume-2-binaries** with the count and conversation-grouping summary. Ask **`re-walk`** / **`skip-binaries-section`** / **`quit`**.
     - On `re-walk`: re-fire **Step 9 Phase 5** for the unchecked items. Phase 5 already iterates per-conversation, ticking checkboxes as the user confirms — works as-is.
     - On `skip-binaries-section`: advance to sub-step 4e without changes.

   - **Sub-step 4e — Cleanup wrap.** Re-fire **Phase 7** (cleanup wrap). User says `done` / `later` / `quit` again. On `done`, tracker advances to `cleanup_done=true` and the migration is closed. On `later`, the skill stays re-invocable for another round.

5. **On `cleanup-now`**: skip to Phase 7 directly. Same `done`/`later`/`quit` semantics.

6. **On `leave`**: exit cleanly. No state change.

Closing message after Step 5-resume's Phase 7 re-fire: same Prompt B-X-1 (Track B closing), with conditional reminders re-evaluated against the post-resume tracker state. If the user re-skipped everything they re-walked, the reminders match what they were before; if they completed items this round, those reminders are dropped.

### Step 5-single — Track B for single-project source (B-1c branch)

Fires when Step 5's source detection found `transition-data/tracker.html` (single-project tracker) in the working folder. Skip Steps 5.5, 6, 7, and the multi-project version of 8 — they don't apply. The whole single-project Track B is just:

1. **Display Prompt B-1c** (single-project Track B opener, see locked copy). Wait for "ready" / "quit". The opener acknowledges what was detected — name of the migrated project, that its blueprint is present in `transition-data/project-blueprint.md`, and what's about to happen.
1a. **Render the tracker as a Cowork sidebar artifact.** Call `mcp__cowork__create_artifact` with the contents of `transition-data/tracker.html` so the user has the same at-a-glance view in single-project mode that they would in multi-project mode (symmetry with Step 5 sub-step 2a). One-row summary table is fine — the tracker covers a single project. After the bootstrap step lands and the user says "done," call `update_artifact` to flip `relinked: "pending"` → `relinked: "done"` so the sidebar reflects completion.
2. **Verify the project's transition-data is complete.** Confirm these files exist:
   - `transition-data/project-blueprint.md` (with a Section 7 starting prompt)
   - `transition-data/cowork-space-memory/` (with at least `MEMORY.md` if Cowork memory was dumped on the source side, or empty/absent if not)
   - `_PROJECT_BRIEF.md` at the project root
   If `project-blueprint.md` is missing, display the **blueprint-missing branch** locked copy (same prompt used in Step 8 for the multi-project case): the user can re-generate from disk or accept the gap. If `cowork-space-memory/` is absent, just note it in the inventory display — many projects don't have per-project memory.
3. **Display Prompt B-1c-inventory** showing the user what's about to be restored:
   - Project name
   - Conversation count (count files in `conversation-history/`)
   - Cowork memory entry count (count `.md` files in `transition-data/cowork-space-memory/` minus `MEMORY.md` if present)
   - Working-files indicator (`_PROJECT_BRIEF.md` reports the working files at root)
4. **Custom Instructions walkthrough (Step 1 of 2 in the B-1c bootstrap flow).** Read `transition-data/project-blueprint.md` and locate Section 2. Branch on its content:
   - **Section 2 has a non-empty fenced block** (the source project had Custom Instructions) → display **Prompt B-1c-customs-present**. Inline the fenced block in the blockquote when it's ≤30 lines; when longer, call `mcp__cowork__present_files` against the blueprint path so the user can open it in the right-side pane and copy the fenced block from there. Wait for `done` / `skip` / `quit`. Advance to sub-step 5 on `done` or `skip`.
   - **Section 2 has the empty-placeholder string** ("*(no custom instructions on source; leave the new project's settings empty)*") → display **Prompt B-1c-customs-empty**. Per Discipline rule #9 (auto-advance for informational prompts), advance immediately to sub-step 5 — no user input required.
5. **Bootstrap prompt (Step 2 of 2 in the B-1c bootstrap flow). Display the right B-1c-bootstrap variant** based on whether the current Cowork project's working folder IS the destination folder:
   - If the skill was invoked from inside the destination project (`transition-data/tracker.html` was detected in the CURRENT working folder, not via picker) → **B-1c-bootstrap-in-place** variant. Bootstrap goes in a fresh chat in THIS Cowork project.
   - If the destination folder came in via the picker (current working folder is something else) → **B-1c-bootstrap-relocated** variant. The user needs a Cowork project pointed at the destination folder (existing or newly created); bootstrap goes in a fresh chat there.
   Both variants display the canonical short outer pastable prompt — three lines pointing the destination Claude at `transition-data/project-blueprint.md` and naming Section 7 as the first directive. The outer prompt is short by design; the rich content lives inside the blueprint where Claude reads it as a whole. Section 7 (in the blueprint on disk) carries the memory-restore preamble (when applicable), the conversation-archive registration, and the project-tailored reading list. Wait for `done` / `skip` / `quit`.
6. **On "done"**: display Prompt B-1c-wrap (one-liner: "All set — this project is restored on the new account. You can delete `transition-data/` whenever you've verified the migration."). Skill exits cleanly.
7. **On "skip"**: same wrap but with a note that the bootstrap prompt is in transition-data if they want to come back to it later.
8. **On "quit"**: exit cleanly without modifying anything.

Single-project Track B does not write a destination-side tracker file — the source-side `transition-data/tracker.html` carries the full state for this project and the destination doesn't need its own on-disk copy. However, it DOES render a Cowork sidebar artifact (step 1a above) for the same visual lock-in that multi-project gives the user. (If the user later runs the migration skill again against the same project, it'll re-detect the tracker and re-offer the bootstrap — idempotent.)

### Step 5.5 — Track B scope (all-projects vs. single-project)

Mirrors Step 1.5 from Track A: ask whether the user is restoring everything from the tracker or just one specific project. Fires after the inventory display, before memory seed. **Only used when Step 5 took the B-1a or B-1b branch (multi-project hub)** — B-1c (single-project source) skips this entirely.

Display the **track-b-scope-selection** prompt from `references/skill-user-facing-text.md`. Wait for response.

- **"all"** → set `restore_scope = "all"`. Memory seed runs (Step 6), catch-all setup runs if applicable (Step 7), walk-through runs over every pending project (Step 8).
- **"one"** → display the **track-b-single-project-name** prompt; wait for the user to type a project name. Match against `projects[].name` and `cowork_projects[].name` in the tracker (case-insensitive substring). Set `restore_scope = "single"`, `restore_target = "<typed-name>"`, `restore_match = {<spaceId or null>, <web-uuid or null>, <name from tracker>}`. If zero matches, display the **track-b-single-project-no-match** prompt listing what the tracker contains; offer pick / retry / quit.
- **"quit"** → end the skill cleanly.

**Effect on downstream steps in single-project mode:**

- **Memory seed (Step 6)** is offered but defaults to skip when `restore_scope == "single"` (account-level memory is account-wide; if the user is restoring one project they've likely already seeded). The locked-copy prompt **B-MS-1-single** is a short variant that says "memory seed is account-level — if you've already done it, type 'skip'; if this is a fresh account, type 'ready'."
- **Catch-all setup (Step 7)** is skipped entirely if the matched project isn't routed to the catch-all (Cowork-native projects and Part 1 reconstructed-in-place projects have no catch-all relationship). If the matched project IS catch-all-routed, run Step 7 normally so the user can pick the catch-all folder.
- **Walk-through (Step 8)** filters the pending-projects loop to just the matched project (see Step 8 item 1).

### Step 6 — Track B Phase 2 (memory seed)

Fires after Step 5's inventory display. Memory seeds Claude's account-level memory on the new account from `memory-capture.md` so per-project conversations later in Track B inherit the global context.

Orchestration:

1. Display **Prompt B-MS-1** (memory seed opener).
2. Wait for user response:
   - **"done"** → display **Prompt B-MS-2** (done confirmation). Mark memory-seed-phase as `done` in the tracker. Proceed to Step 6.5.
   - **"skip"** → display **Prompt B-MS-3** (skip confirmation). Mark memory-seed-phase as `skipped` in the tracker. **Skip Step 6.5 too** (nothing to validate if seed wasn't run) and proceed directly to Step 7.
   - **"quit"** → end the skill cleanly.

### Step 6.5 — Track B memory validation (immediate)

Fires right after Step 6 when memory seed completed (`done`). The user is still in Claude Chat (the seed happened there; Cowork can't reach account-level memory). Doing validation now is the same prompt + same surface, just one more paste in the same chat — much better than queuing it to the end of Track B and forcing the user back to Chat after all the destination-side project work.

Skipped when Step 6 returned `skip` (nothing seeded, nothing to validate). Skipped in single-project mode if the user wasn't doing a fresh-account seed (handled per scope at Step 6 level).

Orchestration:

1. Display **Prompt B-V-1** (validation opener) telling the user to paste the validation prompt — verbatim from `assets/validation-prompt.md` — into the *same no-project Claude Chat conversation they just used for the seed*. They compare the response against the `memory-capture.md` on disk; anything missing or wrong, they fix on the new account (memory edit or upload + ask Claude to fill gaps).
2. Wait for **`done`** / **`skip`** / **`quit`**.
3. Display **Prompt B-V-2** (done — validation passed or user accepted gaps) or **Prompt B-V-3** (skip — user deferred validation). Proceed to Step 7.

The late-stage Phase 6 that existed in pre-v1.6.1 builds was redundant with this immediate step and is dropped entirely. If the user wants to re-validate at the end of Track B (e.g., to check whether the new account picked up additional memory during per-project work), they can paste the validation prompt themselves in any no-project Chat conversation — but the skill doesn't prompt them to do it twice.

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

1. **Compute the resume state.** Walk the tracker's `projects[]` + `cowork_projects[]` arrays. Filter to entries where `relinked == "pending"` (treat missing field as "pending"). If `restore_scope == "single"` (from Step 5.5), further filter to the entry whose name matches `restore_target` (case-insensitive substring; same matching rule used in Step 5.5). Count: `<N_total>` = total entries before any scope filter, `<N_done>` = entries where `relinked == "done"` or `"done_no_bootstrap"`, `<N_pending>` = filtered list length (after both pending and scope filters). In single-project mode, `<N_total>` reflects the full tracker but `<N_pending>` is the single-project pending count (0 or 1).
2. **Display the resume status line** at the start of Track B Phase 4 (before Prompt B-6):
   > "Resuming Track B walk-through. `<N_done>` of `<N_total>` projects already relinked — starting with `<first-pending-project-name>`."
   If `<N_done>` is 0 (fresh start), show a simpler line: "Starting Track B walk-through across `<N_total>` projects." [Bug #45 — resume-from-pending status display.]
3. Display **Prompt B-6** (walk-through verbose intro). Use `<N_walkthrough>` = `<N_pending>` (the filtered count, not the total — the walk-through only touches pending projects).
4. Iterate, in tracker order, over the **pending** projects only:
   - From `projects` array: filtered entries where `reconstructed == "done_in_place"` AND `relinked == "pending"`. `<source_kind>` = `"reconstructed from web/chat"`.
   - From `cowork_projects` array: filtered entries where `relinked == "pending"`. `<source_kind>` = `"Cowork from old account"`.
5. For each pending project, display the **per-project pattern** prompt with substitutions filled in from the tracker entry (`<project_name>`, `<source_kind>`, `<N_convs>`, `<N_docs>`, `<folder_path>`). For Part 2 entries that carry a `reattach_folders` array (recon-driven Part 2 path), also include the suggested reattach-folder list in the prompt — these are the working folders that were attached to the source-account sessions for that project, filtered for noise. The user can attach the same folders on the new account, or pick different ones; the list is informational.
6. Wait for "ready" / "skip" / "quit":
   - **"ready"** → display the **per-project picker bridge**, call `mcp__cowork__request_cowork_directory` with no path.
   - **"skip"** → display **per-project skip confirmation**. Mark `relinked = "skipped"` in the tracker for this project. Update both tracker.html and Cowork artifact. Next project's prompt fires.
   - **"quit"** → end the skill cleanly. Current project + remaining projects stay `relinked = "pending"`. Resume on next invocation picks up from this point.
7. After folder access is granted, verify the folder's structure:
   - **Blueprint found at `transition-data/project-blueprint.md`** → display the **happy-path post-pick** prompt. Wait for "done" / "defer". Mark `relinked = "done"` (on "done") or `relinked = "done_no_bootstrap"` (on "defer"). Update both tracker.html and Cowork artifact.
   - **Blueprint missing (Part 2 only)** → display the **blueprint-missing branch**. Wait for "continue" / "back" / "skip". Handle each as appropriate.
   - **Folder structure unexpected** → display the **folder-wrong branch**. Wait for "pick" (re-fire picker) / "skip" / "quit".
8. Cancel handling: if `request_cowork_directory` returns "Directory selection was cancelled by the user" after the user said "ready"-then-implicit-pick, re-ask with pick / skip / quit (same as Track A's cancel pattern).
9. After all pending projects walked: advance tracker `phase` to `"track-b-walkthrough-complete"`. Update both tracker.html and Cowork artifact. Proceed to Step 8.5.

### Step 8.5 — Track B scheduled-tasks recreation (multi-project only)

Fires after Step 8 (per-project walk-through) and before Step 9 (binary recovery / validation / cleanup). **Single-project Track B (B-1c branch) skips this step entirely** — Track A's Step 3.7 was already skipped in single-project mode, so there are no scheduled tasks to recreate.

Mirrors Track A's Step 3.7 in reverse: Track A auto-captured the user's scheduled tasks into `scheduled-tasks-export.md` at the hub root; Track B walks the user through recreating them on the new account.

Orchestration:

1. **Check for scheduled tasks to recreate.** Read the tracker's `scheduled_tasks` array. If empty or absent, display the **scheduled-tasks-zero confirmation** one-liner ("No scheduled tasks captured at source — moving on.") and proceed to Step 9. Also accept the case where the array is non-empty but `<hub>/scheduled-tasks-export.md` is missing (rare; surface a one-line warning and proceed — the tracker JSON alone is not enough since prompts live in the export file).

2. **Read `<hub>/scheduled-tasks-export.md`** to recover each task's verbatim prompt. Parse the file (it's a structured markdown — each task has an H2 with `<N>. <taskId>`, a bullet list with Description/Cron/Enabled/Dependencies, and a fenced code block containing the prompt). Match each parsed entry against the tracker's `scheduled_tasks` array by `taskId`.

3. **Display the opener** — Prompt B-ST-1 (scheduled-tasks opener) — naming the count of tasks captured. Wait for `ready` / `skip` / `quit`. On `skip`, mark all tasks as `recreated_on_destination: false` in the tracker, display the wrap, advance to Step 9. On `quit`, end cleanly.

4. **Iterate over tasks in tracker order**, displaying **Prompt B-ST-2 (per-task)** for each: the task's `taskId`, description, cron expression + human-readable schedule, enabled state, dependency note (if `has_dependencies == true`, list the attached folder names parsed from the export's Dependencies bullet), and the verbatim prompt body (inline if ≤30 lines; otherwise inline the first 20 lines and add "[full prompt continues in `scheduled-tasks-export.md` § task <N>]"). Wait for `recreate` / `skip` / `quit`.

   - **On `recreate`**: call `mcp__scheduled-tasks__create_scheduled_task` with the task's `taskId`, `description`, `cronExpression`, and `prompt` (verbatim from the export). If the call succeeds, mark `recreated_on_destination: true` in the tracker entry and update both `tracker.html` and the Cowork sidebar artifact. If the call fails (taskId already exists on destination, schedule conflict, etc.), surface the error inline and re-ask `recreate-with-new-id` / `skip` / `quit`. For `recreate-with-new-id`, append a suffix (e.g., `-imported`) and retry once.

   - **On `skip`**: mark `recreated_on_destination: false`. Advance to next task.

   - **On `quit`**: end the skill cleanly. Tracker preserves whatever's been recreated so far; user can resume by re-invoking the skill.

5. **After all tasks**, display **Prompt B-ST-wrap** with: `<N_recreated>` recreated, `<N_skipped>` skipped. If any recreated tasks had `has_dependencies == true`, list them with their dependency folders as a reminder: "These tasks reference attached folders that you'll need to re-attach via *Cowork → each task's settings* before they next fire: \<list>." Update tracker `phase` to `"track-b-scheduled-tasks-complete"`. Proceed to Step 9.

The orchestrator does NOT attempt to re-attach folder dependencies via MCP — folder attachment is a Cowork UI action per task, not exposed via the scheduled-tasks MCP API. The reminder in the wrap is the user-facing handoff for that manual step.

### Step 8.7 — Track B custom-skills installation walk-through

Fires after Step 8.5 (scheduled tasks) and before Step 9 (binary recovery / cleanup). **Single-project Track B (B-1c branch) skips this step entirely** — Track A's Step 3.5 was skipped in single-project mode, so there are no captured skills to install.

Bakes in the off-script behavior that worked during v1.6.1 testing: surface every captured `.skill` file as a clickable file (via `mcp__cowork__present_files`), explain related-skill groupings, and accept a single `done` / `skip-all` / `quit` for the whole batch. Account-aware: pre-checks which skills are *already installed* on the destination so the migration skill itself (and any others the user pre-installed) doesn't appear as "ready to install."

Orchestration:

1. **Read installed-skill slugs from the destination account.** Use `mcp__workspace__bash` to list the `.claude/skills/` mount that's exposed to this Cowork session:

   ```bash
   ls -1 /sessions/<session>/mnt/.claude/skills/ 2>/dev/null
   ```

   The result is a list of folder names (one per installed skill). The exact mount path is in this session's system-prompt "Shell access" section — read it from there, don't guess. Each folder name is the skill's slug (e.g. `account-migration`, `vulscan`). Treat the list as authoritative for "installed on this account." If the listing fails or returns empty, treat all captured skills as not-yet-installed and continue.

2. **Reconcile against tracker's `custom_skills[]`.** For each captured-skill entry, derive the slug as the filename minus `.skill` (e.g. `account-migration.skill` → `account-migration`). For each entry whose slug appears in the installed-skill list, set `installed: true` on the tracker entry. For entries not in the installed list, set `installed: false`. Persist the update to both `tracker.html` and the Cowork sidebar artifact before displaying the opener.

3. **Branch on the pending count.** Let `N_pending` = entries with `installed: false`.

   - **`N_pending == 0`** (all captured skills are already installed): display the **B-CS-allinstalled** one-liner ("Custom skills already installed — moving on.") per Discipline rule #9. Set tracker `phase: "track-b-custom-skills-complete"`. Proceed to Step 9.
   - **`N_pending >= 1`**: continue.

4. **Surface the pending `.skill` files.** Call `mcp__cowork__present_files` with the absolute paths of the pending `.skill` files (read them from `<hub>/skills/` — the folder where Track A's auto-export landed). They render in chat as clickable cards with a **Save skill** install button. Skip the already-installed entries — do not surface them.

5. **Display the opener.** Prompt **B-CS-1** names `N_pending` and gives the bundle summary (filename + size for each pending skill, with `vulscan-*` and `copy-*` flagged as related groups when present). End with the `done` / `skip-all` / `quit` ask.

6. **Wait for user.**
   - **On `done`**: re-read `.claude/skills/` to confirm what's now actually installed (the user may have installed only some of the surfaced files). For each captured entry, re-derive `installed: true|false` from the fresh listing. Persist to tracker. Display **B-CS-done** with the actual installed count + any still-pending (these stay `installed: false` and can be revisited via the resume re-walk in Step 5-resume).
   - **On `skip-all`**: leave all pending entries as `installed: false`. Display **B-CS-skip-all**. (No tracker mutation beyond what step 2 already did.)
   - **On `quit`**: end the skill cleanly. Tracker preserves whatever installed-state was set in step 2.

7. Set tracker `phase: "track-b-custom-skills-complete"`. Proceed to Step 9.

**Detection-mechanic notes:**

- The `.claude/skills/` mount is read-only and surfaces both bundled Anthropic skills (docx, pdf, pptx, xlsx, schedule, setup-cowork, skill-creator, consolidate-memory) and any user-installed custom skills. The captured-skills export already filtered the bundled set out via `export_custom_skills.py`, so the slug match in step 2 won't false-positive on the bundled ones.
- `account-migration` will ALWAYS appear installed on Track B (the user installed it to run Track B). The detection naturally filters it out of the walkthrough — no special case needed.
- If the user has installed the skill at the organization level rather than per-account, the slug may not appear in `.claude/skills/` for that account. The user can still mark `done` (skip-all if all are org-level) — the tracker captures intent, not enforcement.
- The user may install via the Save skill button in chat OR by manually uploading via *Cowork → Customize → + → Skills → upload*. Either path lands the skill in `.claude/skills/` and is picked up on the post-`done` re-read.

**Resume integration:** when a user re-invokes the skill on a deferred-cleanup tracker, Step 5-resume offers a **B-Resume-2-skills** sub-step that re-fires Step 8.7's flow if any captured skill is still `installed: false`. Same `re-walk` / `skip-skills-section` / `quit` interface as the other resume sub-steps.

### Step 9 — Track B Phases 5–7 (binary recovery, validation, cleanup)

Fires after walk-through.

#### Phase 5 — Binary recovery

1. Read `_ARTIFACTS_TO_RECOVER.md` from the catch-all. Parse the unchecked items, grouped by conversation. If zero unchecked, display the silent one-liner ("No binaries to recover — moving on.") and proceed to Phase 6.
2. Display **Prompt B-BR-1** (binary recovery opener).
3. Wait for "ready" / "skip" / "quit".
4. On "ready", iterate per-conversation. For each conversation with unrecovered files:
   - Display the **per-conversation pattern** prompt with `<conversation_title>`, `<destination_label>`, `<transcript_relative_path>`, `<N_files>`, the filename list, the `https://claude.ai/chat/<conv_uuid>` URL, and `<artifacts_folder_relative_path>`.
   - Wait for "done" / "skip" / "quit".
   - On "done": **tick the checkboxes** in `_ARTIFACTS_TO_RECOVER.md` for this conversation's files. **Explicit mechanics:** read the file, locate each filename listed under this conversation's `### <conversation_title>` heading, replace `- [ ] <filename>` with `- [x] <filename>` on that line, write the file back. (Per v1.5's manual-intervention audit: this step was previously implicit; making the file-edit pattern explicit so the orchestrator does it consistently.) Move to next.
   - On "skip": leave checkboxes unchecked. Move to next.
   - On "quit": end the skill cleanly.
5. Display **Prompt B-BR-wrap** with the recovered/remaining counts.

#### Phase 6 — (removed in v1.6.1)

Memory validation moved to Step 6.5 (fires immediately after Step 6 seed, while the user is still in Claude Chat). Step 9 now jumps from Phase 5 (binary recovery) directly to Phase 7 (cleanup wrap).

#### Phase 7 — Cleanup wrap

1. Display **Prompt B-C-1** (cleanup opener).
2. Wait for **`done`** / **`later`** / **`quit`**. The `done` keyword means *I completed the cleanup steps above*; `later` means *I'm deferring cleanup and want to come back to it (and any other deferred items) on a later re-invocation of the skill*; `quit` is a clean exit. (Pre-v1.6.1 builds called this `skip`; renamed because `skip` read as "skip a thing the skill was going to do" rather than "I'm leaving the manual cleanup steps for later.")
3. **Update tracker handoff-state.**
   - On `done`: set `cleanup_done: true` and `phase: "track-b-complete"`. Display **Prompt B-C-2** (done).
   - On `later`: set `cleanup_done: false` and `phase: "track-b-complete"`. Display **Prompt B-C-3** (later). The migration is technically "complete" — projects relinked, memory seeded — but `cleanup_done=false` is the signal that a re-invocation of the skill should offer to review deferred items + finish cleanup. See Step 5-resume.
   - On `quit`: exit without changing `phase` or `cleanup_done`. Tracker stays as-is; user can resume from whatever earlier phase the tracker recorded.
4. Display **Prompt B-X-1** (Track B closing). Assemble conditional reminders based on which phases were skipped during this Track B run.
5. Skill exits cleanly.

## The artifact taxonomy (operational reference)

A Claude data export's `chat_messages[].content[]` carries four distinct `tool_use` patterns for assistant-produced content. The skill handles each differently — `reshape_and_extract.py` implements all four. Detail in `references/architecture-notes.md`.

1. **`tool_use: artifacts`** — Claude's web Artifacts panel. Content inline. **Extract** to `<conv-slug>/artifacts/<title>.<ext>` using `type` (and `language` for code) for extension.
2. **`tool_use: create_file`** — file written via Claude's web file tools (typically build scripts). Content inline in `input.file_text`. **Extract** to `<conv-slug>/artifacts/<basename-of-path>`.
3. **`tool_use: bash` heredoc / tee / redirect writes** — file content written by `cat << EOF > path` heredocs (content inline in the bash command itself), or by `tee path` / `> path.ext` redirects (content from a prior command's stdin/stdout, NOT in the bash command). **For intact heredocs:** extract to `<conv-slug>/artifacts/<basename-of-path>`. **For tee, redirect, or truncated heredocs (renderer's `[Omitted long matching line]` marker present):** list in `_ARTIFACTS_TO_RECOVER.md` — content is not recoverable from the transcript alone. Added in v1.5; caught a class of bug that lost intact CSVs across v1.0–v1.4.
4. **`tool_use: present_files`** binary outputs (`.docx`, `.xlsx`, etc.) — only the filepath reference is in the export, no binary. **Not extractable.** List in `_ARTIFACTS_TO_RECOVER.md` at the catch-all root.

**Mojibake detection (v1.5).** `reconstruct.py` scans each extracted knowledge document for visible double-UTF-8 mojibake patterns (`Â`, `âœ`, `â€`, `âš`, `âžž`, `Ã©`, `Ã¨`, `Ã¢`). When found, the affected filenames are surfaced in a Notes-section bullet at the top of the project's `_PROJECT_BRIEF.md`. Detection only — no auto-correction (round-trip isn't reliable; user compares against original on-disk copies and replaces as needed).

## Tracker JSON schema (handoff-state)

`tracker.html` carries an embedded `<script type="application/json" id="handoff-state">` block. Track A writes it; Track B reads it. Full schema in `references/architecture-notes.md`. Key fields:

- `schema_version` — currently `1`.
- `phase` — string enum: `"track-a-part-1-complete"`, `"track-a-part-2-complete"`, `"track-a-complete"`, `"track-b-walkthrough-complete"`, `"track-b-complete"`.
- `catchall` — `{name, folder_path, orphan_count, subfolder_count, ...}` for the catch-all.
- `projects` — array of Part 1 web/chat projects. Each entry: `{order, name, uuid, docs, convs, folder_path, disposition, reconstructed, relinked}`.
- `cowork_projects` — array of Part 2 Cowork projects (added during Track A Step 3 per-folder). Each entry: `{name, folder_path, has_blueprint, relinked}`. Entries added via the v1.5 recon-driven path also carry `{space_id, session_count, reattach_folders}` — the spaceId from the recon CSV, the session count attributed to that spaceId, and the noise-filtered union of `userSelectedFolders` across those sessions. Fallback-path entries omit those three fields.
- `custom_skills` — array of captured custom skills (populated by Step 3.5; install-state mutated by Track B Step 8.7). Each entry: `{filename, size_bytes, installed}`. `installed` is set during Track B Step 8.7's pre-check (reconciling `<hub>/skills/` filenames against the destination account's `.claude/skills/` mount) and re-checked on `done` after the user installs. Track A writes entries with `installed: false` (or omits the field — Track B treats absent as false).

When writing the tracker, the skill writes both `tracker.html` (file on disk) and the Cowork sidebar artifact in lockstep. After every state transition during either track, update both representations.

## Cloud-synced hub truncation gotcha

The user's migration hub may sit inside a cloud-synced folder (any flavor — the same failure mode happens across cloud-sync products on Windows and macOS). Cloud-sync clients can leave files in a partially-synced state where the directory entry exists but a read returns "no such file" or a truncated body. The sandbox's bash mount also keeps a per-path attribute cache that can serve stale views after host-side writes — see the discipline rules below.

**Four failure modes to avoid:**

- **Bundled scripts read at rest in the hub may be truncated.** Always write fresh copies from this skill folder to a private scratch directory (inside the agent's session outputs, NOT the user's hub) at start of run (Step 0 above). Don't trust `.py` files at rest in the hub.
- **Files written into the hub and immediately surfaced to the user via `mcp__cowork__present_files` may upload partially.** The render-recon-script case is the canonical example: the orchestrator writes the rendered PowerShell/bash into the hub folder, the cloud-sync client starts uploading, and when the user clicks the present-files link they may receive a truncated copy. **Pattern to follow**: render to the private scratch directory first, then copy the file into the hub via host-side `Write` (not bash), then read back via host-side `Read` and verify the byte length matches the source. Only after that verification, surface via `present_files`.
- **Reading files at rest in the hub** for verification — prefer the host-side `Read` tool over `mcp__workspace__bash`, since they use different code paths and the host-side often succeeds where bash fails on the same path. Note: the host-side Read isn't iron-clad either; for high-stakes disagreements between bash and host-side Read, do a per-file rename (`mv X X.tmp && mv X.tmp X` in bash) to force a fresh attribute lookup, then re-read both.
- **Write-back cascade** — never write back to disk content that was sourced from a bash read of a pre-existing hub-resident file. The bash read may be returning a stale or truncated view; writing that content back via a host-side tool produces NTFS truncation of the source file. This is the most destructive failure mode. If a script needs to update part of a tracker or a recovery-checklist file, source the existing state from process memory or regenerate from authoritative data (tracker JSON, manifest CSV, etc.) — never round-trip through bash-read-then-write.

## Cowork session storage — what's reachable and what isn't

`mcp__cowork__request_cowork_directory` refuses paths inside Cowork's install storage. This is intentional — the install root is private to the local Cowork install. That said, the v1.5 recon mechanism (Step 2.0) lets us extract non-sensitive session metadata via a user-run native-shell script that walks the per-session JSON files: `sessionId`, `spaceId` (project identity), `title`, timestamps, `isArchived`, and `userSelectedFolders` (the working-folder reattach list). Sensitive fields (initial messages, system prompts, MCQ answers, enabled MCP tools) are deliberately excluded.

Once the recon CSV exists in the hub, the hub Cowork session can additionally pull session transcripts via `mcp__session_info__read_transcript` (which works account-wide, across spaceIds). Per-space memory dirs are NOT mounted into the hub session, so per-project Cowork memory still requires a per-project paste prompt (`assets/cowork-memory-dump-prompt.md`) run inside each project's own source-account Cowork session.

`_PROJECT_BRIEF.md` is still written for every project. Working-folder re-attachment on the destination is user-driven (via the picker), with the reattach-folder list from recon shown as informational guidance.

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
- **Never round-trip bash-read content through a host-side write.** See "Cloud-synced hub truncation gotcha" above for the cascade this prevents.

## What's NOT in this version

- **Auto-tagging of conversation content as work vs. personal.** Some users want to migrate only work content from a comingled personal account. The skill provides selective-pick at the project level but does not classify individual conversations. Manual review inside the catch-all serves this purpose.
- **Per-file granularity in binary recovery.** Recovery is per-conversation (user opens each conversation once, downloads all its referenced files). If a single conversation has many files, the user takes care of them in one pass.
- **Automated validation of new-account memory state.** The validation phase asks the user to compare Claude's response to `memory-capture.md` themselves rather than diffing automatically.
- **Cross-machine path translation in the tracker.** Folder paths in the tracker are the source-account machine's paths. On the new account at the same workstation, they remain valid; on a different machine, the user navigates via the picker. The skill does not attempt to translate paths.
- **Artifact extraction from dumped Cowork session transcripts.** Cowork session transcripts (dumped via `cowork-session-transcript-dump-prompt.md`) carry tool calls only as `[assistant] (called Write)` bracket indicators — the input arguments (filename, content) are collapsed by the `read_transcript` API. Files written by Cowork sessions live on disk in the project's working folder already, so current state is preserved through the filesystem. Historical / intermediate file versions from within a session are not recoverable from the transcript. Revisit if a future MCP version exposes tool inputs.
