# diff-review

AI code review service: clients POST a unified diff, the service reviews it
asynchronously and returns structured findings. See `CANDIDATE-TASK.md` for
the full contract and `SUBMISSION.md` for architecture notes.

## Running locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Configuration

Settings are read from environment variables (or a local `.env` file, see
`.env.example`).

| Variable          | Required | Description                                                              |
|--------------------|----------|---------------------------------------------------------------------------|
| `SERVICE_TOKEN`    | yes      | Bearer token required on every `/v1/*` request.                          |
| `GEMINI_API_KEY`   | no       | Google Gemini API key. Needed only for the `llm` provider.               |
| `GEMINI_MODEL`     | no       | Gemini model name used by the `llm` provider. Defaults to `gemini-3.6-flash`. |

If `GEMINI_API_KEY` is not set, requests with `"options": {"provider": "llm"}`
still return `202` and a `jobId`, but the job ends up `failed` with a clear
error ("llm provider not configured") instead of crashing. The same applies
if the Gemini API call fails at runtime for any reason (network error,
unsupported region, rate limit, etc.) — the worker catches it and marks the
job `failed` with the upstream error message.

## Providers

- **`mock`** — deterministic rule-based findings (see `app/providers/mock.py`),
  used to score the pipeline independent of any model.
- **`llm`** — calls Gemini (`app/providers/llm.py`) with the same chunking/
  ordering/caching pipeline as `mock`. Requires `GEMINI_API_KEY` on the
  server; the API never sends or accepts a model key from clients.

## Deployment

Deployed on [Fly.io](https://diff-review.fly.dev)

## Tests

```bash
pytest
```
