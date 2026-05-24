# Skill user-facing text — locked copy

This file is the canonical source for every user-facing prompt the
`account-migration` skill displays. When `SKILL.md` says "display
Prompt N," find Prompt N in this file and display the fenced block
verbatim. Wording is deliberate — do not paraphrase, do not embellish.

Each prompt is followed by a short "decisions" block explaining why
the wording is what it is. The skill does not display the decisions
blocks — they're operational context so future iterations don't undo
a deliberate choice.

Substitution markers appear in `<…>` brackets. The skill fills these
in at runtime from tracker state, manifest counts, or user-provided
names. Never display a prompt with unfilled markers.

---

# Track A — source-account preparation

## Prompt 0 — skill opener + Track A/B branch

Fires when the skill is invoked. The same skill drives both Track A
(source account preparation, Parts 1 and 2) and Track B (destination
account relink, Part 3), so the first thing the user does is tell the
skill which side they're on. On "old" the skill displays the Part 1
banner and proceeds to Prompt 1. On "new" the skill displays the Part 3
banner and proceeds to the Track B opener.

### ▶ Skill speaking ◀

> ═══[ Transitioning between 2 Claude Accounts ]═══

> This will be handled in 3 phases. The first two are performed in your
> old account and the third in your new account.

> There is no way to directly import conversations into the new account.
> The compromise is to extract the conversation history into individual
> files which are stored within a new Cowork Project. This archive
> project can then be searched and pruned as necessary.

> This skill will walk you through the necessary steps and allow you to
> make decisions about what data should be migrated.

> Which side are you starting from?

> - Say **old** — preparing your old account for transfer (Parts 1 and 2).
> - Say **new** — picking up on your new account to relink everything
>   that was prepared on the old side (Part 3).


### Prompt 0 decisions

- **"old" / "new" as keywords.** Short, unambiguous, hard to mistype.
  Avoids "Track A" / "Track B" jargon at the very first interaction.
- **No "quit" here.** If the user opened the skill by mistake, they can
  just close the chat. Quit appears later in the per-project picks.
- **Routes the Part banner.** "old" → Part 1 banner + Prompt 1.
  "new" → Part 3 banner + Track B opener.
- **No partial-flow handling at Prompt 0.** A user who started Track A
  on the old account and then re-invokes the skill on the new account
  picks "new"; the tracker carries cross-account state via the embedded
  handoff-state JSON in `tracker.html`.

---

# Track A scope + install recon (between Prompt 0 and Part 1)

Two short steps run between the Track A side-selection and the Part 1
banner: ask whether the user is migrating their whole account or just
one project this run, and do a one-time install recon that tells us
which Cowork sessions belong to which project.

## Scope-selection prompt

Fires after the user says "old" at Prompt 0, BEFORE the Part 1 banner.

### ▶ Skill speaking ◀

> Before I dig in — are you migrating your whole account this run, or
> just one specific project?

>   - **all**   — every web/chat project + every Cowork project.
>   - **one**   — a single named project. I'll skip everything else.
>   - **quit**  — close the skill.

> Most people pick **all** the first time and **one** for follow-up runs
> (re-migrating a single project after a fix, validating a specific
> project on the new account, etc.).


## Single-project-name prompt

Fires only if the user picks "one" at the scope-selection prompt.

### ▶ Skill speaking ◀

> Which project? Type the name as you remember it on the old account
> (case doesn't matter; I'll match by substring). Examples:

>   - "Newsletter"
>   - "Q3 planning"
>   - "the script library"

> I'll look for it on both the web/chat side and the Cowork side. If I
> find it in only one place, that's fine — projects often live on just
> one side. If I can't find it at all, I'll show you what I did see so
> you can spot a typo.


## Single-project no-match prompt

Fires only if `scope_target` matched zero candidates on BOTH sides
after the install recon completes.

### ▶ Skill speaking ◀

> I couldn't find a project matching "<scope_target>" on either side.
> Here's what I did find:

>   Web/chat projects (from your export):
>     - <name 1>
>     - <name 2>
>     - …

>   Cowork projects (from the session recon):
>     - <name 1>  (<N> sessions)
>     - <name 2>  (<N> sessions)
>     - …

> Three options:

>   - **pick** + a name from the lists above — I'll re-scope to that one.
>   - **retry** — type a different name from scratch.
>   - **quit** — close the skill.


## Install recon — explainer

Fires after the scope choice (one or all) and before the Part 1 banner.

### ▶ Skill speaking ◀

> One quick setup step. To know which Cowork sessions belong to which
> project, I need a small piece of data that lives outside the sandbox I
> run in — the per-session JSON files on your disk. I can't read those
> from in here, but you can read them in a native shell and hand the
> result back as a CSV.

> I've put a small script next to this chat — it walks the session
> files and writes a CSV with the bare metadata I need (session id,
> project id, title, dates, working folders attached). Nothing
> sensitive: no message content, no system prompts, no answers to
> setup questions.

> Save the script wherever you want on your machine. Run it in a normal
> shell (PowerShell on Windows, Terminal on Mac — no admin needed). It
> writes the CSV next to itself. Drop the CSV into this project's folder
> when it's done.

> Say **ready** once the CSV is in the folder. Or **skip** if you'd rather
> not run it (I'll fall back to a slower, manual path for each Cowork
> project). Or **quit** to close out.


## Install recon — recon-summary

Fires after the user says "ready" and the CSV parses cleanly.

### ▶ Skill speaking ◀

> Got it. The recon turned up:

>   - <N_projects> projects with attributed sessions
>   - <N_sessions> sessions total
>   - <N_blank> sessions without a project (most are utility/background
>     runs — I'll set those aside)
>   - <N_folders> working folders identified across all projects

>   <if migration_scope == "single">
>   Matched your scope target ("<scope_target>") to:
>     - <N_part1_matches> web/chat project(s)
>     - <N_part2_matches> Cowork project(s)
>   </if>

> Heading into Part 1 next.


---

# Part 1 — preparing claude.ai web/chat projects (source account)

## Prompt 1 — "give me your two input files"

Fires after the user says "old" at Prompt 0, preceded by the Part 1
banner.

### ▶ Skill speaking ◀

> Project migration — Track A (Reconstruct)

> Hi. I'll take the projects and conversations from your old Claude
> account, rebuild them as complete folders on disk, and hand them off
> to your new account.

> Before I start, I need two files. Both go into this project's folder.

> File 1 of 2 — your data export

> On claude.ai (the account you're migrating from):

> 1. Click your avatar → Settings → Privacy.
> 2. Click Export data. Anthropic emails you a download link, usually
>    within a few minutes (occasionally longer).
> 3. Download the zip. It'll be named like
>    `data-YYYY-MM-DD-…-batch-0000.zip`.
> 4. Move it into this project's folder. If your browser saved it
>    straight to `Downloads\`, drag it over.

> Heads up: if your export produced multiple batch files (rare, only for
> very large accounts), bring all of them.

> File 2 of 2 — a saved copy of your Chats page

> The export has every conversation but doesn't say which project each
> one belongs to. I'll recover that from a saved copy of your chats list.

> 1. On claude.ai, click Chats in the left sidebar.
> 2. Scroll all the way to the bottom of the list. The page only loads
>    older chats as you scroll — if you don't reach the bottom, those
>    chats won't be in the saved file. Stop scrolling when nothing new
>    appears.
> 3. File → Save Page As → choose "Webpage, Complete".
>      - Safari users: don't pick "Web Archive" — that's a binary
>        format I can't read. Choose "Page Source" instead.
> 4. The default filename is `claude.html`. Rename it (anything works —
>    `chats.html`, `AllChats.html`, whatever) before saving.
> 5. Save it into this project's folder. The save will also produce
>    a same-named `_files\` folder next to it — leave that alongside,
>    I won't use it but it's harmless.

> Ready check

> Say **ready** once both files are in the folder. I'll list what I found
> before I start extracting, so you can confirm I'm working from the
> right inputs.


### Prompt 1 decisions

- **Sidebar item is "Chats"** (not "All Chats"). Internal code names
  like `AllChats` / `parse_allchats.py` are not user-facing.
- **What the user sees on the Chats page:** the word "Chats", a search
  bar, then a flat list of chats each with a date. Do NOT describe the
  3-column table — that's the parser's view of the rendered HTML, not
  what the user sees in the browser.
- **File location is this project's folder, no alternatives.** No
  picker fallback, no chat-attachment alternative. Browser-default
  Downloads users will copy files into the folder manually. End-of-Track-A
  cleanup assumes files live here.
- **Drop the "Projects index vs Chats" warning.** Step 1 already says
  "click **Chats** in the sidebar"; if the user saves the wrong page,
  the parser detects zero `/chat/` links and surfaces the error at
  parse time.
- **Keep "scroll until nothing new appears"** as the bottom-of-list cue
  for the lazy-loaded chats list.
- **Keep the rename-from-`claude.html` instruction.** Avoids collisions
  with any future per-project page-save fallbacks.

## Prompt 2 — inventory + run

After user says "ready", skill displays inventory and proceeds without
an additional gate.

### ▶ Skill speaking ◀

> Got it. In the folder I see:

>   • Export: `<export_filename>` (<export_size>)
>   • Chats save: `<chats_filename>` (<chats_size>)

> Both look right. Unpacking the export and parsing the Chats save now.

> This is pure file-sorting and organization as I split them into individual
> files and build an index. Boring work and takes about half a minute. Hang
> tight.


### Prompt 2 decisions

- File sizes shown, no timestamps (size catches zero-byte / wrong-file
  problems; timestamp is noise).
- **No privacy reassurance line.** Don't preemptively defend against
  unraised concerns — it draws attention to the thing it's trying to
  dispel.
- No explicit "proceed?" gate — user just said "ready", gating again is
  pointless friction.
- "Hang tight" rather than "starting now" — friendlier, sets expectation
  for the half-minute pause.

### Prompt 2 edge-case branches (separate from happy path)

These are NOT Prompt 2 itself; they replace it when conditions don't hold.

- **No export zip found** → "I don't see an export yet — finish step 4 of
  the previous instructions and say 'ready' again."
- **Multiple zips (multi-batch export)** → list all, treat as one bundle.
- **`.webarchive` file present** → catch early: "Safari saved that as a
  binary archive I can't read; please re-save as 'Page Source' and replace
  it."
- **No html found** → "I don't see a saved Chats page yet — finish steps
  1–5 and say 'ready'."
- **Multiple html files** → parser content-detects automatically; no
  user-facing surprise unless none parse.

## Prompt 2.5 — post-run headline

Single message after the scripts finish; no artificial "building tracker"
filler — tracker reveal is a separate prompt immediately after.

### ▶ Skill speaking ◀

> All set! Let me show you what I've found.

> - ✓ <N_total> conversations across <N_projects> projects in your export.
> - ✓ <N_attributed> are attributed to specific projects → we'll walk through these one at a time.
> - ✓ <N_orphans> are loose chats with no project assignment.
> - ✓ <N_dropped> were deleted from claude.ai → dropped.


### Prompt 2.5 decisions

- Bullets with `- ✓` (plain checkmark, not emoji). Scans quickly; the
  three-bucket rule is visible at a glance.
- Plain ✓ over ✅ — less celebratory next to the "dropped" line.
- Conditional rendering: the **deleted** line is omitted when the count
  is 0 (most users will have nothing to drop).
- **Project count filters "How to use Claude"** (built-in starter) silently
  from all user-facing counts.
- **Orphan line is neutral** — doesn't yet name the catch-all (the
  user hasn't created it yet). Their destination is explained in
  Prompt 3.
- No "building tracker now" sign-off. Tracker construction is near-instant
  (templated from `attribution_map.csv` we just built); a fake pause line
  would be dishonest.

## Prompt 3 — tracker reveal + catch-all setup

**Catch-all is the first interactive step.** Its name needs to appear on
the tracker and in per-project prompts before the walk-through fires.
Tracker is rendered as a Cowork sidebar artifact + `tracker.html` in the
hub folder (dual rendering); user-facing copy mentions only the artifact.

### ▶ Skill speaking ◀

> I've opened your tracker.

> First step: set up the catch-all. This will be a Cowork project that
> collects any conversations without a clear home — both orphan chats
> with no project assignment, and conversations from projects you choose
> not to reconstruct.

> You'll need to create this project yourself, because Claude can't create
> Cowork projects. In Cowork:

> 1. Start a new project → Start from scratch.
> 2. Name it Migrated Conversation History (suggestion — use any
>    name you'd like; whatever you choose will appear on the tracker and
>    in the prompts that follow).
> 3. Come back to this chat to continue.

> Say **ready** when the project is created. Once you do, I'll bring
> up a folder picker so you can select the project folder you just
> created.


### Prompt 3 decisions

- **Tracker = artifact, not "open in browser".** File-on-disk exists for
  cross-account handoff; sidebar artifact is the UX surface.
- **Catch-all setup is the first interactive step**, not the last.
- **Catch-all is a real Cowork project**, created from scratch by the
  user. Picking an orphan folder via `request_cowork_directory` alone
  would only register it as a working folder of the hub project, not
  a discoverable Cowork project on the user's project list. The skill
  cannot create Cowork projects — it must wait for the user.
- **"Migrated Conversation History"** is a suggestion, not a requirement.

## Prompt 3.5 — post-ready bridge

Fires immediately after the user says "ready" in Prompt 3, and immediately
before the skill calls `request_cowork_directory` (picker mode, no path).
The bridge tells the user what's about to happen so the picker UI isn't
abrupt. Same pattern repeats for every per-project pick.

### ▶ Skill speaking ◀

> Got it. Bringing up the folder picker now so you can select
> <catchall_name>'s folder.


## Prompt 4 — first per-project pick

Verbose form (full rules + per-project import instruction). Subsequent
prompts (Pattern 5–N) drop the verbose rules block.

### ▶ Skill speaking ◀

> Catch-all ready: <catchall_name> at
> `<catchall_folder_path>`.

> Heads up: the export contains both your active and archived chat
> projects. If you want to include any of the archived projects in this
> transition, you'll need to unarchive them first — otherwise you won't
> be able to import them.

> Now I'll walk through your <N_projects> projects in alphabetical order.
> For each one we'll do the same thing:

> 1. You'll import the project from claude.ai into a new Cowork project
>    on this account. In Cowork: **New project → Import project →
>    select the project from your chat list**. Cowork creates a local
>    folder for it.
> 2. Say **ready** once the import is done — or say **skip** to
>    route the project's conversations to the catch-all without
>    importing (good for projects you already know you don't want to
>    migrate), or **quit** to stop the migration entirely.
> 3. If you said **ready**, I'll ask pick, skip, or quit
>    again:
>    - pick — I'll have you select the newly-imported folder and
>      reconstruct the project's conversation history into it. If you
>      point me at an existing folder you've been working in instead,
>      I'll leave it alone and route conversations to <catchall_name>.
>    - skip — I won't reconstruct the project. Its conversations
>      still go to <catchall_name> for manual review.
>    - quit — stop the migration entirely. The tracker stays on
>      disk so you can resume later.

> --- Project 1 of <N_projects> ---

> <project_name> — <N_convs> conversations, <N_docs> knowledge docs.

> To include it: in Cowork, **New project → Import project → select
> "<project_name>" from your chat list, then say **ready** here.

> Or say **skip** (route to catch-all without importing) or **quit**
> (stop the migration).


### Prompt 4 decisions

- **Status line `--- Project N of M ---` at the top of the per-project
  block.** Recurring rhythm; user always knows where they are.
- **Walk-through uses the user-visible project count.** Built-in starter
  projects are filtered silently; the user doesn't need to know.
- **Rules as bulleted sentences, each on its own line.** Reads as a
  decision tree the user is walking through.
- **Skip and non-empty pick both route conversations to catch-all.**
  Mechanically identical; only the framing differs (non-empty = "I'm
  protecting your folder"; skip = "for manual review, just in case").
  Skip is "defer the decision", not "delete the content."
- **Catch-all referred to by its real name**, not as "the catch-all
  bucket." Concrete > abstract.
- **Quit option as a third response.** Three options: pick / skip / quit.
  Quit ends the whole skill cleanly; tracker stays on disk.
- **Archived-projects heads-up.** Archived projects need to be unarchived
  on claude.ai before Cowork's Import project flow will see them. The
  skill's job is to warn the user, not detect archived state.

## Prompt 4.5 — post-ready pick/skip

Fires immediately after the user says "ready" following the import step
in Prompt 4 or any Pattern 5–N prompt. Terse — the rules were already
laid out in Prompt 4's intro.

### ▶ Skill speaking ◀

> To continue, do you want to pick or skip this project?


### Prompt 4.5 decisions

- **No "Imported." prefix.** The skill shouldn't presume the user
  actually did the import — they may have said "ready" without
  importing, or there may have been a misclick. Stay neutral and let
  the picker step surface any inconsistency.
- **No "quit" option here.** Quit is already on the import-step prompt.
  Re-offering it after "ready" would be friction. The user who's
  reached Prompt 4.5 has signalled they want to proceed with this
  project — pick or skip is the right remaining choice.

## Cancel handling — picker-cancelled re-ask

Fires when `request_cowork_directory` returns "Directory selection was
cancelled by the user" after the user said "pick". Never silently
fall through to skip — re-ask.

### ▶ Skill speaking ◀

> Picker was cancelled — that might've been a mistake.

> pick to re-open the folder picker, skip to route this project's
> conversations to <catchall_name>, or quit to stop the migration
> entirely.


## Post-pick folder-picker bridge

Fires immediately after the user says "pick" in any Prompt 4–N, and
immediately before the skill calls `request_cowork_directory` (picker
mode, no path). Parallel to Prompt 3.5 for the catch-all. Folder access
is always the picker — never guess a path, never ask the user to type
one.

### ▶ Skill speaking ◀

> Bringing up the folder picker so you can select <project_name>'s folder.


If the user said "skip", this bridge does NOT fire — skip goes straight
to the post-pick confirmation line.

## Post-pick confirmation lines

Brief — these likely scroll past as the next per-project prompt loads,
so they're acknowledgment, not detail. One of three depending on what
the user did:

### ▶ Skill speaking ◀

> <project_name> picked (empty folder). Project will be reconstructed.

> <project_name> picked (existing folder). Conversations will be stored in <catchall_name>.

> <project_name> project skipped. Its conversations will be stored in <catchall_name> for your final review.


Then the next per-project prompt fires immediately.

## Pattern — Prompts 5 through N: subsequent per-project picks

Same structure as Prompt 4's per-project block, minus the catch-all
confirmation and the verbose walk-through-intro + rules. Each subsequent
prompt is:

### ▶ Skill speaking ◀

> --- Project N of <N_projects> ---

> <project_name> — <N_convs> conversations, <N_docs> knowledge docs.

> To include it: in Cowork, **New project → Import project → select
> "<project_name>" from your chat list, then say **ready** here.

> Or say **skip** (route to catch-all without importing) or **quit**
> (stop the migration).


User responses at this prompt:
- **"ready"** → Prompt 4.5 fires
- **"skip"** → straight to the post-pick "project skipped" confirmation line; next project's prompt fires
- **"quit"** → end the skill cleanly

The cancel-handling re-ask applies to every per-project pick (only after
the user has reached the picker via "pick" at Prompt 4.5).

## Prompt N+1.5 — Part 1 boundary wrap

Fires after the last per-project pick/skip in Part 1, unless every
project was skipped (in which case the all-skip soft-confirm fires
instead). Reconstruction happens inline as each pick is made — by the
time this wrap fires the folders are already populated. Marks the
boundary between Part 1 and Part 2; the Part 2 banner fires immediately
after this wrap.

~~~
▶ Part 1 complete ◀

All <N_projects> web/chat projects handled. Here's what's now on disk:

Reconstructed into your newly-imported Cowork folders (<N_reconstructed>):
  • <project_name> — <N_convs> conversations + <N_docs> knowledge docs
  • …

Routed to **<catchall_name>** (<N_routed>):
  • <project_name> — existing folder picked, your folder
    left untouched, <N_convs> conversations placed in
    <catchall_name>/<project_name>/
  • <project_name> — skipped, <N_convs> conversations placed in
    <catchall_name>/<project_name>/
  • …

<catchall_name> also contains your <N_unattributed>
unattributed conversations under `unattributed-conversations/`.

Each project folder has a `_PROJECT_BRIEF.md` summarizing what's in it
and where it came from. Where a conversation produced inline artifacts
(code, scripts, markdown), they're in `<conv-slug>/artifacts/` next to
its transcript. Each project also has a
`transition-data/project-blueprint.md` — a synthesized narrative
summary you'll use when recreating the project on your new account.

⚠ <N_recover> binary files (.docx, .xlsx, etc.) Claude generated during
your conversations are referenced in transcripts but **not in your
export**. They're listed in
`<catchall_name>/_ARTIFACTS_TO_RECOVER.md` — open it now and recover
them from claude.ai before your old account is deleted.

Up next: Part 2 — your existing Cowork projects on this machine that
aren't on claude.ai.
~~~

### Prompt N+1.5 decisions

- **Two-bucket summary**, not three. "Reconstructed in place" and
  "routed to catch-all" are the two outcomes; non-empty pick and skip
  both feed the second bucket but are differentiated in the per-project
  bullet so the user remembers which kind of decision they made.
- **Concrete numbers per project.** Conversation counts + knowledge
  doc counts per reconstructed project. Same for catch-all subfolders.
- **Inline reconstruction, not deferred.** Reconstruction fires immediately
  after each pick/skip is confirmed, so by the time the Part 1 wrap
  displays the folders are populated. Rationale: the user wants to
  verify results as they go, decisions are already captured at pick
  time, and if the session crashes mid-walk-through, inline work is
  preserved.
- **No cleanup here.** End-of-Track-A cleanup fires only after Part 2.
- **"Up next" line transitions to Part 2.** Production skill displays
  the Part 2 banner immediately after this wrap.

### Per-pick inline reconstruction (operational reference)

For every "pick" or "skip" the user makes in the walk-through, the
skill performs the file work *immediately* after the post-pick
confirmation, before displaying the next per-project prompt:

- **Empty pick** → write `_PROJECT_BRIEF.md`, `knowledge/` (from the
  export's project JSON), and `conversation-history/` (with INDEX.md +
  attributed transcripts) into the picked folder. Where a transcript's
  conversation produced inline artifacts, write them to
  `conversation-history/<conv-slug>/artifacts/`.
- **Non-empty pick** → leave picked folder untouched. Write a per-project
  subfolder in the catch-all with the same layout as a reconstructed
  project (`_MIGRATION_NOTE.md` instead of `_PROJECT_BRIEF.md` at the
  subfolder root, then `conversation-history/INDEX.md` + transcripts +
  per-conv `<conv-slug>/artifacts/` for inline artifacts).
- **Skip** → same as non-empty pick on the catch-all side.

After the last project, the skill also writes:

- The catch-all's own `_PROJECT_BRIEF.md` (summarizing what's inside).
- `unattributed-conversations/` inside the catch-all with INDEX + the
  orphan transcripts + per-conv `<conv-slug>/artifacts/` where inline
  artifacts were produced. Do not filter orphans on message count —
  empty conversations still belong here; the user can prune later.
- **`_ARTIFACTS_TO_RECOVER.md`** at the catch-all root listing the
  binary files referenced in transcripts but not in the export.

### Artifact handling — three kinds the export captures differently

Conversations may produce three different kinds of "thing the assistant
made". The skill handles each differently:

1. **`tool_use: artifacts`** (Claude's web Artifacts panel; types like
   `text/markdown`, `application/vnd.ant.code`, `image/svg+xml`,
   `application/vnd.ant.react`, `application/vnd.ant.mermaid`,
   `text/html`). Content is inline in `tool_use.input.content`. **Extract**
   into per-conversation `<conv-slug>/artifacts/<title>.<ext>` using
   `type` (and `language` for code) to pick the extension.

2. **`tool_use: create_file`** (file written via Claude's web file tools;
   typically a build script that later runs via `bash_tool`). Content
   is inline in `tool_use.input.file_text`. **Extract** to
   `<conv-slug>/artifacts/<basename-of-path>` using the `path` field's
   basename, or a generated name if no path is set.

3. **`tool_use: present_files`** binary outputs (`.docx`, `.xlsx`,
   `.pdf`, `.pptx`, images, archives). Only the filepath is in the
   export, no binary content. **Not extractable** — list each unique
   `(conv, basename)` in `<catchall_name>/_ARTIFACTS_TO_RECOVER.md`
   with a `[ ]` checkbox, the source conversation, and instructions to
   recover from claude.ai before the old account is deleted.

The `_ARTIFACTS_TO_RECOVER.md` file is organized as:

- Reconstructed projects first (alphabetical), each listing the convs
  with recoverable binaries.
- Then catch-all per-project subfolders (alphabetical).
- Then orphans (`unattributed-conversations`).

For each conversation in the list, the transcript filename is shown so
the user can find it quickly. If multiple `present_files` calls referenced
the same file, the count is shown ("3× referenced") to signal iteration.

---

# Part 2 — preparing Cowork projects (source account)

Part 2 fires immediately after the Part 1 boundary wrap. Same selective-pick
philosophy as Part 1 with two key differences:

1. **There's no Import step** — the user's Cowork projects are already on
   disk. They hand each one over by picking its folder.
2. **Discovery is folder-by-folder, not catalogued up front.** Cowork's
   project list is walled off to skills (`request_cowork_directory`
   refuses paths inside it; no folder→web-uuid mapping). So the skill
   asks the user to pick folders in a loop until they cancel; on cancel
   it confirms whether they're done.

## Part 2 Prompt 1 (recon variant) — opener

Used when the install recon completed successfully in Step 2.0
(`recon_data` is populated). The skill already knows which Cowork
projects you have, how many sessions each one had, and which working
folders they pulled in. The opener lists them and asks for go-ahead.

### ▶ Skill speaking ◀

> Part 2 handles your existing Cowork projects on this machine. From
> the install recon, here are the Cowork projects I can see (excluding
> this migration hub itself):

>   <for each in-scope project, oldest activity first>
>   - <project name guess>
>       <N> sessions, last active <YYYY-MM-DD>
>       Working folder(s) attached: <first 1-2 folder paths, truncated
>                                    in the middle if long>
>   </for>

> What I'll do for each one, going down the list:

>   1. Bring up the folder picker so you can select the project's
>      working folder. I need access to write the transcripts and the
>      blueprint into it.
>   2. Pull each session's transcript directly from your local install
>      and write them into <project>/conversation-history/.
>   3. Ask you to paste a short prompt into a fresh Cowork conversation
>      in that project on the old account so its project memory gets
>      dumped (memory is per-project and I can't reach it from this
>      session).
>   4. Generate the project blueprint from everything that just landed.

> When you're ready, say **continue** and we'll start with the first
> project on the list. Say **skip** if you want to bypass Part 2
> entirely (no Cowork projects to migrate, or you'd rather handle them
> manually).

> continue or skip?


## Part 2 Prompt 1 (fallback variant) — opener

Used only when the install recon was skipped or failed in Step 2.0
(`recon_data` is `None`). This is the v1.4-era flow preserved verbatim
for users without native-shell access. Cowork's internal session
storage is walled off, so we can't discover projects automatically and
the user hands each one over by picking its folder.

### ▶ Skill speaking ◀

> Part 2 handles your existing Cowork projects on this machine — the
> ones you've been working in with Cowork on the desktop.

> Before we start, an important heads-up: since you skipped the install
> recon, three things per Cowork project will need a manual paste step
> to migrate:

> - Working-folder attachments (which other folders are linked to
>   each project). Open each Cowork project on your old account and note
>   these — you'll re-attach them on the new account.
> - Cowork session history (your past chats with Claude inside
>   Cowork on these projects). You'll paste a prompt in each project's
>   source-account Cowork session to dump them.
> - Project memory (`memory.md` if you've used Cowork sessions inside
>   the project). Same pattern — paste a prompt in the project's source-
>   account session.

> What this skill *does* preserve regardless: your working files stay
> exactly where they are, and I write a `_PROJECT_BRIEF.md` next to them
> describing what's there.

> I can't discover your Cowork projects automatically on this path, so
> I'll need you to hand each one over by picking its folder.

> When you're ready, say **continue** and I'll bring up a folder
> picker. Pick the folder for one Cowork project at a time. When you've
> handed me all of them, cancel the picker and I'll confirm you're done.

> If you don't have any Cowork projects you want to migrate, say
> **skip** and I'll go straight to the wrap-up.

> continue or skip?


## Part 2 — per-project header (recon variant)

Fires once per in-scope project at the top of each iteration in the
recon-driven path. Sets the user up to grant folder access for that
specific project.

### ▶ Skill speaking ◀

> Project <N> of <N_total>: <project name guess>

>   - <N_sessions> sessions
>   - First active <YYYY-MM-DD>, last active <YYYY-MM-DD>
>   - Working folder(s) seen attached to these sessions:
>       <folder path 1>
>       <folder path 2>
>       …

> I'll need access to this project's working folder to write the
> transcripts and the blueprint into it. Bringing up the folder picker —
> select the folder for <project name guess>.

> If this project isn't one you want to migrate, say **skip** to move
> to the next one. **quit** ends the skill cleanly (you can resume
> later from the tracker).


## Part 2 Prompt 1.5 — folder picker bridge

Fires after user says "continue" at Prompt 1, AND after the cancel-confirmation
re-loops the picker. Same wording either way.

### ▶ Skill speaking ◀

> Bringing up the folder picker. Pick the folder for one of your Cowork
> projects.


## Part 2 Prompt 2 — per-folder processing confirmation

Fires after each successful folder pick. Writes the brief, confirms,
reopens the picker. The simpler form reflects Part 2's degraded scope
(working files preserved + brief written; nothing else migrates per the
session-storage wall).

### ▶ Skill speaking ◀

> Got it: <folder_name>.

> I wrote `_PROJECT_BRIEF.md` next to your working files, plus
> `transition-data/migration-prompt.md` — a prompt for you to run in
> this project on your old-account Cowork before deletion (it produces
> the blueprint that becomes the bootstrap for your new-account version
> of this project). Your folder contents are untouched.

> Pick another Cowork project, or cancel when you're done.


The brief carries the full "what doesn't migrate" caveats so they're
preserved in writing alongside each project. The migration-prompt is
the user-side path to generating a `project-blueprint.md` for Part 2
projects, since the skill itself can't reach the Cowork session data.

## Part 2 cancel-confirmation

Fires when the user cancels the picker mid-loop.

### ▶ Skill speaking ◀

> Picker was cancelled. Are you done picking Cowork projects?

> Say **done** to wrap up Part 2, **continue** to bring the picker
> back up, or **quit** to stop the migration entirely.


## Part 2 wrap

Fires after "done" at the cancel-confirmation, or after "skip" at
Prompt 1.

### ▶ Skill speaking ◀

> ▶ Part 2 complete ◀

> <N_cowork> Cowork projects handled. Each one has a `_PROJECT_BRIEF.md`
> next to its working files plus a `transition-data/migration-prompt.md`
> with the prompt to run in that project's old-account Cowork session.
> Your folders' existing contents are unchanged.

> Reminder of what you'll need to do manually before deleting the old
> account:

> - Run each `transition-data/migration-prompt.md` in the matching
>   Cowork project on the old account. Save the response as
>   `transition-data/project-blueprint.md`.
> - Capture your global memory — see the Track A wrap (coming up
>   next) for the prompt to run.
> - Recover the binary files flagged in
>   `<catchall_name>/_ARTIFACTS_TO_RECOVER.md`.
> - Note each Cowork project's working-folder attachments — Cowork's
>   internal storage doesn't migrate, so re-attach manually on the new
>   account.

> Each project's `_PROJECT_BRIEF.md` has a per-project version of these
> reminders.


(If "skip" → the wrap omits the per-project summary and just says
*"Part 2 skipped — no Cowork projects to migrate."*)

### Part 2 decisions

- **"continue" / "skip" / "done" / "quit" as keywords.** Match Part 1's
  vocabulary so users don't have to learn a second set.
- **Picker cancel is overloaded** — in Part 1 it could be an accident;
  in Part 2 it's the *designated done-signal*. The cancel-confirmation
  prompt makes that explicit (done/continue/quit), so accidental cancels
  in Part 2 still get caught.
- **No "pick / skip" per folder.** The user already chose to give us
  this folder by picking it; the skill processes it. If they picked
  wrong, they can cancel and start over by `continue`-ing again.
- **Reconstruction inline.** Same rule as Part 1: every picked folder
  gets processed before the next picker fires.

---

# Custom-skills capture (end of Track A, before cleanup wrap)

Fires after the Part 2 wrap and before the Track A cleanup wrap. The
user gathers any custom `.skill` installer files into a `skills/`
subfolder in the hub so they can be re-installed on the new account.
Cowork's installed-skills location is generally walled off, so the
skill cannot extract installers automatically — the user has to source
them from where they originally got them. One prompt-and-wait cycle so
users can't skip past it accidentally.

## Custom-skills confirmation — auto-export complete

Fires after Step 3.5 sub-steps 1 + 2 have run (auto-packaged the migration
skill + auto-exported any other installed custom skills).

### ▶ Skill speaking ◀

> Custom Cowork skills — handled automatically.

> I packaged this migration skill into the hub's `skills/` subfolder, then
> repackaged every other custom skill installed on this account into the
> same folder. The bundled `anthropic-skills` plugin members (docx, pdf,
> pptx, schedule, etc.) are skipped — they re-install automatically with
> Cowork on the new account.

> What's in `skills/` now:

>   • `account-migration.skill` (<size>)
>   • `<other-custom-skill>.skill` (<size>)
>   • …

> Say **done** to lock this in, **hold** if you want to add another
> `.skill` file by hand (one I couldn't see — e.g., a skill you downloaded
> but never installed), or **quit** to stop the migration.


## Custom-skills add-by-hand soft re-ask

Fires on `hold` at the auto-export confirmation. User wants to drop a
`.skill` file into the hub's `skills/` folder that the auto-export missed.

### ▶ Skill speaking ◀

> Drop the additional `.skill` file(s) into `<HUB>/skills/` and say
> **ready**. I'll re-scan and update the listing.


## Custom-skills confirmation — files found

Fires after the user says "ready" and the skill detects one or more
`.skill` (or `.zip`) files in the hub's `skills/` subfolder.

### ▶ Skill speaking ◀

> Got it. In `skills/` I see:

>   • <filename>.skill (<size>)
>   • …

> The Track B handoff will point at these so you can re-install them on
> the new account.


## Custom-skills confirmation — empty folder or no folder

Fires when the user says "ready" but the `skills/` subfolder is empty
or doesn't exist. Soft re-ask, not an error.

### ▶ Skill speaking ◀

> I see `account-migration.skill` in `skills/` (I put that there) but no
> other custom skills yet — either you have no other custom skills to
> bring (in which case say **skip** and we'll move on with just the
> migration skill) or your copy hasn't landed yet (in which case drop
> them in and say **ready** again).


## Custom-skills confirmation — skip

Fires after the user says "skip". One line; the next prompt fires
immediately.

### ▶ Skill speaking ◀

> No other custom skills to migrate — moving on. (The migration skill
> itself is already saved in `skills/account-migration.skill` for the
> new-account install.)


### Custom-skills decisions

- **Skill auto-creates `skills/` and packages itself in.** Before
  displaying the opener, the skill runs `scripts/package_self.py`
  against its own source folder and writes a fresh `account-migration.skill`
  into `<hub>/skills/`. This forecloses the most common failure mode
  (user can't find the original installer for the migration skill
  itself). User responsibility is reduced to OTHER custom skills they
  may want to bring.
- **Separate prompt-and-wait**, not silent inspection. Prompts the
  user explicitly rather than guessing based on folder state. A silent
  check means most users would never know other custom skills *could*
  be migrated.
- **"ready" / "skip" / "quit" vocabulary**, matching Part 1 / Part 2.
- **Sized listing**, matching Prompt 2's inventory style. Catches the
  same zero-byte / truncated-file failure mode for the same reason.
- **Soft empty-folder re-ask** acknowledges the migration skill is
  already there even when no other skills have been added. Avoids the
  user thinking nothing has happened.
- **No content validation** of the `.skill` files themselves. They're
  zip archives, but the skill doesn't need to verify them at this
  stage — Cowork's install flow will validate at install time on the
  new account.


## Scheduled-tasks capture

Fires only in multi-project Track A (single-project skips). Captures
the user's Cowork scheduled tasks (cron-style recurring prompts) into a
self-contained export file at `<hub>/scheduled-tasks-export.md`.

### Scheduled-tasks opener

### ▶ Skill speaking ◀

> One more thing before the end-of-Track-A wrap — your scheduled tasks.

> Cowork's scheduled tasks (the cron-style recurring prompts you've set
> up via the `schedule` skill) don't carry across accounts automatically.
> I can list them and write a self-contained export file you can use to
> recreate each one on the new account.

> I'll list what's active, capture each task's cron expression and prompt
> verbatim into `scheduled-tasks-export.md` at the hub root, and note any
> tasks that depend on attached working folders or external Windows state
> (those need a little extra setup on the new account).

> No input needed — running now.


### Scheduled-tasks confirmation — tasks exported

Fires after the export file lands on disk. Keep this confirmation
MINIMAL — the captured tasks now appear in the tracker's Scheduled
Tasks section (rendered visibly in the HTML table) and Track B's
Step 8.5 walks through recreation on the new account. The user does
not need cron expressions, recreation instructions, or dependency
notes surfaced in chat at end of Track A — that's noise. The export
file and the tracker section have all of it.

### ▶ Skill speaking ◀

> Captured `<N>` scheduled task(s) to `scheduled-tasks-export.md`. See
> the tracker's Scheduled Tasks section for the list; Track B Step 8.5
> handles recreation on the new account.


### Scheduled-tasks confirmation — zero tasks

Fires when `mcp__scheduled-tasks__list_scheduled_tasks` returns nothing.

### ▶ Skill speaking ◀

> No scheduled tasks active on the old account. Nothing to export — moving on.


### Scheduled-tasks decisions

- **Multi-project only.** Single-project Track A skips this step. Scheduled
  tasks are account-level resources, not project-scoped; capturing them
  during a focused one-project transfer is out of scope.
- **No user input mid-step.** The step lists tasks via the MCP tool, reads
  each prompt's `SKILL.md` from disk, and writes the export file —
  mechanical end-to-end. The user sees a single "captured N tasks" line
  when it's done.
- **Verbatim prompts.** Each task's prompt body is captured verbatim from
  its `SKILL.md` — no editing, no summarizing, no analysis. Discipline
  rule #10 applies (the export IS the archive; the description IS the
  description).
- **Dependency annotation, not deep analysis.** The export's "Dependencies"
  bullet notes whether the prompt references mounted working folders or
  external Windows state (a true/false-style flag plus the names of any
  attached folders). It does NOT analyze what the task does or hypothesize
  whether the dependencies will still exist on the new account — that's
  the user's call when recreating.

---

# Prompt N+1 — all-skip final-gate

Fires only when the user reached the end of the walk-through without
picking a folder for any of the projects. The catch-all still has all
the conversation history (orphans + per-project subfolders), so nothing
is lost — this is a "are you sure?" confirmation, not a "stop, you'll
lose everything" alarm.

### ▶ Skill speaking ◀

> Walk-through done — and you skipped every project.

> <catchall_name> now contains all your conversation history (orphan
> chats + a per-project subfolder for each skipped project), but no
> project folders will be reconstructed on disk.

> That's a valid outcome if you only wanted to preserve the chat history
> for review. If it was intentional, say "yes, finalize" to wrap up
> Track A. If you'd like to revisit any project choices, just tell me
> which one.


### Prompt N+1 decisions

- **Soft confirmation, not hard alarm.** Under the corrected skip rule
  (skip routes conversations to catch-all), nothing is destroyed in the
  all-skip case — the user just chose to not reconstruct any project
  folders. The prompt confirms intent.
- **Open-ended "tell me which" for partial revisit**, not a coarse
  "redo from scratch." Most all-skip users meant to all-skip; if any
  individual project needs revisiting, free-text covers it.
- **Doesn't fire for partial-skip cases** (some skipped, some picked).
  Per-project choices are atomic; the user actively decided each one.

---

# Prompt N+2 — Track A wrap (cleanup + Track B handoff)

End of Track A. Skill deletes sensitive intermediates and writes the
README + `memory-capture-prompt.md` to the hub, then displays this
prompt. Explicit 4-step bootstrap so the user knows how to start
Track B on the new account.

### ▶ Skill speaking ◀

> Track A complete!

> Cleaned up: removed the export zip, the saved Chats page, the parse
> artifacts, and the extracted transcripts from this folder. Your
> reconstructed projects, the catch-all folder, the tracker, and your
> `skills/` subfolder are all intact.

> Next: Track B — bring everything into your new account.

> To get started on the new account, you'll do four quick setup steps:

> 1. Make sure the migration hub folder is on the new-account machine
>    (same workstation, cloud-sync, or copy it over — whichever way
>    you transfer folders between machines).
> 2. Install this skill on the new account: **Customize → + → Skills →
>    upload** `account-migration.skill` from this hub's `skills/`
>    subfolder.
> 3. Import the migration hub itself as a Cowork project on the new
>    account using New project → Choose existing folder. Name it
>    the same as it was on this account.
> 4. Open a conversation in that project, tell Claude *"continue the
>    migration from the old side"*, and pick **new** when asked.

> After that the skill drives the rest — memory seeding, project
> relinks, binary recovery, validation, and cleanup.

> One more thing to do before you start Track B (or before deleting
> this account, whichever comes first): capture your global memory. In
> Claude Chat (claude.ai in your browser, or the Chat surface in
> Claude Desktop — NOT Cowork), sign in to the OLD account, start a
> no-project conversation, and paste one of the prompts in
> `memory-capture-prompt.md` in this folder (the file walks you through
> choosing between the wholesale and corporate-carve-out variants).
> Save Claude's response as `memory-capture.md` in this same folder —
> Track B will pick it up during the memory seeding phase.

> Full step-by-step is in `README - Final Transition to New Account.md`
> in this folder. The skill-assisted path is at the top; manual fallback
> instructions follow.

> Run those four steps when you're ready and I'll see you on the other side.


## Prompt N+2-single — Track A wrap (single-project mode)

Fires at end of Track A when `migration_scope == "single"`. Replaces
Prompt N+2 in single-project mode — no hub, no global memory capture,
no per-project plurality.

### ▶ Skill speaking ◀

> Track A complete for <project name> — everything needed to bring
> this project to the new account lives inside its working folder now.

> What's in the project folder:

>   - `conversation-history/`
>       <N_transcripts> session transcripts (chronological) + `INDEX.md`
>   - `transition-data/cowork-space-memory/`
>       <N_memory> Cowork memory entries dumped from this project on the
>       old account (or absent/empty if this project had no per-project
>       memory to dump)
>   - `transition-data/project-blueprint.md`
>       The destination-side bootstrap — has a verbatim Section 7
>       starting prompt that restores memory and loads project context
>       on the new account in one paste.
>   - `transition-data/skills/account-migration.skill`
>       This skill, bundled so it travels with the project (install it
>       on the new account before invoking).
>   - `transition-data/tracker.html`
>       Carries the migration state so when you invoke the skill on the
>       new account, it auto-detects this is a single-project transfer
>       and adapts the flow.
>   - `transition-data/_RESUME_ON_NEW_ACCOUNT.md`
>       Short instructions for the new-account side, in case you want
>       to read ahead.
>   - `_PROJECT_BRIEF.md`
>       Provenance + a "Resuming on the new account" section.
>   - Your working files at the root — untouched.

> To bring <project name> to the new account:

>   1. Make sure this folder is on the new-account machine (sync it, or
>      copy it over).
>   2. Install this skill on the new account if you haven't already:
>      Customize → + → Skills → upload
>      `transition-data/skills/account-migration.skill`.
>   3. Create a new Cowork project on the new account using
>      New project → Choose existing folder and select this same
>      folder. Name it the same as it was on the old account.
>   4. Open a conversation in that project, tell Claude
>      *"finish migrating this project from the old side"*, and pick
>      **new** when asked. The skill will detect this is a
>      single-project migration and walk you through one short step
>      (pasting Section 7 into a fresh chat). That's it.

> See `transition-data/_RESUME_ON_NEW_ACCOUNT.md` for the same
> instructions in writing if you want to reference them later.


### Prompt N+2 decisions

- **Cleanup happens before display**, not asked-for-confirmation. The
  intermediates are sensitive (full export, all chat metadata, the
  attribution map) and there's no reason to keep them after Track A.
  Specific files listed in the prompt because the user dropped them in
  themselves and will recognize what was removed.
- **The 4-step setup is explicit.** Without it, users finish Track A
  and have no idea how to start Track B on the new account. The README
  has the same steps in the skill-assisted top section.
- **Skill installation step explicitly names the file** (`account-migration.skill`)
  and the Cowork UI path (`Customize → + → Skills → upload`). Removes
  guesswork.
- **Hub-as-project framing in step 3.** The skill's B-1a detect-at-runtime
  path expects the hub to be a Cowork project on the new account, with
  the hub folder as its working folder. Telling the user to use "Choose
  existing folder" sets this up. Name-it-the-same preserves consistency
  with the old account's hub project name.
- **Memory capture is called out separately** as a "do this before
  deletion" item. It produces `memory-capture.md` which Track B's
  memory-seed phase consumes.
- **"See you on the other side"** as the closer — friendly, matches the
  voice of "All set!" and "Hang tight" earlier in the flow.

---

# Track B — destination-account relink

## Prompt B-1a — Track B opener (hub detected via working folder)

Fires when the skill detects it's running inside a Cowork project whose
working folder IS the migration hub (presence of `tracker.html`).
Preceded by the Part 3 banner: `▶ Part 3: Setting Up Claude Cowork (New Account) ◀`.

### ▶ Skill speaking ◀

> Project migration — Track B (Relink)

> Track B picks up on the new account. I can see I'm running inside the
> migration hub project, which means I can read the tracker the old side
> left for me. The tracker tells me which projects you reconstructed,
> which ones you routed to the catch-all, your Cowork projects from the
> old account, and where the recovery checklist lives.

> The actual content — your project folders, the catch-all, the
> blueprints, the recovery checklist — is in sibling folders on this
> machine that aren't linked to me yet. As we walk through each project
> you'll create a new Cowork project pointing at its folder, and I'll
> ask for access at the moment I need to verify what's there.

> Here's the plan:

> 1. Seed your global memory on this account from the snapshot the old
>    side produced.
> 2. Set up the catch-all as a Cowork project here.
> 3. Walk through each project from the old side. For each one, you'll
>    create a new Cowork project using "Choose existing folder" pointing
>    at its on-disk folder. I'll verify the blueprint and inventory the
>    contents, then walk you through pasting custom instructions and
>    bootstrapping a first conversation.
> 4. Recover any binary files (.docx, .xlsx, etc.) that were referenced
>    in transcripts but couldn't be extracted from the export.
> 5. Validate that everything carried across the way you expected, then
>    clean up the migration hub.

> Say **ready** to start, **hold** if you need a minute, or **quit**
> to stop the migration.


## Prompt B-1b — Track B opener (no source detected, picker needed)

Fires when the skill is NOT running inside a known migration source
(no `tracker.html` at working-folder root, no `transition-data/tracker.html`
inside the working folder — invoked from a fresh Cowork project, a
different Cowork project, or a no-project conversation). Preceded by
the Part 3 banner.

### ▶ Skill speaking ◀

> Project migration — Track B (Relink)

> Track B picks up on the new account. The source side left behind a
> tracker file that tells me what was migrated and what's still needed.

> I'm not currently running inside the migration source. Point me at the
> right folder and I'll read it from there. Two shapes are possible
> depending on what you did on the old side:

>   - Whole-account migration → point me at the hub folder (the
>     one that contains `tracker.html`, `README - Final Transition to
>     New Account.md`, and a `skills/` subfolder).

>   - Single-project transfer → point me at the **project folder
>     itself** (the one whose `transition-data/` subfolder contains
>     `tracker.html` and `project-blueprint.md`).

> I'll detect which one based on what's in the folder you pick and
> adapt the rest of the flow accordingly.

> Say **ready** when you're ready and I'll bring up the folder picker.
> Say **hold** if you don't have the source on this machine yet, or
> **quit** to stop the migration.


## Prompt B-1c — Track B opener (single-project source detected)

Fires when the skill detects `transition-data/tracker.html` in the
current working folder — the user is invoking Track B from inside the
migrated project itself. Preceded by the Part 3 banner.

### ▶ Skill speaking ◀

> Project migration — Track B (Relink)

> I can see I'm running inside a single-project migration — your
> `transition-data/` folder has the tracker and blueprint the old side
> left behind. There's no hub to fetch, no other projects to walk
> through, no catch-all to set up. Just one project to bring online here.

> What's about to happen:

>   1. I'll verify the migration package is intact (blueprint, dumped
>      transcripts, dumped Cowork memory if any, the working files).
>   2. I'll surface what's about to land in this Cowork project's
>      memory and conversation context.
>   3. If the source project had Custom Instructions set, I'll show
>      you the text to paste into the new project's *Custom Instructions*
>      field. (If the source had none, we skip this step.)
>   4. You'll start a fresh chat in the project and paste a short
>      bootstrap prompt I'll show you. That triggers the per-project
>      memory restore (if memory was dumped) and loads the project's
>      full context.
>   5. You're done. The `transition-data/` folder is safe to delete
>      once you've verified the restore.

> Say **ready** to start, or **quit** to stop.


## Prompt B-1c-inventory — single-project inventory display

Fires after "ready" at B-1c. Reports what was found in `transition-data/`.

### ▶ Skill speaking ◀

> Inventory for <project name>:

>   - <N_transcripts> session transcripts in `conversation-history/`
>   - <N_memory> Cowork memory entries in
>     `transition-data/cowork-space-memory/`
>     <if 0: bullet reads "No per-project Cowork memory was dumped
>     on the source side (either there was none, or the dump produced
>     no entries) — nothing to restore here.">
>   - <N_working_files> working files at the project root
>     (see `_PROJECT_BRIEF.md` for the list)
>   - The migration skill is bundled in `transition-data/skills/` so
>     you can install it on this account if you haven't already.

> Everything looks ready. Next I'll walk you through the two action steps —
> Custom Instructions first (if applicable), then the bootstrap prompt.


## Prompt B-1c-customs-present — Custom Instructions paste walkthrough (Section 2 non-empty)

**Step 1 of 2 in the B-1c bootstrap flow.** Fires after the inventory
display when the blueprint's Section 2 contains a non-empty fenced block.
The skill reads `transition-data/project-blueprint.md`, extracts the
fenced block inside Section 2, and surfaces it for the user to copy into
the destination project's *Custom Instructions* field.

**Inline vs. file-pointer rule.** If the fenced block is ≤30 lines, the
skill inlines the text in the blockquote below. If longer, the skill
points at the blueprint file and surfaces it via
`mcp__cowork__present_files` so the user can open it in the right-side
pane and copy from there.

### ▶ Skill speaking ◀

> Step 1 of 2 — **Custom Instructions.** The source project had Custom
> Instructions set. Paste the following text verbatim into the new
> project's *Custom Instructions* field (in *Cowork sidebar → this
> project → Settings → Custom Instructions*). No commentary, no quotation
> marks — just the text between the fence lines.

> <if fenced block ≤30 lines, inline it below:>

> ```
> <Section 2 fenced-block content>
> ```

> <if fenced block >30 lines:>

> The fenced block is on the long side, so I've surfaced
> `transition-data/project-blueprint.md` in the right-side pane — open
> it, scroll to Section 2, and copy the fenced block from there.

> Come back here when you've pasted it and say **done**. Or **skip** to
> leave Custom Instructions empty on the new project (you can always
> paste them later), or **quit**.


## Prompt B-1c-customs-empty — Custom Instructions skip (Section 2 empty)

**Step 1 of 2 in the B-1c bootstrap flow (skip variant).** Fires after
the inventory display when the blueprint's Section 2 has the
empty-placeholder string (source had no Custom Instructions). Auto-advances
to Step 2 per Discipline rule #9 — no input required.

### ▶ Skill speaking ◀

> Step 1 of 2 — **Custom Instructions.** The source project had no Custom
> Instructions set; nothing to paste into the new project's settings.
> Advancing to the bootstrap prompt.


## Prompt B-1c-bootstrap — single-project bootstrap prompt (Step 2 of 2)

**Step 2 of 2 in the B-1c bootstrap flow.** Fires after the Custom
Instructions step (B-1c-customs-present `done`/`skip` or
B-1c-customs-empty auto-advance). The skill displays a short outer
pastable prompt that tells the destination-side Claude to read the
blueprint and treat its Section 7 as the first directive. Section 7
itself (in the blueprint on disk) carries the memory-restore preamble
(for Part 2 projects) plus the project-specific numbered work directives.

**Which variant to display** depends on whether the skill is currently
running inside a Cowork project whose working folder IS the migrated
project's folder:

- If the working folder matches the picked folder (skill was invoked
  from inside the destination project) → **B-1c-bootstrap-in-place**.
- If the working folder is something else (skill was invoked from
  another project or no-project; user pointed at the destination via
  the picker) → **B-1c-bootstrap-relocated**.

### B-1c-bootstrap-in-place

Used when the skill is running *inside the destination Cowork project*.

### ▶ Skill speaking ◀

> Step 2 of 2 — **bootstrap prompt.** To finish restoring `<project name>`,
> paste the prompt below as the first message in a *fresh chat in this same
> Cowork project*. (Open a new chat from the *Cowork sidebar* — don't paste
> it here; this conversation already has its own context and won't bootstrap
> cleanly mid-stream.)

> The prompt — copy verbatim:

> ────────────────────────────────────────

> This is a project I'm migrating from my old Claude account. Read
> `transition-data/project-blueprint.md` for the full project context,
> then treat its Section 7 — Recommended Starting Prompt — as your
> first directive.

> ────────────────────────────────────────

> What happens when you paste it: Claude reads the entire blueprint —
> including its "How to use this file" header that explains the bipartite
> layout — then follows Section 7 as its first directive. Section 7
> restores any dumped Cowork memory (if this project had memory on the
> source side), registers the conversation archive as on-demand reference,
> and walks Claude through the project-tailored reading list.

> Come back here when you've done it and say **done**. Or **skip** if you'd
> rather handle the paste later (the blueprint stays in place), or
> **quit**.


### B-1c-bootstrap-relocated

Used when the user invoked the skill from a Cowork project whose working
folder is NOT the migrated project's folder (the destination folder came
in via the picker).

### ▶ Skill speaking ◀

> Step 2 of 2 — **bootstrap prompt.** To finish restoring `<project name>`,
> you need a Cowork project on this account whose working folder IS the
> migrated project's folder. The skill found the migration data via the
> picker, but you're currently running in a different project — the
> bootstrap has to land in the right one.

> Set up the destination project if you haven't already:

>   1. In the *Cowork sidebar*: *New project → Choose existing folder*
>      → pick `<project folder path>`.
>   2. Open a fresh chat inside that new project.
>   3. Paste the prompt below as the first message.

> (If you already have a Cowork project pointed at that folder, just
> step 2 + 3.)

> The prompt — copy verbatim:

> ────────────────────────────────────────

> This is a project I'm migrating from my old Claude account. Read
> `transition-data/project-blueprint.md` for the full project context,
> then treat its Section 7 — Recommended Starting Prompt — as your
> first directive.

> ────────────────────────────────────────

> What happens when Claude reads it: it reads the entire blueprint —
> including the "How to use this file" header that explains the bipartite
> layout — then follows Section 7 as its first directive. Section 7
> restores any dumped Cowork memory (if this project had memory on the
> source side), registers the conversation archive as on-demand reference,
> and walks Claude through the project-tailored reading list.

> Come back here when you've done it and say **done**. Or **skip** if you'd
> rather handle the paste later, or **quit**.


## Prompt B-1c-wrap — single-project Track B wrap

Fires after "done" or "skip" at B-1c-bootstrap.

### ▶ Skill speaking ◀

> Single-project restore complete.

> This project — <project name> — is now live on the new account.
> Both `transition-data/` and `_PROJECT_BRIEF.md` at the project root are
> migration scaffolding only — once you've verified the project looks
> right, you can delete them. (Keep them around as a migration record if
> you prefer; nothing depends on either after this point.) Your project's
> own working files, the `conversation-history/` archive, and the
> restored per-project memory are what's load-bearing going forward.

> If you have more projects to migrate, run the skill again on the
> source account for each one, then point me at each project folder
> on this side as you bring it across.


### Prompt B-1 decisions (both variants)

- **No "bring across" framing.** By the time B-1 fires, the hub is
  already on this machine (or accessible via sync). The skill just
  needs to find it — or detect it's already in the hub's working folder.
- **Access constraint acknowledged explicitly.** Second paragraph in
  both variants tells the user that the project folders / catch-all /
  blueprints aren't linked yet and will be granted per-project via the
  picker as the walk-through proceeds. Sets expectation for the
  multi-picker flow.
- **5-step plan inline.** Mirrors Prompt 4 verbose-first pattern. User
  just arrived from Track A and wants to know what's ahead.
- **B-1a explicitly names the hub detection** ("I can see I'm running
  inside the migration hub project"). Tells the user the skill found
  things on its own.
- **B-1b adds the picker invocation note.** Same content as B-1a
  otherwise; consistent voice across both branches.
- **Vocabulary `ready / hold / quit`.** "hold" is the wait verb (distinct
  from skip, which means "do nothing for this item and proceed"). Quit
  ends the skill cleanly; tracker stays on disk for resume.

## Prompt B-2 — picker bridge (multi-project hub or single-project folder)

Fires only on the B-1b path, after user says "ready". Skipped on the
B-1a / B-1c paths.

### ▶ Skill speaking ◀

> Got it. Bringing up the folder picker now. Pick whichever folder
> you have — a multi-project hub or a single project's folder. I'll
> detect which one and adapt from there.


## Prompt B-3 — silent tracker parse + validation

Tracker parsing is instantaneous so there's no "hang tight" message
analogous to Track A's Prompt 2. Happy path goes silently to B-4.
Failure branches below.

### Prompt B-3b — partial corruption (JSON unparseable, HTML table readable)

### ▶ Skill speaking ◀

> The tracker's JSON state block is unreadable, but I can see the
> rendered table inside the file. I'll work from that — counts and
> dispositions are fine, but I won't have exact folder paths to pre-fill,
> so you'll be navigating the folder picker by name for each project.

> Continuing.


### Prompt B-3c — disaster (no JSON, no usable HTML table)

### ▶ Skill speaking ◀

> I couldn't read the tracker file usefully. The handoff state and the
> rendered table are both unrecoverable, and without the tracker I don't
> have a list of what projects to walk through or where their folders
> live.

> Options:

> - Say **pick** to point me at a different folder. The hub may have
>   been copied somewhere else, and the one I just looked at is the
>   damaged copy.
> - Say **quit** to stop. Open the `README - Final Transition to New
>   Account.md` in the hub folder and follow it manually — it has the
>   same steps as this walk-through, just non-interactive. You can also
>   try repairing the tracker (open it in a text editor, or restore from
>   the Cowork sidebar artifact on the old account if you still have
>   access) and re-run Track B once it's parseable.


## Prompt B-4 — hub inventory display

Mirror of Track A's Prompt 2.5. Plain `- ✓` checkmarks. Conditional
rendering: drop any bullet whose count is 0.

### ▶ Skill speaking ◀

> Got it. From the tracker:

> - ✓ <N_part1_reconstructed> reconstructed projects from your old web/chat side.
> - ✓ <N_part2_cowork> Cowork projects from the old account.
> - ✓ The catch-all: <catchall_name> with <N_orphans> orphan
>    conversations and <N_part1_catchall> archived per-project subfolders.
> - ✓ <N_scheduled_tasks> scheduled task(s) captured at source.
> - ✓ <N_custom_skills> custom skill(s) to install on this account.
> - ✓ <N_recover> binary file(s) to recover from claude.ai before
>    old-account deletion.

> The flow: seed your global memory, validate the seed, set up the
> catch-all, walk through each project, recreate scheduled tasks,
> install custom skills, recover binaries, and clean up. I'll drive
> each step in order — you decide per item.


---

## Track B scope (between B-4 inventory and B-MS-1 memory seed)

Mirror of Track A's Step 1.5 scope gate. Lets the user restore just one
project from the tracker instead of walking the entire list.

### track-b-scope-selection

Fires after the B-4 inventory display.

### ▶ Skill speaking ◀

> Before we start working through the list — restoring everything from
> the tracker, or just one specific project this run?

>   - **all**   — every project in the tracker that's still pending.
>   - **one**   — a single named project. Everything else stays pending,
>               ready for a future run.
>   - **quit**  — close the skill (tracker stays on disk).

> Most people pick **all** the first time the new account is set up, and
> **one** for follow-up runs (re-doing a project after a fix, or
> adding a project that wasn't ready during the initial pass).


### track-b-single-project-name

Fires only if the user picks "one" at the scope-selection prompt.

### ▶ Skill speaking ◀

> Which project? Type the name as it appears in the tracker (case
> doesn't matter; I'll match by substring). The tracker has:

>   <enumerate projects[].name and cowork_projects[].name from the
>    tracker, in the same order the tracker shows them, with a leading
>    tag for which side: [Part 1] or [Part 2]>

> If I can't find a match I'll list these again so you can spot a
> typo. Otherwise we'll jump straight to that project's relink.


### track-b-single-project-no-match

Fires only if `restore_target` matched zero entries.

### ▶ Skill speaking ◀

> I couldn't find a project matching "<restore_target>". The tracker
> contains:

>   Part 1 (reconstructed from web/chat):
>     - <name 1>  (status: <relinked>)
>     - <name 2>  (status: <relinked>)
>     - …

>   Part 2 (Cowork from old account):
>     - <name 1>  (status: <relinked>)
>     - <name 2>  (status: <relinked>)
>     - …

> Three options:

>   - **pick** + a name from the lists above — I'll re-scope to that one.
>   - **retry** — type a different name from scratch.
>   - **quit** — close the skill.


---

## Memory seed (Track B Phase 2)

Fires after B-4. Before any per-project work, the user seeds Claude's
account-level memory on the new account from the snapshot the old side
produced. Per-project conversations later in Track B inherit this
context automatically.

### Prompt B-MS-1 — memory seed opener

### ▶ Skill speaking ◀

> First step: seed your global memory.

> The old account produced `memory-capture.md` — a snapshot of
> everything Claude knew about you globally on that account: your role,
> work context, communication preferences, recurring patterns, and so
> on. On this account Claude doesn't know any of that yet, so we'll
> load it now before anything else.

> Heads up: account-level memory is read and written through **Claude
> Chat** (claude.ai in a browser, or the Chat surface in Claude
> Desktop), not in Cowork. So you'll do this part there — not in this
> Cowork conversation — then come back here to continue.

> To seed it:

> 1. Open Claude Chat (claude.ai in a browser, or the Chat surface
>    in Claude Desktop — NOT Cowork). Sign in to your NEW account.
> 2. Start a new conversation — no project selected (just a fresh
>    chat).
> 3. Attach `memory-capture.md` from the migration hub folder to the
>    conversation.
> 4. Paste this prompt:
>    *"I'm migrating from a previous Claude account. The attached
>    `memory-capture.md` is a snapshot of everything you knew about me
>    there — my role, work context, communication preferences,
>    technical domains, recurring workflows, and other persistent
>    context. Please review it and commit the relevant facts to your
>    memory of me on this account. Be thorough."*
> 5. Wait for Claude to confirm what's been saved.

> Come back here (Cowork) and say **done** when finished. Or
> **skip** if you didn't capture memory on the old side (or don't
> want global memory seeded), or **quit** to stop the migration.


### Prompt B-MS-1-single — memory seed opener (single-project mode)

Variant of **B-MS-1** used when `restore_scope == "single"` (Step 5.5).
Account-level memory is account-wide and likely already seeded from a
prior run; this short prompt confirms before redoing it.

### ▶ Skill speaking ◀

> Memory seed step. Since you're restoring just one project this run,
> your account-level memory may already be in place from an earlier
> restore.

>   - **skip**   — global memory is already seeded, jump straight to the
>                project relink. (Common choice in single-project mode.)
>   - **ready**  — fresh account, seed global memory first. I'll walk you
>                through it (same Claude-Chat-side steps as a full
>                restore — attach memory-capture.md, paste the prompt,
>                come back when Claude confirms).
>   - **quit**   — stop the migration.


### Prompt B-MS-2 — memory seed done confirmation

### ▶ Skill speaking ◀

> Memory seeded. Claude on this account now has your global context for
> the per-project setup that follows.


### Prompt B-MS-3 — memory seed skip confirmation

### ▶ Skill speaking ◀

> Memory seeding skipped — Claude on this account will pick up your
> context conversation by conversation as you work.


### Memory seed decisions

- **Fires before catch-all setup and the walk-through.** Per-project
  conversations later in Track B inherit seeded memory automatically.
  Seeding once is cheaper than uploading `memory-capture.md` in every
  per-project bootstrap.
- **No-project conversation required.** Memory edits apply to the
  account level. Doing this inside a project would scope it incorrectly.
- **The seed prompt is also written as an asset** (`memory-seed-prompt.md`)
  so the user can re-find it if they close the chat between B-MS-1
  and the no-project conversation.

---

## Catch-all setup (Track B Phase 3)

Fires after memory seed. Catch-all on the new account needs to become
a Cowork project so the user can browse it natively (review orphans +
per-project subfolders).

### Prompt B-5 — catch-all setup

### ▶ Skill speaking ◀

> Next: set up the catch-all on this account.

> The catch-all on disk is at:
> <catchall_folder_path>

> In Cowork:
> 1. Start a new project → Choose existing folder.
> 2. Navigate to the path above and select it.
> 3. Name it <catchall_name> — same as on the old side, so the
>    per-project routing language in the walk-through stays consistent.
> 4. Come back here.

> Say **ready** when the project is created. I'll bring up a folder
> picker so I can access it and confirm the orphans + per-project
> subfolders are intact.


### Prompt B-5.5 — catch-all picker bridge

### ▶ Skill speaking ◀

> Got it. Bringing up the folder picker now so I can access
> <catchall_name>'s folder.


### Prompt B-5.6 — catch-all post-pick confirmation

### ▶ Skill speaking ◀

> Catch-all confirmed: <N_orphans> orphan conversations and
> <N_part1_catchall> per-project subfolders, all present. You'll
> review the contents on the new account inside <catchall_name> once
> the walk-through is done.


---

## Walk-through (Track B Phase 4)

Per-project relink iteration. Covers Part 1 reconstructed + Part 2
Cowork projects only. Part 1 catch-all-routed projects are reviewed
inside the catch-all (set up in B-5), not walked individually.

### Prompt B-6 — walk-through verbose intro

### ▶ Skill speaking ◀

> Now I'll walk through your <N_walkthrough> projects in order —
> <N_part1_reconstructed> reconstructed from your web/chat side, plus
> <N_part2_cowork> Cowork projects from the old account. For each one
> we'll do the same thing:

> 1. You'll create a new Cowork project on this account using **New
>    project → Choose existing folder**, then select the project's
>    on-disk folder. The folders are already where the old-side skill
>    left them — same paths if both accounts run on this machine, or
>    wherever you copied them to.
> 2. Say **ready** once the project is created — or **skip** to
>    defer this project (you can come back to it later, the on-disk
>    folder isn't touched), or **quit** to stop the migration.
> 3. After **ready** I'll bring up a folder picker so I can access the
>    project's folder, verify the blueprint is there, and give you the
>    short checklist for finishing the setup (paste custom instructions,
>    bootstrap a first conversation).

> The <N_part1_catchall> projects you routed to the catch-all on the
> old side aren't in this walk-through — they live as subfolders inside
> <catchall_name> for you to review there. I'll remind you when we
> wrap.


### Pattern — per-project prompts B-7 through B-N

### ▶ Skill speaking ◀

> --- Project N of <N_walkthrough> ---

> <project_name> — <source_kind>
> <N_convs> conversations · <N_docs> knowledge docs
> Folder: `<folder_path>`

> In Cowork: New project → Choose existing folder, select the folder
> above, then say **ready** here.

> Or **skip** (defer this project) or **quit** (stop the migration).


`<source_kind>` values: `reconstructed from web/chat` (Part 1 empty pick) or `Cowork from old account` (Part 2).

### Per-project picker bridge (after "ready")

### ▶ Skill speaking ◀

> Got it. Bringing up the folder picker so I can access
> <project_name>'s folder.


### Per-project post-pick — blueprint found (happy path)

### ▶ Skill speaking ◀

> Got it. <project_name> has its blueprint and knowledge
> files ready. Finish setting it up on this account:

> 1. Open the new Cowork project you just created.
> 2. Open `transition-data/project-blueprint.md`. Copy the **Custom
>    Instructions** section into the project's settings.
> 3. Start a conversation in the project. Paste this prompt (it's
>    also saved in `_PROJECT_BRIEF.md`'s "Resuming on the new account"
>    section if you'd rather grab it from there):
>    *"This is a project I'm migrating from my old Claude account.
>    Read `transition-data/project-blueprint.md` for full context, then
>    treat its Recommended Starting Prompt section as my first
>    directive — that's the project-tailored resumption point.
>    Knowledge files referenced in the blueprint are in `knowledge/`
>    (for reconstructed projects) or in this project's folder (for
>    Cowork projects)."*

> Say **done** when finished to move to the next project. Or
> defer to move on without finishing the bootstrap (you can
> come back to it later). I won't verify the steps above — I don't have
> access to inspect the new Cowork project's settings.


### Per-project post-pick — blueprint missing (Part 2 only)

Fires when a Part 2 Cowork project's folder is picked but
`transition-data/project-blueprint.md` isn't present. Means the user
didn't run the migration-prompt on the old account before deletion.

### ▶ Skill speaking ◀

> <project_name>'s folder is accessible, but I don't see a
> `transition-data/project-blueprint.md`. That means the per-project
> migration prompt didn't get run on the old account before deletion.

> You can either:

> - Say **continue** to finish setting up the project anyway. You'll
>   paste the custom instructions and bootstrap by hand from whatever
>   you remember about the project. Knowledge files are still
>   accessible from the on-disk folder.
> - Say back if you still have access to the old account and
>   can run the migration prompt now (in that Cowork project, paste the
>   contents of `transition-data/migration-prompt.md`, save the response
>   as `transition-data/project-blueprint.md`). Then come back here and
>   say **done**.
> - Say **skip** to defer this project entirely.


### Per-project post-pick — folder wrong / unexpected structure

### ▶ Skill speaking ◀

> I can access the folder you picked, but it doesn't look like
> <project_name>'s folder — I expected to see <expected_marker>
> and instead I see <found_contents>.

> Maybe you picked the wrong folder? Say **pick** to try the folder
> picker again, **skip** to defer this project, or **quit** to stop.


### Per-project skip confirmation

Fires when user said "skip" at the per-project prompt (no picker fires).

### ▶ Skill speaking ◀

> <project_name> deferred. You can come back to it later by
> re-running the skill and picking **new** — the tracker will still show
> this project as pending.


Then the next per-project prompt fires immediately.

### Walk-through decisions

- **Walk-through covers Part 1 reconstructed + Part 2 Cowork only.**
  Part 1 catch-all-routed projects review inside the catch-all set up
  in B-5; they don't get their own walk-through entries.
- **Single-prompt happy path with 3 user actions** (open project, paste
  CI, bootstrap). No per-step gating. Faster than checkpointing each,
  costs the user progressive feedback for a single end-of-block "done".
- **Knowledge files surfaced in the bootstrap prompt**, not as a
  separate step. They're already accessible via filesystem when the
  user does "Choose existing folder" — no upload needed.
- **`done` vs `defer` after the happy-path checklist.** "done"
  means "I finished the steps, next project please"; defer
  means "I'll do the bootstrap later, move on now." Distinct meanings.
- **`continue` / `back` / `skip` in blueprint-missing branch.**
  Three actions: proceed without blueprint, go back to old account
  and generate one, or skip this project.

---

## Scheduled-tasks recreation (Track B Step 8.5, multi-project only)

Fires after the per-project walk-through and before binary recovery.
Mirrors Track A's Step 3.7 in reverse: Track A captured the user's
scheduled tasks into `scheduled-tasks-export.md` at the hub root; Track B
walks the user through recreating each one on the new account, calling
`mcp__scheduled-tasks__create_scheduled_task` automatically when the user
confirms.

Skipped entirely in single-project Track B (B-1c branch) — Track A's
Step 3.7 already skipped single-project, so the tracker's
`scheduled_tasks` array is empty.

### Prompt B-ST-zero — no scheduled tasks captured

Fires when the tracker's `scheduled_tasks` array is empty or missing.
One-liner, auto-advance per Discipline rule #9.

### ▶ Skill speaking ◀

> No scheduled tasks captured at source — moving on.


### Prompt B-ST-1 — scheduled-tasks opener

Fires when there's at least one captured scheduled task. Names the count
and the count-with-external-dependencies subset before iterating.

### ▶ Skill speaking ◀

> Next: scheduled tasks. Track A captured `<N_total>` scheduled task(s)
> from your old account into `scheduled-tasks-export.md`. I'll walk you
> through them one at a time. For each, you decide **recreate** (I'll
> create the task on this account right now, using the cron and prompt
> from the export) or **skip** (leave it out — you can always add it
> manually later).

> <if any task has external dependencies>
> Note: `<N_with_deps>` of these task(s) reference attached working
> folders or external Windows state. I'll create the task spec; you'll
> need to re-attach the referenced folders via *Cowork → each task's
> settings* before they next fire. I'll remind you with a list at the
> end.
> </if>

> Say **ready** to start the walk-through, **skip** to skip all
> scheduled tasks (you can handle them manually from the export file
> later), or **quit**.


### Prompt B-ST-2 — per-task prompt

Fires once per scheduled task in tracker order. Inline the verbatim
prompt if ≤30 lines; if longer, inline the first 20 lines and point at
the export file for the remainder. Use italics for *Cowork → task
settings* locations, backticks for filenames.

### ▶ Skill speaking ◀

> **Scheduled task `<idx>` of `<N_total>` — `<taskId>`**

>   - **Description:** `<description>`
>   - **Cron:** `<cronExpression>` (`<schedule_human>`)
>   - **Enabled at capture time:** `<yes/no>`
>   <if has_dependencies>
>   - **External dependencies:** this task references `<folder>`,
>     `<folder>`, …. After I create the task you'll need to re-attach
>     those folders via *Cowork → this task's settings*.
>   </if>

> **Prompt:**

> ```
> <verbatim prompt body, first 30 lines>
> ```
> <if longer than 30 lines>

> (Full prompt continues in `scheduled-tasks-export.md` § `<idx>`.)
> </if>

> Say **recreate** and I'll create the task on this account, **skip**
> to leave it out, or **quit** to stop the migration here.


### Prompt B-ST-3 — per-task done confirmation

Fires after a successful `mcp__scheduled-tasks__create_scheduled_task`
call. Auto-advances to the next task.

### ▶ Skill speaking ◀

> Created `<taskId>` on this account (cron `<cronExpression>`).
> <if has_dependencies>Remember to re-attach the referenced folders.</if>


### Prompt B-ST-3-error — per-task error re-ask

Fires when `mcp__scheduled-tasks__create_scheduled_task` returns an
error (taskId already exists, schedule conflict, etc.).

### ▶ Skill speaking ◀

> Couldn't create `<taskId>`: `<error message from MCP tool>`.

> Say **recreate-with-new-id** and I'll retry with `<taskId>-imported`,
> **skip** to move on without recreating this task, or **quit**.


### Prompt B-ST-4 — per-task skip confirmation

Auto-advance to the next task.

### ▶ Skill speaking ◀

> Skipped `<taskId>` — you can recreate it manually later from
> `scheduled-tasks-export.md`.


### Prompt B-ST-wrap — scheduled-tasks wrap

Fires after the last task. Surfaces the recreate/skip counts plus a
reminder about dependency folders for any recreated task that has them.

### ▶ Skill speaking ◀

> Scheduled tasks: `<N_recreated>` recreated, `<N_skipped>` skipped.

> <if any recreated task has dependencies>
> These recreated task(s) reference attached folders — re-attach them
> via *Cowork → each task's settings* before they next fire:
>   • `<taskId>` (needs: `<folder>`, `<folder>`)
>   • …
> </if>

> Moving on to artifact recovery.


### Scheduled-tasks decisions

- **Automation via the MCP tool, not manual handoff.** When the user
  says `recreate`, the orchestrator calls
  `mcp__scheduled-tasks__create_scheduled_task` directly with the cron,
  prompt, and description captured at source. No "tell Claude in
  another conversation" indirection — the task lands on the new
  account in this same conversation. The user just confirms.
- **Verbatim prompt, no editing.** The prompt body comes from
  `scheduled-tasks-export.md` exactly as Track A captured it. Don't
  paraphrase, condense, or "clean it up" (Discipline rule #10).
- **Dependency-folder reattach is the user's manual step.** The
  scheduled-tasks MCP doesn't expose folder attachment per-task;
  that's a Cowork UI setting. The wrap surfaces a reminder per
  dependency-having task; the user re-attaches via Cowork's task
  settings UI.
- **Single-project Track B skips.** Symmetric with Track A's
  Step 3.7 skip in single-project mode. Scheduled tasks are
  account-level resources; a focused one-project transfer doesn't
  touch them.


## Custom-skills installation (Track B Step 8.7)

Fires after scheduled tasks, before binary recovery. The orchestrator
pre-checks the destination account's `.claude/skills/` mount and
reconciles it with the captured-skills list from the tracker —
anything already installed (notably `account-migration` itself) is
filtered out before the user-facing list is displayed. Single-project
Track B skips this section entirely.

### Edge case — all captured skills already installed

If Step 8.7's pre-check finds every captured skill already present on
the destination account (`installed: true` after reconciliation),
B-CS-1 doesn't fire. One-liner; auto-advance per Discipline rule #9.

### ▶ Skill speaking ◀

> Custom skills already installed on this account — moving on.


### Prompt B-CS-1 — custom-skills installation opener

Fires when there's at least one captured skill the destination doesn't
already have installed. Surface the pending `.skill` files via
`mcp__cowork__present_files` *before* displaying this prompt so they
render as clickable Save-skill cards in chat. Substitute the actual
filename + size list; flag `vulscan-*` as a related set and
`copy-to-scratch.skill` / `copy-from-scratch.skill` as a pair when
those skills appear in the pending list.

### ▶ Skill speaking ◀

> `<N_pending>` custom skill(s) to install on this account. I've
> surfaced each `.skill` file above as a clickable card — for each
> one, click the card and use the **Save skill** / install button that
> appears. They'll land in the same place all skills do (*Cowork →
> Customize → Skills tab*).

> The bundle:

>   • `<skill-1>.skill` (`<size>`)
>   • `<skill-2>.skill` (`<size>`)
>   • …

> <if vulscan-* group present>
> Note: the four `vulscan-*` skills are a related set — they
> likely chain together. Install them all if you use that workflow.
> </if>

> <if both copy-from-scratch.skill and copy-to-scratch.skill present>
> Note: `copy-from-scratch.skill` and `copy-to-scratch.skill` are
> a pair — install both or neither.
> </if>

> When all `<N_pending>` are installed (or any you don't want to keep
> are skipped), say **done** and I'll re-check the
> installed-skill list and update the tracker. Say **skip-all** to
> leave the remaining ones uninstalled — you can install them later
> from the same `skills/` folder in the hub. Say **quit** to stop the
> migration here without closing things out.


### Prompt B-CS-done — custom-skills install confirmation

Fires after the user says `done`. The orchestrator re-reads the
destination's `.claude/skills/` mount to confirm what's actually
installed; the counts below reflect that fresh read, not the
user's claim. If some surfaced skills are still missing, name them
so the user knows.

### ▶ Skill speaking ◀

> `<N_now_installed>` custom skill(s) installed on this account.
> <if N_still_pending > 0>
> `<N_still_pending>` still pending — these aren't blocking, you can
> install them anytime from the same `skills/` folder in the hub.
> Pending:
>   • `<skill-1>.skill`
>   • `<skill-2>.skill`
>   • …
> </if>

> Moving on to artifact recovery.


### Prompt B-CS-skip-all — custom-skills skip-all confirmation

Fires after the user says `skip-all`.

### ▶ Skill speaking ◀

> Skipping custom-skill installation. The `.skill` files stay in
> `<hub>/skills/` — install them anytime via *Cowork → Customize →
> the + button → Skills tab*. (Re-run the skill and pick **new** to
> walk through them again later.)


### Custom-skills installation decisions

- **Pre-check before display.** The migration skill itself is always
  installed on the destination during Track B (it's how the user got
  here). The pre-check naturally filters it out. Same logic catches
  any skills the user pre-installed on the new account before running
  Track B.
- **Detection is filesystem-based, not behavioral.** Listing
  `.claude/skills/` is the source of truth — folder name = installed
  slug. No reliance on chat-context's `<available_skills>` block,
  which the skill can't introspect.
- **Org-level skills.** If the user has installed a skill at the
  organization level rather than per-account, the slug may not
  appear in `.claude/skills/` for that account. The tracker captures
  intent; nothing enforces re-install. `skip-all` is the clean way to
  acknowledge org-level coverage.
- **Single-project Track B skips.** Symmetric with Track A's
  Step 3.5 skip in single-project mode. No captured skills means
  nothing to install.
- **Re-check on `done`.** Don't trust the user's claim — re-read
  `.claude/skills/` after they say `done`. The Save-skill button
  is per-file; they may have installed some and not others.


## Binary recovery (Track B Phase 5)

Walks the `_ARTIFACTS_TO_RECOVER.md` checklist interactively. Conversation
by conversation, since the user opens each conversation once on
claude.ai and downloads all its referenced files in one pass. Skill
ticks checkboxes after the user confirms each conversation done.

### Prompt B-BR-1 — binary recovery opener

### ▶ Skill speaking ◀

> Next: recover the binary files that couldn't be extracted from the
> export.

> When Track A processed your conversations, it found <N_recover>
> files (.docx, .xlsx, .pdf, .pptx, etc.) that were referenced in
> transcripts but not included in the data export. They're listed in
> `<catchall_name>/_ARTIFACTS_TO_RECOVER.md`.

> These files only exist inside conversations on claude.ai in your old
> account. Once that account is deleted, they're gone permanently. If
> you've already started the old-account deletion process, recover what
> you can now.

> We'll walk through them conversation by conversation — opening each
> conversation in the old account, downloading the files, and saving
> them to disk next to the transcript. I'll tick off each conversation's
> checkboxes after you confirm you've recovered its files.

> The files span <N_convs_with_binaries> conversations. Some have
> one file, some have several.

> Say **ready** to start the first conversation, **skip** if
> you've already recovered everything or don't want to recover any of
> it, or **quit** to stop. (If you skip or quit, the unchecked items
> remain in `_ARTIFACTS_TO_RECOVER.md` so you can come back later.)


### Pattern — per-conversation recovery prompts

### ▶ Skill speaking ◀

> --- Conversation N of <M> ---

> <conversation_title>
> <destination_label>
> Transcript: `<transcript_relative_path>`

> Files to recover (<N_files>):
>   • <filename_1>
>   • <filename_2>
>   • …

> On claude.ai (old account):
> 1. Open the conversation: <claude.ai_url>
> 2. Download each file from the conversation's file panel.
> 3. Save them to:
>    `<artifacts_folder_relative_path>`

> Say **done** when finished, **skip** to defer this conversation,
> or **quit** to stop.


`<destination_label>` is one of three strings derived from the conversation's bucket:
- Part 1 reconstructed → `Project: <project_name> (reconstructed)`
- Part 1 routed to catch-all → `Project: <project_name> (routed to catch-all)`
- Catch-all orphan → `Catch-all orphan (no project)`

### Prompt B-BR-wrap — binary recovery wrap

### ▶ Skill speaking ◀

> Binary recovery <complete | partial>. <N_recovered> files
> recovered across <N_done_convs> conversations.


If skipped any, append:

### ▶ Skill speaking ◀


> <N_remaining> files in <N_skipped_convs> conversations are
> still pending. They're in `_ARTIFACTS_TO_RECOVER.md` with unchecked
> boxes. Recover them before deleting the old account, or re-run the
> skill and pick **new** to resume.


### Edge case — no binaries to recover

If `_ARTIFACTS_TO_RECOVER.md` has zero unchecked items (or doesn't
exist), B-BR-1 doesn't fire. Skill silently moves to validation with a
one-liner:

### ▶ Skill speaking ◀

> No binaries to recover — moving on.


### Binary recovery decisions

- **Conversation-batched, not per-file.** User opens each conversation
  once and downloads all its files. Mirrors how the user would do it
  manually.
- **Skill auto-ticks `_ARTIFACTS_TO_RECOVER.md` checkboxes** when user
  says "done". Trust model: user wouldn't say done if they hadn't
  recovered. Partial recoveries fall through to skip.
- **Conversation URL inline** for one-click convenience. Format is
  `https://claude.ai/chat/<uuid>`. Points at the OLD account's
  conversation — if the user isn't logged in on this browser session,
  they'll need to log in first.

---

## Memory validation (Track B Step 6.5 — immediate, right after seed)

Fires immediately after Step 6 returns `done`. The user is still in
Claude Chat (the seed happened there — Cowork can't write account-level
memory). Validation is the same surface, just one more paste in the same
conversation. Doing it now avoids a context switch back to Chat at the
end of Track B.

If Step 6 returned `skip` (no seed), this step is skipped too —
nothing to validate.

### Prompt B-V-1 — validation opener

### ▶ Skill speaking ◀

> Quick check while you're still in Claude Chat from the seed step —
> let's make sure the new account picked up what you migrated.

> In the *same no-project Claude Chat conversation you just used for
> seeding* (don't start a new one — the seed memory is fresher in this
> conversation), paste this prompt:

> ```
> Based on everything you know about me, tell me:
> - Who I am and what I do
> - What projects or topics are top of mind for me
> - How I prefer to communicate
> - Any tools, frameworks, or domains I work in
> - Anything else you consider important context

> Be thorough — I'm checking that a migration was successful.
> ```

> Compare Claude's response against `memory-capture.md` in this hub
> folder. If anything important is missing or wrong, you have two
> options to fix it before continuing:

>   • Add a memory edit on the Claude Chat conversation directly
>     ("remember that …").
>   • Attach `memory-capture.md` again in the same conversation and
>     ask Claude to fill in the gaps.

> Come back here (Cowork) and say **done** when the response looks
> right, **skip** if you'd rather defer validation (you can run the
> prompt above any time in a no-project Chat conversation), or **quit**.


### Prompt B-V-2 — validation done

### ▶ Skill speaking ◀

> Memory validated. Catch-all setup is next.


### Prompt B-V-3 — validation skip

### ▶ Skill speaking ◀

> Validation deferred — moving on. If you want to check later, paste the
> validation prompt in any no-project Chat conversation on this account.


---

## Cleanup wrap (Track B Phase 7)

### Prompt B-C-1 — cleanup opener

### ▶ Skill speaking ◀

> Last step: clean up the migration hub.

> You've done the work — projects relinked, memory seeded, binaries
> recovered. The migration hub itself is no longer load-bearing.

> Before you clean up, decide whether to keep a long-term record of how
> the migration ran. If yes, copy these out to a separate archive
> location now (they'll be deleted with the hub folder):

>   • `tracker.html` — final state of the migration
>   • `README - Final Transition to New Account.md` — the checklist
>   • Any per-project blueprints you might want to reference later

> Then clean up in this order:

> 1. In Cowork on the old account: open the migration hub project
>    and use *Settings → Archive project*. (Cowork has no delete,
>    only archive.)
> 2. In Explorer: delete the migration hub folder from disk.
> 3. In Cowork on this account: open the migration hub project
>    (the one you imported to run Track B) and use *Settings → Archive
>    project*.

> Both the archive AND the folder delete are required. Archive alone
> leaves an orphan folder on disk; folder delete alone leaves an orphan
> project registration.

> Say **done** to confirm you've completed the cleanup steps above and
> let me close out the migration. Say **later** if you want to leave
> the hub in place for now — I'll mark the migration as deferred, and
> when you re-invoke this skill against the hub later, I'll walk you
> through any items you skipped (deferred projects, scheduled tasks,
> binaries still pending) and re-offer cleanup. Say **quit** to stop
> without closing things out.


### Prompt B-C-2 — cleanup done

### ▶ Skill speaking ◀

> Hub cleaned up. Track B complete.


### Prompt B-C-3 — cleanup later

### ▶ Skill speaking ◀

> Cleanup deferred — the migration hub stays on disk and in Cowork.
> When you're ready, re-invoke this skill against the hub and pick
> **new** at the side-selection prompt; I'll recognize the deferred
> state, list anything you skipped along the way, offer to re-walk
> each section, and re-prompt for cleanup.

> Track B complete (cleanup pending).


---

## Track B resume — re-invocation on a deferred-cleanup migration

Fires when Step 5's phase routing finds `phase == "track-b-complete"`
AND `cleanup_done` is false or absent (the user previously chose
`later` at the cleanup wrap, or is running v1.6.1+ against a
pre-v1.6.1 tracker). Multi-project Track B only.

### Prompt B-Resume-closed — migration already fully closed

Fires when `phase == "track-b-complete"` AND `cleanup_done == true`.
One-liner; exits cleanly.

### ▶ Skill speaking ◀

> This migration is already complete and the hub was cleaned up on a
> prior run. Nothing left to do — pick a different project to work
> in. The tracker stays on disk as a record.


### Prompt B-Resume-1 — resume opener

Fires when re-entry is detected and there's work to revisit.

### ▶ Skill speaking ◀

> Welcome back. This migration is in deferred-cleanup state — Track B
> wrapped up but you chose **later** on the cleanup step. Here's
> what's still outstanding:

>   <conditional bullets — drop any whose count is 0>
>   • `<N_skipped_projects>` project(s) deferred during the
>     walk-through
>   • `<N_skipped_tasks>` scheduled task(s) not recreated
>   • `<N_pending_skills>` custom skill(s) still pending install
>   • `<N_unchecked_binaries>` binary file(s) still pending recovery
>     in `_ARTIFACTS_TO_RECOVER.md`

> Say **review** and I'll walk you through each section, offering one
> more pass per deferred item — you can decide per-item to do it now
> or keep it deferred. Say **cleanup-now** to skip the review and go
> straight to the cleanup wrap. Say **leave** to exit without
> changing anything; the migration stays in deferred-cleanup state and
> we can come back to it again later.


### Prompt B-Resume-2-projects — re-walk deferred projects?

Fires in resume sub-step 4a when there's at least one skipped project.

### ▶ Skill speaking ◀

> Deferred projects (`<N>`):

>   • `<project_name>` — `<session_count>` session(s), blueprint
>     `<present|absent>`
>   • …

> Say **re-walk** and I'll re-fire the per-project walk-through for
> these — you decide again per project (`done` / `skip` / `quit`).
> Say **skip-projects-section** to leave them deferred and move on to
> the next section. Say **quit** to stop the resume.


### Prompt B-Resume-2-tasks — re-walk deferred scheduled tasks?

Fires in resume sub-step 4b when there's at least one non-recreated
scheduled task.

### ▶ Skill speaking ◀

> Scheduled tasks not yet recreated on this account (`<N>`):

>   • `<taskId>` — `<cron_human>`
>   • …

> Say **re-walk** and I'll re-fire the per-task recreate flow.
> Each task: `recreate` (I'll create it on this account using the
> captured cron + prompt) / `skip` / `quit`. Say
> **skip-tasks-section** to leave them deferred and move on. Say
> **quit** to stop the resume.


### Prompt B-Resume-2-skills — re-walk pending custom skills?

Fires in resume sub-step 4c when at least one `custom_skills[]` entry
is still `installed: false` after re-reconciling against the
destination's live `.claude/skills/` listing.

### ▶ Skill speaking ◀

> Custom skill(s) not yet installed on this account (`<N>`):

>   • `<filename-1>.skill` (`<size>`)
>   • `<filename-2>.skill` (`<size>`)
>   • …

> Say **re-walk** and I'll re-surface them as clickable Save-skill
> cards (same flow as the first pass: `done` after you install
> what you want / `skip-all` to leave the rest / `quit`). Say
> **skip-skills-section** to leave them pending and move on. Say
> **quit** to stop the resume.


### Prompt B-Resume-2-binaries — re-walk unchecked binaries?

Fires in resume sub-step 4c when `_ARTIFACTS_TO_RECOVER.md` still has
unchecked items.

### ▶ Skill speaking ◀

> Binaries still pending recovery (`<N>` files across `<M>`
> conversation(s)). The list is in `_ARTIFACTS_TO_RECOVER.md` in the
> catch-all. Recover before the old account is deleted, or the files
> are lost permanently.

> Say **re-walk** and I'll re-fire the per-conversation binary
> recovery flow. Say **skip-binaries-section** to leave them deferred
> and move on. Say **quit** to stop the resume.


### Track B resume decisions

- **Resume detection at Step 5 phase routing**, before the inventory
  display. The tracker's `phase` + `cleanup_done` fields are
  authoritative. `cleanup_done` absent (pre-v1.6.1 tracker) is treated
  as false, preserving resume capability on older trackers.

- **Resume reviews deferrals, not redoes everything.** The re-walk
  only re-fires steps that have outstanding deferred items. Memory
  seed isn't offered because there's no per-item state to revisit —
  if the user wants to re-seed, they invoke memory-seed-prompt.md
  manually in Claude Chat.

- **Resume mutates tracker state mid-walk only for skipped projects.**
  The `skipped` → `pending` flip lets Step 8 iterate the projects via
  its normal pending-only filter. Scheduled tasks and binaries don't
  need a flip — their step-level filters already iterate non-completed
  items.

- **Each section is independently skippable.** A user can review
  projects without revisiting scheduled tasks, or jump straight to
  cleanup. The sub-step prompts wrap that as `skip-<section>-section`
  rather than `skip` (the latter would be ambiguous with per-item
  skips inside each re-walk).

- **Re-fired Phase 7 cleanup wrap closes the loop.** `done` →
  `cleanup_done: true` and the migration is fully closed (B-Resume-closed
  fires on any future re-invocation). `later` → still
  `cleanup_done: false`, so the user can resume again.


---

## Track B closing

### Prompt B-X-1 — closing

Fires after either B-C-2 or B-C-3 (or after B-C-1 if user quit at
cleanup). Adapts based on what was skipped.

### ▶ Skill speaking ◀

> Your projects are relinked on this account. Open any of them to pick
> up where you left off.

> <conditional reminders>

> Welcome to the new side.


Conditional reminders, each appended on its own line if the corresponding phase was skipped:

- Memory seed skipped: *"Memory seeding was skipped — Claude on this account will pick up your context conversation by conversation as you work, or you can run the seed prompt manually later from `memory-seed-prompt.md` in the hub."*
- Binary recovery skipped (with remaining items): *"Binary recovery has **<N_remaining>** files pending. `_ARTIFACTS_TO_RECOVER.md` lists them; recover before deleting the old account."*
- Some projects deferred in walk-through: *"**<N_skipped>** projects were deferred during the walk-through. The tracker shows them as pending; re-run the skill and pick \"new\" to come back to them."*
- Custom skills still pending: *"**<N_pending_skills>** custom skill(s) are still pending install. The `.skill` files are in `<hub>/skills/`; install anytime via *Cowork → Customize → + → Skills tab*."*
- Cleanup skipped: *"The migration hub stays on disk until you clean it up manually."*

### Track B closing decisions

- **Adapts to skipped phases.** Concrete reminders only when relevant.
  Avoids cluttering the closing with status of phases the user did
  complete; surfaces only the things they may need to come back to.
- **"Welcome to the new side"** as the closer — friendly, matches the
  "See you on the other side" voice at end of Track A.
