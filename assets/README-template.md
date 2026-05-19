# Final Transition to New Account

You're at the boundary between Track A (old account preparation) and
Track B (new account setup). Your old account has been prepared:

- Project folders reconstructed in place or routed to **<catchall_name>**
  (Part 1 — web/chat projects).
- Your Cowork project folders annotated with `_PROJECT_BRIEF.md` and,
  where applicable, a `transition-data/project-blueprint.md`
  (Part 2 — desktop projects).
- Artifact recovery checklist written at
  `<catchall_name>/_ARTIFACTS_TO_RECOVER.md`.
- Custom skills (if any) collected in this hub's `skills/` subfolder,
  including `account-migration.skill` itself for use on the new account.
- `memory-capture-prompt.md` and `memory-seed-prompt.md` written to
  this hub for the memory-capture/seed flow across accounts.

## How to run Track B (recommended: skill-assisted)

The same skill that ran Track A drives Track B. Do these setup steps
once on the new account, then invoke the skill and it walks you
through everything else.

### Setup (one-time)

1. **Sign into Cowork on the new account.**

2. **Make sure the migration hub folder is on this machine.** Three
   common scenarios:
   - Same workstation as the old account → the folder is already at
     its original path.
   - OneDrive / Dropbox / Drive sync → wait for the sync to finish on
     this machine before continuing.
   - Manual transfer (USB drive, network share, etc.) → put the hub
     folder wherever you'd like on this machine.

3. **Install the migration skill on this account.** In any Cowork
   session, click **Customize** in the sidebar → click the **+**
   button → click the **Skills** tab → upload `account-migration.skill`
   from this hub's `skills/` subfolder. (If `skills/` is empty or the
   `.skill` file is missing, see *"If you don't have the skill
   installer"* below.)

4. **Import the migration hub as a Cowork project on this account.**
   - Start a new project → **Choose existing folder**.
   - Browse to and select this migration hub folder.
   - Name it the same as it was on the old account (default is the
     folder name, which is usually what you want).

### Run the skill

5. Open a new conversation inside the imported hub project.
6. Tell Claude: *"continue the migration from the old side"* (or
   invoke the skill directly if your install supports a slash command).
7. When the skill asks which side, say **"new"**.

The skill walks you through:

1. **Memory seed** — seed your global memory on this account from
   the snapshot captured on the old side.
2. **Catch-all setup** — re-create the catch-all as a Cowork project
   on this account.
3. **Per-project walk-through** — for each reconstructed project and
   each Cowork project, create a new Cowork project pointing at its
   on-disk folder, paste in custom instructions from the blueprint,
   and bootstrap a first conversation.
4. **Binary recovery** — walk through `_ARTIFACTS_TO_RECOVER.md`,
   downloading binary files from claude.ai before the old account is
   deleted.
5. **Validation** — confirm your global memory carried across.
6. **Cleanup** — archive and delete the migration hub when everything
   is in place.

You can **"skip"** any phase or **"quit"** at any time and resume
later — the tracker preserves your state between sessions.

### If you don't have the skill installer

If the migration skill itself wasn't included in the `skills/` folder
(or you've lost the `.skill` file), you have two options:

- Re-source it from wherever you originally got it (a marketplace,
  source repo, or maintainer distribution).
- Skip Track B's skill-assisted flow and use the manual fallback
  steps below.

---

## Manual steps (fallback)

These are the same steps the skill performs, written so you can do
them by hand if the skill isn't available or you prefer manual.

### Step 0 — Capture global memory (BEFORE deleting the old account)

Cowork's auto-memory doesn't migrate between accounts. If
`memory-capture.md` doesn't exist yet in this hub folder, capture it
now from the **old** account before deletion.

In **Claude Chat** (claude.ai in a browser, or the Chat surface in
Claude Desktop — NOT Cowork), sign in to the OLD account and start a
new conversation with no project selected. Paste one of the prompts
saved at `memory-capture-prompt.md` in this hub folder (the file walks
you through choosing between the wholesale and corporate-carve-out
variants). Save Claude's response as `memory-capture.md` next to this
README.

(Account-level memory is read and written through Claude Chat —
claude.ai web or Claude Desktop's Chat surface — not Cowork. That's
why this step happens there.)

### Step 1 — Seed global memory on the new account

In **Claude Chat** (claude.ai in a browser, or the Chat surface in
Claude Desktop — NOT Cowork), sign in to the NEW account and start a
new conversation with no project selected. Attach `memory-capture.md`
from this hub folder, then paste the prompt saved at
`memory-seed-prompt.md`. Claude will commit the captured facts to
its memory on this account.

(Same reason as Step 0 — account-level memory lives on the Claude
Chat surface, not in Cowork.)

### Step 2 — Recover unrecovered artifacts

- [ ] Open `<catchall_name>/_ARTIFACTS_TO_RECOVER.md`.
- [ ] For each unchecked file:
  1. Open the listed conversation on `claude.ai` in your old account.
  2. Find the file in the conversation's file panel.
  3. Download it. Save it next to the conversation's transcript on disk.
  4. Tick the box in the recovery file.
- [ ] If a build script was captured by `create_file` (visible in the
  conversation's `<conv-slug>/artifacts/` subfolder), you can regenerate
  the binary locally by running the script instead of downloading.

If the old account is deleted before all boxes are ticked, the
remaining files are lost permanently.

### Step 3 — Set up the catch-all on the new account

- [ ] Sign into Cowork on the new account.
- [ ] Start a new project → **Choose existing folder** → select the
      `<catchall_name>` folder.
- [ ] Name it the same as it was on the old account.

This becomes the destination for orphan conversations and the
per-project subfolders routed there during Track A.

### Step 4 — Recreate each project on the new account

Each project's folder has (or will have) a
`transition-data/project-blueprint.md` — a structured summary covering
project purpose, custom instructions, key decisions, work in progress,
knowledge inventory, recurring context, and a recommended starting
prompt.

**For Part 1 projects (reconstructed from the data export):** the
blueprint was auto-generated by the skill from the conversation
transcripts and project JSON. Ready to use.

**For Part 2 projects (Cowork-side):** the skill couldn't reach the
conversation data, so it wrote `transition-data/migration-prompt.md`
instead — a prompt for you to run in each project on the old account.
Before deleting the old account:

- [ ] For each Part 2 project you're bringing across:
  1. Open the project in your old-account Cowork.
  2. Start a new conversation in that project.
  3. Open `transition-data/migration-prompt.md`, copy the prompt, paste
     it.
  4. Save the response as `transition-data/project-blueprint.md` in
     that project folder.
  5. Delete the now-unneeded `migration-prompt.md`.

Skip any project you don't plan to migrate.

Then, on the **new** account, for each project you're bringing across:

- [ ] Start a new project → **Choose existing folder**.
- [ ] Browse to the project's on-disk folder and select it.
- [ ] Name it the same as it was on the old account.
- [ ] Open `transition-data/project-blueprint.md`. Copy the **Custom
      Instructions** section into the new project's settings.
- [ ] Start a conversation. Paste this prompt (it's also in the
      project's `_PROJECT_BRIEF.md` under "Resuming on the new account"):

```
This is a project I'm migrating from my old Claude account. Read
`transition-data/project-blueprint.md` for full context, then treat
its **Recommended Starting Prompt** section as my first directive
— that's the project-tailored resumption point. Knowledge files
referenced in the blueprint are in `knowledge/` (for reconstructed
projects) or in this project's folder (for Cowork projects).
```

- [ ] Repeat for each project.
- [ ] **Re-install any other custom Cowork skills** you collected.
  In Cowork on the new account, click **Customize** in the left
  sidebar → click the **+** button → click the **Skills** tab →
  upload each `.skill` file from the `skills\` subfolder of this hub.
  If your organization has a curated skill registry, install from
  there instead.

### Step 5 — Review the catch-all

Open the catch-all project on the new account.

Each per-project subfolder has a `_MIGRATION_NOTE.md` explaining where
its conversations came from. Decide what to do with each:

- [ ] **Keep** as a permanent archive of routed conversations.
- [ ] **Fold** specific transcripts into other projects (copy them
      where they belong).
- [ ] **Delete** if you no longer need them.

The `unattributed-conversations/` folder holds your orphan chats
(conversations that weren't in any project). Same options apply.

### Step 6 — Validate

In **Claude Chat** (claude.ai in a browser, or the Chat surface in
Claude Desktop — NOT Cowork), sign in to the NEW account and start a
fresh conversation with no project selected. Paste this prompt:

```
Based on everything you know about me, tell me:
- Who I am and what I do
- What projects or topics are top of mind for me
- How I prefer to communicate
- Any tools, frameworks, or domains I work in
- Anything else you consider important context

Be thorough — I'm checking that a migration was successful.
```

Compare the response against `memory-capture.md`. If anything is
missing or wrong, add a memory edit on the new account directly, or
upload `memory-capture.md` again and ask Claude to fill in the gaps.

### Step 7 — Clean up the migration hub

When everything is relinked and validated, the migration hub itself
can go away.

Before you clean up, decide whether to keep a long-term record of how
the migration ran. If yes, copy these out to a separate archive
location now (they'll be deleted with the hub folder):

- `tracker.html` — final state of the migration
- This README
- Any per-project blueprints you might want to reference later

Then clean up in this order:

1. **In Cowork on the old account:** **Settings → Archive project**
   for the migration hub. (Cowork has no delete, only archive.)
2. **In Explorer:** delete the on-disk folder for the migration hub.
3. **In Cowork on the new account:** **Settings → Archive project**
   for the migration hub project you imported here to run Track B.

Both the archive AND the folder delete are required. Archive alone
leaves an orphan folder on disk; folder delete alone leaves an orphan
project registration.

---

Generated by the account-migration skill at end of Track A.
