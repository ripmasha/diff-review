# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

diff-review is an AI code review service: clients POST a unified diff, the service analyzes it asynchronously (queued/running/done/failed job lifecycle, with SSE progress streaming) and returns structured, ordered findings.

Reviews run through a provider interface with two implementations behind the same pipeline (parsing, chunking, caching, idempotency, rate limiting):
- **mock** — deterministic rule-based findings (regex/pattern checks against added diff lines), used for scoring the pipeline independent of any model.
- **llm** — a real LLM call producing findings in the same schema. No API key is configured yet; this path must fail gracefully (a `failed` job with a clear error) rather than crash when the model is unreachable.

Stack: FastAPI (Python). Deployment target not yet decided.

## Working style

Bias toward caution over speed. For trivial tasks, use judgment.

### Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### Surgical Changes

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

### Goal-Driven Execution

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

## Comment instructions

- Avoid adding comments by default.
- Add a comment only when the code contains important logic that cannot be made clear through better naming or simpler structure.
- Do not add comments that describe what the code already clearly shows.
- Keep necessary comments short and write them in English.
- Do not use em dashes or en dashes in comments.


