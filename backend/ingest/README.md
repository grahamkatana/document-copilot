# `ingest/` — SEC Filing Ingestion Pipeline

This package downloads, parses, chunks, embeds, and stores SEC filings (10-Ks and similar) so they can be retrieved by the application's RAG (retrieval-augmented generation) layer.

---

## Modules at a Glance

| Module | Responsibility |
|---|---|
| `load_source_documents.py` | Read a filing manifest and populate the `source_documents` table |
| `sec_tables.py` | Parse raw HTML and extract structured financial tables |
| `chunking.py` | Convert an HTML filing into `ChunkRecord`s via Docling |
| `embeddings.py` | Call the OpenAI Embeddings API in batches |
| `chunk_and_embed.py` | Orchestrate chunking + embedding + writing to the database |

Run them in this order:

```
uv run python -m ingest.load_source_documents
uv run python -m ingest.chunk_and_embed --all
```

---

## Step-by-Step Data Flow

### 1. `load_source_documents` — Register filings

Reads `data/markdown/manifest.json`, which is a hand-curated (or script-generated) list of SEC filings. For each filing it creates a `SourceDocument` row that carries the filing metadata (ticker, CIK, accession number, dates, etc.) and the raw Markdown content of the filing.

**Why a separate step?** The manifest is the single authoritative list of *which* filings belong in the system. Separating this step from chunking means you can inspect or curate what's registered before committing compute resources to embedding.

---

### 2. `sec_tables` — Structured table extraction

Before Docling touches the document, this module scans the raw HTML with a hand-rolled `HTMLParser` subclass (`_TreeParser`) and pulls out every `<table>` that looks like a financial table.

**Why not rely on Docling for tables?** Docling's chunker produces reasonable Markdown tables, but SEC filings often use deeply nested `<td>`/`<th>` structures, inline XBRL facts (`ix:nonFraction`, etc.), split dollar-sign cells, and sales-vs-change layouts that a generic converter doesn't handle well. `sec_tables` applies SEC-specific heuristics:

- **`_is_meaningful`** — discards layout/spacing tables that contain no numeric cells.
- **`_normalize_rows`** — detects "Change" column patterns (Year / Sales / YoY%) and reconstructs them as properly labelled columns.
- **`_table_context`** — walks the DOM siblings to find the title text above the table and any footnotes below it, and extracts a units string like "in millions".
- **`InlineFact`** — preserves XBRL inline fact metadata (concept name, context ref, decimals) attached to individual cells, so the data stays machine-readable.

Each extracted table gets a SHA-256 hash of the source HTML so downstream code can detect if a table was re-extracted from the same source.

---

### 3. `chunking` — Document → `ChunkRecord` list

`chunk_document()` is the main entry point. It does two things in parallel:

**3a. Narrative chunking via Docling `HybridChunker`**

Docling converts the HTML to its internal document model, then `HybridChunker` splits it hierarchically (by heading structure) and then token-aware (capped at 512 tokens). Two custom pieces layer on top:

- **`PatchedOpenAITokenizer`** — SEC filings contain `<|...|>`-style XBRL tokens that tiktoken's default special-token handling rejects. The patch allows them through without counting them as control tokens.
- **`MarkdownTableSerializerProvider`** — tells Docling to serialise tables as compact Markdown rather than as prose, which preserves alignment for the LLM.

Each chunk is wrapped in a `ChunkRecord` with a page number (from Docling provenance), a section heading path (`_section_from_chunk`), and a `chunk_kind` of `"narrative"`.

**3b. Per-row table chunks**

For every chunk that Docling identifies as containing a table, the code looks up the matching `ExtractedTable` from `sec_tables` (by checking if the first row label or cell values appear in the Docling chunk text). The matching table is then exploded into one `ChunkRecord` per data row via `_table_row_chunk_text`.

**Why one chunk per row?** A full financial statement table can be hundreds of tokens and its rows answer very different questions (revenue vs. net income vs. EPS). Splitting by row means a vector search for "Apple net income 2023" hits the right row directly rather than a dense block containing dozens of unrelated figures. Each row chunk includes the table title, units, and column headers so it is self-contained.

Tables that Docling never surfaces (because they were in parts of the HTML that Docling skipped) are appended at the end in a second pass.

---

### 4. `embeddings` — Text → float vectors

`embed_texts()` is a thin wrapper around `openai.embeddings.create`. It batches the input in groups of 100 (the `EMBED_BATCH_SIZE`), sorts the response by index (the API does not guarantee order), and validates that every returned vector has exactly `settings.openai_embedding_dimensions` dimensions before appending it.

**Why validate dimensions?** The OpenAI API accepts a `dimensions` parameter for Matryoshka-truncated embeddings. Silently getting a different-dimension vector would corrupt pgvector similarity searches without an obvious error.

---

### 5. `chunk_and_embed` — Orchestration and persistence

`ingest_document()` ties everything together and writes to three tables:

- **`document_chunks`** — one row per `ChunkRecord`, with the embedding vector, section, page, token count, and a JSONB `chunk_metadata` blob that carries the full filing metadata and any table-specific fields.
- **`document_tables`** — one row per distinct `ExtractedTable` (deduplicated by `table_index`). Stores the full Markdown and structured `table_data` JSON. The `table_id` FK is written back into the `chunk_metadata` of each `table_row` chunk so the app can join from a chunk hit to the full table.
- **`message_citations`** (cascading delete only) — existing citations for a document are removed when `--force` re-ingests it.

**Idempotency flags:**

| Flag | Behaviour |
|---|---|
| `--skip-existing` (default on) | If a document already has chunks, skip it entirely |
| `--force` | Delete existing chunks/tables/citations, then re-ingest |
| `--dry-run` | Run chunking only; print a sample chunk; write nothing |
| `--max-chunks N` | Cap chunks per document — useful for smoke tests |

---

## Key Design Decisions

**Two-layer table strategy.** Docling handles narrative prose well but treats tables generically. The custom `sec_tables` extractor runs directly on the raw HTML where XBRL attributes and cell structure are still intact. The chunker bridges the two by using Docling's chunk boundaries to detect *which* tables are relevant to a given section, then substituting the richer `sec_tables` representation.

**`ChunkRecord` is a plain dataclass.** Nothing in the chunking layer knows about SQLAlchemy or the database schema. This keeps the chunking logic independently testable (and runnable with `--dry-run`) without needing a database connection.

**Metadata is duplicated into every chunk.** Each `DocumentChunk.chunk_metadata` JSON blob contains the full filing metadata (ticker, CIK, form, dates, etc.). This is intentional: it means a retrieval result is self-contained and the application layer does not need to join back to `source_documents` for display or citation purposes.

**Frozen dataclasses throughout `sec_tables`.** All table data structures (`InlineFact`, `TableCell`, `TableRow`, `ExtractedTable`) are frozen and use `__slots__`. This makes them hashable, prevents accidental mutation during the multi-pass chunking logic, and keeps memory use lower for large filings.