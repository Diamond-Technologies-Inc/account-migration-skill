# Validation prompt

Run this on your NEW Claude account once Track B (the destination-side relink) is complete. It's a sanity check that the new account has the context it needs.

Open a fresh conversation (no project selected) and paste the prompt below. Compare the response against your `memory-capture.md` (from Track A Step 0). If anything's missing or wrong, fix it by adding a memory edit on the new account or by uploading a supporting context file.

---

## Prompt to paste

```
Based on everything you know about me, tell me:
- Who I am and what I do
- What projects or topics are top of mind for me
- How I prefer to communicate
- Any tools, frameworks, or domains I work in
- Anything else you consider important context

Be thorough — I'm checking that migration was successful.
```
