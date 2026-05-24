# account-migration

A Claude Skill that walks users through migrating projects, conversations, and accumulated context between two Claude accounts — bridging the gap that Anthropic's data export creates without an import.

> **Why this exists.** Anthropic exports your Claude data but doesn't import it. Conversation history in the export is flat and unattributed to projects; Cowork session storage is walled off from skills by design; custom instructions, project knowledge, and global memory don't migrate automatically. This skill drives a tracked, decision-driven walk-through across both source and destination accounts to bridge that gap.

## What it does

The skill runs in two tracks across the source and destination accounts:

- **Track A (source account)** — process the user's data export, recover per-project attribution from a saved copy of their Chats page, walk through a pick/skip decision per claude.ai project, reconstruct picked projects as on-disk folders with custom instructions, knowledge, and per-conversation transcripts. Cowork projects on the source machine are discovered via a user-run sessions-recon script (no manual picker loop in the typical path) — the skill pulls each project's session transcripts directly via the session-info MCP and asks for a memory dump per project. Custom `.skill` installers (including this one) and scheduled tasks are auto-captured from the install for the new account. A `tracker.html` carries cross-account state.

- **Track B (destination account)** — the same skill, invoked on the new account. Reads the tracker the source side wrote, seeds the new account's global memory from a snapshot, immediately validates the seed, walks through relinking each project (Part 1 reconstructed + Part 2 Cowork) by creating new Cowork projects pointing at the existing on-disk folders, actively recreates each captured scheduled task on the new account via the scheduled-tasks MCP, walks through installing the captured custom skills (filtering out anything already installed on the destination), walks through downloading binary files that couldn't be extracted from the export, and cleans up. Cleanup is optional — if you say `later`, the skill marks the migration as deferred and re-walks deferred items on a subsequent invocation.

Direction-agnostic: personal→corporate, corporate→personal, personal→personal. Direction is metadata, not mechanics.

**Two scopes:** whole-account (every project) or single-project (one project at a time — useful for re-dos and one-off transfers). The skill detects scope from your invocation phrasing and confirms before proceeding.

## Repository layout

```
SKILL.md                               ← orchestration + discipline rules
assets/                                ← prompts and templates written to the user's hub
  README-template.md
  memory-capture-prompt.md
  memory-seed-prompt.md
  migration-prompt-template.md         ← fallback path only as of v1.5
  validation-prompt.md
  cowork-memory-dump-prompt.md         ← per-project source-side memory dump
  cowork-memory-restore-prompt.md      ← destination-side memory restore (also embedded in blueprints)
  cowork-session-transcript-dump-prompt.md  ← fallback path only as of v1.5
  recon-script-windows.ps1.template    ← Windows sessions-recon template
  recon-script-mac.sh.template         ← macOS sessions-recon template
references/                            ← longer reference material the skill reads on demand
  skill-user-facing-text.md            ← canonical locked copy of every user-facing prompt
  architecture-notes.md                ← three project categories, four artifact kinds, tracker schema
scripts/                               ← Python scripts run via the skill's bash environment
  extract_export.py                    ← splits the data export into per-conversation transcripts
  parse_allchats.py                    ← recovers per-project attribution from saved Chats page
  reconstruct.py                       ← writes per-project folders for Part 1 reconstructed projects
  reshape_and_extract.py               ← extracts artifacts (four categories) per conversation
  generate_blueprint.py                ← writes transition-data/project-blueprint.md for any project
  blueprint_coverage_check.py          ← end-of-Track-A gate: every picked project has a blueprint
  derive_install_root.py               ← self-determines install root + UUIDs from the mount table
  render_recon_script.py               ← renders the OS-appropriate sessions-recon script
  parse_recon_csv.py                   ← parses the recon CSV into structured per-project JSON
  package_self.py                      ← repackages this skill into a .skill for Track B
  export_custom_skills.py              ← repackages other installed user skills into .skill files

README.md                              ← this file
LICENSE                                ← MIT License
CHANGELOG.md                           ← version history
```

The skill source files live at the repository root for browse-ability. Pre-built `.skill` binaries are distributed via [GitHub Releases](https://github.com/dbachen-dt/account-migration-skill/releases) rather than committed to the repository, so source history stays clean and each release has a clear version → binary mapping. A `.skill` file is just a zip containing a top-level `account-migration/` folder with the source files inside — produced by zipping a copy of those files with `skill-creator`'s `package_skill.py` or any standard zip tool (see "Build from source" below for the exact command).

## Installing

### Option 1 — Cowork (recommended for most users)

1. Download the latest `account-migration.skill` from the [Releases](https://github.com/dbachen-dt/account-migration-skill/releases/latest) page.
2. In Cowork: **Customize → + → Skills → Upload**, select the `.skill` file.
3. Open a new conversation. Tell Claude *"I need to migrate to a new Claude account"* (or any natural-language phrasing). The skill self-identifies and asks which side you're starting from.

### Option 2 — Build from source (for users who want to verify the binary)

A `.skill` file is just a zip that contains a top-level folder named after the skill (`account-migration/`) with the source files inside. The source files in this repo are at the root, so building a `.skill` means wrapping them in that folder name and zipping.

1. Clone or download this repository.
2. Verify the source files are intact (`SKILL.md`, `assets/`, `references/`, `scripts/` — see the Repository layout above).
3. Build the `.skill` (Linux/macOS shell shown; Windows users can use 7-Zip or PowerShell's `Compress-Archive` equivalently):

   ```sh
   mkdir -p _build/account-migration
   cp -r SKILL.md assets references scripts _build/account-migration/
   (cd _build && zip -r ../account-migration-rebuilt.skill account-migration)
   rm -rf _build
   ```

4. Download the shipped `account-migration.skill` from the [Releases](https://github.com/dbachen-dt/account-migration-skill/releases/latest) page and compare:

   ```sh
   unzip -l account-migration.skill         # file list of the shipped binary
   unzip -l account-migration-rebuilt.skill # file list of the binary you built
   ```

   The file lists should match. For a deeper check, unzip both and `diff -r`:

   ```sh
   unzip -d _shipped account-migration.skill
   unzip -d _rebuilt account-migration-rebuilt.skill
   diff -r _shipped _rebuilt
   rm -rf _shipped _rebuilt
   ```

   You should see no content differences (only filesystem metadata like timestamps).

5. Install the binary you built via the same Cowork UI upload step from Option 1.

This is how you can audit that the shipped `.skill` matches the source in this repository.

## How it works (architecture overview)

### Track A flow

```
Prompt 0 (which side?) → "old"
  ↓
Scope selection (whole-account or single-project)
  ↓
Install recon (Step 2.0)
  Skill self-determines its install root from the sandbox mount table and
  renders an OS-appropriate sessions-recon script (PowerShell on Windows,
  bash+python3 on macOS). User runs it natively to produce a CSV of
  per-session metadata (sessionId, spaceId, title, timestamps, working folders).
  parse_recon_csv.py groups rows by spaceId — that's the project-membership map.
  ↓
Part 1 — claude.ai web/chat projects
  Drop the data export (.zip) and a saved copy of the Chats page (.html) into the hub
  → extract_export.py splits conversations.json into per-conversation files
  → parse_allchats.py recovers project attribution from the Chats HTML
  → tracker.html written + rendered as a Cowork sidebar artifact
  → Catch-all Cowork project created by user
  → Per-project walk-through (pick / skip / quit) — alphabetical
  → reconstruct.py + reshape_and_extract.py + generate_blueprint.py run inline after each pick
  ↓
Part 2 — Cowork projects on the source machine
  Recon-driven (primary): for each in-scope spaceId, the hub session pulls
  every attributed transcript via session-info MCP and writes them to disk.
  User pastes a per-project memory-dump prompt in each project's own source-account
  Cowork session (Cowork space memory isn't reachable across spaces).
  generate_blueprint.py writes transition-data/project-blueprint.md per project.
  ↓
Custom-skills capture (Step 3.5)
  package_self.py repackages this migration skill into the hub's skills/ folder.
  export_custom_skills.py walks the .claude/skills/ mount, filters bundled
  anthropic-skills + the migration skill, and repackages every other user
  custom skill as a .skill file into the same folder.
  ↓
Scheduled-tasks capture (Step 3.7, multi-project only)
  Skill enumerates active scheduled tasks via the scheduled-tasks MCP, captures
  each task's cron, prompt body, dependencies, and writes scheduled-tasks-export.md.
  Track B will recreate these on the new account.
  ↓
Blueprint coverage check (Step 3.6)
  blueprint_coverage_check.py verifies every picked project has a blueprint
  before the user is told the old account is safe to delete.
  ↓
Track A wrap
  README - Final Transition + memory-capture-prompt + tracker handoff state
  + scheduled-tasks-export written to hub. User runs memory-capture-prompt
  on the old account (no-project Chat conversation).
```

### Track B flow

```
Prompt 0 (which side?) → "new"
  ↓
Hub access (detect-at-runtime OR folder picker)
  Skill reads tracker.html's embedded handoff-state JSON.
  If the tracker shows a deferred-cleanup migration, the skill offers to
  re-walk skipped items + re-fire cleanup; otherwise proceeds to Phase 2.
  ↓
Memory seed (Phase 2)
  User pastes memory-seed-prompt in a no-project Claude Chat conversation,
  attaching memory-capture.md.
  ↓
Memory validation (Step 6.5 — immediate)
  Still in the same Chat conversation: user pastes a validation prompt and
  confirms the seed worked. Done while the user is still on the Chat side
  (avoids an end-of-Track-B context switch back to Chat).
  ↓
Catch-all setup (Phase 3)
  User imports the catch-all folder as a Cowork project on the new account.
  ↓
Per-project walk-through (Phase 4 — Step 8)
  For each Part 1 reconstructed project + Part 2 Cowork project (alphabetical):
    User creates a Cowork project (Choose existing folder)
    → skill verifies the project's blueprint
    → User pastes Custom Instructions + a short bootstrap prompt
      (the bootstrap points the destination Claude at the blueprint's Section 7
       directive, which itself drives memory restore + history archival)
  ↓
Scheduled-tasks recreation (Step 8.5 — active walk-through, multi-project only)
  For each captured task: skill calls mcp__scheduled-tasks__create_scheduled_task
  directly with the cron, prompt, and description from the source-side export.
  User says "recreate" / "skip" per task. Folder-dependency reattach surfaced
  as a manual reminder per task (Cowork UI step, not MCP-exposed).
  ↓
Custom-skills installation (Step 8.7 — active walk-through, multi-project only)
  Skill reads .claude/skills/ on the destination, filters out anything already
  installed (notably this migration skill itself), and surfaces the pending
  .skill files as clickable "Save skill" cards. User installs what they want;
  skill re-reads the mount on `done` to confirm.
  ↓
Binary recovery (Phase 5)
  Walk through _ARTIFACTS_TO_RECOVER.md conversation by conversation,
  downloading files from claude.ai before the old account is deleted.
  Skill ticks each conversation's checkboxes after the user confirms recovery.
  ↓
Cleanup (Phase 7)
  User says `done` (archive both hub Cowork projects + delete on-disk hub),
  `later` (leave hub in place; skill flags migration as deferred-cleanup and
  re-walks any skipped items on a subsequent run), or `quit`.
```

### The four artifact kinds in the export

A Claude data export's conversation messages can contain four patterns of assistant-produced content, each requiring different handling:

- `tool_use: artifacts` — Claude's web Artifacts panel. Content is inline; extracted to per-conversation `artifacts/` subfolders.
- `tool_use: create_file` — files written via Claude's web file tools (typically build scripts). Content is inline; extracted similarly.
- `tool_use: bash` heredoc / tee / redirect writes — file content written by `cat << EOF > path` heredocs (content inline in the bash command itself), or by `tee`/`>` redirects (content from a prior command's stdout). Intact heredocs are extracted; tee/redirect writes and truncated heredocs (the renderer's `[Omitted long matching line]` marker) get listed in `_ARTIFACTS_TO_RECOVER.md` instead — content not recoverable from the transcript alone.
- `tool_use: present_files` — binary outputs like `.docx`, `.xlsx`, `.pdf`, `.pptx`. Only the filepath reference is in the export; the binary itself isn't. These get listed in `_ARTIFACTS_TO_RECOVER.md` for manual recovery from claude.ai before the old account is deleted.

### Tracker JSON schema

The `tracker.html` file carries an embedded `<script type="application/json" id="handoff-state">` block as the cross-account state vehicle. Full schema documented in [`account-migration/references/architecture-notes.md`](account-migration/references/architecture-notes.md). Top-level fields: `schema_version`, `phase`, `cleanup_done`, `totals`, `catchall`, `projects[]`, `cowork_projects[]`, `custom_skills[]`, `scheduled_tasks[]`. Phase progresses through `track-a-part-1-complete` → `track-a-part-2-complete` → `track-a-complete` → `track-b-walkthrough-complete` → `track-b-scheduled-tasks-complete` → `track-b-custom-skills-complete` → `track-b-complete`.

## Compatibility and requirements

- **Cowork** (the desktop Claude application that supports custom skills). The skill uses Cowork-specific tools: `mcp__cowork__request_cowork_directory` for folder access, `mcp__cowork__create_artifact` for the live tracker, `mcp__cowork__present_files` for the custom-skill install cards, and the `session-info` and `scheduled-tasks` MCPs for transcript pulls and scheduled-task recreation.
- **Claude account data export** from claude.ai (Settings → Privacy → Export data). This is what the skill processes in Track A Part 1.
- **A saved copy of the user's Chats page** (HTML) from claude.ai. This is what recovers per-project attribution since the data export's `conversations.json` has no project-linkage field.
- **Windows or macOS host** for the install-recon step. The skill renders an OS-appropriate sessions-recon script the user runs natively (PowerShell on Windows, bash+python3 on macOS). The recon mechanism itself is OS-agnostic at the principle level; macOS path translation is validated against real Cowork installs but treat it as newer than the Windows path. Linux Cowork installs (if/when they exist) need the macOS path translated for `~/.config` instead of `~/Library` — pattern is the same.
- **The Cowork bash sandbox.** All scripts run inside Cowork's bash environment (Python 3, common CLI tools preinstalled). No external dependencies.

## Known limitations

- **Per-space Cowork memory still requires a per-project paste prompt.** The session-info MCP can read transcripts across spaceIds, but the per-project `memory/` directories aren't mounted into the hub session. Track A's Part 2 writes a `cowork-memory-dump-prompt.md` into each project's `transition-data/` folder; the user pastes it in that project's own source-account Cowork session, which is the only context that can write that project's memory. Track B's blueprint Section 7 restores it on the destination side.
- **Cowork session storage is walled off by design.** Project working-folder attachments and project-level Custom Instructions aren't readable by skills. Custom Instructions are captured at user request via the dump prompt; folder re-attachment on the destination is via the picker (per-project, with the recon's `userSelectedFolders` list shown as guidance).
- **Conversation deletion is honored.** Conversations deleted on claude.ai before the export are present in the export as skeletons (empty messages, empty names). The skill drops these explicitly rather than carrying them across — content is gone anyway.
- **Binary files in `present_files` artifacts and `tee`/redirect writes are not extractable.** The skill flags them for manual recovery from claude.ai before the old account is deleted. Once the old account is gone, unrecovered files are lost permanently.
- **The skill does not classify conversations as work vs. personal.** If you're migrating only corporate content off a comingled personal account, you'll review each project at pick time and use the catch-all for case-by-case decisions.
- **Scheduled-task folder dependencies are a manual step.** The scheduled-tasks MCP doesn't expose per-task folder attachment, so Track B's Step 8.5 creates the task spec but the user re-attaches any referenced folders via the Cowork task settings UI. Step 8.5's wrap surfaces a reminder per dependency-having task.

## Security and privacy

- **The skill reads your data export locally on your machine.** Nothing is uploaded anywhere by the skill itself.
- **Custom instructions, project knowledge, conversation content, and account memory are all touched** during the migration. Treat the migration hub folder accordingly (don't share it; clean it up at the end).
- **The skill is read-only with respect to your source-account data.** It writes new files (reconstructed project folders, the catch-all, the tracker) but does not modify or delete content on claude.ai or in your existing Cowork projects.
- **Account deletion is your call, not the skill's.** The skill recommends deleting the old account only after Track B is complete and binaries are recovered. The decision and the action are yours.
- **The `.skill` file is just a zip.** You can inspect every script and prompt the skill runs before installing — see "Build from source" above.

## Disclaimer

This skill is provided as-is for the purpose of bridging Anthropic's export-without-import gap. While it has been tested against real account data, account migration touches everything you care about across two accounts — projects, conversations, memory, custom instructions, knowledge files. Test against a non-critical account first if you can. Read the prompts the skill displays before saying "ready" — the skill is explicit about what it's about to do at each step.

The skill cannot recover what isn't in the data export (deleted conversations, locally-edited binary files that exist only in claude.ai's storage). It surfaces these limitations as it goes; respect them.

## Contributing

Issues and pull requests welcome. Areas of likely interest:

- Additional edge cases in the export format (alternative `tool_use` patterns, schema changes in future Anthropic exports).
- Better recovery flows when `tracker.html` is corrupted or out of sync with the on-disk state.
- Optional automation of binary recovery using the Claude API (Track B Phase 5 currently requires the user to download manually).
- Localization of user-facing prompts.

When contributing, the rule of thumb for the skill bundle is: **every file in the bundle is read by users who don't know who built it**. Keep author-personal, project-specific, and development-history content out of bundled files. Working drafts and iteration notes belong in project-root files (like this README's repository's own working files), not inside the `account-migration/` source folder.

## License

MIT License. See [LICENSE](LICENSE).

## Maintainer

Duncan Bachen, Diamond Technologies, Inc.

## Acknowledgements

Built on Anthropic's [Skills](https://github.com/anthropics/skills) system. The structure (SKILL.md + assets + references + scripts) follows the conventions documented in Anthropic's [Complete Guide to Building Skills for Claude](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf). The skill-creator skill from the official anthropic-skills bundle was used during development.
