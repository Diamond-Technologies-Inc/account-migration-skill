# account-migration

A Claude Skill that walks users through migrating projects, conversations, and accumulated context between two Claude accounts — bridging the gap that Anthropic's data export creates without an import.

> **Why this exists.** Anthropic exports your Claude data but doesn't import it. Conversation history in the export is flat and unattributed to projects; Cowork session storage is walled off from skills by design; custom instructions, project knowledge, and global memory don't migrate automatically. This skill drives a tracked, decision-driven walk-through across both source and destination accounts to bridge that gap.

## What it does

The skill runs in two tracks across the source and destination accounts:

- **Track A (source account)** — process the user's data export, recover per-project attribution from a saved copy of their Chats page, walk through a pick/skip decision per claude.ai project, reconstruct picked projects as on-disk folders with custom instructions, knowledge, and per-conversation transcripts. Cowork projects on the source machine get their own annotation pass. The user collects any custom `.skill` installer files (including this one) for the new account. A `tracker.html` carries cross-account state.

- **Track B (destination account)** — the same skill, invoked on the new account. Reads the tracker the source side wrote, seeds the new account's global memory from a snapshot, walks through relinking each project (Part 1 reconstructed + Part 2 Cowork) by creating new Cowork projects pointing at the existing on-disk folders, walks through downloading binary files that couldn't be extracted from the export (before the old account is deleted), runs validation, and cleans up.

Direction-agnostic: personal→corporate, corporate→personal, personal→personal. Direction is metadata, not mechanics.

## Repository layout

```
account-migration/                     ← the skill source (canonical)
  SKILL.md                             ← orchestration + discipline rules
  assets/                              ← prompts and templates written to the user's hub
    README-template.md
    memory-capture-prompt.md
    memory-seed-prompt.md
    migration-prompt-template.md
    validation-prompt.md
  references/                          ← longer reference material the skill reads on demand
    skill-user-facing-text.md          ← canonical locked copy of every user-facing prompt
    architecture-notes.md              ← three project categories, three artifact kinds, tracker schema
  scripts/                             ← Python scripts run via the skill's bash environment
    extract_export.py
    parse_allchats.py
    reconstruct.py
    reshape_and_extract.py

account-migration.skill                ← pre-built binary (just a zip of the source folder)
README.md                              ← this file
LICENSE                                ← MIT License
CHANGELOG.md                           ← version history
```

The source folder is the canonical artifact. The `.skill` file is a build output for installation convenience — produced by zipping the source folder with `skill-creator`'s `package_skill.py` or any standard zip tool.

## Installing

### Option 1 — Cowork (recommended for most users)

1. Download `account-migration.skill` from this repository (or from a tagged Release).
2. In Cowork: **Customize → + → Skills → Upload**, select the `.skill` file.
3. Open a new conversation. Tell Claude *"I need to migrate to a new Claude account"* (or any natural-language phrasing). The skill self-identifies and asks which side you're starting from.

### Option 2 — Build from source (for users who want to verify the binary)

1. Clone or download this repository.
2. Verify the source folder is intact (no missing files, expected structure above).
3. Package it: `cd account-migration && zip -r ../account-migration-rebuilt.skill .`
4. Compare against the shipped `.skill`:
   - `unzip -l account-migration.skill` and `unzip -l account-migration-rebuilt.skill` — file lists should match.
   - Optionally diff: `unzip -d shipped/ account-migration.skill && diff -r shipped/account-migration account-migration/` — should produce no differences except for filesystem metadata.
5. Install the binary you built via the same Cowork UI upload step.

This is how you can audit that the shipped `.skill` is exactly what the source represents.

### Option 3 — Claude Code plugin marketplace

If you use Claude Code, you can add this repository as a plugin marketplace and install from there. (See Anthropic's [Claude Skills docs](https://github.com/anthropics/skills) for the marketplace mechanics.)

## How it works (architecture overview)

### Track A flow

```
Prompt 0 (which side?) → "old"
  ↓
Part 1 — claude.ai web/chat projects
  Drop the data export (.zip) and a saved copy of the Chats page (.html) into the hub folder
  → extract_export.py splits conversations.json into per-conversation files
  → parse_allchats.py recovers project attribution from the Chats HTML
  → tracker.html written + rendered as a Cowork sidebar artifact
  → Catch-all Cowork project created by user
  → Per-project walk-through (pick / skip / quit)
  → reconstruct.py + reshape_and_extract.py run inline after each pick
  ↓
Part 2 — Cowork projects on the source machine
  Picker loop: user picks each Cowork project folder; skill writes a brief +
  a per-project migration-prompt the user runs in old-account Cowork
  ↓
Custom-skills capture
  User collects all custom .skill installers (including this one) into hub's skills/
  ↓
Track A wrap
  README + memory-capture-prompt + tracker handoff state written to hub
  Skill exits, user runs memory-capture-prompt on old account before deletion
```

### Track B flow

```
Prompt 0 (which side?) → "new"
  ↓
Hub access (detect-at-runtime OR folder picker)
  Skill reads tracker.html's embedded handoff-state JSON
  ↓
Memory seed
  User pastes memory-seed-prompt in a no-project conversation, attaching memory-capture.md
  ↓
Catch-all setup
  User imports the catch-all folder as a Cowork project on the new account
  ↓
Per-project walk-through
  For each Part 1 reconstructed project + Part 2 Cowork project:
    User creates a Cowork project (Choose existing folder) → skill verifies blueprint
    → User pastes custom instructions, bootstraps a conversation
  ↓
Binary recovery
  Walk through _ARTIFACTS_TO_RECOVER.md conversation by conversation,
  downloading files from claude.ai before the old account is deleted
  ↓
Validation
  User runs the validation prompt, compares against memory-capture.md
  ↓
Cleanup
  Archive hub project on both accounts; delete the on-disk hub folder
```

### The three artifact kinds in the export

A Claude data export's conversation messages can contain three patterns of assistant-produced content, each requiring different handling:

- `tool_use: artifacts` — Claude's web Artifacts panel. Content is inline; extracted to per-conversation `artifacts/` subfolders.
- `tool_use: create_file` — Files written via Claude's web file tools (typically build scripts). Content is inline; extracted similarly.
- `tool_use: present_files` — Binary outputs like `.docx`, `.xlsx`, `.pdf`, `.pptx`. Only the filepath reference is in the export; the binary itself isn't. These get listed in `_ARTIFACTS_TO_RECOVER.md` for manual recovery from claude.ai before the old account is deleted.

### Tracker JSON schema

The `tracker.html` file carries an embedded `<script type="application/json" id="handoff-state">` block as the cross-account state vehicle. Full schema documented in [`account-migration/references/architecture-notes.md`](account-migration/references/architecture-notes.md). Top-level fields: `schema_version`, `phase`, `totals`, `catchall`, `projects[]`, `cowork_projects[]`, `custom_skills[]`.

## Compatibility and requirements

- **Cowork** (the desktop Claude application that supports custom skills). The skill uses Cowork-specific tools: `mcp__cowork__request_cowork_directory` for folder access, `mcp__cowork__create_artifact` for the live tracker.
- **Claude account data export** from claude.ai (Settings → Privacy → Export data). This is what the skill processes in Track A Part 1.
- **A saved copy of the user's Chats page** (HTML) from claude.ai. This is what recovers per-project attribution since the data export's `conversations.json` has no project-linkage field.
- **Windows, macOS, or Linux.** No platform-specific functionality beyond folder paths.

## Known limitations

- **Cowork session storage is walled off by design.** Cowork session conversation history, project `memory.md`, and working-folder attachments are NOT readable by skills. Part 2 of Track A writes only a project brief and a migration-prompt for the user to run themselves. The user re-attaches working folders manually on the new account.
- **Conversation deletion is honored.** Conversations deleted on claude.ai before the export are present in the export as skeletons (empty messages, empty names). The skill drops these explicitly rather than carrying them across — content is gone anyway.
- **Binary files in `present_files` artifacts are not in the export.** The skill flags them for manual recovery from claude.ai before the old account is deleted. Once the old account is gone, unrecovered files are lost permanently.
- **The skill does not classify conversations as work vs. personal.** If you're migrating only corporate content off a comingled personal account, you'll review each project at pick time and use the catch-all for case-by-case decisions.

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
