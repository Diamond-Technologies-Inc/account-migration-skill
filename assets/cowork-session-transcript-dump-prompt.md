# Cowork session transcript dump prompt (source account, per project)

> **Fallback path in v1.5+.** The primary transcript-archive path is the install recon (SKILL.md Step 2.0): the hub Cowork session derives every project's session list from a CSV the user produces with a small native-shell script, then pulls each session's transcript directly via `mcp__session_info__read_transcript`. This paste-prompt asset is preserved for two narrow cases: (a) users who skipped the install recon in Step 2.0, and (b) recovery of pre-spaceId-era sessions (sessions from before a Cowork project existed as a discrete space, which won't have a spaceId for the recon CSV to attribute). Use the recon path whenever possible — it's faster, authoritative, and doesn't require a paste per project. The content-scan logic in this prompt's STEP 3 still works correctly for blank-spaceId fallback because it looks for the project's folder path in transcript text, independent of spaceId.

Run this prompt inside each Cowork-native project on the source account whose accumulated session history you want to carry to the new account.

**Where this fits in the migration flow.** A Cowork project's session transcripts hold the "why" behind decisions that never made it to disk — design discussions, debugging context, mid-session pivots, intermediate file versions. The account-migration skill's blueprint generator and downstream artifact extractor read these transcripts (along with the project's working folder contents and dumped memory) to reconstruct a faithful project history on the new account.

This is the Cowork-native equivalent of what the export-extraction scripts do for web Claude Chat conversations: produce per-conversation `.md` files under `conversation-history/` at the project root. Different source, same destination shape — the new account's project sees one unified history folder regardless of whether each entry came from a web chat or a Cowork session.

**Workflow per project.**

1. Open the project's Cowork conversation on the source account.
2. Confirm Claude has access to the project's working folder. If a fresh conversation hasn't been granted access yet, grant it before continuing.
3. Paste the prompt below.
4. Claude auto-filters sessions by project membership and dumps every match — no confirmation step. The filter combines two heuristics: (a) title keyword match against the project folder name and obvious variants, (b) content path scan in each session's transcript for the project's mounted folder. Either match → include. Expect 30-120 seconds depending on total account-session count (one short transcript probe per session in the account).
5. Confirm the `conversation-history/` folder at the project root contains the new `_sess_` files plus an updated `INDEX.md`.
6. Move to the next project.

If the auto-filter finds zero in-scope sessions, Claude reports that and stops — nothing gets written. (Normal for projects where the user has not yet had a Cowork session work substantively inside the folder.)

If the auto-filter over-includes a session (e.g., a session that briefly mentioned this project's name without actually working in it), the spurious `_sess_` file is easy to delete after the dump completes. If the auto-filter misses a session you know belongs here, run the dump manually for just that session ID via a one-line `mcp__session_info__read_transcript` call.

If the working folder isn't accessible on this machine (folder lives on a different computer), Claude will report the limitation and stop. Transcripts are too large to dump inline; run the prompt on the machine where the folder lives or grant folder access first.

**About the `_sess_` designator.** Filenames carry `_sess_` between the slug and the short UUID to distinguish Cowork session dumps from web chat conversations (which get `_chat_`). Same `conversation-history/` folder, same naming structure overall, just a typed identifier for searchability and source clarity.

**About artifact extraction.** This prompt dumps the transcripts only. Cowork session transcripts (returned by `read_transcript`) show tool calls as bracket indicators (`[assistant] (called Write)`) without the input arguments, so per-session artifact extraction from these dumps isn't possible with the current API. Files written by Cowork sessions live on disk in the project's working folder already — current state is preserved through the filesystem, not the transcript. The transcripts are useful for the *reasoning* behind decisions (what's in the blueprint), not for file recovery.

---

## Prompt to paste

```
Please dump this Cowork project's session transcripts to disk for
migration to a new account. Mechanical task — confirm scope, write
files, report.

STEP 1 — Confirm working folder access.

Identify this project's working folder from the connected-folders
section of your system prompt. Call this WORK_DIR. Use the path
syntax appropriate for your host — Windows-style for Windows,
POSIX-style for macOS or Linux. Don't translate or reconstruct;
just use what your environment hands you.

If no working folder is connected, report "Working folder not
accessible — paste this prompt in a session with folder access
granted, or run it on the machine where the project folder lives"
and stop.

STEP 2 — List accessible sessions.

Call mcp__session_info__list_sessions with limit=500. This returns
recent local Claude sessions on this account, NOT scoped to the
current project. The list is sorted most-recent-first.

If the list is empty, report "No sessions accessible" and stop.

STEP 3 — Auto-filter sessions by project membership.

The mcp__session_info__list_sessions output does NOT carry project
membership in its metadata — sessions from every project on this
account come back in one flat list. Filter automatically using two
heuristics in parallel. Either match qualifies a session.

Heuristic A — TITLE keyword match (cheap, runs first):
  Derive title keywords from WORK_DIR's basename:
    - The project folder name itself.
    - Tokens after splitting the folder name on hyphens, spaces,
      underscores, and dots. (E.g., a folder named "<word1>-<word2>"
      yields keywords [<word1>, <word2>, "<word1>-<word2>"]; a
      folder named "<word1> <word2> <word3>" yields all three plus
      the full name.)
    - Drop common stop-words ({"the", "a", "an", "and", "or", "of",
      "for"}) and tokens of length < 3.
  For each session, lowercase the title and check whether any
  derived keyword (also lowercased) appears as a substring. Match
  → include.

Heuristic B — CONTENT path scan (catches generic-titled sessions
that Heuristic A misses):
  For each session NOT already matched by Heuristic A:
      try:
          transcript = mcp__session_info__read_transcript(
              session_id=session.session_id,
              limit=80,
              format='full',
              max_wait_seconds=0
          )
      except Exception:
          continue  # skip unreadable sessions
      # WORK_DIR appears in the transcript text — most often via
      # tool-call output paths, present_files URLs, or file paths
      # the assistant mentions when summarizing work. The full
      # WORK_DIR is the strongest signal; a fragment that includes
      # the parent segment (e.g., "Projects\<project_name>" or
      # "Projects/<project_name>") catches paths the renderer may
      # have URL-encoded or truncated.
      if WORK_DIR in transcript OR
         (parent_segment + "/" + project_name) in transcript OR
         (parent_segment + "\\" + project_name) in transcript:
          include this session.

The 80-message probe limit keeps the scan bounded — sessions with
substantial content typically reference WORK_DIR within the first
several tool calls. A session that only briefly touched the
project may be missed, but that's an acceptable trade-off vs.
asking the user to pick every session manually.

If after both heuristics the in-scope list is empty, report:
"No sessions found belonging to this project (auto-filter scanned
all accessible sessions). Either this is a fresh project with no
Cowork session history, or the heuristics missed them; the latter
case is uncommon."
and stop without writing anything.

STEP 4 — Reverse to chronological order and assign ordinals.

Take the in-scope list and reverse it (list_sessions returns
most-recent-first; reverse to get oldest-first). Number 01, 02,
03, ... (2-digit zero-padded ordinals).

STEP 5 — Build the per-session filename.

For each selected session, compute its filename:

  YYYY-MM-DD_NN_<slug>_sess_<short-id>.md

where:
  - YYYY-MM-DD = today's date (the dump date). Use shell `date` or
    your environment's date facility to get it; format as ISO
    calendar date.
  - NN = 2-digit ordinal from STEP 4 (01, 02, ...)
  - <slug> = the session title, lowercased, spaces and underscores
    converted to hyphens, special characters (anything not in
    [a-z0-9-]) removed, runs of multiple hyphens collapsed, leading
    and trailing hyphens stripped, capped at 60 characters. If the
    title is empty, use "untitled"
  - <short-id> = first 8 characters of the session UUID. The
    session_id field looks like "local_e0580121-..."; strip the
    "local_" prefix and take the first 8 chars of what remains

Example: today's date YYYY-MM-DD, a session titled "Migrate Claude
Project Data" with ID local_e0580121-cd7d-49d6-bb40-c56e379119d5
sorted first becomes:
  YYYY-MM-DD_01_migrate-claude-project-data_sess_e0580121.md

STEP 6 — Dump each selected session.

For each selected session in chronological order:
  - Call mcp__session_info__read_transcript with the session's ID
    and format='full'.
  - Write the transcript content verbatim to:
      <WORK_DIR>/conversation-history/<filename>
  - The Write tool creates intermediate directories as needed.
  - Don't summarize, don't paraphrase, don't add headers — verbatim.
  - If a read or write fails for a specific session, log it and
    continue to the next session. Do not abort the whole run.

STEP 7 — Write or update the index.

Locate <WORK_DIR>/conversation-history/INDEX.md.

If the file exists (the project already has web-chat conversations
indexed there), append a new section. If it doesn't exist, create
it with the header described below.

The INDEX.md section format mirrors the existing web-chat schema:

  # Conversation history index

  | # | Time | Conversation | Msgs | Opens with |
  |---|------|--------------|-----:|------------|
  | 1 | <date HH:MM> | [name](file.md) | <count> | <opener> |
  ...

For Cowork sessions, fill the columns as:
  - # = the existing INDEX's next ordinal (continue numbering past
    any web-chat rows already there)
  - Time = today's date plus session ordinal (e.g., "YYYY-MM-DD 01")
    since we can't get session start times
  - Conversation = [session title](filename)
  - Msgs = total turn count from the transcript (count user +
    assistant messages); leave blank if not easily determinable
  - Opens with = first ~80 characters of the first user message in
    the transcript (the user's opening prompt); leave blank if not
    easily determinable

Keep INDEX.md mechanical — no analysis, no decisions, no notes.
Rich navigation notes (load-bearing decisions, what's not on disk,
etc.) are a separate pass downstream.

STEP 8 — Report.

Reply with a short summary, no narrative:
  - WORK_DIR
  - Sessions listed (total accessible on account)
  - Sessions matched by title heuristic (count)
  - Sessions matched by content scan (count, excluding already-title-matched)
  - Sessions written successfully (count + the title list)
  - Output directory
  - Any read or write failures (which session IDs, what error)

Listing the written-session titles in the report lets the user spot any
unexpected inclusions and delete those files post-dump if needed.
```
