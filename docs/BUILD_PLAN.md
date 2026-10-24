# Sanad — Build Plan and Client Requirements

**Owner:** Imam Mousa Ali Ibrahim
**Date:** 25 October 2026
**Purpose:** single working document for the build. Hand this to Claude Code at the start of a session.

---

## How to read this document

| Part | What it is | Authority |
|---|---|---|
| **Part 1** | Build plan — what to build, what to defer, by when | **Authoritative on scope and schedule** |
| **Part 2** | Decisions log — every decision settled so far | **Authoritative on behaviour and requirements** |
| **Part 3** | The client's correspondence, verbatim | Context and reasoning behind Part 2 |

**Where Part 1 and Part 3 disagree on dates or scope, Part 1 wins.**

Part 3 describes a real-world engagement with hardware procurement, board approvals and an on-site installation running to 31 January 2027. That is the client's calendar, not the build calendar. **The GPU procurement thread is out of scope for the build** — it is kept because the reasoning behind the hardware constraint shapes D3, not because anything needs to be built for it.

---

# Part 1 — Build plan

## Objective

Produce a **portfolio-grade** working system that demonstrates competence to a prospective client on Upwork, in two weeks.

This is not the same as a client-grade system. Client-grade means it survives three years on someone's server. Portfolio-grade means it works, it is honest about its limits, and it proves the developer can build the client-grade version.

## Available time

~30–40 hours per week, alongside full-time employment. **Two weeks for Sanad**, starting Monday 26 October.

## The cut line

### Build — these are the reasons the project is worth showing

| Area | Requirement |
|---|---|
| **Bilingual interface** | `ar.json` + `en.json` from the first commit. `dir` follows locale. CSS logical properties only. Full mirroring. `?lang=ar` and `?lang=en` both work. |
| **Arabic text handling** | Normalise alef forms, hamza forms, taa marbuta, tatweel, diacritics before matching — keep the original string. A search for `التعليم` must match `التعليــم`. |
| **Ingestion pipeline** | PDF/DOCX/TXT → text per page → clean → chunk → embed → store. Each stage visible in the UI. Failures show a readable reason. |
| **Chunking** | Page-bounded, paragraph-aligned, ~350 tokens target, 512 hard max, ~15% overlap. See D1. |
| **Embeddings** | `BAAI/bge-m3`, run locally. See D2. |
| **Retrieval + answer** | Answer generated from retrieved chunks only. Citations to document and page. Click a citation, the page opens. |
| **Three-band refusal gate** | Refuse / low-confidence-with-banner / answer. See D4. **This is the single most important behaviour in the product.** |
| **Evaluation harness** | **15 questions** (reduced from 25) with expected answers, a script that runs them, a score reported in the README including the failures and why. |
| **Three roles** | Viewer / Editor / Admin. Restricted documents excluded from *retrieval* for Viewers, not merely hidden. |
| **Guest account** | Read access, sample data, `?lang=en` by default. |
| **`docker compose up`** | Brings the whole system up on a clean machine. |
| **README** | English. Includes the Decisions section and the evaluation score. |

### Defer to v2 — say so in the README rather than pretending they do not exist

- Document versioning, `version_group_id`, superseded handling, the amendment chain
- Paragraph-level citation highlighting — **page-level is sufficient**
- The detailed Admin usage log and retention policy
- Bulk upload with per-file progress states — a simple multi-file upload is enough
- Everything GPU: procurement, benchmarking, tier tables, measured answer times
- API-mode provider switching — keep the abstraction, ship local only

Listing deferred items explicitly in the README is itself a signal of professionalism. Hiding them is not.

## Language and presentation

The build is bilingual either way. What changes is how it is presented.

- **The demo opens in English.** The guest link is `?lang=en`. A foreign client who opens an Arabic-first page closes it.
- **The README is in English.**
- **The language toggle is the demonstration moment.** Record a 15-second clip: press the toggle, the entire interface mirrors — layout, charts, dates, numbers. Most developers cannot do this correctly.
- **Positioning:** not *"I build Arabic applications"* but *"I build applications that work correctly in both directions — most developers get RTL wrong."* Arabic is a capability that differentiates, not a frame that confines.

## Schedule

| Week | Dates | Work |
|---|---|---|
| 1 | 26 Oct – 1 Nov | Ingestion, chunking, embeddings, retrieval, Ask screen, bilingual shell |
| 2 | 2 – 8 Nov | Roles, Library, document viewer, refusal gate, evaluation harness, Docker, README |
| — | **~8 Nov** | **Sanad complete, published to portfolio** |
| 3 | 9 – 15 Nov | Majra |
| 4 | 16 – 22 Nov | Mirsad |

End of November is the honest buffer.

**Start bidding on Upwork immediately. Do not wait for the portfolio.** The two tracks run in parallel. A real client teaches more than a practice project, because a real client pays, delays and changes their mind.

## Definition of done

- [ ] `docker compose up` works on a clean machine
- [ ] Guest account reaches a working answer with a citation in under three clicks
- [ ] Language toggle mirrors the interface without losing state
- [ ] Evaluation script runs and reports a score; failures documented in the README
- [ ] The refusal behaviour is demonstrable — a question with no answer in the corpus produces a refusal, not an invention
- [ ] README has a Decisions section
- [ ] Deferred items listed honestly

## The two things that are never cut

1. **The refusal gate.** A system that invents answers is worse than no system. The client said this is the single most important behaviour, and it is also the thing that distinguishes a developer who has thought about failure from one who has only thought about the happy path.

2. **The evaluation score.** Most portfolios are screenshots. This one ships a number that proves the thing works. If time runs short, reduce the question count — do not remove the harness.

---

# Part 2 — Decisions log

Every decision settled so far, in one place. Sources: *Client Answers to Open Questions* (24 Oct), *Client Review of the Decisions Draft* (24 Oct), *Client reply* (25 Oct).

## Technical decisions

| # | Decision | Resolution |
|---|---|---|
| **D1** | Chunk size and overlap | Page-bounded, paragraph-aligned. ~350 tokens target, 512 hard max, ~15% overlap. Page tail under 80 tokens merges into the previous chunk on the same page. Tokens, not characters — Arabic attaches clitics, so character and word counts both mislead. |
| **D2** | Embedding model | `BAAI/bge-m3`, local, 1024-d. Local for privacy, not cost — an API would be cheaper. Keep that sentence in the README verbatim. |
| **D3** | Local model or API for generation | **Local only.** API path stays in the code behind a deliberate override, for benchmarking on synthetic data only. Never enabled for client documents. |
| **D4** | Weak but non-empty retrieval | Three-band gate biased toward refusing: refuse / low-confidence with amber banner / normal answer. The LLM outputs `NO_ANSWER` when excerpts do not contain the answer. Any answer without a valid `[n]` citation is turned into a refusal. |
| **D5** | Document updates | *Deferred to v2 for the portfolio build.* Client decision for the record: both, explicitly — full rewrite becomes a new version, a letter sits alongside as a linked document, with the whole chain visible. |
| **D6** | Citation depth | *Page-level for the portfolio build.* Paragraph-level deferred to v2. |

## Client answers

| # | Question | Answer |
|---|---|---|
| **Q1** | API-mode LLM sending excerpts off-server | **No.** Local only. Pattern masking is insufficient — donor agreements contain confidential commercial terms, not just names and IDs. |
| **Q2** | Restricted documents | **Yes.** One `restricted` flag. Editors and Admins only. Must be excluded from *retrieval* for Viewers — a Viewer must never receive an answer drawn from a restricted document, even uncited. |
| **Q3** | Share of scanned images | Unknown; client estimates 15–20% (material from 2015 and earlier). Fail clearly with *"this file has no text layer (scanned image)"* rather than indexing empty. Report the real count. |
| **Q4** | Guest account | Sample data only. Never reaches a real document. |
| **Q5** | "Type" in the Library | **Both** — file type and document category. Categories: annual report, donor agreement, programme evaluation, field survey, budget, board minutes. Flag anything that does not fit rather than inventing a category. |
| **Q6** | Digits in the Arabic interface | **Latin (123) by default in both languages.** Switchable in config. This is how the client writes reports and how donors read them. |
| **Q7** | Usage log retention | 12 months then automatic deletion. Admins may see who asked what. *Detailed log deferred to v2.* |
| **Q8** | Server hardware | 16 cores, 64 GB RAM, **no GPU**. Dell PowerEdge T440 tower, Ubuntu 22.04, two free full-height x16 **Gen 3** slots, single **495 W** non-redundant PSU, **no spare GPU power connectors**. *Procurement out of scope for the build.* |
| **Q9** | Scale | 300–400 new documents per year. Under 20 accounts, 5–8 concurrent. |
| **Q10** | Real sample documents | Eight annual reports, **already published publicly** on the client's website. No de-identification needed; use them normally. |

## Behaviour requirements added during review

| Requirement | Source |
|---|---|
| The Ask screen must never look frozen. Stream the answer, or show the stage — searching / reading sources / writing. If an answer will take more than ~20 seconds, say so **before** the user starts waiting. | Client review, D3 |
| Streaming must never weaken the refusal rule. If the final check rejects an answer, the streamed text is **replaced** by the refusal message. The amber low-confidence banner appears **before** the first word, not after. | Imam's reply, accepted |
| Refusals split into *"the documents don't cover this"* and *"the model found nothing usable in what it read"* — that split separates honesty from a retrieval problem. | Imam's reply, accepted |
| When a citation comes from a converted Word file, the citation card says so, because the page number may differ from Word's own paging. | Client review |
| Network isolation stated plainly in the README, in one paragraph the client's IT person can point at. | Client review |

## Data handling rule — binding

> No content from the Foundation's archive is ever sent to any external service, including AI coding assistants, under any circumstances, **including debugging**. Diagnosis uses file names, error messages, page counts and extracted statistics only. If a document must be examined, it is examined on the Foundation's own server.

This goes in the README. The moment it protects is not the build — it is January, when something fails on a specific document and a person under time pressure is tempted to paste it into a tool.

**Exception:** the eight sample reports are already public and may be handled normally.

---

# Part 3 — Client correspondence, 25 October 2026

> **From:** Al-Mustaqbal Development Foundation
> **To:** Imam Mousa Ali Ibrahim
> **Re:** Your reply to our review, and the GPU request for quotation

This is the clearest plan we have been given by a supplier, and the GPU note is the first time anyone has told us *"we cannot give you the figure yet, and here is exactly why"* instead of inventing one. That is worth more to us than a fast answer.

### 1. Server details

**Make and model:** Dell PowerEdge T440 — **tower**, not rack.

| | |
|---|---|
| CPU | 2 × Intel Xeon Silver 4208 (8 cores each, 16 total) |
| RAM | 64 GB |
| OS | **Ubuntu 22.04 LTS** (not 24.04 — please confirm driver 570 is available) |
| Free PCIe slots | Two full-height **x16, Gen 3** |
| Power supply | Single **495 W**, not redundant |
| Spare GPU power connectors | **None** |

Khaled, our IT person, will send photos of the inside of the case by **29 October**.

Three things we can already see might matter:

- The power supply is 495 W and not redundant. If a 145 W card is too close to the limit, quote the replacement supply as a separate line.
- There are no spare GPU power cables.
- The slots are **Gen 3**, not Gen 4 or 5. If that slows anything down, tell us by how much.

### 2. Our board meeting — and this is a problem

**The next regular board meeting is 15 December**, after your November ordering deadline.

Our **Director can approve a capital purchase up to USD 5,000** with the Treasurer's written agreement. Above that we need an extraordinary board approval by email, which takes about two weeks.

- Under USD 5,000 all in → approval within about a week of the quote.
- Over USD 5,000 → two weeks, and harder.

The RTX PRO 4000 at USD 3,100–3,400 plus VAT, customs and installation should land under the threshold. The RTX PRO 4500 at USD 4,600–5,800 almost certainly will not.

**So treat "does the RTX PRO 4000 physically fit our T440?" as the most valuable thing you can establish this month.** We need the quote in our hands by **20 November**.

### 3. Amendments to donor agreements

Both happen. **Most are letters** changing specific clauses — a budget reallocation, a no-cost extension, a change of reporting dates — with the original still in force for everything untouched. **Occasionally a full restatement**, usually on a long extension.

Your default is right. What we need on top: when we open an agreement, we must see **the whole chain at a glance**, in date order. One agreement can carry four amendments across three years, and our question is always *"what are the current terms?"* — which no single document answers alone.

### 4. The eight sample reports, and your handling proposal

**We agree, and you raised this before we did. That is the reason we are comfortable working with you.**

**A correction that makes your life easier:** the eight reports are **already published on our public website**. We chose them for that reason. Use them normally.

**The rule that actually matters** applies to the real archive, with no exceptions — and the moment that concerns us is January, during installation, when something fails on a specific document. Write the rule down now, while nobody is under pressure, and put it in the README. If that makes some debugging impossible, tell us now and we will plan for it.

The eight reports will be sent by **28 October**.

### 5. VAT

Likely exempt, but do not assume it. As a registered non-profit we can usually obtain exemption on donor-funded capital purchases, but it requires Ministry paperwork and is not instant. **Quote with 16% VAT as a separate line** so we see the full figure against the Director's threshold. We will pursue the exemption in parallel.

### 6. Overall deadline

Confirmed. **Week 1 starts Monday 26 October.** **Final acceptance 31 January 2027.** Your milestone dates — 8 November, 19–22 November, 17–20 December — accepted as written.

### 7. The four smaller points

Answered in our note of 24 October (Q2, Q5, Q6, Q7). Repeated so nothing is blocked: restricted flag **yes**; "Type" **both**; digits **Latin**; log retention **12 months**.

One request offered helpfully: please keep a **single running list of what we have decided**. Over three months we will answer many questions, and if the same ones come back we will start to wonder whether our earlier answers were recorded. A decisions log in the repository settles that permanently — and it is the document we will hand to whoever maintains this after you.

### Comments on the quotation template

**Approved to send, with five changes.**

1. **Three suppliers, not two.** Our procurement rules require three written quotes above USD 2,000.
2. **Validity 45 days, not 30.** A 30-day quote could expire before the Director signs.
3. **Price in both ILS and USD.** Our board works in USD, our accounts in ILS.
4. **Ask each supplier for a fallback:** *"If the preferred card is unavailable within the stated lead time, what would you recommend instead that meets §1 and fits §2, and at what price?"* This avoids a second round in December.
5. **Add our registration details and CC our finance officer.** Sent with the photos on 29 October.

The clause requiring the supplier to **confirm in writing that the card physically and electrically fits** is the one we would have forgotten, and the one that will protect us.

### One correction

The **production-model score is the number we will quote to our board and judge acceptance on.** The CPU score is context. If the GPU has not arrived by week 8, report the production-model score measured on rented hardware and label it clearly. Do not let a late delivery turn into a missing number.

---

*End of document.*
