# Open questions

Last updated 24 Oct 2026, after the client's review of the decisions draft and the project owner's answers. Each open item has the default we'll build if we don't hear back. Every default is reversible.

## Still open — client (Al-Mustaqbal Development Foundation)

| # | Question | Why it matters | Our default |
|---|---|---|---|
| **N1** | **Server make, model and chassis** (rack or tower), with photos of the inside if possible: free PCIe x16 slots, height and length clearance, PSU wattage, spare PCIe power connectors. The full checklist is in the [research note](research/2026-10-24-gpu-and-hosted-apis.md) §1. | Decides which 24 GB card physically fits and whether the PSU must be upgraded, so it decides the price (deliverable 1). Rack servers often accept only passively cooled data-centre cards. | We prepare RFQs for two card classes (data-centre and workstation) until we know. |
| **N2** | **Date of the next board meeting**, when the GPU price has to be in hand. | Deadline for deliverables 1–2. | We target the end of week 2 (8 Nov). |
| **N3** | **Donor agreement amendments:** is each amendment a **full consolidated text** of the agreement, or a **letter changing some clauses**? | A consolidated text can supersede the previous version. A partial letter must not, or the unchanged clauses disappear from answers (DECISIONS D5). | D5 as approved: a consolidated amendment is uploaded as a new version, and a letter as an ordinary document alongside the agreement. The schema carries an optional amendment link; its screens are built only if letters are the norm. |
| **N8** | **Can the foundation buy VAT-exempt** (NGO registration or donor agreement terms)? Please also ask suppliers to show VAT and customs separately. | Changes the installed price by ~16%. | Quote with VAT shown separately. |
| **N7** | **Overall deadline and final acceptance date.** The owner asked on 24 Oct; the reply is pending. | Fixes the January install and final acceptance; until then the ROADMAP timeline is provisional. | Final acceptance together with the GPU install, before 31 Jan 2027. |
| **N4** | **Handling of the eight sample reports.** Parts of this project are built with AI coding assistants that run on a cloud service. If an assistant *reads* the text of your reports, that text leaves your control, which is the thing you've asked us to prevent. Do you agree to this procedure? (a) The reports stay on the project owner's machine, never in git and never sent to any API. (b) Only scripts that output **aggregate numbers** (rates and counts, no text, titles or names) are run on them. (c) Anything visual is inspected by the project owner personally. | Your privacy rule applies to the samples too, even if de-identified. | Procedure (a)+(b)+(c). The project owner runs the scripts himself if needed. |
| **N5** | **How will the eight sample reports reach us, and when?** | The week-4 page-split report (deliverable 3) and the week-8 highlight rate (deliverable 5) need them. | By week 2 at the latest. |
| **N6** | **Milestone dates.** We assume week 1 starts on **Mon 26 Oct 2026**, so the week-4 demo falls on ~19–22 Nov and the week-8 demo on ~17–20 Dec. Correct? | Fixes the plan in ROADMAP. | As assumed. |
| Q2 | **Should some documents be restricted** (salary sheets, beneficiary lists) to Editors and Admins only? | As written, every Viewer can read every document. | No restriction in v1. We'd recommend a small `restricted` flag. |
| Q5 | **"Type" in the Library:** file type (PDF/Word/Text) or document category (annual report, donor agreement, evaluation, survey, budget, board minutes)? | The brief uses "type" for both. | We store and filter on both. Please confirm the category list. |
| Q6 | **Digits in the Arabic interface:** Arabic-Indic (١٢٣) or Latin (123)? | Affects every date and number shown. | Arabic-Indic (the `Intl` default for `ar`), switchable in config. |
| Q7 | **Usage log retention:** how long should questions be kept, and may Admins read every staff member's questions? | Questions can themselves contain personal data. | Kept indefinitely, visible to Admins, retention configurable. |
| Q9 | **Scale:** documents added per year and expected concurrent users? | Sizing, and whether one worker is enough. | ~4,000 documents now, under 20 concurrent users. |

## Answered — client (24 Oct 2026)

| # | Answer |
|---|---|
| Q1 | **No API mode for documents**, now or later, unless their policy changes. The API path stays in code behind the override file, for benchmarking on synthetic data only. |
| Q3 | Scanned files fail clearly ("no text layer"). The client wants **the count** after the first full ingestion run on the archive (deliverable 4). |
| Q4 | Guest sees **sample documents only**. |
| Q8 | **REVISED.** The server has 16 cores and **64 GB** of RAM. The **GPU is approved in principle** once we provide a local installed price (in writing) and a measured or clearly estimated answer time. Build on CPU in weeks 1–8; the GPU must be in place **before 31 January**. |
| Q10 | The client refers to **"our eight sample reports"**, so real samples are coming. Delivery and handling are in N4 and N5. |
| — | Production speed target: **under 15 s per answer**. The Ask screen must never look frozen (stream, show stages, warn when more than ~20 s is expected). |

## Project owner (Imam)

### Open

| # | Question | Needed for | Default |
|---|---|---|---|
| **P4** | **Approve renting one RTX PRO 4000 Blackwell for ~2–3 h** on Vast.ai: about $1 of use, but a $5 minimum top-up. Synthetic data only, and the instance is destroyed afterwards. This is narrowed from three cards because the owner's RTX 5080 PC now covers development speed. The 5080 can't stand in for the client's card: it has more memory bandwidth, so it would flatter the numbers by ~30%. | Deliverable 2 (measured time), target week 2 | No rental. Deliverable 2 becomes an estimate scaled from the 5080, clearly marked. |
| **P6** | **Set up the RTX 5080 PC as the dev LLM server**:<br>1. Install Ollama.<br>2. Make it listen on the LAN (`OLLAMA_HOST=0.0.0.0:11434`), and allow port 11434 only from the local network.<br>3. Send the manager the PC's local IP. | S3 quality runs (week 1–2), then R1/E1 development, the week-4 baseline, E2 sweeps (week 6) and headline runs (week 8) | S3 and later tasks run on the Mac (Metal or CPU), which is slower. |
| **P5** | **Create a free Google Gemini API key** (Google AI Studio; needs only a Google Cloud project, no card; officially available in Palestine). Put it in your local `.env` only, never committed. Optional: if you have a Claude Max or Team plan, its monthly API credits make Claude a free second reference. | S3, E1 and E2 reference runs on synthetic data | Skip the reference runs. |

### Answered 24 Oct 2026

| # | Answer | Consequence |
|---|---|---|
| P0 | **Push hold lifted** (24 Oct). | `main` pushed. Executors push their task branches and open PRs; the manager verifies and merges with the owner's go-ahead. |
| P1 | **The repo stays public, deliberately.** | `docs/brief.md` may be public. Still never commit client documents, secrets or anything under `data/`. |
| P2 | **Agents may download public files for testing**, with conditions: they go inside the project folder, they are git-ignored, and they are deleted when no longer needed. | Downloads go in `spikes/_downloads/` (git-ignored), listed in a committed manifest with a fetch script, and deleted after the manager's verification. Unchosen model weights are removed too. See CLAUDE.md. |
| P3 | **Prefer a free API for QA.** Is Anthropic mandatory? **No.** | Benchmarks against a hosted reference model use the **Google Gemini API free tier** (`gemini-3.1-flash-lite`, `gemma-4-31b-it`) through the `openai_compat` adapter, on **synthetic data only**. Cohere's trial key is the backup. The `anthropic` adapter is built but needs no key. See the research note. |
