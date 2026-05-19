# Global memory capture prompt

Claude's account-level memory of you is read and written through **Claude Chat** — that's the surface at claude.ai in a browser, or the Chat view in Claude Desktop. Cowork is a separate desktop surface for working with files and skills; it doesn't have access to account-level memory. So this prompt runs in Claude Chat (either claude.ai or Claude Desktop's Chat surface), NOT in a Cowork session.

**On the OLD account, in Claude Chat (claude.ai or Claude Desktop's Chat surface, NOT Cowork), start a new conversation with no project selected** and paste one of the two prompts below. Save Claude's response as `memory-capture.md` in this migration hub folder. The migration skill picks it up during Track B's memory-seed phase (or you can apply it manually per the Track B README's Step 1).

Do this BEFORE deleting your old account — once the account is gone, the memory it holds is gone.

## Which prompt?

Two variants depending on your migration scenario:

- **Prompt A — Wholesale migration.** Use this if you want everything Claude knows about you carried across. Typical cases: personal→personal account move, consolidating two personal accounts, moving from a personal account to a new personal account (different email), or moving comingled personal+work to a new account where you want everything to come with you.

- **Prompt B — Corporate carve-out.** Use this if you're moving work-related context from a comingled personal account to a separate corporate (Teams) account, and you want the new account to know your work context only — not your hobbies, family, or other personal entries. The prompt biases the dump toward work and produces an exclusion list for personal items so you can verify what was filtered.

Pick one, paste it, save the response as `memory-capture.md`.

---

## Prompt A — Wholesale migration

```
I'm migrating to a new Claude account. Please create a markdown file
called memory-capture.md containing:

1. Your complete memory of me — verbatim, exactly as stored
2. All memory edits I've made — numbered, exact text
3. My work context: role, company, team, projects
4. My communication preferences: tone, format, length
5. Technical domains and tools I work with
6. Recurring workflows or patterns in how I use you
7. Anything else that helps you work effectively with me

Be exhaustive.
```

---

## Prompt B — Corporate carve-out

```
I'm migrating corporate-related context to a company-issued Claude
account. Please create a markdown file called memory-capture.md
containing:

1. Your complete memory of me — verbatim, exactly as stored
2. All memory edits I've made — numbered, exact text
3. My work context: role, company, team, clients, projects
4. My communication preferences as they relate to work
5. Technical domains and tools I work with professionally
6. Recurring workflows or patterns in how I use you for work
7. Anything else that helps you work effectively with me on work topics

Then, in a separate section titled "Personal entries (exclude from new
account)", list any memory entries that are clearly personal (hobbies,
family, non-work interests) and shouldn't be carried across to the
corporate account.

Be exhaustive on the work side. Be precise about the personal-side
exclusions.
```
