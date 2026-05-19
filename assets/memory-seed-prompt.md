# Global memory seed prompt

Claude's account-level memory of you is read and written through **Claude Chat** — that's the surface at claude.ai in a browser, or the Chat view in Claude Desktop. Cowork is a separate desktop surface for working with files and skills; it doesn't have access to account-level memory. Seeding writes to account-level memory, so this prompt runs in Claude Chat, NOT in a Cowork session — even though the rest of Track B is driven from Cowork.

**On the NEW account, in Claude Chat (claude.ai or Claude Desktop's Chat surface, NOT Cowork), start a new conversation with no project selected.** Attach `memory-capture.md` from this migration hub folder, then paste the prompt below. This loads the captured snapshot back into Claude's account-level memory on the new side, so per-project conversations later in Track B inherit the global context.

The account-migration skill prompts you for this during Track B's memory-seed phase (you switch to Claude Chat, run the seed, then come back to Cowork and say "done"). Use this file directly only if you're following the manual fallback path in the Track B README.

---

## Prompt to paste

```
I'm migrating from a previous Claude account. The attached
`memory-capture.md` is a snapshot of everything you knew about me
there — my role, work context, communication preferences, technical
domains, recurring workflows, and other persistent context.

Please review it and commit the relevant facts to your memory of me on
this account. Be thorough — better to save too much than to lose
context.
```

After Claude confirms what's been saved, the global memory is seeded on the new account. You can verify with the validation prompt later in Track B.
