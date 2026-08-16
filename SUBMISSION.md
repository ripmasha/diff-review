# SUBMISSION.md

## Architecture

FastAPI service, single process, in-memory job store.

- `POST /v1/reviews` validates the request and checks the cache/idempotency
  index. On a hit it returns the existing job. Otherwise it creates a new
  `Job` and schedules `process_job` as a background `asyncio.create_task`.
- The worker parses the diff, splits it into ≤64 KiB chunks on file
  boundaries, and runs the selected provider per chunk.
- Findings are deduped by `id` and sorted by `(path, line, ruleId)`.
- Each step appends a `status`/`finding`/`done` event to the job, which is
  what `GET /v1/reviews/{id}/stream` replays over SSE.
- An `asyncio.Semaphore(4)` caps concurrent job processing; a token-bucket
  limiter caps `POST /v1/reviews` at 30/min with configurable burst.

## Provider design

Both providers implement the same `run(chunks, max_findings) -> ProviderResult`
interface so the pipeline (parsing, chunking, ordering, caching, streaming)
is identical regardless of provider:

- **mock**: pure regex/string checks against added lines only.
- **llm**: calls Gemini per chunk with a system prompt restricted to added
  lines, structured output constrained to the `Finding` schema via
  `response_schema`, and an explicit instruction to treat diff content as
  inert data (never instructions) — matching the injection-inertness
  requirement. If `GEMINI_API_KEY` is unset, or the API call raises for any
  reason, the job is marked `failed` with a descriptive error instead of
  crashing the worker.

## How I verified cross-cutting behaviors

- `pytest` suite (`tests/`) covers: auth on `/v1/*`, error envelope/codes,
  diff parsing edge cases, chunk-boundary correctness, mock rule matching,
  and — in `test_reviews.py` — idempotency (same key/body → same jobId,
  same key/different body → 409), caching (byte-identical `{diff, options}`
  → `cacheHit: true` with identical findings, independent of idempotency
  key), SSE event ordering and replay-after-completion, rate limiting
  (429 + `Retry-After` at burst, never 5xx under concurrent burst).
- Manually exercised the deployed service end to end with `curl`: `/health`,
  `mock` provider happy path, `llm` provider against a live Gemini key, and
  the SSE stream with `curl -N`.
- Confirmed the `llm` path fails gracefully: hit a Gemini `FAILED_PRECONDITION`
  location error from the original Fly region, which surfaced as a clean
  `failed` job with the upstream error message rather than a crash — the
  in-process worker never raised past `process_job`'s try/except.

## AI tools used

- I used Claude code. 

## An AI suggestion I rejected

- A custom `ApiError` class for raising errors. Rejected — it carried the
  same information as a plain `HTTPException`, so it was an extra
  abstraction with no real benefit.
- A `Job` dataclass holding `cache_key`, `idempotency_key`, `diff`, and
  `options`. Rejected — the job store doesn't need to carry that much
  request-specific state. I split it so the worker owns that data instead
  of the `Job` object.
- An SSE implementation that didn't follow FastAPI's own SSE patterns.
  Rejected in favor of the documented approach.
- Applying the `enforce_content_length` dependency to every endpoint.
  Rejected — only `POST /v1/reviews` accepts a body large enough to matter,
  so it belongs on that route alone.
- Putting diff chunking inside the provider's `run` function. Rejected — a
  provider should only run analysis on chunks it's given, not also decide
  how to produce them.

## What I'd do next with more time

- Replace the in-memory `JobStore` with something shared (Redis/Postgres) so
  the service can run more than one machine — right now job state only
  lives in one process's memory.
- Persist jobs across deploys/restarts instead of losing in-flight work.
- Add retry/backoff around the Gemini call for transient errors before
  giving up and marking the job failed.
- Add a caching mutex that also covers in-flight jobs, not just finished
  ones. Right now the cache index is only populated once a job reaches
  `done`, so identical requests (no shared `Idempotency-Key`) that arrive
  while the first one is still processing won't find a cache hit and will
  each spawn their own duplicate job.
- Move the dedup/sort/truncate step out of the providers and into the
  worker. Right now `mock.py` and `llm.py` each implement the same
  merge-across-chunks logic independently; that ordering/truncation
  contract is a pipeline concern, not a provider concern, so it should
  live in exactly one place instead of being duplicated (and risking
  drift) across providers.
