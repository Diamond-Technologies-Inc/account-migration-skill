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

```
═══[ Transitioning between 2 Claude Accounts ]═══

This will be handled in 3 phases. The first two are performed in your
old account and the third in your new account.

There is no way to directly import conversations into the new account.
The compromise is to extract the conversation history into individual
files which are stored within a new Cowork Project. This archive
project can then be searched and pruned as necessary.

This skill will walk you through the necessary steps and allow you to
make decisions about what data should be migrated.

Which side are you starting from?

- Say **"old"** — preparing your old account for transfer (Parts 1 and 2).
- Say **"new"** — picking up on your new account to relink everything
  that was prepared on the old side (Part 3).
```

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

# Part 1 — preparing claude.ai web/chat projects (source account)

## Prompt 1 — "give me your two input files"

Fires after the user says "old" at Prompt 0, preceded by the Part 1
banner.

```
Project migration — Track A (Reconstruct)

Hi. I'll take the projects and conversations from your old Claude
account, rebuild them as complete folders on disk, and hand them off
to your new account.

Before I start, I need two files. Both go into this project's folder.

File 1 of 2 — your data export

On claude.ai (the account you're migrating from):

1. Click your avatar → Settings → Privacy.
2. Click Export data. Anthropic emails you a download link, usually
   within a few minutes (occasionally longer).
3. Download the zip. It'll be named like
   `data-YYYY-MM-DD-…-batch-0000.zip`.
4. Move it into this project's folder. If your browser saved it
   straight to `Downloads\`, drag it over.

Heads up: if your export produced multiple batch files (rare, only for
very large accounts), bring all of them.

File 2 of 2 — a saved copy of your Chats page

The export has every conversation but doesn't say which project each
one belongs to. I'll recover that from a saved copy of your chats list.

1. On claude.ai, click Chats in the left sidebar.
2. Scroll all the way to the bottom of the list. The page only loads
   older chats as you scroll — if you don't reach the bottom, those
   chats won't be in the saved file. Stop scrolling when nothing new
   appears.
3. File → Save Page As → choose "Webpage, Complete".
     - Safari users: don't pick "Web Archive" — that's a binary
       format I can't read. Choose "Page Source" instead.
4. The default filename is `claude.html`. Rename it (anything works —
   `chats.html`, `AllChats.html`, whatever) before saving.
5. Save it into this project's folder. The save will also produce
   a same-named `_files\` folder next to it — leave that alongside,
   I won't use it but it's harmless.

Ready check

Say "ready" once both files are in the folder. I'll list what I found
before I start extracting, so you can confirm I'm working from the
right inputs.
```

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

```
Got it. In the folder I see:

  • Export: `<export_filename>` (<export_size>)
  • Chats save: `<chats_filename>` (<chats_size>)

Both look right. Unpacking the export and parsing the Chats save now.

This is pure file-sorting and organization as I split them into individual
files and build an index. Boring work and takes about half a minute. Hang
tight.
```

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

```
All set! Let me show you what I've found.

- ✓ **<N_total> conversations across <N_projects> projects** in your export.
- ✓ **<N_attributed>** are attributed to specific projects → we'll walk through these one at a time.
- ✓ **<N_orphans>** are loose chats with no project assignment.
- ✓ **<N_dropped>** were deleted from claude.ai → dropped.
```

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

```
I've opened your tracker.

First step: set up the catch-all. This will be a Cowork project that
collects any conversations without a clear home — both orphan chats
with no project assignment, and conversations from projects you choose
not to reconstruct.

You'll need to create this project yourself, because Claude can't create
Cowork projects. In Cowork:

1. Start a new project → **Start from scratch**.
2. Name it **Migrated Conversation History** (suggestion — use any
   name you'd like; whatever you choose will appear on the tracker and
   in the prompts that follow).
3. Come back to this chat to continue.

Say **"ready"** when the project is created. Once you do, I'll bring
up a folder picker so you can select the project folder you just
created.
```

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

```
Got it. Bringing up the folder picker now so you can select
**<catchall_name>**'s folder.
```

## Prompt 4 — first per-project pick

Verbose form (full rules + per-project import instruction). Subsequent
prompts (Pattern 5–N) drop the verbose rules block.

```
Catch-all ready: **<catchall_name>** at
`<catchall_folder_path>`.

Heads up: the export contains both your active and archived chat
projects. If you want to include any of the archived projects in this
transition, you'll need to unarchive them first — otherwise you won't
be able to import them.

Now I'll walk through your <N_projects> projects in alphabetical order.
For each one we'll do the same thing:

1. You'll import the project from claude.ai into a new Cowork project
   on this account. In Cowork: **New project → Import project →
   select the project from your chat list**. Cowork creates a local
   folder for it.
2. Say **"ready"** once the import is done — or say **"skip"** to
   route the project's conversations to the catch-all without
   importing (good for projects you already know you don't want to
   migrate), or **"quit"** to stop the migration entirely.
3. If you said **"ready"**, I'll ask **pick**, **skip**, or **quit**
   again:
   - **pick** — I'll have you select the newly-imported folder and
     reconstruct the project's conversation history into it. If you
     point me at an existing folder you've been working in instead,
     I'll leave it alone and route conversations to **<catchall_name>**.
   - **skip** — I won't reconstruct the project. Its conversations
     still go to **<catchall_name>** for manual review.
   - **quit** — stop the migration entirely. The tracker stays on
     disk so you can resume later.

--- Project 1 of <N_projects> ---

**<project_name>** — <N_convs> conversations, <N_docs> knowledge docs.

To include it: in Cowork, **New project → Import project → select
"<project_name>"** from your chat list, then say **"ready"** here.

Or say **"skip"** (route to catch-all without importing) or **"quit"**
(stop the migration).
```

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

```
To continue, do you want to **pick** or **skip** this project?
```

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

```
Picker was cancelled — that might've been a mistake.

**pick** to re-open the folder picker, **skip** to route this project's
conversations to **<catchall_name>**, or **quit** to stop the migration
entirely.
```

## Post-pick folder-picker bridge

Fires immediately after the user says "pick" in any Prompt 4–N, and
immediately before the skill calls `request_cowork_directory` (picker
mode, no path). Parallel to Prompt 3.5 for the catch-all. Folder access
is always the picker — never guess a path, never ask the user to type
one.

```
Bringing up the folder picker so you can select **<project_name>**'s folder.
```

If the user said "skip", this bridge does NOT fire — skip goes straight
to the post-pick confirmation line.

## Post-pick confirmation lines

Brief — these likely scroll past as the next per-project prompt loads,
so they're acknowledgment, not detail. One of three depending on what
the user did:

```
**<project_name>** picked (empty folder). Project will be reconstructed.

**<project_name>** picked (existing folder). Conversations will be stored in **<catchall_name>**.

**<project_name>** project skipped. Its conversations will be stored in **<catchall_name>** for your final review.
```

Then the next per-project prompt fires immediately.

## Pattern — Prompts 5 through N: subsequent per-project picks

Same structure as Prompt 4's per-project block, minus the catch-all
confirmation and the verbose walk-through-intro + rules. Each subsequent
prompt is:

```
--- Project N of <N_projects> ---

**<project_name>** — <N_convs> conversations, <N_docs> knowledge docs.

To include it: in Cowork, **New project → Import project → select
"<project_name>"** from your chat list, then say **"ready"** here.

Or say **"skip"** (route to catch-all without importing) or **"quit"**
(stop the migration).
```

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

## Part 2 Prompt 1 — opener

Fires immediately after the Part 1 wrap and the Part 2 banner. Cowork's
internal session storage is intentionally walled off to skills — Part 2
does not capture conversation history, memory.md, or working-folder
attachments. The opener sets that expectation up front.

```
Part 2 handles your existing Cowork projects on this machine — the
ones you've been working in with Cowork on the desktop.

Before we start, an important heads-up: Cowork's internal session
storage is walled off to skills by design, so three things from each
Cowork project **don't migrate** via this skill — you'll need to
handle them manually:

- **Working-folder attachments** (which other folders are linked to
  each project). Open each Cowork project on your old account and note
  these — you'll re-attach them on the new account.
- **Cowork session history** (your past chats with Claude inside
  Cowork on these projects). Capture anything important before
  transitioning.
- **Project memory** (`memory.md` if you've used Cowork sessions inside
  the project). Same wall — also won't carry across.

What this skill *does* preserve: your working files stay exactly where
they are, and I write a `_PROJECT_BRIEF.md` next to them describing
what's there and what didn't migrate.

I can't discover your Cowork projects automatically, so I'll need you
to hand each one over by picking its folder.

When you're ready, say **"continue"** and I'll bring up a folder
picker. Pick the folder for one Cowork project at a time. When you've
handed me all of them, cancel the picker and I'll confirm you're done.

If you don't have any Cowork projects you want to migrate, say
**"skip"** and I'll go straight to the wrap-up.

**continue** or **skip**?
```

## Part 2 Prompt 1.5 — folder picker bridge

Fires after user says "continue" at Prompt 1, AND after the cancel-confirmation
re-loops the picker. Same wording either way.

```
Bringing up the folder picker. Pick the folder for one of your Cowork
projects.
```

## Part 2 Prompt 2 — per-folder processing confirmation

Fires after each successful folder pick. Writes the brief, confirms,
reopens the picker. The simpler form reflects Part 2's degraded scope
(working files preserved + brief written; nothing else migrates per the
session-storage wall).

```
Got it: **<folder_name>**.

I wrote `_PROJECT_BRIEF.md` next to your working files, plus
`transition-data/migration-prompt.md` — a prompt for you to run in
this project on your old-account Cowork before deletion (it produces
the blueprint that becomes the bootstrap for your new-account version
of this project). Your folder contents are untouched.

Pick another Cowork project, or cancel when you're done.
```

The brief carries the full "what doesn't migrate" caveats so they're
preserved in writing alongside each project. The migration-prompt is
the user-side path to generating a `project-blueprint.md` for Part 2
projects, since the skill itself can't reach the Cowork session data.

## Part 2 cancel-confirmation

Fires when the user cancels the picker mid-loop.

```
Picker was cancelled. Are you done picking Cowork projects?

Say **"done"** to wrap up Part 2, **"continue"** to bring the picker
back up, or **"quit"** to stop the migration entirely.
```

## Part 2 wrap

Fires after "done" at the cancel-confirmation, or after "skip" at
Prompt 1.

```
▶ Part 2 complete ◀

<N_cowork> Cowork projects handled. Each one has a `_PROJECT_BRIEF.md`
next to its working files plus a `transition-data/migration-prompt.md`
with the prompt to run in that project's old-account Cowork session.
Your folders' existing contents are unchanged.

Reminder of what you'll need to do manually before deleting the old
account:

- **Run each `transition-data/migration-prompt.md`** in the matching
  Cowork project on the old account. Save the response as
  `transition-data/project-blueprint.md`.
- **Capture your global memory** — see the Track A wrap (coming up
  next) for the prompt to run.
- **Recover the binary files** flagged in
  `<catchall_name>/_ARTIFACTS_TO_RECOVER.md`.
- **Note each Cowork project's working-folder attachments** — Cowork's
  internal storage doesn't migrate, so re-attach manually on the new
  account.

Each project's `_PROJECT_BRIEF.md` has a per-project version of these
reminders.
```

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

## Custom-skills opener

```
One more thing before we wrap up Track A — your custom Cowork skills.

I've already saved a fresh copy of this migration skill into the
`skills/` subfolder next to your tracker — so you'll have it on the
new account without having to find the original installer.

If you've installed OTHER custom skills or plugins on the old account
beyond what came bundled with Cowork (the `anthropic-skills` plugin),
you'll need their installer files to re-install on the new account.
Cowork's installed-skills location on disk is generally walled off, so
the easiest path is to gather their original installer files from
where you got them.

To bring additional custom skills across:

1. In another Cowork session on the old account, ask Claude:
   *"list my installed skills"*. Note which are part of the default
   `anthropic-skills` plugin (no action needed) versus custom ones you
   imported yourself.
2. For each custom skill: find its original installer (typically a
   `.skill` file). Common locations: your `Downloads\` folder, a
   source repo, or the marketplace / distribution you got it from.
3. Drop each installer file into the `skills\` subfolder alongside the
   migration skill I already put there.

Say **"ready"** once you've added them (or **"skip"** if you have no
other custom skills to bring — the migration skill is already in
place), or **"quit"** to stop the migration.
```

## Custom-skills confirmation — files found

Fires after the user says "ready" and the skill detects one or more
`.skill` (or `.zip`) files in the hub's `skills/` subfolder.

```
Got it. In `skills/` I see:

  • <filename>.skill (<size>)
  • …

The Track B handoff will point at these so you can re-install them on
the new account.
```

## Custom-skills confirmation — empty folder or no folder

Fires when the user says "ready" but the `skills/` subfolder is empty
or doesn't exist. Soft re-ask, not an error.

```
I see `account-migration.skill` in `skills/` (I put that there) but no
other custom skills yet — either you have no other custom skills to
bring (in which case say **"skip"** and we'll move on with just the
migration skill) or your copy hasn't landed yet (in which case drop
them in and say **"ready"** again).
```

## Custom-skills confirmation — skip

Fires after the user says "skip". One line; the next prompt fires
immediately.

```
No other custom skills to migrate — moving on. (The migration skill
itself is already saved in `skills/account-migration.skill` for the
new-account install.)
```

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

---

# Prompt N+1 — all-skip final-gate

Fires only when the user reached the end of the walk-through without
picking a folder for any of the projects. The catch-all still has all
the conversation history (orphans + per-project subfolders), so nothing
is lost — this is a "are you sure?" confirmation, not a "stop, you'll
lose everything" alarm.

```
Walk-through done — and you skipped every project.

**<catchall_name>** now contains all your conversation history (orphan
chats + a per-project subfolder for each skipped project), but no
project folders will be reconstructed on disk.

That's a valid outcome if you only wanted to preserve the chat history
for review. If it was intentional, say **"yes, finalize"** to wrap up
Track A. If you'd like to revisit any project choices, just tell me
which one.
```

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

```
Track A complete!

Cleaned up: removed the export zip, the saved Chats page, the parse
artifacts, and the extracted transcripts from this folder. Your
reconstructed projects, the catch-all folder, the tracker, and your
`skills/` subfolder are all intact.

Next: Track B — bring everything into your new account.

To get started on the new account, you'll do four quick setup steps:

1. Make sure the migration hub folder is on the new-account machine
   (same workstation, OneDrive/Dropbox/Drive sync, or copy it over).
2. Install this skill on the new account: **Customize → + → Skills →
   upload** `account-migration.skill` from this hub's `skills/`
   subfolder.
3. Import the migration hub itself as a Cowork project on the new
   account using **New project → Choose existing folder**. Name it
   the same as it was on this account.
4. Open a conversation in that project, tell Claude *"continue the
   migration from the old side"*, and pick **"new"** when asked.

After that the skill drives the rest — memory seeding, project
relinks, binary recovery, validation, and cleanup.

One more thing to do **before** you start Track B (or before deleting
this account, whichever comes first): capture your global memory. In
**Claude Chat** (claude.ai in your browser, or the Chat surface in
Claude Desktop — NOT Cowork), sign in to the OLD account, start a
no-project conversation, and paste one of the prompts in
`memory-capture-prompt.md` in this folder (the file walks you through
choosing between the wholesale and corporate-carve-out variants).
Save Claude's response as `memory-capture.md` in this same folder —
Track B will pick it up during the memory seeding phase.

Full step-by-step is in **`README - Final Transition to New Account.md`**
in this folder. The skill-assisted path is at the top; manual fallback
instructions follow.

Run those four steps when you're ready and I'll see you on the other side.
```

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

```
Project migration — Track B (Relink)

Track B picks up on the new account. I can see I'm running inside the
migration hub project, which means I can read the tracker the old side
left for me. The tracker tells me which projects you reconstructed,
which ones you routed to the catch-all, your Cowork projects from the
old account, and where the recovery checklist lives.

The actual content — your project folders, the catch-all, the
blueprints, the recovery checklist — is in sibling folders on this
machine that aren't linked to me yet. As we walk through each project
you'll create a new Cowork project pointing at its folder, and I'll
ask for access at the moment I need to verify what's there.

Here's the plan:

1. Seed your global memory on this account from the snapshot the old
   side produced.
2. Set up the catch-all as a Cowork project here.
3. Walk through each project from the old side. For each one, you'll
   create a new Cowork project using "Choose existing folder" pointing
   at its on-disk folder. I'll verify the blueprint and inventory the
   contents, then walk you through pasting custom instructions and
   bootstrapping a first conversation.
4. Recover any binary files (.docx, .xlsx, etc.) that were referenced
   in transcripts but couldn't be extracted from the export.
5. Validate that everything carried across the way you expected, then
   clean up the migration hub.

Say **"ready"** to start, **"hold"** if you need a minute, or **"quit"**
to stop the migration.
```

## Prompt B-1b — Track B opener (no hub detected, picker needed)

Fires when the skill is NOT running inside the migration hub project
(invoked from a different Cowork project, or a no-project conversation).
Preceded by the Part 3 banner.

```
Project migration — Track B (Relink)

Track B picks up on the new account. The migration hub from the old
side has the tracker I need to read — it tells me which projects you
reconstructed, which ones you routed to the catch-all, your Cowork
projects from the old account, and where the recovery checklist lives.

I'm not currently running inside the hub project. Point me at the hub
folder and I'll read the tracker from there. It's the folder that
contains `tracker.html`, `README - Final Transition to New Account.md`,
and a `skills/` subfolder.

The actual content — your project folders, the catch-all, the
blueprints, the recovery checklist — is in sibling folders on this
machine that aren't linked to me yet. As we walk through each project
you'll create a new Cowork project pointing at its folder, and I'll
ask for access at the moment I need to verify what's there.

Here's the plan once I have the hub:

1. Seed your global memory on this account from the snapshot the old
   side produced.
2. Set up the catch-all as a Cowork project here.
3. Walk through each project from the old side. For each one, you'll
   create a new Cowork project using "Choose existing folder" pointing
   at its on-disk folder. I'll verify the blueprint and inventory the
   contents, then walk you through pasting custom instructions and
   bootstrapping a first conversation.
4. Recover any binary files (.docx, .xlsx, etc.) that were referenced
   in transcripts but couldn't be extracted from the export.
5. Validate that everything carried across the way you expected, then
   clean up the migration hub.

Say **"ready"** when you're ready and I'll bring up a folder picker
for the hub. Say **"hold"** if you don't have the hub on this machine
yet, or **"quit"** to stop the migration.
```

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

## Prompt B-2 — hub picker bridge

Fires only on the B-1b path, after user says "ready". Skipped on the
B-1a path.

```
Got it. Bringing up the folder picker now so you can select the
migration hub folder.
```

## Prompt B-3 — silent tracker parse + validation

Tracker parsing is instantaneous so there's no "hang tight" message
analogous to Track A's Prompt 2. Happy path goes silently to B-4.
Failure branches below.

### Prompt B-3b — partial corruption (JSON unparseable, HTML table readable)

```
The tracker's JSON state block is unreadable, but I can see the
rendered table inside the file. I'll work from that — counts and
dispositions are fine, but I won't have exact folder paths to pre-fill,
so you'll be navigating the folder picker by name for each project.

Continuing.
```

### Prompt B-3c — disaster (no JSON, no usable HTML table)

```
I couldn't read the tracker file usefully. The handoff state and the
rendered table are both unrecoverable, and without the tracker I don't
have a list of what projects to walk through or where their folders
live.

Options:

- Say **"pick"** to point me at a different folder. The hub may have
  been copied somewhere else, and the one I just looked at is the
  damaged copy.
- Say **"quit"** to stop. Open the `README - Final Transition to New
  Account.md` in the hub folder and follow it manually — it has the
  same steps as this walk-through, just non-interactive. You can also
  try repairing the tracker (open it in a text editor, or restore from
  the Cowork sidebar artifact on the old account if you still have
  access) and re-run Track B once it's parseable.
```

## Prompt B-4 — hub inventory display

Mirror of Track A's Prompt 2.5. Plain `- ✓` checkmarks. Conditional
rendering: drop any bullet whose count is 0.

```
Got it. From the tracker:

- ✓ **<N_part1_reconstructed>** reconstructed projects from your old web/chat side.
- ✓ **<N_part2_cowork>** Cowork projects from the old account.
- ✓ The catch-all: **<catchall_name>** with **<N_orphans>** orphan
   conversations and **<N_part1_catchall>** archived per-project subfolders.
- ✓ **<N_recover>** binary files to recover from claude.ai before
   old-account deletion.
- ✓ **<N_custom_skills>** custom skills to install on this account.

Five things to do: seed your global memory, set up the catch-all,
walk through each project, recover the binaries, and validate.
```

---

## Memory seed (Track B Phase 2)

Fires after B-4. Before any per-project work, the user seeds Claude's
account-level memory on the new account from the snapshot the old side
produced. Per-project conversations later in Track B inherit this
context automatically.

### Prompt B-MS-1 — memory seed opener

```
First step: seed your global memory.

The old account produced `memory-capture.md` — a snapshot of
everything Claude knew about you globally on that account: your role,
work context, communication preferences, recurring patterns, and so
on. On this account Claude doesn't know any of that yet, so we'll
load it now before anything else.

Heads up: account-level memory is read and written through **Claude
Chat** (claude.ai in a browser, or the Chat surface in Claude
Desktop), not in Cowork. So you'll do this part there — not in this
Cowork conversation — then come back here to continue.

To seed it:

1. Open **Claude Chat** (claude.ai in a browser, or the Chat surface
   in Claude Desktop — NOT Cowork). Sign in to your NEW account.
2. Start a new conversation — **no project selected** (just a fresh
   chat).
3. Attach `memory-capture.md` from the migration hub folder to the
   conversation.
4. Paste this prompt:
   *"I'm migrating from a previous Claude account. The attached
   `memory-capture.md` is a snapshot of everything you knew about me
   there — my role, work context, communication preferences,
   technical domains, recurring workflows, and other persistent
   context. Please review it and commit the relevant facts to your
   memory of me on this account. Be thorough."*
5. Wait for Claude to confirm what's been saved.

Come back here (Cowork) and say **"done"** when finished. Or
**"skip"** if you didn't capture memory on the old side (or don't
want global memory seeded), or **"quit"** to stop the migration.
```

### Prompt B-MS-2 — memory seed done confirmation

```
Memory seeded. Claude on this account now has your global context for
the per-project setup that follows.
```

### Prompt B-MS-3 — memory seed skip confirmation

```
Memory seeding skipped — Claude on this account will pick up your
context conversation by conversation as you work.
```

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

```
Next: set up the catch-all on this account.

The catch-all on disk is at:
**<catchall_folder_path>**

In Cowork:
1. Start a new project → **Choose existing folder**.
2. Navigate to the path above and select it.
3. Name it **<catchall_name>** — same as on the old side, so the
   per-project routing language in the walk-through stays consistent.
4. Come back here.

Say **"ready"** when the project is created. I'll bring up a folder
picker so I can access it and confirm the orphans + per-project
subfolders are intact.
```

### Prompt B-5.5 — catch-all picker bridge

```
Got it. Bringing up the folder picker now so I can access
**<catchall_name>**'s folder.
```

### Prompt B-5.6 — catch-all post-pick confirmation

```
Catch-all confirmed: **<N_orphans>** orphan conversations and
**<N_part1_catchall>** per-project subfolders, all present. You'll
review the contents on the new account inside **<catchall_name>** once
the walk-through is done.
```

---

## Walk-through (Track B Phase 4)

Per-project relink iteration. Covers Part 1 reconstructed + Part 2
Cowork projects only. Part 1 catch-all-routed projects are reviewed
inside the catch-all (set up in B-5), not walked individually.

### Prompt B-6 — walk-through verbose intro

```
Now I'll walk through your **<N_walkthrough>** projects in order —
**<N_part1_reconstructed>** reconstructed from your web/chat side, plus
**<N_part2_cowork>** Cowork projects from the old account. For each one
we'll do the same thing:

1. You'll create a new Cowork project on this account using **New
   project → Choose existing folder**, then select the project's
   on-disk folder. The folders are already where the old-side skill
   left them — same paths if both accounts run on this machine, or
   wherever you copied them to.
2. Say **"ready"** once the project is created — or **"skip"** to
   defer this project (you can come back to it later, the on-disk
   folder isn't touched), or **"quit"** to stop the migration.
3. After "ready" I'll bring up a folder picker so I can access the
   project's folder, verify the blueprint is there, and give you the
   short checklist for finishing the setup (paste custom instructions,
   bootstrap a first conversation).

The **<N_part1_catchall>** projects you routed to the catch-all on the
old side aren't in this walk-through — they live as subfolders inside
**<catchall_name>** for you to review there. I'll remind you when we
wrap.
```

### Pattern — per-project prompts B-7 through B-N

```
--- Project N of <N_walkthrough> ---

**<project_name>** — <source_kind>
**<N_convs>** conversations · **<N_docs>** knowledge docs
Folder: `<folder_path>`

In Cowork: **New project → Choose existing folder**, select the folder
above, then say **"ready"** here.

Or **"skip"** (defer this project) or **"quit"** (stop the migration).
```

`<source_kind>` values: `reconstructed from web/chat` (Part 1 empty pick) or `Cowork from old account` (Part 2).

### Per-project picker bridge (after "ready")

```
Got it. Bringing up the folder picker so I can access
**<project_name>**'s folder.
```

### Per-project post-pick — blueprint found (happy path)

```
Got it. **<project_name>** has its blueprint and knowledge
files ready. Finish setting it up on this account:

1. Open the new Cowork project you just created.
2. Open `transition-data/project-blueprint.md`. Copy the **Custom
   Instructions** section into the project's settings.
3. Start a conversation in the project. Paste this prompt (it's
   also saved in `_PROJECT_BRIEF.md`'s "Resuming on the new account"
   section if you'd rather grab it from there):
   *"This is a project I'm migrating from my old Claude account.
   Read `transition-data/project-blueprint.md` for full context, then
   treat its **Recommended Starting Prompt** section as my first
   directive — that's the project-tailored resumption point.
   Knowledge files referenced in the blueprint are in `knowledge/`
   (for reconstructed projects) or in this project's folder (for
   Cowork projects)."*

Say **"done"** when finished to move to the next project. Or
**"skip ahead"** to move on without finishing the bootstrap (you can
come back to it later). I won't verify the steps above — I don't have
access to inspect the new Cowork project's settings.
```

### Per-project post-pick — blueprint missing (Part 2 only)

Fires when a Part 2 Cowork project's folder is picked but
`transition-data/project-blueprint.md` isn't present. Means the user
didn't run the migration-prompt on the old account before deletion.

```
**<project_name>**'s folder is accessible, but I don't see a
`transition-data/project-blueprint.md`. That means the per-project
migration prompt didn't get run on the old account before deletion.

You can either:

- Say **"continue"** to finish setting up the project anyway. You'll
  paste the custom instructions and bootstrap by hand from whatever
  you remember about the project. Knowledge files are still
  accessible from the on-disk folder.
- Say **"go back"** if you still have access to the old account and
  can run the migration prompt now (in that Cowork project, paste the
  contents of `transition-data/migration-prompt.md`, save the response
  as `transition-data/project-blueprint.md`). Then come back here and
  say "done".
- Say **"skip"** to defer this project entirely.
```

### Per-project post-pick — folder wrong / unexpected structure

```
I can access the folder you picked, but it doesn't look like
**<project_name>**'s folder — I expected to see <expected_marker>
and instead I see <found_contents>.

Maybe you picked the wrong folder? Say **"pick"** to try the folder
picker again, **"skip"** to defer this project, or **"quit"** to stop.
```

### Per-project skip confirmation

Fires when user said "skip" at the per-project prompt (no picker fires).

```
**<project_name>** deferred. You can come back to it later by
re-running the skill and picking "new" — the tracker will still show
this project as pending.
```

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
- **`done` vs `skip ahead` after the happy-path checklist.** "done"
  means "I finished the steps, next project please"; "skip ahead"
  means "I'll do the bootstrap later, move on now." Distinct meanings.
- **`continue` / `go back` / `skip` in blueprint-missing branch.**
  Three actions: proceed without blueprint, go back to old account
  and generate one, or skip this project.

---

## Binary recovery (Track B Phase 5)

Walks the `_ARTIFACTS_TO_RECOVER.md` checklist interactively. Conversation
by conversation, since the user opens each conversation once on
claude.ai and downloads all its referenced files in one pass. Skill
ticks checkboxes after the user confirms each conversation done.

### Prompt B-BR-1 — binary recovery opener

```
Next: recover the binary files that couldn't be extracted from the
export.

When Track A processed your conversations, it found **<N_recover>**
files (.docx, .xlsx, .pdf, .pptx, etc.) that were referenced in
transcripts but not included in the data export. They're listed in
`<catchall_name>/_ARTIFACTS_TO_RECOVER.md`.

These files only exist inside conversations on claude.ai in your old
account. Once that account is deleted, they're gone permanently. If
you've already started the old-account deletion process, recover what
you can now.

We'll walk through them conversation by conversation — opening each
conversation in the old account, downloading the files, and saving
them to disk next to the transcript. I'll tick off each conversation's
checkboxes after you confirm you've recovered its files.

The files span **<N_convs_with_binaries>** conversations. Some have
one file, some have several.

Say **"ready"** to start the first conversation, **"skip"** if
you've already recovered everything or don't want to recover any of
it, or **"quit"** to stop. (If you skip or quit, the unchecked items
remain in `_ARTIFACTS_TO_RECOVER.md` so you can come back later.)
```

### Pattern — per-conversation recovery prompts

```
--- Conversation N of <M> ---

**<conversation_title>**
<destination_label>
Transcript: `<transcript_relative_path>`

Files to recover (<N_files>):
  • <filename_1>
  • <filename_2>
  • …

On claude.ai (old account):
1. Open the conversation: <claude.ai_url>
2. Download each file from the conversation's file panel.
3. Save them to:
   `<artifacts_folder_relative_path>`

Say **"done"** when finished, **"skip"** to defer this conversation,
or **"quit"** to stop.
```

`<destination_label>` is one of three strings derived from the conversation's bucket:
- Part 1 reconstructed → `Project: <project_name> (reconstructed)`
- Part 1 routed to catch-all → `Project: <project_name> (routed to catch-all)`
- Catch-all orphan → `Catch-all orphan (no project)`

### Prompt B-BR-wrap — binary recovery wrap

```
Binary recovery <complete | partial>. **<N_recovered>** files
recovered across **<N_done_convs>** conversations.
```

If skipped any, append:

```

**<N_remaining>** files in **<N_skipped_convs>** conversations are
still pending. They're in `_ARTIFACTS_TO_RECOVER.md` with unchecked
boxes. Recover them before deleting the old account, or re-run the
skill and pick "new" to resume.
```

### Edge case — no binaries to recover

If `_ARTIFACTS_TO_RECOVER.md` has zero unchecked items (or doesn't
exist), B-BR-1 doesn't fire. Skill silently moves to validation with a
one-liner:

```
No binaries to recover — moving on.
```

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

## Validation (Track B Phase 6)

### Prompt B-V-1 — validation opener

```
Almost done — let's validate that your global memory came across
correctly.

Validation reads account-level memory, which is exposed through
**Claude Chat** (claude.ai in a browser, or the Chat surface in
Claude Desktop), not in Cowork. So like the seeding step, this part
happens in Claude Chat, then you come back here.

To run validation:

1. Open **Claude Chat** (claude.ai in a browser, or the Chat surface
   in Claude Desktop — NOT Cowork). Sign in to your NEW account.
2. Start a new conversation — **no project selected**.
3. Paste this prompt:
   *"Based on everything you know about me, tell me: who I am and
   what I do, what projects or topics are top of mind, how I prefer
   to communicate, any tools or domains I work in, and anything else
   you consider important context. Be thorough — I'm checking that a
   migration was successful."*
4. Compare Claude's response against `memory-capture.md` in this hub
   folder.
5. If anything important is missing or wrong, you have two options:
   - Add a memory edit on the Claude Chat conversation directly.
   - Attach `memory-capture.md` again and ask Claude to fill in the
     gaps.

Come back here (Cowork) and say **"done"** when validation looks
good. **"skip"** if you didn't seed memory (or want to skip
validation), or **"quit"** to stop.
```

### Prompt B-V-2 — validation done

```
Validated. Last step: clean up the migration hub.
```

### Prompt B-V-3 — validation skip

```
Validation skipped — moving on to cleanup.
```

---

## Cleanup wrap (Track B Phase 7)

### Prompt B-C-1 — cleanup opener

```
Last step: clean up the migration hub.

You've done the work — projects relinked, memory seeded, binaries
recovered, validation passed. The migration hub itself is no longer
load-bearing.

Before you clean up, decide whether to keep a long-term record of how
the migration ran. If yes, copy these out to a separate archive
location now (they'll be deleted with the hub folder):

  • `tracker.html` — final state of the migration
  • `README - Final Transition to New Account.md` — the checklist
  • Any per-project blueprints you might want to reference later

Then clean up in this order:

1. **In Cowork on the old account:** open the migration hub project
   and use **Settings → Archive project**. (Cowork has no delete,
   only archive.)
2. **In Explorer:** delete the migration hub folder from disk.
3. **In Cowork on this account:** open the migration hub project
   (the one you imported to run Track B) and use **Settings → Archive
   project**.

Both the archive AND the folder delete are required. Archive alone
leaves an orphan folder on disk; folder delete alone leaves an orphan
project registration.

Say **"done"** when finished, or **"skip"** if you want to keep the
hub around for now (for example, to come back to a deferred project
or recover binaries you missed). The tracker stays usable if you
re-run the skill and pick "new" later.
```

### Prompt B-C-2 — cleanup done

```
Hub cleaned up. Track B complete!
```

### Prompt B-C-3 — cleanup skip

```
Cleanup skipped — the migration hub stays on disk and in Cowork. You
can clean it up later via the same steps when you're ready.

Track B complete!
```

---

## Track B closing

### Prompt B-X-1 — closing

Fires after either B-C-2 or B-C-3 (or after B-V-2 if user quit at
cleanup). Adapts based on what was skipped.

```
Your projects are relinked on this account. Open any of them to pick
up where you left off.

<conditional reminders>

Welcome to the new side.
```

Conditional reminders, each appended on its own line if the corresponding phase was skipped:

- Memory seed skipped: *"Memory seeding was skipped — Claude on this account will pick up your context conversation by conversation as you work, or you can run the seed prompt manually later from `memory-seed-prompt.md` in the hub."*
- Binary recovery skipped (with remaining items): *"Binary recovery has **<N_remaining>** files pending. `_ARTIFACTS_TO_RECOVER.md` lists them; recover before deleting the old account."*
- Some projects deferred in walk-through: *"**<N_skipped>** projects were deferred during the walk-through. The tracker shows them as pending; re-run the skill and pick \"new\" to come back to them."*
- Cleanup skipped: *"The migration hub stays on disk until you clean it up manually."*

### Track B closing decisions

- **Adapts to skipped phases.** Concrete reminders only when relevant.
  Avoids cluttering the closing with status of phases the user did
  complete; surfaces only the things they may need to come back to.
- **"Welcome to the new side"** as the closer — friendly, matches the
  "See you on the other side" voice at end of Track A.
