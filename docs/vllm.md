# Optional vLLM profile

ResearchForge talks to language models through a **provider-independent orchestration layer**. Business logic never binds to a specific model ID or vendor SDK.

Local GPU availability varies. ResearchForge does **not** start vLLM in the default Compose stack.

## Start vLLM separately

```bash
# Example only — adjust model, GPU flags, and ports for your machine
docker run --gpus all -p 8001:8000 \
  vllm/vllm-openai:latest \
  --model <your-open-weight-model> \
  --served-model-name researchforge-local
```

Any OpenAI-compatible server works (vLLM, and future adapters).

## Configure the API (no code changes)

Point the API at the endpoint via environment variables:

```env
AI_PROVIDER=openai_compatible
# Preferred LLM_* names
LLM_BASE_URL=http://host.docker.internal:8001/v1
LLM_API_KEY=not-needed-for-local-vllm
LLM_MODEL=researchforge-local
LLM_TIMEOUT_SECONDS=120
LLM_MAX_CONCURRENCY=4
LLM_MAX_OUTPUT_TOKENS=2048

# Optional retrieval / rerank endpoints (reserved for future adapters)
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=researchforge-embed
RERANKER_BASE_URL=
RERANKER_MODEL=researchforge-rerank
```

Legacy aliases still work: `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL_NAME`, `AI_TIMEOUT_SECONDS`, `AI_MAX_TOKENS`.

### Change the model without modifying application code

1. Serve a different open-weight model from vLLM (`--served-model-name` / `--model`).
2. Update `LLM_MODEL` (and `LLM_BASE_URL` if the port changes).
3. Restart the API process.

Prompt templates live in `apps/api/prompts/*.yaml` and are versioned independently of model choice.

## Testing without a model

```env
AI_PROVIDER=fake
```

The fake provider returns deterministic structured JSON suitable for CI. Integration tests force `APP_ENV=test` / `AI_PROVIDER=fake`.

## Health check

```http
GET /api/v1/ai/health
```

Returns provider name, model, circuit-breaker state, and a lightweight `/models` probe for OpenAI-compatible backends.

## Privacy defaults

- Manuscript / prompt text is **not** logged by default (`AI_LOG_PROMPT_TEXT=false`).
- User content is never used for training unless `training_opt_in` is true; even then it is only marked eligible.
- Projects can set `ai_enabled=false` (“Do not send this project to AI”).
