# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.6.2] — 2026-05-24

End-to-end Track B test-run polish — three issues surfaced during a full destination-account dry run.

### Added

- **Track B Step 8.7 — custom-skills installation walk-through** (multi-project only). Fires after scheduled-tasks recreation, before binary recovery. The orchestrator pre-checks the destination account's `.claude/skills/` mount (via the read-only sandbox listing), reconciles installed slugs against the tracker's `custom_skills[]` array, and only surfaces the *pending* `.skill` files via `mcp__cowork__present_files` (clickable Save-skill cards in chat). The migration skill itself is naturally filtered out — it's always already installed on the destination during Track B. Single `done` / `skip-all` / `quit` ask for the whole batch; `done` re-reads the mount to confirm what's actually installed. New locked-copy prompts: `B-CS-allinstalled`, `B-CS-1`, `B-CS-done`, `B-CS-skip-all`.
- **Resume sub-step for pending skills** — Step 5-resume now offers a `B-Resume-2-skills` re-walk when any captured skill is still uninstalled. Re-fires Step 8.7's surface-and-install flow.
- **`installed` field on `custom_skills[]` tracker entries** — set during Step 8.7's pre-check (and refreshed on user `done`). Tracker JSON schema updated; absent value treated as `false` for back-compat with pre-v1.6.2 trackers.

### Changed

- **Track B tracker re-render preserves Track B framing.** New explicit rule in SKILL.md: whenever the tracker is rendered or re-rendered during Track B (artifact-stale sync, manual write-back, mid-walk state update, etc.), the phase chip, the projects table's relinked-column / status badges, the Custom Skills status mapping (`installed` / `pending install`, not Track A's blanket `ready to install`), and the Scheduled Tasks status mapping all reflect actual handoff-state fields. Fixes the regression where a mid-Track-B `update_artifact` call could re-render the tracker with Track A framing (missing relinked-column, blanket "ready to install" skills).
- **B-4 hub-inventory display lists scheduled tasks and clarifies the flow.** Adds the `<N_scheduled_tasks>` line (was previously invisible in the inventory) and updates the trailing "things to do" line to enumerate all eight Track B phases instead of the stale five-step summary.

### Fixed

- **Custom-skills install was an implicit user task.** Pre-v1.6.2, Track B's `Custom Cowork Skills` tracker section listed the captured skills with no walk-through — the skill assumed the user would install them via the README. Step 8.7 closes that gap with an active surface-and-install pass.
- **Tracker listed the migration skill as `ready to install` on Track B.** Pre-v1.6.2 the tracker rendered every captured skill with the same status regardless of whether the destination account already had it. Step 8.7's pre-check fixes the misleading display.

---

## [1.6.1] — 2026-05-24

The first major release since v1.4. Covers everything that landed across internal milestones v1.5.0, v1.5.1, v1.5.2, v1.6.0, and v1.6.1 — all rolled into this public release. The skill is now substantially more autonomous and robust: an authoritative project-membership map drives Part 2 directly from the user's install (no more per-project paste prompts for transcripts), a redesigned Side B bootstrap puts the destination Claude in the right place with one short paste, custom skills and scheduled tasks are auto-captured for the new account, and single-project migrations are a first-class flow.

### Added — major capabilities

- **Install recon — authoritative session-to-project attribution.** A small user-run native-shell script (Windows PowerShell or macOS bash+python3) walks the Cowork install's per-session JSON files and writes a CSV the skill reads. From the CSV the skill knows which sessions belong to which project (via `spaceId`) and which working folders were attached to each (via `userSelectedFolders`), with no heuristic guessing. Sensitive fields (initial messages, system prompts, MCQ answers, enabled MCP tools) are deliberately not read. The skill self-determines the install root from the sandbox mount table — no user input, no path guessing, no install-shape assumptions. New supporting bundle: `scripts/derive_install_root.py`, `scripts/render_recon_script.py`, `scripts/parse_recon_csv.py`, `assets/recon-script-windows.ps1.template`, `assets/recon-script-mac.sh.template`. SKILL.md Step 2.0 documents the flow.

- **Single-project migration mode.** A new Step 1.5 scope gate asks whether the user is migrating their whole account or just one specific project. If "one," the user names the project; downstream per-project loops in both Part 1 and Part 2 filter to that name. Zero matches on a side is a clean "no work on that side this run" rather than an error. Side B mirrors with Step 5.5 (multi-project) and Step 5-single (single-project, auto-detected from `transition-data/tracker.html` at the destination project's root).

- **Bipartite blueprint pattern — Section 7 as a directive, not a paste target.** Every project blueprint now opens with a "How to use this file" header naming the bipartite split: human-facing sections (Section 2 Custom Instructions paste-into-settings, Section 7 first-directive-for-Claude) vs. AI-facing sections (1 Purpose, 3 Key Decisions, 4 Work in Progress, 5 Knowledge Base, 6 Recurring Context). Section 7 was restructured from "paste this prompt" to a numbered directive block: optional memory-restore preamble (only when Cowork memory was dumped) → project-tailored reading list → on-demand archive registration (via a datestamped memory entry: `reference_pre_migration_archive_YYYYMMDD`) → Section 4 open-items short summary → acknowledgment back to user. Avoids pre-loading every transcript (a 5-transcript project saves ~10-20k tokens at bootstrap time).

- **Canonical short outer bootstrap prompt — three lines, used verbatim in four places.** Side B's user-pasted prompt is a single short pointer: *"Read `transition-data/project-blueprint.md` for the full project context, then treat its Section 7 as your first directive."* Used everywhere a user needs to bootstrap a fresh chat on the new account: skill locked copy for both B-1c-bootstrap variants, README-template manual fallback, `_RESUME_ON_NEW_ACCOUNT.md`, and `_PROJECT_BRIEF.md`'s "Resuming on the new account" section. The rich content stays inside the blueprint.

- **Two-step Side B bootstrap (B-1c flow).** Step 5-single sub-step 4 walks the user through Custom Instructions paste first (Step 1 of 2) via new locked copy prompts **B-1c-customs-present** (Section 2 non-empty — inline the fenced block if ≤30 lines, otherwise surface the blueprint via `mcp__cowork__present_files` so the user can copy from the right-side pane) and **B-1c-customs-empty** (Section 2 empty, auto-advance). The chat bootstrap is Step 2 of 2. Previously the Section 2 paste step was silently skipped.

- **`scripts/generate_blueprint.py`** — unified blueprint generator for both Part 1 (reconstructed-from-export) and Part 2 (Cowork-native) projects. Reads disk-resident data only. Writes `transition-data/project-blueprint.md` with mechanical sections filled (Section 2 Custom Instructions verbatim, Section 5 Knowledge Base inventory, Section 7 with memory-restore preamble embedded verbatim from `assets/cowork-memory-restore-prompt.md` when applicable) and clear TODO markers in synthesis-required sections (1 Purpose, 3 Key Decisions, 4 WIP, 6 Recurring Context, plus Section 7 items 1 + 3). Writes `transition-data/_BLUEPRINT_SYNTHESIS_NOTES.md` with raw input excerpts the hub Claude uses to write the final synthesis. For Part 2 projects, also writes `_PROJECT_BRIEF.md` at project root.

- **Auto-export user custom skills.** A new `scripts/export_custom_skills.py` reads the read-only `.claude/skills/` mount, filters out the bundled `anthropic-skills` plugin members (docx, pdf, pptx, xlsx, schedule, setup-cowork, skill-creator, consolidate-memory) and the `account-migration` skill itself (handled separately by `package_self.py`), and repackages every remaining installed custom skill into a `.skill` zip in the hub's `skills/`. Step 3.5 runs this after auto-packaging the migration skill, so by the time the user sees the confirmation prompt, every transferable skill is already in place. Manual drag-drop into `skills/` is still supported as a fallback for skills the user has on disk but never installed.

- **Deferred-cleanup resume on re-invocation.** Track B's Phase 7 cleanup wrap now offers `done` / **`later`** (renamed from the previous misleading `skip`) / `quit`. `later` sets a new `cleanup_done: false` flag in the tracker JSON; on a subsequent invocation of the skill against the same hub, Step 5's phase router detects the deferred state and branches to a new Step 5-resume. The resume flow lists outstanding deferred items (skipped projects, non-recreated scheduled tasks, unchecked binaries from `_ARTIFACTS_TO_RECOVER.md`) and offers a per-section re-walk: user can `review` everything, `cleanup-now` to skip the review and finalize, or `leave` to defer again without changing anything. Within `review`, each deferred section (projects / tasks / binaries) is independently skippable. Re-walking projects flips `relinked: "skipped"` entries back to `pending` so Step 8's existing iteration handles them; tasks and binaries don't need a flip because their step-level filters already iterate non-completed items. After all sections, Phase 7 fires again so the user can finalize cleanup (`done` → `cleanup_done: true`, migration fully closed) or defer again. Pre-v1.6.1 trackers (no `cleanup_done` field) are treated as deferred — resume capability works retroactively.

- **Scheduled-tasks capture + active recreation walk-through (multi-project only).** A new Step 3.7 on the source side lists active Cowork scheduled tasks via `mcp__scheduled-tasks__list_scheduled_tasks`, reads each prompt verbatim from `Documents\Claude\Scheduled\<taskId>\SKILL.md`, and writes a self-contained `scheduled-tasks-export.md` at the hub root with cron expression, description, enabled state, and any dependencies (attached working folders, external Windows state). The matching new **Step 8.5 on the destination side** walks the user through recreating each captured task: for every task in `scheduled_tasks`, the skill displays the spec and prompts `recreate / skip / quit`; on `recreate` it calls `mcp__scheduled-tasks__create_scheduled_task` directly with the cron + prompt + description, so the task lands on the new account in the same conversation. For tasks with attached working-folder dependencies, the wrap surfaces a per-task reminder to re-attach folders via *Cowork → each task's settings*. Single-project Track A AND Track B both skip these steps (scheduled tasks are account-level resources, out of scope for a one-project transfer).

- **`scripts/blueprint_coverage_check.py`** — end-of-Track-A ship-readiness check (Step 3.6). Verifies every project folder has `transition-data/project-blueprint.md`. Exits non-zero if any missing; the orchestrator surfaces the gap before the source-account-delete step.

- **`assets/cowork-memory-dump-prompt.md`** — per-project source-side paste prompt for Cowork memory. The skill writes it into each Part 2 project's `transition-data/`; user pastes in a fresh Cowork conversation in that project; Claude dumps memory to `transition-data/cowork-space-memory/`.

- **`assets/cowork-session-transcript-dump-prompt.md`** — fallback path for session-transcript dumps. The primary v1.6 path pulls transcripts from the hub session directly via `read_transcript`. This standalone prompt covers users who skip the install recon and the narrow edge case of blank-spaceId sessions.

- **`assets/cowork-memory-restore-prompt.md`** — destination-side memory-restore fallback (also embedded verbatim into Section 7 of every blueprint with Cowork memory).

- **4th artifact category in `reshape_and_extract.py`** — `tool_use:bash` heredoc / tee / redirect writes. Intact `cat << EOF > path` heredocs extract to `<conv-slug>/artifacts/`; truncated heredocs and ambiguous tee/redirect writes get flagged in `_ARTIFACTS_TO_RECOVER.md`. Closes a class of bug that lost intact CSVs in v1.0–v1.4.

- **Mojibake detection in `reconstruct.py`.** Knowledge files are scanned for visible double-UTF-8 patterns. Detected filenames surface in a Notes-section bullet at the top of the project's `_PROJECT_BRIEF.md` — detection only, user resolves manually.

- **Track B sidebar artifact + resume-from-pending walk-through.** Step 5 calls `create_artifact` for the tracker on the Cowork sidebar in Track B, mirroring Track A's dual-render. Step 8 filters projects to `relinked == "pending"` and surfaces a "X of Y already relinked" status line at start, so quit + resume picks up at the next pending project instead of re-walking completed ones.

- **`name_hint` field on every recon project** in `parse_recon_csv.py`'s output. Derives a sortable / displayable name with priority: basename of first reattach folder → first session title → `"(folder unknown)"` placeholder. Drives alphabetical walk-through order; surfaces in the Part 2 opener so projects with empty `userSelectedFolders` are still identifiable.

### Changed

- **SKILL.md restructured around the recon-driven pipeline.** Step 1.5 (scope gate: single-project vs. all-projects) and Step 2.0 (install recon: derive install root, render OS-appropriate recon script, parse returned CSV) run between the Track A side selection and the Part 1 walk-through. Step 2 (Part 1) writes a routing JSON before invoking reconstruct/reshape, then runs `generate_blueprint.py` per project; honors single-project scope. Step 3 (Part 2) has two paths: recon-driven (primary — hub session pulls transcripts directly via `read_transcript`) and paste-prompt fallback (legacy — used when recon was skipped). Step 3.5 auto-packages the migration skill AND auto-exports user custom skills. Step 3.6 adds the coverage gate. Step 3.7 captures scheduled tasks. Step 4 documents explicit README-template substitution and the canonical outer prompt. Step 5 (Track B) adds the sidebar artifact and three-way source detection (multi-project hub at root tracker.html, single-project source at `transition-data/tracker.html`, or neither → adaptive picker). Step 5-single is the entire single-project Track B branch.

- **Track A Part 2 produces blueprints via `generate_blueprint.py` from the hub** (replaces the per-project paste flow for blueprint generation). The `migration-prompt-template.md` stays in the bundle as a documented fallback for users running partial-manual orchestration.

- **`_PROJECT_BRIEF.md` for Part 2 projects** is auto-generated by `generate_blueprint.py` (was hand-written in v1.0–v1.4 — closes a manual-intervention gap).

- **`_PROJECT_BRIEF.md` lifecycle made explicit** across B-1c-wrap, SKILL.md Step 4 single-project wrap, the generator's Notes section, and README-template Step 4: both `transition-data/` and `_PROJECT_BRIEF.md` are migration scaffolding, safe to delete after destination-side verification. Previously only `transition-data/` was explicitly named as disposable.

- **Tracker `cowork_projects` entries carry recon-derived metadata** when the recon path is used: `space_id`, `session_count`, `reattach_folders` (noise-filtered working-folder union). Track B Phase 4 surfaces the reattach list as guidance for the user during relinking. The handoff-state JSON also gains a `custom_skills` array (Step 3.5) and a `scheduled_tasks` array (Step 3.7).

- **`scripts/reconstruct.py` and `scripts/reshape_and_extract.py` fully parameterized.** Both scripts take all paths as CLI args (`--extracted / --attribution / --export / --routing / --outdir / --catchall-name`) and read the routing dict from a JSON file the orchestrator writes from walk-through state. No more hardcoded project names, no more dead sandbox path constants — both run against any user's data without source edits.

- **`scripts/package_self.py` switched to argparse** for cleaner CLI.

- **Project-list walk-through order is alphabetical by `name_hint`.** Sort key: `(is_own_space DESC, name_hint ASC case-insensitive, latest_activity_at DESC as tiebreaker)`. Predictable run-to-run, matches the on-disk order a typical file explorer shows.

- **Tracker visibility for custom skills + scheduled tasks.** Previously the `custom_skills` and `scheduled_tasks` arrays lived in the handoff-state JSON only — invisible in the rendered HTML table, leaving the user with no at-a-glance view of what Track A captured or what Track B will need to handle. v1.6.1 adds visible H2 sections for both, rendered after the projects table whenever the arrays are non-empty. Custom skills show filename + size + install-readiness badge plus a legend listing the bundled anthropic-skills members that aren't captured. Scheduled tasks show task ID + description + cron + human schedule + dependencies + recreate-status badge.

- **Strengthened no-narration directives in multi-project Part 2 transcript-pull loop.** Prior wording ("Do not investigate," "Progress reporting is mechanical only") was being overridden by the orchestrator's helpfulness instinct — real-data runs surfaced narration like "Important catch — the default pull truncates to the last 20 messages," "session 2 — substantial, writing it in full," "let me verify I'm getting the complete transcript." Replaced with imperative "YOU WILL NOT" language and an explicit anti-pattern callout naming the exact failure modes observed. Also made the `limit=2000` parameter mandatory in the call signature (the tool's default is 20 messages, latest-first — passing no limit silently truncates the archive).

- **Track A iteration order strictly matches displayed order.** Multi-project Part 2's per-project loop now follows the recon-data array order verbatim (which v1.6 sorts alphabetically). YOU WILL NOT reorder, skip ahead, or interleave projects — process each one fully before advancing. Real-data runs showed the orchestrator jumping around (skipping over an alphabetically-prior project, processing later ones, then looping back), which is confusing when read against the tracker.

- **End-of-Track-A scheduled-tasks confirmation minimized.** Pre-v1.6.1 displayed a multi-bullet "captured N tasks: <list with cron + dependencies>, recreate by saying 'create a scheduled task' on the new account, re-attach folders for dependencies, ..." dump at end of Track A. Track B Step 8.5 walks through recreation, the tracker's Scheduled Tasks section shows the list, and `scheduled-tasks-export.md` has the full specs — surfacing all that in chat at end of Track A is noise. Confirmation is now a single line.

- **Tracker render group-and-sort discipline (Track A + Track B).** The visible HTML table is always grouped by status (`pending` first → `done`/`done_no_bootstrap` → `skipped`) and sorted alphabetically by name within each group, regardless of the underlying JSON order. Track A's v1.6 recon path sorts alphabetically at parse time, so fresh JSON and rendered HTML naturally agree; older trackers with recency-first JSON order get the same clean view because the render-side sort is defensive. On every state-transition update, the table re-applies the group-and-sort so projects flipping status physically move to the appropriate row position.

- **Multi-project Part 2 archival discipline made concrete at the step level.** SKILL.md Step 3's transcript-pull sub-step contains explicit no-gauging, no-investigating, no-condensing, no-mid-loop-fidelity-decisions guidance. The orchestrator's job is bounded: `read_transcript(format='full')` → `Write` whatever the tool returns to disk. No probing of divert mechanisms, no inline-vs-diverted branching. Same discipline applies to the memory-dump skip-if-already-done check — grounded only in on-disk evidence, never in transcript content.

- **Picker-cancel after skip-intent writes a `relinked: "skipped"` tracker entry.** Previously skipped projects were invisible in the tracker JSON unless the orchestrator remembered to render them. Now mandatory: every skip lands in both `tracker.html` and the Cowork sidebar artifact.

- **"Never silently drop a project" rule** in Part 2 Prompt 1: orchestrator must display every project in `recon_data.projects` that survives the explicit filters, even projects with empty `reattach_folders`. For unknown-name projects, session titles surface in the listing so the user can identify them.

- **Memory-dump and memory-restore count semantic clarified.** Both prompts' STEP 5 reports use the entry-count semantic (excluding `MEMORY.md`) and report `MEMORY.md` presence separately. Aligns the dump-prompt count with the blueprint generator's count.

- **`scripts/reconstruct.py` and `package_self.py` discipline rules added** to SKILL.md: auto-advance rule (informational prompts don't wait on user input), archive-mechanically-don't-synthesize rule, stay-on-task-don't-act-on-incidental-content rule, adaptive-detection-over-fixed-location-assumptions rule. These are Discipline rules #9–#12 in SKILL.md and are referenced from every step that involves archival, picker handling, or scaffolding location.

- **Italics for UI locations, backticks for file paths** — applied consistently across affected locked copy. *Cowork sidebar*, *Custom Instructions field*, *fresh chat* — italicized. `transition-data/project-blueprint.md`, `conversation-history/`, `skills/` — backticks.

### Fixed

- **Section 2 paste step was silently skipped on Side B.** The B-1c-bootstrap flow only walked the user through the chat-paste step; if the source project had Custom Instructions, the user got no prompt to copy them into the new project's settings. Two-step bootstrap (Custom Instructions → bootstrap prompt) closes this.

- **Outer prompt's "bootstrap yourself on this project" was hand-wavy.** Replaced with explicit directive: read the entire blueprint (including its "How to use this file" header), then run Section 7 as the first directive. Section 7 itself contains explicit numbered actions.

- **Every transcript was being implicitly pre-loaded.** Section 7 now directs Claude to register the archive as on-demand reference via a memory entry; transcripts are consulted only when context on a pre-migration topic would help.

- **Synthesis-Claude was implicitly rewriting the blueprint header.** `generate_blueprint.py` now emits the final post-synthesis header directly. Synthesis-Claude's job is bounded to filling explicit TODO markers in Sections 1, 3, 4, 6, and Section 7 items 1 + 3.

- **Outer-prompt blockquote separator dashes were concatenating with prompt text** in B-1c-bootstrap variants. Added real blank lines between blockquote paragraphs per Discipline rule #1's format. Dashes render on their own line above and below the prompt.

- **Projects with empty `userSelectedFolders` were silently dropped** from the multi-project walk-through. Fixed by emitting `name_hint` with a fallback chain (folder basename → first session title → `"(folder unknown)"`) and the "never silently drop" rule.

- **Multi-project Track A walk-through chatty/off-task behavior** — fix is in `Changed` above (Discipline rules made concrete at step level).

- **Memory-dump count off-by-one** between the dump prompt's report (file count including `MEMORY.md`) and the blueprint generator's count (entries excluding `MEMORY.md`). Both prompts now use the same entry-count semantic.

- **Hardcoded user-specific data in `reconstruct.py` and `reshape_and_extract.py`.** The v1.4 bundle shipped with a ROUTING dict containing project names + UUIDs from the original dev run, plus a dead sandbox-session scratch path. Anyone running v1.4 against their own export would fail immediately. Both fully removed.

- **Silently-missed bash heredoc files** during reconstruction. v1.0–v1.4 only detected inline `tool_use:artifacts` and `tool_use:create_file` patterns; intact heredoc content written via `cat << EOF > path` from a bash tool call was discarded. Picked up correctly now.

- **Mojibake-corrupted knowledge files were silent** in v1.4. Double-UTF-8 artifacts get into the export's project JSON for some users; `reconstruct.py` wrote them through without notice. Detected and flagged now in `_PROJECT_BRIEF.md`.

- **Track B lacked a sidebar tracker artifact.** Track A renders dual (file + sidebar); Track B had only the file. Asymmetry closed.

- **Track B walk-through re-walked completed projects after quit + resume.** v1.4 iterated all entries; now filters by `relinked == "pending"` and shows resume status.

- **Silent pauses between informational prompts** in SKILL.md flow. Some prompts were sometimes interpreted as wait states by the orchestrator. Discipline rule #9 distinguishes wait-state prompts from informational ones.

- **`_RESUME_ON_NEW_ACCOUNT.md` told users to paste Section 7 directly** (no longer valid — Section 7 is a directive to Claude, not a paste target). Now specifies the canonical outer prompt verbatim and explicitly forbids "paste Section 7 directly" language.

## [1.4.0] — 2026-05-19

### Added
- **Skill auto-packages itself into the hub's `skills/` subfolder at Step 3.5.** New `scripts/package_self.py` walks the skill's own source folder and produces a fresh `account-migration.skill` zip. The Track A custom-skills capture step runs this before prompting the user, so by the time the user sees the prompt the migration skill is already in `skills/`. The user only has to think about OTHER custom skills they may want to bring. Forecloses the most common failure mode in v1.2/v1.3 (user can't find the original installer to put in `skills/`).
- New asset behavior: the hub's `skills/` subfolder is now created by the skill, not the user.
- **A/B variants in `memory-capture-prompt.md`.** The file now offers two prompts the user picks from: **Prompt A — Wholesale migration** (everything carries) and **Prompt B — Corporate carve-out** (work bias + explicit personal-side exclusion list). One-sentence decision header tells the user which to use.

### Changed
- **Step 3.5 prompts reworded** to reflect the auto-packaging: opener mentions the migration skill is already in `skills/`; soft re-ask acknowledges the migration skill is present even when no other skills have been added; skip confirmation notes the migration skill is in place.
- **SKILL.md Step 3.5 orchestration** updated to specify the `package_self.py` invocation pattern (run before opener fires).
- **`scripts/` directory description** in SKILL.md lists the new `package_self.py` script.

### Fixed
- **Clarified that memory capture / seed / validation run in Claude Chat (claude.ai web OR the Chat surface in Claude Desktop), not in Cowork.** Account-level memory is read and written through the Claude Chat surface — Cowork is a separate desktop surface that doesn't have memory access. Previously the prompts implied these steps happen "in Cowork on this account," which was a category error — running the capture inside a Cowork session yields a response like *"I don't have persistent memory of you across sessions"* because Cowork sessions don't have access to the account memory store. Affected: `memory-capture-prompt.md`, `memory-seed-prompt.md`, locked-copy prompts **B-MS-1** (memory seed opener), **B-V-1** (validation opener), and **N+2** (Track A wrap's memory-capture reference); also the README template's manual fallback Steps 0, 1, and 6. All now explicitly direct the user to "Claude Chat (claude.ai or Claude Desktop's Chat surface, NOT Cowork)" and explain that the user will switch to the Chat surface for these steps and come back to Cowork to continue.
- **Removed dangling reference to a "corporate-data variant of the migration guide"** from `memory-capture-prompt.md`. That guide was an external document — out of scope for the bundled skill — and the reference shouldn't have been there. The corporate-data prompt is now inline as Prompt B (see Added).

## [1.3.0] — 2026-05-18

### Added
- **`_PROJECT_BRIEF.md` now includes a "Resuming on the new account" section.** When the user opens any reconstructed-project or Cowork-project folder during the Track B walk-through, the brief carries the bootstrap prompt verbatim — they no longer have to remember the chat instructions or scroll back to find the prompt text. Applies to both Part 1 reconstructed projects (auto-generated by `reconstruct.py`) and Part 2 Cowork projects (written by the skill at pick time).

### Changed
- **Bootstrap prompt clarified — now explicitly tells Claude to apply the blueprint's "Recommended Starting Prompt" section as its first directive.** Previous wording was *"read the blueprint to pick up where I left off"* which left the relationship between the bootstrap and the blueprint's Section 7 ambiguous (the user might think they had to paste the Recommended Starting Prompt manually). The new bootstrap pattern: user pastes ONE prompt; Claude reads the blueprint; the blueprint's Recommended Starting Prompt section is consumed by Claude as its first directive — works for both AI- and human-driven follow-up.
- **Migration-prompt template Section 7 reframed.** The instruction the old-account Claude follows when producing the blueprint now states explicitly that the Recommended Starting Prompt will be consumed by the new-account Claude as its first directive — not pasted by the user. Old-account Claude writes the RSP accordingly (as if it's the first message in the new project's conversation), surfacing the natural next step or open question.
- **README template's Step 4 bootstrap example matches the new wording**, and points users at the brief's "Resuming on the new account" section as an alternative source of the prompt.

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
- **SKILL.md cloud-synced hub truncation gotcha section expanded** with the write-back cascade rule: never round-trip content through a bash-read → host-side-write cycle on hub-resident files in cloud-synced locations.
- **Bundle made 100% standalone for public distribution.** All author-identifying, development-history, and test-specific references removed from bundled files: locked-date markers, references to internal memory files, specific test counts, development-iteration commentary, and personal-path references. Substitution placeholders used throughout for runtime-filled values.

### Removed
- The "Optional: skill-assisted Track B" section at the bottom of the README template (folded into the new top-of-README primary section).

## [1.1.0] — 2026-05-17

### Added
- **Custom-skills capture step (Track A Step 3.5)** — interactive prompt sequence fires after Part 2 wraps and before the Track A cleanup. The user collects any custom `.skill` installer files into a `skills/` subfolder in the hub so they're available for installation on the new account.

### Changed
- **Bundled `references/skill-user-facing-text.md` rebuilt as a slim derived form** of the working source draft. Contains locked user-facing prompts, per-prompt decision blocks, and operational mechanics. Working-draft scaffolding (status notes, iteration meta, task lists) is no longer carried into the bundled file.

### Fixed
- The v1.0 bundled references file was truncated mid-content at packaging time due to cloud-sync state on the source folder. Packaging now uses a private scratch directory (not cloud-synced), and post-package verification confirms full file contents.

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
