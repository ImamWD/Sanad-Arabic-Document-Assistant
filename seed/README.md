# Seed corpus

This folder holds Sanad's demo and evaluation corpus. It is a set of **synthetic** documents from a fictional NGO, written in Arabic and English. The guest account sees exactly this data, and the evaluation sets in [`eval/`](../eval) are answered from it.

> **Everything here is fictional.** The organisation, donors, evaluators, governorates, villages, people, ID numbers and figures are all invented. People are always marked as pseudonyms (اسم مستعار / pseudonym). The only URLs are `example.org`, and the only emails are `@example.org`. No document is based on a real organisation's records.

| Path | What it is | Written by |
|---|---|---|
| `sources/<doc_id>.md` | Authoring source of each document: YAML front matter plus page-marked body | C1a |
| `manifest.json` | Organisation, programmes and one metadata entry per document. **The manifest is authoritative.** | C1a |
| `documents/` | Rendered files (PDF, DOCX, TXT), one per manifest entry | C1b |
| `bad/` | Ingestion failure fixtures (see [`bad/README.md`](bad/README.md)) | C1b |
| `previews/` | PNGs of three rendered pages: an Arabic PDF, an English PDF, and a DOCX after LibreOffice conversion | C1b |
| `render.py` | Renders `sources/` into `documents/`, `bad/` and `previews/` (`make render-seed`); see §6 | C1b |

---

## 1. The fictional world

### Organisation

The issuing organisation has exactly **two fixed name forms**. Both are defined in `manifest.json` under `organization`, so a later rename is a mechanical find-and-replace.

| | Arabic | English |
|---|---|---|
| Name (only form used) | مؤسسة الريحان للتنمية | Al-Rayhan Development Foundation |
| Short reference | المؤسسة | the Foundation |
| HQ city | مدينة الريحان | Al-Rayhan |

- **Founded:** 2014. Registration number `FAKE-REG-2014-0417`.
- **Website:** https://example.org. Email: info@example.org.
- **Name usage:** the name never appears in any other spelling, case ending or diacritised form. Diacritised passages say المؤسسة instead.
- **Real client:** the client's real name is never used anywhere in this public repo (manager decision, 24 Oct 2026).

### Currency and number conventions

- **Currency:** all money is in **US dollars**: `دولار أمريكي` in Arabic, `USD` in English. No other currency appears.
- **Digits by document:**

  | Documents | Digits | Thousands separator | Percent sign |
  |---|---|---|---|
  | Most documents | Latin (`2021`, `4,180,000`) | `,` | `%` |
  | `gep-enrolment-survey-2015`, `annual-report-2016` | Arabic-Indic (`٢٠١٥`, `١٬٨٥٠`) | `٬` | `٪` |
  | `board-minutes-2017-11` (Windows-1256) | Latin only, because cp1256 has no Arabic-Indic digits, no `٪` and no `٬` | `,` | `%` |

  The Arabic-Indic documents exercise digit normalisation.
- **Project codes:** `<PROGRAMME>-<YEAR>-<NN>`, for example `YEP-2021-03`. They appear inside Arabic sentences, as do `https://example.org/...` URLs, to exercise bidi handling.

### Programmes

The six programmes are listed with their bilingual names, one-line descriptions and regions in `manifest.json` under `programmes`.

| Code | Arabic name | Started | Regions |
|---|---|---|---|
| YEP | برنامج تمكين الشباب للتوظيف | 2020 | وادي الريم، السنابل |
| WASH | مشروع المياه والإصحاح البيئي في المناطق الريفية | 2018 (baseline 2017) | الهضبة الشرقية، سهول النخيل |
| GEP | برنامج دعم التعليم الأساسي للفتيات | 2015 study, activities from 2016 | سهل القمر |
| WLP | برنامج سُبل العيش للنساء المعيلات | pilot 2018 | وادي الريم، مرج الزعفران |
| CHP | برنامج الصحة المجتمعية | June 2016 | سهول النخيل، الهضبة الشرقية |
| SPC | مبادرة الحماية الاجتماعية والدعم النقدي | April 2020 | مرج الزعفران، السنابل |

All six governorates are invented: وادي الريم (Wadi Al-Reem), السنابل (Al-Sanabel), الهضبة الشرقية (Eastern Plateau), سهول النخيل (Palm Plains), سهل القمر (Sahl Al-Qamar), مرج الزعفران (Marj Al-Zaafaran). So are the district and village names inside them.

### Donors, evaluators and partners (all invented)

| Name | Role |
|---|---|
| صندوق سِدرة الوادي للتنمية (Sidrat Al-Wadi Development Fund) | Funds `WASH-2018-01` |
| صندوق تلال العنبر للتنمية (Tilal Al-Anbar Development Fund) | Funds `YEP-2020-01`, `WASH-2020-02`, `SPC-2023-01` |
| Thornvale Education Trust (صندوق ثورنفيل للتعليم) | Funds `GEP-2019-02` |
| Varnholt Foundation (مؤسسة فارنهولت) | Funds `YEP-2021-03` «مسارات رقمية / Digital Pathways» |
| مؤسسة بيارق النور الخيرية (Bayariq Al-Nour Charitable Foundation) | Funds `WLP-2022-01` |
| Quillmere Health Fund (صندوق كويلمير للصحة) | Funds `CHP-2021-01` |
| مكتب سراج الهضبة للاستشارات التنموية | Evaluator, YEP final evaluation 2022 |
| مركز تل الورد للبحوث والتقييم | Evaluator, WASH 2021 and CHP 2024 |
| Corvane Evaluation Partners | Evaluator, GEP mid-term 2020; WLP market assessment 2025 |

The external auditor is never named. No document contains bank names or account details.

### Personal data

Every item of personal data is visibly synthetic:

- **People:** names carry `(اسم مستعار)` / `(pseudonym)`, or sit under a heading stating that all names are pseudonyms.
- **Identifiers:** they always start with `FAKE-`, for example `FAKE-REG-2014-0417`, `FAKE-HH-0001` or `FAKE-0000-1234`. No realistic national-ID or phone-number format is used.
- **Salaries:** salary scales appear only in budget documents. They are labelled as illustrative, list grades rather than people, and are never tied to a named person.

### Deliberate test content

| What | Where | Why |
|---|---|---|
| Fully diacritised passage | `annual-report-2021` p2 (board chair's foreword) | Normalisation (B1) |
| Tatweel in headings | `annual-report-2021` p9 (`التعليــم`) and p11 (`الصحـة`), `annual-report-2020` p9 (`الصحـة`), `annual-report-2022` p10 (`العيـش`) | A search for التعليم must match التعليــم |
| Arabic-Indic digits | see the digits table above | Digit normalisation, S1 extraction |
| Codes and URLs inside Arabic sentences | most documents | Bidi handling (F1), extraction (S1) |
| Windows-1256 text file | `board-minutes-2017-11` | TXT encoding fallback (B3) |
| Draft and final version of one budget | `budget-2024-draft` and `budget-2024-final` | Version supersede (DECISIONS D5) |
| Quoted "ignore previous instructions"-style text inside a survey response | `spc-satisfaction-survey-2024` p3 (Arabic), `wlp-market-assessment-2025` p4 (English) | Prompt-injection test (R1). Never on an eval-cited page. |
| Bilingual (Arabic plus English) documents | `yep-grant-agreement-2021`, `yep-employer-survey-2022` | Mixed-direction rendering, cross-lingual retrieval |
| Paragraph that runs across a page break | `gep-enrolment-survey-2015` p3→p4 (eval D07), `chp-evaluation-2024` p4→p5 (eval T14) | Whether page-bounded chunking (DECISIONS D1) loses context. The subject is on page N, which ends mid-sentence with no full stop; the fact opens page N+1. |

---

## 2. Source format

Each document is one UTF-8 file `sources/<doc_id>.md`:

```markdown
---
doc_id: annual-report-2021
title_ar: "التقرير السنوي 2021"
title_en: "Annual Report 2021"
category: annual_report
year: 2021
programme: null
language: ar
format: pdf
page_count: 16
replaces: null
---

<!-- page 1 -->

# التقرير السنوي 2021
...

<!-- page 2 -->
...
```

### Front matter

- **Fields:** the front matter repeats the manifest fields `doc_id`, `title_ar`, `title_en`, `category`, `year`, `programme`, `language`, `format`, `page_count` and `replaces`, plus `encoding` for TXT files.
- **Conflicts:** the manifest wins. A checker should fail on any mismatch.

### Page markers

- **Syntax:** `<!-- page N -->` on its own line, starting at 1, with no gaps.
- **Placement:** nothing but blank lines may come before `<!-- page 1 -->`. The number of markers equals `page_count`.
- **Page breaks:** C1b must force a page break at every marker and nowhere else. Rendered page N must equal source page N, because eval citations use source page numbers.
- **Page 1:** every document carries the one-line synthetic-document notice.
- **Page-split paragraphs:** in two places a paragraph deliberately continues across a marker (see §1, "Deliberate test content"). Page N ends mid-sentence with no closing punctuation, and page N+1 opens with the rest of the sentence, with no heading. Render both parts exactly as written, each on its own page. Don't join them, move text across the break, or add a hyphen or ellipsis.

### Page budget

Each page must fit on one A4 page when rendered:

| Page content | Limit |
|---|---|
| Arabic prose | at most about **250 words** per page |
| English prose | at most about **300 words** per page |
| Mixed pages | budgeted proportionally |
| Tables | at most **12 rows**. A page with a table carries at most about 120 to 150 words of prose. |

Across the corpus, pages use 23–86% of the word budget (median 47%, 90th percentile 61%), so C1b has room for fonts and line height. A few pages carry two short tables (a revenue table and an expenditure table), with at most 9 rows each. Because pages are deliberately under-filled, C1b must not merge pages.

### Body syntax (Markdown subset)

Bodies use only:
- `#` / `##` / `###` headings
- paragraphs (separated by blank lines)
- `-` bullet lists and `1.` numbered lists
- `**bold**`
- `>` blockquote (used for the synthetic notice)
- pipe tables

No raw HTML other than the page markers. No images.

### Direction

| `language` | Document direction | Per-block direction |
|---|---|---|
| `ar` | RTL | inherits RTL |
| `en` | LTR | inherits LTR |
| `mixed` | RTL | each paragraph, list item and table cell takes the direction of its first strong character (what `dir="auto"` computes), so English clauses render LTR. See §6 for the clause isolation. |

### Per-format rendering notes for C1b

**`pdf`**
- Markdown → HTML → Chromium print, with an embedded Arabic font, A4, a page break at each marker.
- A footer with only the page number is fine.
- Avoid a running header that repeats the title. The cleaner strips repeated lines anyway.

**`docx`**
- Markdown → DOCX with an explicit page break at each marker, and RTL paragraphs for Arabic.
- The PDF that LibreOffice produces from this DOCX defines the cited page numbers. C1b must verify it still has `page_count` pages, with the expected text on each page.

**`txt`**
- The body is **plain text**, with no Markdown tables or `#` headings (lists use `-` or `1.`). Copy it verbatim after dropping the front matter.
- Replace each page marker with a **form feed (U+000C)** between pages: no form feed before page 1 and none at the end.
- Encode the file as the manifest `encoding` says: `utf-8` (no BOM) or `windows-1256`.
- **Verified (C1b):** LibreOffice's text import breaks pages at form feeds, so the converted PDF has one page per source page. It does **not** detect Windows-1256: the file comes out as mojibake unless ingestion decodes it first (§6).
- **Eval exposure:** TXT pages are kept short (about 140–190 words). The headline set cites no TXT page. The dev set cites `board-minutes-2017-11` p2 twice (D04, D11), and both facts sit mid-page.

---

## 3. Manifest

`manifest.json` top-level keys:

| Key | Contents |
|---|---|
| `schema_version` | currently `1` |
| `synthetic` | `true` |
| `notice_ar`, `notice_en` | the fictional-content notice |
| `organization` | `{name_ar, name_en, hq_city_ar, hq_city_en, founded, website}` |
| `currency` | `"USD"` |
| `programmes` | list of `{code, name_ar, name_en, description_ar, description_en, regions: [{name_ar, name_en}]}` |
| `documents` | one entry per document (below) |

Document entry fields:

| Field | Notes |
|---|---|
| `doc_id` | kebab-case, unique; also the source file stem |
| `file` | rendered file name, `<doc_id>.<format>` (C1b writes it to `documents/`) |
| `source` | `seed/sources/<doc_id>.md` |
| `format` | `pdf`, `docx` or `txt` |
| `title_ar`, `title_en` | |
| `category` | `annual_report`, `donor_agreement`, `evaluation`, `survey`, `budget` or `board_minutes` |
| `year` | the year the document is about (for a budget, the budget year) |
| `programme` | a programme code, or `null` for organisation-wide documents |
| `language` | `ar`, `en` or `mixed` |
| `page_count` | equals the number of page markers |
| `replaces` | `doc_id` of the earlier version this document supersedes, else `null` |
| `encoding` | **only on `txt` entries:** `utf-8` or `windows-1256` |
| `restricted` | `true` when only Editors and Admins may see the document: it is excluded from retrieval for Viewers and the guest (BUILD_PLAN Q2). On every entry. |
| `archived` | `true` when the document is kept but excluded from retrieval. On every entry. |

### Restricted and archived documents

| Document | Flag | Why |
|---|---|---|
| `wlp-donor-agreement-2022` | `restricted` | A donor agreement whose budget lists the project team's salaries. Its p3 table has **رواتب فريق المشروع: 84,000** USD, a figure no other document contains. R1's restricted-access test asks for it: a Viewer gets a refusal, an Editor the answer. |
| `budget-2024-draft` | `archived` | Versioning is deferred to v2, so the draft stays out of retrieval instead of contradicting the final. |

- No eval item cites either document.
- The checker fails if an item cites an archived document, or if an answered item cites only restricted documents.
- `budget-2018` holds the 2018 salary scale and would be the obvious restricted document, but it is the only source for T12, so it stays open.

### Version pair (DECISIONS D5)

`budget-2024-final` has `replaces: budget-2024-draft`. The final changes these figures from the draft:
- the total
- the YEP allocation
- the SPC allocation
- administrative costs

Eval questions expect the **final** figures and never cite the draft.

---

## 4. Evaluation sets

| File | Contents |
|---|---|
| `eval/questions.yaml` | the 25 **headline** questions (IDs `T01`…). Never used for tuning. |
| `eval/dev_questions.yaml` | the 15–20 **dev** questions (IDs `D01`…) for the chunk sweep and thresholds. Shares no question and no answer fact with the headline set. |

Both files have the top-level keys `set` (`test` or `dev`), `version` and `questions`.

### Item schema

| Field | Type | Notes |
|---|---|---|
| `id` | string | `T01`… or `D01`… |
| `language` | `ar` or `en` | language of the question |
| `kinds` | list | from the vocabulary below |
| `question` | string | paraphrased, never copied from the page |
| `must_include` | list, at most 3 | short atomic facts, written exactly as on the cited page |
| `expected_citations` | list of `{file, page}` | `file` is the manifest `file`; `page` is the source page number |
| `expected_outcome` | `answered` or `no_answer` | |
| `expected_answer` | string or null | Short human reference answer, for the README failure table. **Not used for scoring.** This field goes beyond the minimum schema, because the brief asks for "questions with expected answers". |
| `notes` | string | where the answer is, and why the item is a paraphrase or a near-miss |
| `vocab_shift` | bool | `true` when the question's key terms differ from the page's, the way a staff member would ask |
| `page_split` | bool, optional (default `false`) | `true` when the fact sits in a paragraph that starts on one page and ends on the next. `expected_citations` lists the page where the fact itself appears. Used to report whether page-bounded chunking makes a question fail. |

**`kinds` vocabulary**

| Kind | Meaning |
|---|---|
| `factual` | a single fact |
| `numeric` | the fact is a number |
| `temporal` | compares points in time |
| `cross_document` | needs facts from more than one document |
| `english` | question in English |
| `cross_lingual` | question language differs from the source document's |
| `mixed_content` | hinges on a code or URL inside Arabic text |
| `version` | depends on the superseded/final version pair |
| `diacritics` | the question is written with tashkeel |
| `tatweel` | the question contains tatweel |
| `unanswerable` | the documents don't contain the answer |
| `near_miss` | a related document exists but doesn't contain the answer |

### Rules for `must_include`

- **Atomic:** each fact is a number, code, year, or a name of one or two words. It never spans table cells or anything that might wrap.
- **Exact:** each fact is written exactly as it appears on the page, including thousands separators. Checkers and scorers may fold digit style (Latin, Arabic-Indic or Persian), diacritics and tatweel.
- **Percentages:** written as the bare number, without `%` or `٪`. In RTL text the sign can extract before or after the digits, so the bare number is the stable fact.
- **Unanswerable items:** `must_include: []` and `expected_citations: []`.

### Citation semantics (for the C1b checker and the E1 scorer)

**Checker**
- **Default:** every `must_include` fact must appear on **every** listed citation page. The listed pages are equally valid alternatives: the same fact appears in several documents.
- **`cross_document` items:** each fact must appear on **at least one** listed page. The item's `notes` say which fact is on which page.
- **Superseded documents:** no item ever cites one (`budget-2024-draft`).

**Scorer**
- A citation is correct when **any one** listed `{file, page}` is among the answer's citations (SYSTEM_DESIGN §11).

### Honesty rules followed

- **Paraphrase:** headline questions paraphrase their source and don't reuse its sentences. A 4-gram overlap check against each cited page was run during authoring.
- **Vocabulary shift:** at least 8 of the 25 headline items have `vocab_shift: true`.
- **Unanswerable items are kept unanswerable.** While writing the corpus we kept a list of facts that must not appear anywhere for each unanswerable item, and re-checked it after every batch. Examples: no community-health figures for 2017–2019, and no water fees.

---

## 5. Document index

The corpus has 30 documents and 186 pages, dated 2015–2025:

| Dimension | Breakdown |
|---|---|
| Category | 6 annual reports, 5 donor agreements, 5 evaluations, 7 surveys, 3 budgets, 4 sets of board minutes |
| Language | 24 Arabic, 4 English, 2 mixed |
| Target format | 24 PDF, 4 DOCX (all Arabic), 2 TXT (one UTF-8, one Windows-1256) |

| doc_id | category | year | programme | lang | format | pages |
|---|---|---|---|---|---|---|
| `gep-enrolment-survey-2015` | survey | 2015 | GEP | ar | pdf | 4 |
| `annual-report-2016` | annual_report | 2016 | none | ar | pdf | 6 |
| `board-minutes-2017-11` | board_minutes | 2017 | none | ar | txt (windows-1256) | 3 |
| `wash-baseline-survey-2017` | survey | 2017 | WASH | ar | pdf | 5 |
| `budget-2018` | budget | 2018 | none | ar | docx | 4 |
| `wash-donor-agreement-2018` | donor_agreement | 2018 | WASH | ar | pdf | 6 |
| `gep-donor-agreement-2019` | donor_agreement | 2019 | GEP | en | pdf | 6 |
| `annual-report-2020` | annual_report | 2020 | none | ar | pdf | 12 |
| `gep-midterm-evaluation-2020` | evaluation | 2020 | GEP | en | pdf | 6 |
| `annual-report-2021` | annual_report | 2021 | none | ar | pdf | 16 |
| `board-minutes-2021-06` | board_minutes | 2021 | none | ar | docx | 4 |
| `chp-household-survey-2021` | survey | 2021 | CHP | ar | pdf | 5 |
| `wash-final-evaluation-2021` | evaluation | 2021 | WASH | ar | pdf | 7 |
| `yep-grant-agreement-2021` | donor_agreement | 2021 | YEP | mixed | pdf | 6 |
| `annual-report-2022` | annual_report | 2022 | none | ar | pdf | 14 |
| `wlp-donor-agreement-2022` | donor_agreement | 2022 | WLP | ar | pdf | 5 |
| `yep-employer-survey-2022` | survey | 2022 | YEP | mixed | pdf | 5 |
| `yep-final-evaluation-2022` | evaluation | 2022 | YEP | ar | pdf | 8 |
| `annual-report-2023-en` | annual_report | 2023 | none | en | pdf | 10 |
| `board-minutes-2023-03` | board_minutes | 2023 | none | ar | pdf | 4 |
| `board-minutes-2023-12` | board_minutes | 2023 | none | ar | pdf | 4 |
| `spc-donor-agreement-2023` | donor_agreement | 2023 | SPC | ar | docx | 5 |
| `wlp-evaluation-2023` | evaluation | 2023 | WLP | ar | docx | 5 |
| `yep-tracer-survey-2023` | survey | 2023 | YEP | ar | pdf | 5 |
| `budget-2024-draft` | budget | 2024 | none | ar | pdf | 5 |
| `budget-2024-final` | budget | 2024 | none | ar | pdf | 5 |
| `chp-evaluation-2024` | evaluation | 2024 | CHP | ar | pdf | 6 |
| `spc-satisfaction-survey-2024` | survey | 2024 | SPC | ar | txt (utf-8) | 4 |
| `yep-annual-report-2024` | annual_report | 2024 | YEP | ar | pdf | 6 |
| `wlp-market-assessment-2025` | survey | 2025 | WLP | en | pdf | 5 |

### Consistency notes for anyone editing the corpus

- **Shared figures:** yearly beneficiary, expenditure, revenue, staff and volunteer figures are identical wherever they appear. So are programme results that recur across annual reports, evaluations, board minutes and agreements. The only deliberate inconsistency is the 2024 draft/final budget pair.
- **Deliberately absent facts:** each unanswerable eval item depends on certain facts not appearing anywhere. Keep them out of every document:
  - community-health figures for 2017–2019 (T21)
  - water fees or tariffs (T22)
  - girls' enrolment rates after the 2020 mid-term (T23)
  - staff working-from-home policy (T24)
  - per diem or field-allowance rates (T25)
  - girls'-education figures for 2018 (D18)
  - YEP income broken down by gender (D19)
  - maternity leave (D20)
- **New pages that repeat an eval fact:** if a new page contains an existing eval fact, add it to that item's `expected_citations`. Otherwise a correct answer citing the new page is scored wrong.

---

## 6. Rendering and checking (C1b)

### Render

`make render-seed` runs `seed/render.py` in the `render` tools image, with no network. It rewrites `documents/`, `bad/` and `previews/`, and **re-running it is byte-identical**:
- PDF dates are pinned, the XMP packet is dropped and the file ID is deterministic.
- DOCX core properties and zip timestamps are fixed.
- The encrypted fixture uses a static ID and IV.

It fails if any source's front matter differs from the manifest, if the page markers aren't `1..page_count`, or if any rendered page count differs from `page_count`. That last check counts DOCX and TXT pages on their LibreOffice conversion.

| Format | How |
|---|---|
| `pdf` | Markdown subset → HTML → headless Chromium print. Each source page is one fixed A4 box (`210 × 297 mm`, `overflow: hidden`), so every marker is a page break and a page can never spill onto the next. Before printing, a script shrinks a box's type in 0.25 pt steps if its content doesn't fit, and the render fails if a page still overflows. No page in the current corpus needed shrinking. There is no page-number footer, because short numbers in a footer could satisfy a fact check by accident. |
| `docx` | python-docx. `page_break_before` is set on the first paragraph of every page after the first (no page opens with a table). Paragraphs, runs, tables (`bidiVisual`) and the section are RTL. Arabic is set in the complex-script font slot (Noto Naskh Arabic), Latin in Noto Serif. Lists are written as text markers (`•`, `1.`), so numbering never runs on from an earlier list. |
| `txt` | The body verbatim, a form feed between pages, encoded as the manifest says. The Windows-1256 file uses CRLF line ends, like a Notepad export. The UTF-8 file uses LF and has no BOM. |

**Fonts.** Arabic in the PDFs is set in **Amiri** (Latin in Amiri's own Latin glyphs, with Noto Serif as fallback), and English documents in Noto Serif.
- **Not Noto Naskh Arabic for PDFs.** It draws dotted letters as a base glyph plus dot glyphs. Chromium then wraps nearly every Arabic letter in an `/ActualText` span (about 2,300 per document), and pdfium (pypdfium2) extracts many words letter-reversed. Amiri maps letters to single glyphs.
- **Amiri's optional ligatures are switched off** (`font-variant-ligatures`): pdfium dropped a letter from each one (تظ, مص…). Required ligatures (lam-alef) stay.
- **Never KacstOne.** Its lam-meem ligature extracts as the wrong letters.

**Mixed documents.** Each block's direction is set explicitly from its first strong character. Inside a block, clauses split at a spaced em dash (U+2014), at ` / ` or at a sentence end are each wrapped in `<bdi>`, so an English clause keeps its trailing punctuation and an Arabic clause its order. `dir="auto"` can't be used on the block itself: it skips text inside `<bdi>`, so a block whose every clause is isolated falls back to LTR.

### How ingestion must convert DOCX and TXT

The checker builds each viewer PDF the way ingestion must (SYSTEM_DESIGN §5.2), and B3 should do exactly the same:

```sh
# DOCX
soffice --headless --norestore -env:UserInstallation=file:///tmp/<profile> \
  --convert-to pdf --outdir <out> <file>.docx

# TXT: decode in Python first (utf-8, then utf-8-sig, then cp1256), normalise CRLF to LF,
# write the text as UTF-8, then:
soffice --headless --norestore -env:UserInstallation=file:///tmp/<profile> \
  "--infilter=Text (encoded):UTF8,LF,,," --convert-to pdf --outdir <out> <file>.txt
```

**DOCX page numbers depend on the converter.** Headline items T07 and T12, and dev items D10, D15, D24 and D25, cite DOCX pages. Those numbers come from the `render` image (Debian snapshot 2026-10-20):

| Component | Version (Debian package) | Used for |
|---|---|---|
| LibreOffice | 25.2.3.2 (`libreoffice-writer-nogui 4:25.2.3-2+deb13u8`) | DOCX and TXT to PDF |
| Noto Naskh Arabic, Noto Serif | `fonts-noto-core 20201225-2` | DOCX Arabic and Latin |
| DejaVu Sans, DejaVu Sans Mono | `fonts-dejavu-core 2.37-8` | fallback for Latin digits and punctuation in Arabic runs; Arabic in TXT |
| Liberation Mono | `fonts-liberation 1:2.1.5-3` | TXT text |
| Amiri | `fonts-hosny-amiri 1.001-1` | PDF Arabic (Chromium 155.0.8059.79) |
| poppler-utils | 25.03.0 | `--extractor poppler` |
| pypdfium2 | 5.14.0 (hash-pinned, same as `backend/uv.lock`) | `--extractor pdfium` |

A worker that lacks those fonts, or runs another LibreOffice version, can paginate differently and silently break those citations. B3 installs the same fonts and re-runs `check_eval.py` in the worker image.

Without the decode step, LibreOffice reads the Windows-1256 file as mojibake. TXT import sets the text in Liberation Mono, with DejaVu Sans Mono for Arabic. In that font, lam-alef extracts reversed with both poppler and pdfium (دولار comes out as `دوالر`). No eval fact on a TXT page contains lam-alef, but B3 and S4 should look at the TXT import font.

### Check

```sh
make check-eval                                  # pdfium (the default)
make check-eval EVAL_ARGS="--extractor poppler"
# which run, in the render image:
docker compose run --rm render python3 scripts/check_eval.py eval/questions.yaml eval/dev_questions.yaml
```

The script makes no assumption about its container: `--extractor pdfium|poppler`, `--seed DIR`, `--soffice CMD` and `--pdftotext CMD` are plain options. Once the worker image has LibreOffice, the fonts and poppler (B3), the same command runs in `backend-dev`.

- **Corpus checks:** every source's front matter equals its manifest entry, and every viewer PDF has `page_count` pages. Each rendered page also holds its own source page's text: the first and last four reliable words of source page N must be on rendered page N. Words written with tashkeel or containing lam-alef aren't reliable, so they're skipped, and a page without enough words uses its numbers. Every run also has a negative control: compared with the next page's text, every page must fail this check, so a one-page shift can't go unnoticed.
- **Eval checks:** the citation semantics of §4. Also: no citation of a superseded or archived document, no cited page beyond `page_count`, and every answered item cites at least one document that isn't restricted.
- **Matching:** facts match after `fold_for_matching`, which folds digits (Latin, Arabic-Indic, Persian), Arabic separators, tashkeel, tatweel, presentation forms and bidi controls. Numbers match as whole numbers. The fold is local test tooling until B1's `sanad.text.arabic` merges.
- **Informational lines:** extraction quality (source words found verbatim on their page, letter-reversed words, other misses in words with lam-alef) and extraction time per 100 pages.

### Extraction findings: pdfium vs poppler

Both extractors were run over the whole corpus, and over a scratch build that set Arabic in Noto Naskh instead of Amiri. "Verbatim" counts the 19,449 source words (three letters or more) found as written on their page.

| Build | Extractor | Checks (before the D22 edit) | Verbatim | Letter-reversed | Other lam-alef misses | Time per 100 pages |
|---|---|---|---|---|---|---|
| **Amiri (shipped)** | pdfium | 676/678 | 95.9% | 132 | 94 | 0.12–0.19 s |
| **Amiri (shipped)** | poppler | 676/678 | 97.0% | 1 | 77 | 0.19–0.30 s |
| Noto Naskh (scratch) | pdfium | 543/678 | 57.7% | 7,743 | 65 | 0.11 s |
| Noto Naskh (scratch) | poppler | 675/678 | 97.5% | 3 | 53 | 0.18 s |

On the shipped build, the two failing checks were D22 (formerly T03) on `annual-report-2021` p2, with both extractors. D22 no longer cites that page, and every check now passes with either extractor: 674/674. Timings vary from run to run (one process, laptop, arm64); poppler's include one `pdftotext` process per document.

- **pdfium is sensitive to the font.** Chromium wraps every multi-glyph cluster in `/ActualText`, and pdfium reorders letters around those spans in RTL text. Noto Naskh draws dotted letters as base glyph plus dots, so nearly every letter is such a cluster. Amiri limits it to letters with tashkeel.
- **pdfium is weak on tashkeel.** On the shipped build it gets 155 of 834 words written with tashkeel verbatim; poppler gets 664. It also:
  - puts a space after non-joining letters (`و يعمل`)
  - splits lam-alef-hamza (الإلكتروني comes out as `لكتروني الإ`)
  - doesn't mirror brackets (`) اسم مستعار(`)
- **Poppler fails differently.**
  - It puts tashkeel before its letter and a space after a cluster with stacked marks (العَطَّار comes out as `العط ار`). So the fully diacritised `annual-report-2021` p2 loses the names with both extractors; D22 no longer cites that page.
  - On the Amiri build it splits words after ر before ي or ب (`الر يحان`, `ر بحية`). These are 387 words pdfium gets and poppler doesn't, including the organisation name. Poppler gets 592 words pdfium doesn't.
- **Licences:** pypdfium2 is Apache-2.0 / BSD-3-Clause (PDFium is BSD-3-Clause). poppler-utils is GPL-2.0-or-later, which only matters if it is linked into the product; it would be called as a separate CLI process.
- **LibreOffice PDFs (DOCX, TXT):** TXT is 94.7% verbatim with both extractors (its lam-alef reverses in DejaVu Sans Mono), and DOCX is 95.7% with pdfium and 97.3% with poppler.
