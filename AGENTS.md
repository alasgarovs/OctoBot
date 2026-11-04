# AGENTS.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.


## Commit Rules

When the user says "make commit":

1. Stage only related changes (do NOT use git add .):

* AI agents must add and commit files individually. Each file change must be staged and committed separately, resulting in exactly one file per commit.

* Bulk staging or committing multiple files at once is not allowed. Each commit message must describe only the change made in that specific file.

```bash
git add <specific-file-or-folder>
```

2. Commit format (STRICT)

Use Conventional Commits:

<type>[optional scope]: <description>

3. Allowed types

* feat — new feature
* fix — bug fix
* docs — documentation only
* style — formatting only (no logic change)
* test — adding or fixing tests
* build — build system changes
* perf — performance improvements

### Selection Preferences

* Prefer "feat" for user-visible changes
* Prefer "fix" for bugs
* Default to "feat" if unsure

### Rules

* Each commit must represent ONE logical change only
* If multiple changes exist → split into multiple commits
* Max 8 words in description
* Lowercase description only
* No filler words (avoid: added, updated, changes)
* Be specific and meaningful

### Examples

feat: product detail page
fix: login redirect bug
docs: api usage guide
style: format navbar component
test: add user model tests
build: configure webpack bundler
perf: optimize database queries
