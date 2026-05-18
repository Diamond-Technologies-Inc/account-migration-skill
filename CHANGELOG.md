# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] — 2026-05-18

### Added
- **Track B (destination account):** full interactive walk-through driving the new-account setup end to end. Phases: memory seed, catch-all setup, per-project walk-through, binary recovery, validation, cleanup wrap, closing.
- **Memory seed phase** at the start of Track B (after the inventory display, before catch-all setup). New asset `assets/memory-seed-prompt.md` is the inverse of `memory-capture-prompt.md` — pasted in a no-project conversation on the new account with `memory-capture.md` attached.
- **Detect-at-runtime hub access.** Track B auto-detects when the skill is running inside the migration hub project (presence of `tracker.html` in the working folder) and skips the folder picker; otherwise prompts the user to pick the hub.
- **Track A wrap (Prompt N+2) rewritten** with an explicit four-step new-account bootstrap (get hub onto new machine → install skill via Customize tab → import hub as Cowork project → invoke skill and pick "new"). Replaces the previous "See you on the other side + README pointer" with concrete instructions.
- **README restructured** with the skill-assisted Track B path as the primary documented flow (top of the README) and the previous step-by-step checklist as a "Manual steps (fallback)" section.
- **Custom-skills capture (Track A Step 3.5)** explicitly foregrounds `account-migration.skill` itself as a required item to collect — without it, the new account cannot run Track B.
- **Tracker JSON schema extensions:** `cowork_projects[]` array (one entry per Part 2 picked folder), `custom_skills[]` array (populated by Step 3.5), and a phase-string enum (`track-a-part-1-complete`, `track-a-part-2-complete`, `track-a-complete`, `track-b-walkthrough-complete`, `track-b-complete`) so resumed sessions can place themselves correctly.

### Changed
- **Per-project relink instructions in Track B simplified** to three user actions (open the new project, paste custom instructions from the blueprint, bootstrap a conversation). Knowledge-file access is surfaced in the bootstrap prompt rather than as a separate upload step — files in the project folder are already accessible to the new Cowork project.
- **SKILL.md OneDrive truncation gotcha section expanded** with the write-back cascade rule: never round-trip content through a bash-read → host-side-write cycle on OneDrive-resident files.
- **Bundle made 100% standalone for public distribution.** All author-identifying, development-history, and test-specific references removed from bundled files: locked-date markers, references to internal memory files, specific test counts, development-iteration commentary, and personal-path references. Substitution placeholders used throughout for runtime-filled values.

### Removed
- The "Optional: skill-assisted Track B" section at the bottom of the README template (folded into the new top-of-README primary section).

## [1.1.0] — 2026-05-17

### Added
- **Custom-skills capture step (Track A Step 3.5)** — interactive prompt sequence fires after Part 2 wraps and before the Track A cleanup. The user collects any custom `.skill` installer files into a `skills/` subfolder in the hub so they're available for installation on the new account.

### Changed
- **Bundled `references/skill-user-facing-text.md` rebuilt as a slim derived form** of the working source draft. Contains locked user-facing prompts, per-prompt decision blocks, and operational mechanics. Working-draft scaffolding (status notes, iteration meta, task lists) is no longer carried into the bundled file.

### Fixed
- The v1.0 bundled references file was truncated mid-content at packaging time due to OneDrive sync state on the source folder. Packaging now uses a non-cloud-synced scratch directory, and post-package verification confirms full file contents.

## [1.0.0] — 2026-05-17

Initial release.

### Included
- **Track A** end-to-end (source-account preparation):
  - Part 1 — process the Claude data export, recover per-project attribution from a saved copy of the Chats page, walk through pick/skip decisions per claude.ai project, reconstruct picked projects as on-disk folders with `_PROJECT_BRIEF.md`, `knowledge/`, and `conversation-history/`. Inline artifacts (`tool_use: artifacts` and `tool_use: create_file`) extracted to per-conversation subfolders. Binary outputs (`tool_use: present_files`) listed in `_ARTIFACTS_TO_RECOVER.md` for manual recovery.
  - Part 2 — picker loop over the user's existing Cowork project folders. Brief written next to each one's working files plus a `transition-data/migration-prompt.md` the user runs in old-account Cowork before deletion.
  - End-of-Track-A wrap — writes `README - Final Transition to New Account.md` and `memory-capture-prompt.md` to the hub.
- **Tracker dual-render** — `tracker.html` written to the hub on disk and rendered as a Cowork sidebar artifact, kept in sync after every state transition.
- **Track B** documented as a manual checklist in the README. The skill itself displays the Part 3 banner on "new" and points users at the manual flow.

### Known limitations at 1.0.0
- Track B is documentation-only (no interactive walk-through).
- Bundled `references/skill-user-facing-text.md` is incomplete at distribution (fixed in 1.1.0).
- No prompt for the user to collect `account-migration.skill` itself for the new-account install (fixed in 1.1.0 via custom-skills capture).
