# Decisions

> **Status: reviewed by the client on 24 Oct 2026.** Every decision below was **accepted**, some with additions, which are marked **Client addition**.
>
> Each decision states what was decided and the experiment that would overturn it. Numbers marked *est.* are pre-measurement estimates; before delivery they are replaced with measured values, and this file becomes the "Decisions" section of the README.
>
> The client's reporting commitments are tracked in [ROADMAP.md › Client deliverables](ROADMAP.md#client-deliverables).

| # | Decision | Client verdict |
|---|---|---|
| D1 | Page-bounded, paragraph-aligned chunks of ~350 tokens | Accepted. Report how often page breaks cut paragraphs (week 4). |
| D2 | `bge-m3`, run locally | Accepted. Keep the "privacy" sentence verbatim in the README. Server has 64 GB of RAM. |
| D3 | Local generation; API mode not used for documents | Decided. GPU approved in principle once we supply a local price and a measured time. Build on CPU until then. |
| D4 | Three-band gate, biased toward refusing | Accepted. Add outcome counts to the Admin log. |
| D5 | Explicit versions; superseded versions leave retrieval | Accepted. Show "v3 — current" and the earlier versions. |
| D6 | Paragraph-level highlight with page fallback | Accepted. Report the success rate on real reports separately. |

---

## D1. Chunk size and overlap for Arabic text

**Decision: accepted by the client.** Chunks are paragraph-aligned and **page-bounded**, sized in **tokens of the embedding model's tokenizer** rather than characters:

| Setting | Value |
|---|---|
| Target size | ~350 tokens |
| Hard maximum | 512 tokens |
| Overlap | ~15% (≈50 tokens, rounded to whole sentences) |
| Merging | A page tail under 80 tokens merges into the previous chunk on the same page |

**Why**
- **Tokens, not characters.** Arabic attaches clitics to words: "وبالمشروع" is "and" + "with" + "the" + "project" in one word. So character counts and word counts both mislead. The embedding model sees tokens, so we budget tokens.
- **~350 tokens** is about one or two Arabic paragraphs. That is enough to hold a claim with its context (programme, year, figure), while staying focused enough to give the reranker clean evidence. Six chunks also fit easily in a small local model's context.
- **Page-bounded** keeps every citation exact, because each chunk belongs to exactly one page. The client said this is the part they care about most: *"We would rather have a slightly worse chunk than a citation we cannot trust."*
- **Paragraph-aligned** means we never cut mid-sentence. Arabic sentence boundaries also include `؟` `،` `؛`.

**Client addition: measure the cost of page-bounding.** By **week 4** we report two things:
- how often a paragraph is split by a page break in the client's **eight sample reports** (and, for comparison, in the synthetic corpus)
- whether any evaluation question fails because of such a split

This is done by the S1 spike's page-split metric and E1's failure category. If the rate is high, we raise it with the client before changing anything.

**How we confirm the parameters.** In E2 we sweep target sizes {200, 350, 500} tokens × overlap {0%, 15%} on the **dev** question set. We pick the best by retrieval recall@5 and end-to-end score, then run the **headline** set once.

---

## D2. Embedding model

**Decision: accepted by the client.** `BAAI/bge-m3`, run **locally** in the `ml` container. The alternates are kept only for the S2 shoot-out.

**Local or API.** Local. Embedding means sending every page of every document to the embedding provider, which breaks "no document content leaves the server". For comparison, a hosted embedding API would cost only a few dollars per 1,000 documents.

> **Cost is not the reason to stay local; privacy is.**
>
> *(The client asked for this sentence to appear in the README in exactly these words.)*

**Cost per 1,000 documents** (*est.*, to be measured in S2)

Assumptions: 25 pages per document and ~600 tokens per page, giving ~15 M tokens and ~45–55 k chunks per 1,000 documents.

| Item | Client server (16 cores, 64 GB, CPU only) | With a 24 GB GPU |
|---|---|---|
| Money | $0 marginal | $0 marginal |
| Indexing time | *est.* 0.5–2 h (client: "fine, this happens once") | *est.* a few minutes |
| Storage (vectors + text + HNSW index) | *est.* ~0.5 GB | same |

**Client correction: the server has 64 GB of RAM, not 32 GB. What changes?**
- **Embedding and indexing time: unchanged.** These are bound by CPU compute, not memory.
- **Headroom: much better.** Postgres, the `ml` service (~3–5 GB), LibreOffice and a CPU-resident LLM fit together with plenty of room to spare. That includes a 14B model on CPU (~9–10 GB at 4-bit).
- **CPU answer time: not faster.** On a CPU, generation speed is limited by memory *bandwidth*, not capacity. Extra RAM lets us *load* a bigger model, which then answers *more slowly*. It does not bring CPU answers under the 15-second target, so the GPU is still needed for production (D3).

**What would change this.** S2 finds another model that clearly beats `bge-m3` on recall@5 at a similar CPU cost.

---

## D3. Local model or API for generation

**Decision: local generation, and no API mode for the client's documents.** The client wrote: *"Still no, and we accept what that costs us … no price makes that acceptable."*

**The API path stays in the code**, behind the deliberate override file, for two purposes only:
- benchmarking on **synthetic** data
- keeping the option open if the client's policy changes

It is never enabled for the client's documents. The project owner prefers a **free** hosted API for those synthetic benchmarks, so we use the **Google Gemini API free tier** through the generic `openai_compat` adapter:
- It is officially available in Palestine and needs no card.
- Free-tier prompts may be used for training, which is acceptable only because the corpus is synthetic.

The `anthropic` adapter is built but optional, and no paid key is required (see [OPEN_QUESTIONS](OPEN_QUESTIONS.md) P3 and P5).

### Speed requirement (client)

> **Under 15 seconds per answer is fine. 30 to 90 seconds is not.** A slow system is not a slower system — it is an unused one.

So **production requires the GPU** (Tier B). A CPU-only server can't meet this target with any model that is good enough.

**How we measure "under 15 seconds".** We time the **total** answer: question embedding, retrieval, reranking, the wait for the first token, and generation. The target is met when **90% of answers (p90) take 15 s or less** on the headline questions. We also report the median. G1 (rented card) and H4 (the client's own card) both use this definition.

**Hardware tiers** (*est.*, to be measured)

| Tier | Hardware | Model class | Est. time per answer | Status |
|---|---|---|---|---|
| A | Client server as-is: 16 cores, 64 GB, no GPU | 7–8B, 4-bit (14B fits but is slower) | 30–90 s (prompt processing of ~4k tokens dominates on CPU) | **Weeks 1–8 demo platform only** |
| B | Client server + 1× 24 GB GPU, likely the **NVIDIA RTX PRO 4000 Blackwell 24 GB** class | 7–14B | *est.* ~4 s (8B) / ~7 s (14B) of LLM time plus ~1–2 s retrieval, **to be measured on a rented card** | **Approved in principle. Required before 31 January.** |
| C | 48–80 GB GPU | ~30B+ | 5–15 s | Not needed |

**What the client needs from us before purchase** (deliverables 1–2):
1. **A local, installed price, in writing, for one specific card.** This covers buying and installing it in Nablus or Ramallah, plus any power supply, cabling or cooling the server needs.
   - Which card fits depends on the server's chassis, PSU and free slot. Many rack servers only take passively cooled data-centre cards; towers can take workstation or consumer cards. We need the server's make and model first (OPEN_QUESTIONS N1).
   - We supply researched online prices and a ready-to-send request for quotation (RFQ). The binding number has to come from a local supplier's written quote.
   - **Research findings, 24 Oct** (details and sources in [research note](research/2026-10-24-gpu-and-hosted-apis.md)):
     - The best value is the **RTX PRO 4000 Blackwell 24 GB**: about USD 3,100–3,400 internationally before local tax, 145 W, single slot. It fits towers and most rack servers with a full-height slot and a 16-pin power cable.
     - Rack servers that only take passive cards point to the RTX PRO 4500 Server Edition 32 GB (about USD 4,600–5,800). Low-profile slots point to the RTX PRO 4000 SFF.
     - The **L4 and A10 are not recommended**: they would miss 15 s with a 14B model.
     - No West Bank shop lists professional cards; only an RTX 5090 (consumer, tower only) at ILS 16,500 in Ramallah. Professional cards come through an importer or the server vendor's partner, with a reported lead time of up to ~2 months, **so the order must be placed in November**.
   - The deliverable is **one figure in writing, not a range**: card model, the installed total in the client's currency (card, VAT and customs, installation, and any PSU, cabling or cooling), supplier, validity date and delivery lead time. Online prices are background only.
2. **A measured answer time on that card class.** We rent the same or an equivalent card for a few hours and time the full pipeline on the **synthetic** corpus, using the p90 definition above. If we can't rent it, we say so and give a clearly marked estimate.

**Phasing (client, REVISED)**
- **Weeks 1–8:** we build and demonstrate on CPU. 30–90 s answers are acceptable at the week-4 and week-8 milestones, which are for evaluating quality. Demo users are told the wait is expected.
- **Before 31 January:** the GPU is in place. The client handles the purchase once we give them the number.
- **The week-8 score is measured on the production model** (the one the GPU will run), not just on whatever is fast enough on CPU. If the CPU demo model differs, we measure both and report the gap.

**How much quality we lose versus a hosted model.** We measure it. The eval runs on the synthetic corpus with the local production model and with a free hosted reference model, and both scores are reported side by side. We expect a local 7–14B model to lose most on three things:
- citation discipline
- refusing near-miss questions
- synthesis across documents

The retrieval-side refusal gate (D4) limits the damage from the second.

**API cost, for reference only** (not used for client documents; Anthropic list prices, Oct 2026; *est.* ~5k input + ~0.8k output tokens per question):

| Model | $/1M in | $/1M out | ≈ per 1,000 questions |
|---|---|---|---|
| `claude-opus-5-5` | 4.00 | 20.00 | ~$36 |
| `claude-sonnet-5-5` | 2.00 | 10.00 | ~$18 |
| `claude-haiku-5-5` | 0.10 | 0.50 | ~$1 |

### Client addition: the Ask screen must never look frozen

Because answers will be slow for two months, the UI must always show progress:
- **Stream the answer** token by token as it is generated.
- **Show the current stage in words**: searching → reading sources → writing. Never just a spinner.
- **Warn up front about slow answers.** If an answer is expected to take more than ~20 s, say so on screen before the user starts wondering. The server estimates this from recent measured speeds on that machine.

See SYSTEM_DESIGN §6 (stream events) and ROADMAP R1/F2. Streaming never weakens the refusal rule:
- the `NO_ANSWER` sentinel is never shown on screen
- the amber low-confidence banner appears before the first word
- if the final check turns an answer into a refusal, the streamed text is replaced by the refusal message

**What would change this.** If G1 and E2 show the production model missing p90 ≤ 15 s on the card, we step down a model size before the client buys.

---

## D4. Weak but non-empty retrieval: answer or refuse?

**Decision: accepted by the client.** The client called it *"the part we are most pleased with"*. The Arabic wording is approved as written.

A **three-band gate** on the reranker's top score, biased toward refusing:

| Band | Condition | Behaviour |
|---|---|---|
| Refuse | top score < `T_refuse` | The LLM is **not called**. UI: "لم أجد في الوثائق المتاحة ما يجيب عن هذا السؤال." / "I couldn't find an answer to this in the available documents." Then up to 3 nearest document titles as "you may want to check", with no claims. |
| Low confidence | `T_refuse` ≤ score < `T_confident` | Answer **with citations** under an amber banner: "هذه الإجابة مبنية على مصادر قد لا تتطابق تماماً مع سؤالك — راجع المصادر قبل الاعتماد عليها." / "This answer is based on sources that may not fully match your question — check them before relying on it." |
| Answer | score ≥ `T_confident` | Normal answer with citations |

There is a second safety net in every band. The LLM must output `NO_ANSWER` when the excerpts don't contain the answer, and any answer without a valid `[n]` citation becomes a refusal.

**Client addition: outcome counts in the Admin usage log.** For a chosen period the Admin screen shows how many questions were:
- **refused**
- **answered with low confidence**
- **answered normally**

It shows each as a count and a percentage, with a trend over the period. The client's reason is that if refusals are high, they need to tell honesty apart from a retrieval problem rather than blame staff for "asking wrong". To support that diagnosis, the summary also lists the most-refused questions, each with its top retrieval score, so an Admin can see whether the documents simply don't cover the topic.

**How we confirm the thresholds.** In E2 we tune both on the dev set: maximise correct refusals on the unanswerable questions while losing at most one answerable question. The README shows screenshots of all three behaviours.

---

## D5. Document updates: replace or sit alongside?

**Decision: accepted by the client.** An Editor uploads a file explicitly as a **new version of** an existing document.
- When the new version is ready, the old one is **superseded**: it leaves retrieval but stays openable.
- Past answers keep resolving to the exact page they cited.
- An ordinary upload always sits alongside existing documents.
- Byte-identical re-uploads are rejected.

**Why.** Replacing silently would break old citations and lose history. Keeping both in retrieval would surface contradictory figures, for example a draft and a final budget.

**Client addition: show the version history.** Donor agreements often get three or four amendments.
- The **Library row** shows the version and its status at a glance, e.g. **"v3 — current"**, with the number of earlier versions.
- The **document page** lists the earlier versions, each with date and uploader, and each one openable.

**Open point (N3).** An amendment that is a **full consolidated text** fits the version model: it replaces the previous version in retrieval. An amendment *letter* that changes only some clauses must **not** supersede the original, because the unchanged clauses still apply. Superseding it would hide them from answers. We have asked the client which form their amendments take.

Until they answer, we build D5 as approved:
- A consolidated amendment is uploaded as a **new version** and supersedes the previous one.
- An amendment letter is uploaded as an **ordinary document** alongside the agreement, so both stay in retrieval.
- The schema already has an optional link from a letter to its agreement ("Amendment 2 of …", which never supersedes). The screens for that link are built only if the client says letters are the norm.

**What would change this.** The client's answer to N3.

---

## D6. How far back do citations point?

**Decision: accepted by the client.** Paragraph-level highlighting for text-layer PDFs:
- Each chunk stores its character span within the page.
- The viewer highlights that span through the pdf.js text layer.
- If the text layer is too fragmented to match, it falls back to highlighting the page.
- Sentence-level highlighting is a possible v2.

**Client addition: report real and synthetic separately.** By **week 8** we report the highlight success rate on the client's **eight real reports** separately from the synthetic corpus. The client will quote the real number to their board.
- For the real reports, which have no test questions, we try to highlight every passage in the documents.
- A highlight **succeeds** when at least 90% of the passage is matched on the right page. Anything else counts as a page-level fallback.
- The project owner runs this measurement on his own machine and reports only the numbers (OPEN_QUESTIONS N4).

**What would change this.** If the S4 and F4 rates on real reports are low, we tell the client and recommend page-level highlighting as the default.

---

## Other decisions

All accepted by the client:

- **DOCX and TXT page numbers.** We convert to PDF on upload and cite pages of that rendition.
  - **Client addition:** a citation from a converted file says so on the citation card, e.g. "Page 4 of the converted PDF; page numbers may differ from Word". A staff member who opens the original in Word and sees a different page number then knows why.
- **Scanned PDFs.** They fail clearly with "this file has no text layer (scanned image)". We report the **count of scanned files** after the first full ingestion run on the client's archive, using an ingestion summary report.
- **Guest account.** Sample documents only.
- **Network isolation.** The containers that touch document content have no internet route. **Client addition:** the README states this in one plain paragraph that the client's IT person can point to when the board asks whether documents can leave the server.
