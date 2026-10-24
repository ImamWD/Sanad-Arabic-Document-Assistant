# Decisions (draft)

> This is a **draft**. Each decision states our current recommendation and the experiment that will confirm or overturn it. Numbers marked *est.* are estimates made before measurement. Before delivery they are replaced with measured values, and this file becomes the "Decisions" section of the README.

---

## D1. Chunk size and overlap for Arabic text

**Recommendation.** Chunks are paragraph-aligned and **page-bounded**, sized in **tokens of the embedding model's tokenizer** rather than characters:

| Setting | Value |
|---|---|
| Target size | ~350 tokens |
| Hard maximum | 512 tokens |
| Overlap | ~15% (≈50 tokens, rounded to whole sentences) |
| Merging | A page tail under 80 tokens merges into the previous chunk on the same page |

**Why**
- **Tokens, not characters.** The brief notes that Arabic takes more characters per concept. Arabic also attaches clitics to words: "وبالمشروع" is "and" + "with" + "the" + "project" in one word. So character counts and word counts both mislead. The embedding model sees tokens, so we budget tokens, and the model's context limit is a token limit too.
- **~350 tokens** is about one or two Arabic paragraphs. That is large enough to hold a claim with its context (programme, year, figure). It is small enough that a single chunk is about one thing, which keeps embeddings sharp and gives the reranker clean evidence. Six chunks also fit easily in a small local model's context.
- **Page-bounded** keeps every citation exact, because a chunk belongs to exactly one page. The cost is that a paragraph split across a page break is cut. The overlap reduces that, and the README lists it as a known limitation.
- **Paragraph-aligned** means we never cut mid-sentence. Arabic sentence boundaries also include `؟` `،` `؛` and `.`.

**How we confirm it.** In E2 we sweep target sizes {200, 350, 500} tokens × overlap {0%, 15%} on the **dev** question set. We measure retrieval recall@5 and end-to-end score, pick the best, then run the **headline** set once.

---

## D2. Embedding model

**Recommendation.** `BAAI/bge-m3`, run **locally** in the `ml` container. It is multilingual with strong Arabic results in published benchmarks, produces 1024-d vectors and takes up to 8k tokens of input. Alternates for the S2 shoot-out are `intfloat/multilingual-e5-large` and `Alibaba-NLP/gte-multilingual-base`. Licences are to be verified in S2.

**Local or API.** Local. Embedding means sending *every page of every document* to the embedding provider, which plainly breaks "no document content leaves the server". So an API embedding option is not offered.

**Cost per 1,000 documents** (*est.*, to be measured in S2)

Assumptions: 25 pages per document, ~600 tokens per page. That gives ~15 M tokens and ~45–55 k chunks per 1,000 documents.

| Item | CPU-only server | Single 24 GB GPU |
|---|---|---|
| Money | $0 marginal (electricity only) | $0 marginal |
| Indexing time | *est.* 0.5–2 h | *est.* a few minutes |
| Storage (vectors + text + HNSW index) | *est.* ~0.5 GB | same |

For comparison, a hosted embedding API would cost only a few dollars per 1,000 documents. **Cost is not the reason to stay local; privacy is.**

---

## D3. Local model or API for generation

**Recommendation.** **Local by default**, as the client prefers, with the API as a config switch for the client to choose. The provider is selected by `LLM_PROVIDER=ollama|anthropic|openai_compat`. API mode also needs an override file that gives the `api` container internet access, so turning it on is a deliberate, visible act.

**Privacy trade-off.** In API mode, the question and the top K excerpts (K≈6, roughly 2–3 pages of text) go to the provider for every question. Those excerpts can contain beneficiary names, ID numbers and salaries. Whole documents never leave, but excerpts do. We need the client's written OK before enabling it (OPEN_QUESTIONS Q1).

**Hardware for local generation** (*est.*, to be measured in S3)

| Tier | Hardware | Model class | Est. time per answer | Verdict |
|---|---|---|---|---|
| A | CPU only, 16 cores, 32 GB RAM | 7–8B, 4-bit | 30–90 s (prompt processing of ~4k tokens dominates on CPU) | Works for demo and light use; slow |
| B | 1× 24 GB GPU (e.g. NVIDIA L4 / A10 / RTX 4090), 32–64 GB RAM | 7–14B | 3–10 s | **Recommended for production** |
| C | 48–80 GB GPU | ~30B+ | 5–15 s | Closest to API quality |

**How much quality we lose.** We will measure this rather than guess. The eval runs against the synthetic seed corpus, which contains no client data, so we can run it with both the local model and Claude and report the two scores side by side. We expect a local 7–14B model to lose most on three things:
- citation discipline
- refusing on near-miss questions
- fluent synthesis across documents

The retrieval-side refusal gate (D4) runs *before* the LLM, which limits the damage from the second point.

**API cost** (Anthropic list prices, Oct 2026; *est.* ~5k input + ~0.8k output tokens per question, to be measured):

| Model | $/1M in | $/1M out | ≈ per question | ≈ per 1,000 questions |
|---|---|---|---|---|
| `claude-opus-5-5` (default when API mode is on) | 4.00 | 20.00 | $0.036 | ~$36 |
| `claude-sonnet-5-5` | 2.00 | 10.00 | $0.018 | ~$18 |
| `claude-haiku-5-5` | 0.10 | 0.50 | $0.001 | ~$1 |

---

## D4. Weak but non-empty retrieval: answer or refuse?

**Recommendation.** A **three-band gate** on the reranker's top score, biased toward refusing. The brief calls invention the single worst failure, so we accept some extra refusals to avoid it.

| Band | Condition | Behaviour |
|---|---|---|
| Refuse | top score < `T_refuse` | The LLM is **not called**. UI: "لم أجد في الوثائق المتاحة ما يجيب عن هذا السؤال." / "I couldn't find an answer to this in the available documents." It then lists up to 3 nearest document titles as "you may want to check", with no claims. |
| Low confidence | `T_refuse` ≤ score < `T_confident` | The answer is generated **with citations** under an amber banner: "هذه الإجابة مبنية على مصادر قد لا تتطابق تماماً مع سؤالك — راجع المصادر قبل الاعتماد عليها." / "This answer is based on sources that may not fully match your question — check them before relying on it." |
| Answer | score ≥ `T_confident` | Normal answer with citations |

There is a second safety net in every band. The LLM must output `NO_ANSWER` when the excerpts don't contain the answer, and any answer without a valid `[n]` citation is turned into a refusal.

**How we confirm it.** In E2 we tune both thresholds on the dev set: maximise correct refusals on the unanswerable questions, subject to losing at most one answerable question. The README will show screenshots of all three behaviours, as the brief asks.

---

## D5. Document updates: replace or sit alongside?

**Recommendation.** **Both, explicitly.** An Editor uploads the file as a **new version of** an existing document, using a "Upload new version" action on the Library row.
- The new file gets the same `version_group_id` and `version + 1`.
- When the new version reaches *ready*, the old version is marked superseded. It leaves **retrieval**, so answers only come from the current version, but it stays openable from the document page ("Earlier versions").
- Past answers that cite the old version still resolve to the exact page they cited, which matters for audit.
- An ordinary upload (not "new version") always sits alongside. Byte-identical re-uploads are rejected as duplicates.

**Why.** Replacing silently would break old citations and lose history. Keeping both in retrieval would surface contradictory figures, for example a draft and a final budget.

---

## D6. How far back do citations point?

**Recommendation.** **Paragraph-level is feasible for text-layer PDFs, and we'll ship it.**
- Each chunk stores its character span within the page text.
- The viewer opens the page and highlights that span through the pdf.js text layer, matching on normalised text.
- If matching fails (some PDFs fragment Arabic text-layer runs), it falls back to highlighting the page.
- The citation card shows the snippet regardless.
- Sentence-level highlighting (the exact supporting sentence) is a possible v2: the LLM would quote its evidence and we would fuzzy-match it inside the chunk.

**How we confirm it.** Spike S4 measures highlight success rate on the seed corpus and on real-world Arabic PDFs. The README reports that number.

---

## Other decisions the client should know about

- **DOCX and TXT page numbers.** Word files have no fixed pages, so we convert DOCX and TXT to PDF on upload and cite pages of that rendition. That is also what the viewer shows. The numbers may differ slightly from Word's on-screen paging.
- **Scanned PDFs.** OCR is out of scope. A scanned file fails clearly with "this file has no text layer (scanned image) — OCR is not supported in this version" rather than silently indexing nothing.
- **Guest account.** The guest sees **only the sample documents**, even on a production install, so real data is never exposed through a shared login. It can be switched off entirely.
- **Network isolation.** The containers that touch document content have no internet route. API mode is the only exception and has to be enabled deliberately.
