# Migration prompt for <PROJECT NAME>

This is a prompt the project-import skill couldn't run for you — Cowork's internal session storage is walled off by design, so the skill can't read the conversation history or accumulated memory for this Cowork project. Instead, the skill is handing you the prompt to run yourself.

**What to do:**

1. Open this project in your old-account Cowork (the project named **<PROJECT NAME>**).
2. Start a new conversation in that project.
3. Copy the prompt below. Paste it into the conversation.
4. Save the response as `transition-data/project-blueprint.md` in this same folder.
5. Delete this `migration-prompt.md` once the blueprint exists — it's no longer needed.

Do this before deleting your old Claude account.

---

## Prompt to paste

```
You have access to this project's instructions, knowledge base, our
conversation history, and any accumulated memory about how we've worked
together. Please produce a structured migration blueprint with these
sections:

1. **Project Purpose** — What this project is for and who it serves.
2. **Custom Instructions** — Reproduce the full system prompt / project
   instructions verbatim.
3. **Key Decisions and Outcomes** — The most important conclusions,
   decisions, or outputs from our conversations.
4. **Work in Progress** — Anything unresolved, ongoing, or that needs
   to continue in the new account.
5. **Knowledge Base Contents** — List every uploaded file or document
   by name and describe what each contributes.
6. **Recurring Context and Accumulated Memory** — Preferences,
   constraints, terminology, or patterns I use consistently in this
   project, plus anything else you remember about this project from
   prior conversations, sessions, or accumulated context. Be
   exhaustive — better to include too much than to miss something I'd
   want carried across.
7. **Recommended Starting Prompt** — Write a single prompt I can paste
   into the new project's first conversation to restore useful context
   immediately.

Be thorough. Do not summarize when full detail matters. Flag anything
you cannot recall or access.
```
