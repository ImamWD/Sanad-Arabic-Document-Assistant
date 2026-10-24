# Open questions

The brief says to raise anything essential *before starting*. Each item has our default, which we'll build if we don't hear back. Every default is reversible.

## For the client (Al-Mustaqbal Development Foundation)

| # | Question | Why it matters | Our default |
|---|---|---|---|
| Q1 | **API-mode LLM sends excerpts off-server.** May we offer it at all? If yes, do you want automatic masking of national-ID and phone-number patterns before sending? | Conflicts with "no document content leaves the server". Excerpts can contain names, IDs and salaries. | Local only. API mode is built but off, and enabling it needs your written OK. |
| Q2 | **Should some documents be restricted** (salary sheets, beneficiary lists) to Editors and Admins only? | As written, every Viewer can read every document. | No restriction in v1, but we'd recommend adding a small `restricted` flag. Your call. |
| Q3 | **Roughly what share of the ~4,000 files are scanned images?** | OCR is out of scope. If a large share is scanned, v1 can't reach that knowledge. | We detect scans and report them clearly. We can produce a count after a dry run on your archive. |
| Q4 | **Guest account on the production server:** keep it restricted to sample data, or disable it? | A shared read login on real data would expose personal data. | Guest sees only sample documents. |
| Q5 | **"Type" in the Library:** file type (PDF/Word/Text) or document category (annual report, donor agreement, evaluation, survey, budget, board minutes)? | The brief uses "type" for both. | We store and filter on both. Please confirm the category list. |
| Q6 | **Digits in the Arabic interface:** Arabic-Indic (١٢٣) or Latin (123)? | Affects every date and number shown. | Arabic-Indic (the `Intl` default for `ar`), switchable in config. |
| Q7 | **Usage log retention:** how long should questions be kept, and is it fine that Admins can read every staff member's questions? | Questions can themselves contain personal data. | Kept indefinitely, visible to Admins. Retention is configurable. |
| Q8 | **Target server hardware:** cores, RAM, and is there an NVIDIA GPU? | Determines which local model we can run and how fast answers are (DECISIONS D3). | We design for a CPU-only 16-core / 32 GB server and recommend a 24 GB GPU. |
| Q9 | **Scale:** documents added per year and expected concurrent users? | Sizing, and whether one worker is enough. | ~4,000 documents now, under 20 concurrent users. |
| Q10 | **Could you share 5–10 de-identified real documents** (ideally older Arabic PDFs)? | Generated test PDFs extract cleanly. Real ones often have reversed text or odd glyphs, so without real samples our evaluation score will overstate what you'll see. | We test on public Arabic reports from international organisations instead. |

## For the project owner (Imam)

| # | Question | Default |
|---|---|---|
| P1 | The GitHub repo is **public**. Keep it public? The brief (client name) is in `docs/brief.md`, and no client documents will ever be committed. | Keep public, but don't push `docs/brief.md` until you confirm. |
| P2 | May executor agents **download public Arabic PDFs** (e.g. UN or NGO annual reports) for extraction tests? They are kept out of git. | Ask for each batch. |
| P3 | An **Anthropic API key** for the S3 quality baseline and for API mode testing, used on synthetic seed data only. | Skip the API baseline until a key is available. |
