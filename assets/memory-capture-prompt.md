# Global memory capture prompt

Run this in your OLD Claude account, in a new conversation with **no project selected**. Save the response as `memory-capture.md` in this migration hub folder. You'll upload it to the new account during Track B (the skill drives this in the memory-seed phase, or you can do it manually per the Track B README's Step 1).

Do this BEFORE deleting your old account. Cowork's auto-memory doesn't migrate between accounts automatically — this prompt is the bridge.

---

## Prompt to paste

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

If you're migrating corporate data off a personal account specifically (rather than moving everything wholesale), modify the prompt to ask Claude to additionally separate personal-only entries (hobbies, family, non-work interests) into a dedicated section so you can identify what NOT to carry across to a corporate account. See the corporate-data variant of the migration guide if that applies.
