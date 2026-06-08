# `scripts/` — Developer Smoke-Test Scripts

Two standalone scripts for manually exercising the retrieval and agent layers end-to-end without starting the full API server.

---

## `retrieval_test.py` — Raw retrieval hits

Runs a fixed set of client-brief-style questions directly against `DocumentRetriever` and prints the top passages, including neighbor context chunks.

```bash
uv run scripts/retrieval_test.py
```

No configuration needed. The three built-in queries cover:

| Query | Filters |
|---|---|
| Apple revenue mix (iPhone / Services / Mac / iPad / Wearables) across 10-Ks | `AAPL 10-K` |
| NVIDIA Data Center demand drivers and customer concentration | `NVDA 10-K` |
| Microsoft Azure / AI infrastructure language changes over time | `MSFT 10-K` |

**Use this to:** verify that chunking, embedding, and FTS are working; inspect which chunks are being scored highest; check that neighbor context is being attached correctly.

---

## `assistant_test.py` — Full agent pipeline

Runs a single query through the complete assistant stack: retrieval → agent reasoning → grounding validation → citation pruning. Prints a timestamped progress log, the final answer, and each citation with its source metadata.

```bash
uv run scripts/assistant_test.py
```

The active query is controlled by `QUERY_KEY` at the top of the file:

```python
QUERY_KEY = "apple-mix"   # change this, then re-run
```

Available keys:

| Key | Query |
|---|---|
| `apple-mix` | Apple revenue mix across 2021–2025 10-Ks |
| `nvda-datacenter` | NVIDIA Data Center demand drivers FY2021–FY2025 |
| `q10-refusal` | Tests whether the agent correctly refuses a question the filings can't answer |
| `underspecified` | Tests handling of a vague, unanswerable question |

**Output format:**

```
Model: gpt-4o
Query (apple-mix): Across Apple's 2021–2025 10-Ks ...

[  0.31s] Retrieving passages...
[  1.04s] Running agent...
[  3.87s] grounding validation ok=True insufficient_evidence=False citations=6

insufficient_evidence: False
validation_ok: True

<answer text>

[1] AAPL 10-K p.23
  Services net sales increased during 2025 ...
[2] AAPL 10-K p.35
  ...
```

**Use this to:** test the full answer quality end-to-end; check whether grounding validation is catching hallucinated citations; exercise the `insufficient_evidence` refusal path with `q10-refusal` or `underspecified`.

---

## Typical workflow

1. Run `retrieval_test.py` first to confirm passages are being retrieved correctly for a new filing or after a re-ingestion.
2. If retrieval looks good, run `assistant_test.py` to check that the agent is citing the right passages and grounding validation passes.
3. To test a new question, add it to the `QUERIES` dict in `assistant_test.py`, update `QUERY_KEY`, and re-run.