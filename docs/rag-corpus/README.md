# RAG reference corpus

Six original, hand-authored reference documents covering evergreen personal
finance concepts: emergency funds, debt payoff, retirement accounts, how
marginal tax brackets work, diversification/asset allocation, and budgeting
frameworks. This is demo/reference content for Milestone 5, not a copy of
real IRS/SEC/Investopedia text — see "Why not scrape real sources" below.

Ingest (or re-ingest after editing) with:

```bash
cd api
uv run python -m app.ai.rag.ingest
```

This chunks each document, embeds the chunks locally (`fastembed`, no API
key), and upserts them into `rag_document`/`rag_chunk`. Re-running is safe:
a document whose content hasn't changed (by content hash) is skipped, and
an edited document has its old chunks replaced.

## Document metadata

Each file's category is inferred from its filename for now (e.g.
`emergency-fund-guidelines.md` → category `emergency_fund`) — see
`app/ai/rag/ingest.py`. Add a new file to this directory and it's picked up
automatically on the next ingestion run.

## Why not scrape real IRS/SEC/Investopedia sources for M5

Directly scraping and re-publishing real IRS/SEC/Investopedia content
raises licensing and accuracy-drift questions (tax figures in particular
change annually) that are out of scope to solve properly in this
milestone. Writing original summaries of well-established, evergreen
concepts — and being explicit in the text itself about which figures are
illustrative rather than current-year-authoritative (see
`tax-brackets-and-marginal-rates.md`) — exercises the exact same retrieval
pipeline honestly, without the app asserting stale or unlicensed content as
fact.

## Adding real documents later

The ingestion pipeline is generic — `RAGDocument.source`/`source_url` exist
specifically so this corpus can grow to include real ingested sources
without a schema change:

- **A PDF or long document**: extend `ingest.py` with a loader for that
  file type, chunk it the same way, and set `source`/`source_url`
  accordingly (e.g. `source="irs_pdf"`, `source_url="https://irs.gov/..."`).
- **A URL**: fetch and extract the text, then run it through the same
  chunk → embed → persist path.
- **User-uploaded documents**: a future milestone could expose an upload
  endpoint that runs the same pipeline with `source="user_upload"`.

None of these require touching `rag_document`/`rag_chunk`, the embedding
provider, or the retrieval/citation code — only a new ingestion source.
