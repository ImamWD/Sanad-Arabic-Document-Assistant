# Research note: GPU options, GPU rental, free hosted LLM APIs

Date: 24 Oct 2026. Produced by the manager's research run: three researchers, each followed by an independent fact-check against the cited pages.

**Every price here is online evidence, not a quote.** Deliverable 1 must be a supplier's written quote (DECISIONS D3).

Exchange rates (ECB, 23 Oct 2026): ≈ 3.12 ILS/USD and ≈ 1.34 USD/GBP. Prices are rising quickly (DRAM shortage, vendor price rises in 2026), so the quote's validity date matters.

---

## 1. Which 24 GB+ card

**Target.** A 7–14B 4-bit model, ~4k-token prompt, ~300-token answer, with p90 total time ≤ 15 s. "LLM time" below means prompt processing plus generation only. Retrieval and reranking add about 1–2 s on top (*est.*).

| Card | VRAM | Power / cooling / size | Fits | LLM time, 8B / 14B | Online price evidence |
|---|---|---|---|---|---|
| **NVIDIA RTX PRO 4000 Blackwell** (primary pick) | 24 GB ECC | 145 W, 16-pin (12V-2x6), single-slot blower, ~241 mm | Towers, and rack servers with a full-height x16 slot plus a 16-pin GPU cable | **~4 s / ~7 s** (*est.* from measured Ollama generation of 98.9 / 57.8 tok/s) | ~USD 3,100 (US, ex tax); Scan UK GBP 3,072 inc VAT (~USD 3,420 ex VAT) |
| NVIDIA RTX PRO 4500 Blackwell **Server Edition** | 32 GB ECC | 165 W, 16-pin, **passive**, full length ~267 mm | Rack servers with GPU-rated airflow | ~6–7 s on 14B (*est.*; no benchmark) | ~GBP 4,320 ex VAT (Sync UK, in stock); ~USD 4,580 (SabrePC, out of stock) |
| NVIDIA RTX PRO 4000 Blackwell **SFF** | 24 GB ECC | 70 W, slot-powered (no cable), low profile, double width, PCIe x8 | Low-profile-only servers | ~10–12 s on 14B (*est.*): thin margin, so benchmark it or use an 8B model | ~GBP 2,616 ex VAT (~USD 3,500); ~USD 3,100 US; 7–9 week lead time reported |
| NVIDIA RTX A5000 (2021) | 24 GB ECC | 230 W, 8-pin, double-slot blower | Towers, 2U with a double-width slot | ~5 s / ~8.6 s (LocalScore) | ~USD 2,950 (US) |
| NVIDIA GeForce RTX 5090 (consumer) | 32 GB | **575 W**, 3.5+ slots, ~340 mm, needs a **1,000 W PSU** | **Tower only** | ~2 s / ~3 s | **Thalji Store, Ramallah: ILS 16,500** (~USD 5,290), 12-month warranty; stock and VAT not shown |
| NVIDIA L4 | 24 GB | 72 W, passive, low profile | Any rack server | ~9 s / **~16.5 s** (fails on 14B) | ~USD 3,950; End of Life at Scan UK |
| NVIDIA A10 | 24 GB | 150 W, passive | Rack only | ~10 s / **~18.7 s** (fails on 14B) | Mostly used (~USD 3,500) |

**Not recommended:**
- L4 and A10: they miss the 15 s target on 14B, and the L4 is end of life.
- Used RTX 3090 or 4090: donor-funded purchases usually need new equipment with an invoice and warranty.
- RTX 4500 Ada: end of life, and slower than the cheaper PRO 4000.
- AMD R9700: plausible on Ollama with ROCm 7, but a less mature stack.

**Local market (Ramallah and Nablus, checked 24 Oct 2026)**
- Only one West Bank shop lists any 24 GB+ card: Thalji Store, Ramallah, with Gigabyte RTX 5090 consumer cards at ILS 16,500–17,300.
- Cobra Shop and Office One (Ramallah) top out at 16 GB.
- **No West Bank retailer lists professional cards** (RTX PRO, L4, A-series). Those need an importer or the server vendor's partner (Dell, HPE or Lenovo); no Palestinian NVIDIA professional partner was found online.
- In Amman, the 24 GB+ cards at Oriental Store are all out of stock.

**Tax and import**
- Palestinian VAT is 16% (PwC Worldwide Tax Summaries, Aug 2026).
- Customs duty on GPUs: likely 0% under the WTO IT Agreement (HS 8473.30), but **unverified** for current PA practice. The supplier or a customs broker should confirm it in writing.
- Whether the foundation can buy VAT-exempt is unknown. Ask their finance office (OPEN_QUESTIONS N8).

**Recommendation for the RFQ.** Specify **performance and fit**, not one product:

> NVIDIA professional GPU, ≥ 24 GB VRAM with ECC, ≥ 600 GB/s memory bandwidth, new, ≥ 3-year warranty, fits the stated server, installation and burn-in included. Show VAT, customs and lead time separately. Quote valid ≥ 30 days, covering the board meeting.

Then list the reference models in order, depending on the chassis (N1):
1. **RTX PRO 4000 Blackwell 24 GB** for a tower, or a rack server with a full-height x16 slot and a 16-pin cable.
2. **RTX PRO 4500 Blackwell Server Edition 32 GB** for a rack server with GPU airflow that prefers vendor-qualified passive cards.
3. **RTX PRO 4000 SFF 24 GB** for low-profile-only slots or no spare GPU power cable. This one must be benchmarked first.

The RTX 5090 (tower only) is the only card available locally right now. It costs more than the PRO 4000 and draws four times the power.

**Server facts needed before anyone can quote** (N1):
- make, model and generation, and service tag
- form factor (1U, 2U, 4U or tower)
- whether the server is on the vendor's GPU qualification list, and which enablement kit it needs (riser, GPU power cable, fans, shroud)
- free PCIe x16 slot: generation and electrical width
- full-height or low-profile, maximum card length, free slot widths
- PSU model, wattage and redundancy, and the current draw
- spare GPU power connectors (16-pin / PCIe 8-pin / EPS 8-pin)
- airflow and room temperature
- BMC fan behaviour with third-party cards
- BIOS (Above 4G decoding)
- OS and kernel (NVIDIA driver ≥ 570 is needed for Blackwell)
- photos of the inside of the chassis

**Lead time.** Professional cards were reported at up to ~2 months, and 7–9 weeks for the SFF. To be installed before 31 January, the order has to be placed in **November**. That makes the board date (N2) critical.

---

## 2. Renting a card to measure answer time (deliverable 2)

**Plan.** Bracket the decision with three cards, on providers that bill per second, need no quota approval and accept crypto if a Palestinian card is declined:

| Card | Why | Where | ≈ $/h |
|---|---|---|---|
| RTX PRO 4000 Blackwell (full 145 W card) | The likely purchase | Vast.ai, verified host | 0.27–0.30 |
| L4 | The floor: if this passes, every card passes | RunPod Secure | 0.59 |
| RTX 4090 (power limit ≥ 450 W) | The ceiling, and a check on "Tier B 3–10 s" | RunPod Secure 0.89, or Vast 0.48+ | 0.48–0.89 |

**Cost.**
- About **$5** of GPU time for roughly 2–2.5 h per card.
- Budget **$10** with re-runs.
- **$15 up front** because of minimum top-ups: RunPod $10 (non-refundable credit) and Vast $5.
- An optional RTX 5090 adds about $2.40.

**Exclusions.**
- Lambda doesn't serve Palestine.
- AWS starts new accounts at a GPU quota of 0.
- The GCP free trial can't use GPUs.
- RunPod's crypto payment requires KYC first.

**Method.**
- RunPod has no Docker Compose and neither provider allows Docker-in-Docker, so we run the plain `ollama/ollama` image on the pod. A local script replays the 25 assembled prompts against it.
- Timings come from Ollama's own response fields (load, prompt eval, eval), plus time to first token. Do one warm-up, then two runs per question per model.
- Embedding and reranking are timed separately.
- Log `nvidia-smi` power limit, clocks and driver with every result. Some cloud 4090s are power-limited.
- **Synthetic corpus only.** The machines belong to third-party hosts. Destroy the instance and its disk afterwards.

---

## 3. Free hosted reference model (owner question P3)

**Anthropic is not required.** The `openai_compat` adapter works with all of these.

| Provider | Free terms | Arabic-capable models | Trains on free prompts? | Card? | Palestine |
|---|---|---|---|---|---|
| **Google Gemini API** (pick) | Free tier with only a Google Cloud project; base URL `https://generativelanguage.googleapis.com/v1beta/openai/` (beta) | `gemini-3.1-flash-lite` (~500 req/day, community-reported); `gemma-4-31b-it` (~1,500 req/day, community-reported, also local in Ollama as `gemma4:31b`); `gemini-3.8-flash` (~20 req/day) | **Yes**, and human review is possible. Acceptable only because the corpus is synthetic. | No | **Officially listed** |
| Cohere (trial key, second pick) | 1,000 calls/month, 20 RPM; meant for evaluation | Command A / A+ (Arabic is an officially optimised language) | Unclear for trial keys | Not stated | Not on its restricted list; test signup |
| OpenRouter `:free` models | 50 requests/day | `gemma-4-31b-it:free`, others | Depends on the upstream provider | No | No list |
| Cloudflare Workers AI | 10,000 neurons/day | Several open models | **No** | Not stated | No list |
| Anthropic | Small free credits for new users; Claude Max and Team plans include monthly API credits (claimable in the Console) | Claude | No (paid API) | Yes (unless claiming plan credits) | **Officially listed** |

**Notes**
- Free limits change often. For example, Gemini cut its free tier in Dec 2025, and GitHub Models was retired in July 2026. Record the provider, model ID and date in every eval result, and pin model IDs.
- Gemini 3.x reasoning can't be turned off on the OpenAI-compatible endpoint. Thinking tokens count against the limits.
- If the owner already has a Claude Max or Team plan, its monthly API credits make Claude a free extra reference. Otherwise a 25-question run on `claude-haiku-5-5` costs about $0.02–0.03 (*est.*).
- `gemma4:31b` is open-weights and runs in Ollama. It is worth adding to the S3 local shoot-out, because the hosted and local scores can then be compared directly. At 4-bit (~19 GB plus context) it fits a 24 GB card tightly and a 32 GB card comfortably.

---

## Sources (primary where possible)

- NVIDIA product pages (RTX PRO 4000 / 4000 SFF / 4500, L4); PNY RTX PRO 4500 Server Edition page
- Measured Ollama numbers: computingforgeeks RTX PRO 4000 vs 5000 benchmarks (June 2026); Hardware Corner llama.cpp results (Mar 2026); LocalScore accelerator and model pages; llama.cpp CUDA and Vulkan scoreboards (ggml-org discussions 15013 and 10879)
- Prices:
  - Scan Computers UK
  - Sync UK (`shop.wearesync.co.uk/900-2g147-0000-000.html`)
  - SabrePC
  - gpuprix and gpudojo trackers
  - Thalji Store Ramallah (`thaljistore.com/ar/categories/graphics-cards`)
  - Cobra Shop
  - Office One
  - Oriental Store Amman
- Tax: PwC Worldwide Tax Summaries, Palestinian Territories (reviewed 12 Aug 2026); US Commerce Country Commercial Guide, West Bank and Gaza
- Rental: RunPod pricing and docs; Vast.ai public bundle API (24 Oct 2026); Lambda, GCP, AWS, Hetzner pricing pages
- APIs:
  - `ai.google.dev/gemini-api/docs/{pricing,rate-limits,available-regions}` and terms (effective 2026-03-23)
  - `docs.cohere.com/docs/rate-limits`
  - `openrouter.ai/docs/api-reference/limits`
  - Cloudflare Workers AI pricing and data usage
  - `anthropic.com/supported-countries`
  - Claude API pricing and API credits for subscribers
