# Global memory seed prompt

Run this on your NEW Claude account at the start of Track B, in a new conversation with **no project selected**. Attach `memory-capture.md` from this migration hub folder to the conversation, then paste the prompt below.

This is the inverse of the memory-capture prompt: it loads the captured snapshot back into Claude's account-level memory on the new side, so per-project conversations later in Track B inherit the global context.

The account-migration skill runs this for you automatically during the memory-seed phase. Use this file directly only if you're following the manual fallback path in the Track B README.

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
