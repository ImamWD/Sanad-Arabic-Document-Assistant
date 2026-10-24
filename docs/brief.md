# Sanad — Arabic Document Assistant

**Client brief · Project 1 of 3**
Prepared for: Imam Mousa Ali Ibrahim
Date: 22 October 2026

---

## 1. Who this is for

Al-Mustaqbal Development Foundation is a mid-sized NGO. Over eleven years they have accumulated roughly 4,000 documents: annual reports, donor agreements, programme evaluations, field surveys, budgets and board minutes. Most are Arabic PDFs, some are Word files, a few are English.

The knowledge exists. Nobody can reach it.

When a donor asks "what were the outcomes of the youth employment programme in 2021?", a staff member spends two hours opening files and guessing at names. New employees are effectively locked out of eleven years of institutional memory. The organisation re-commissions studies it has already done.

They cannot upload these documents to ChatGPT or any foreign cloud service. The files contain beneficiary names, national ID numbers, salary data and donor terms.

---

## 2. What we want

A web application where a staff member asks a question in Arabic and gets an answer drawn from our own documents, with a citation to the source file and page.

It must run on infrastructure we control.

---

## 3. In scope

- Upload documents (PDF, DOCX, TXT) individually or in bulk
- Automatic text extraction, including Arabic PDFs
- Ask questions in Arabic or English
- Answers cite the source document and page number
- Click a citation to open the source at that page
- Search and filter the document library by title, type, year, programme
- Three user roles (below)
- Full Arabic and English interface

## 4. Out of scope

Do not build these. If you think one is essential, raise it before starting.

- Mobile applications
- Editing documents inside the app
- OCR for scanned images (assume text-layer PDFs for v1)
- Multi-organisation tenancy
- Payment or billing
- Email notifications

---

## 5. Roles

| Role | Can do |
|---|---|
| **Viewer** | Ask questions, read answers, open source documents |
| **Editor** | Everything above, plus upload, tag and archive documents |
| **Admin** | Everything above, plus manage users and view usage logs |

---

## 6. Screens

**Login** — email and password. Language switch visible before login.

**Ask** — the main screen. A question box, the answer, and beneath it the citations as cards: document title, page, and a snippet of the matching text. A history of this user's previous questions in a side panel.

**Library** — table of all documents: title, type, year, programme, uploaded by, date, page count, indexing status. Filters and search. Row click opens the document viewer.

**Upload** — drag and drop, multiple files. Shows per-file progress: uploaded, extracting, indexing, ready, failed. A failed file shows why.

**Document viewer** — the source document with the cited page highlighted.

**Admin** — user list with roles, and a usage log: who asked what and when.

---

## 7. Data model

Design the schema yourself, but it must support at least:

- **users** — name, email, password hash, role, preferred language
- **documents** — title, original filename, file path, type, year, programme, uploaded_by, uploaded_at, page_count, status, language
- **chunks** — document_id, page_number, chunk_index, text, embedding
- **queries** — user_id, question, answer, language, created_at
- **citations** — query_id, chunk_id, rank

Explain in the README why you chunked the way you did.

---

## 8. Key flows

**Upload to ready**
File arrives → text extracted per page → text cleaned → split into chunks → embeddings generated → stored → status becomes ready. Each stage is visible in the UI. A failure at any stage shows a readable reason, not a stack trace.

**Question to answer**
Question received → embedded → nearest chunks retrieved → answer generated from those chunks only → citations attached → answer and citations stored.

If no relevant chunk is found, say so. Do not invent an answer. This is the single most important behaviour in the product.

---

## 9. Arabic requirements

This is the part most developers get wrong, so it is specified explicitly.

- **No hardcoded strings anywhere.** All interface text lives in `ar.json` and `en.json` from the first commit.
- **CSS logical properties only** — `margin-inline-start`, not `margin-left`. The layout mirrors itself when direction changes.
- **`dir` follows the active locale**, set on the document root.
- **Dates, numbers and currency formatted through `Intl`**, never manually.
- **Arabic text processing**: handle diacritics, different alef and hamza forms, and the tatweel character when chunking and matching. A search for "التعليم" must match "التعليــم".
- **Mixed content must not break**: an English product code or URL inside an Arabic sentence stays readable and correctly ordered.
- **Seed data in both languages** — real-looking Arabic document titles and programme names, not `test1` or lorem ipsum.
- `?lang=ar` and `?lang=en` both work as entry points.

---

## 10. Technical

- Your choice of stack, but justify it in the README
- Runs entirely on our own server. No document content leaves it.
- The language model may run locally or through an API — tell us the trade-off and let us choose in config
- Docker compose for the whole thing, so our IT person can run it
- Seeded demo data so the app is useful the moment it starts

---

## 11. Evaluation

Build a set of **25 test questions** with expected answers, and a script that runs them and reports how many were answered correctly with the right citation.

We will judge the system on that number, not on how it looks. Include the result in the README, including the questions it fails and why.

This is a deliverable, not an extra.

---

## 12. Acceptance criteria

- A new user can log in, ask an Arabic question, and reach the correct source page in under three clicks
- Uploading 50 documents shows clear progress and recovers from one corrupt file without stopping the batch
- The interface switches language without reloading data or breaking layout
- The evaluation script runs and reports a score
- A guest account exists with read access and sample data loaded
- `docker compose up` brings the whole system up on a clean machine

---

## 13. Decisions you need to make and tell us about

These are genuinely open. We do not know the right answer and want your recommendation with reasoning.

1. **Chunk size and overlap for Arabic text.** Arabic averages more characters per concept than English. What did you choose and why?
2. **Embedding model.** Which one handles Arabic well, and does it run locally or via API? What does that cost us per 1,000 documents?
3. **Local model or API for generation.** We prefer local for privacy. What hardware does that require, and how much quality do we lose?
4. **What happens when retrieval is weak but not empty.** Do you answer with low confidence, or refuse? Show us the behaviour.
5. **Document updates.** If we upload a newer version of a report, does it replace the old one or sit alongside it?
6. **How far back citations point.** Page is the minimum. Is paragraph-level feasible?

Write your answers in the README under "Decisions". We will read that section first.
