# Claude API Cost Estimate for AI Coach

This document provides a cost estimate for planning purposes, projecting what it would cost to power the Case-Study AI coach with the Claude API instead of the current heuristic-based stub.

---

## 1. Assumptions

| Parameter | Value |
|---|---|
| **Models considered** | Claude Sonnet 4, Claude Haiku 4.5 |
| **Sonnet pricing** | $3.00 / MTok input, $15.00 / MTok output |
| **Haiku pricing** | $0.80 / MTok input, $4.00 / MTok output |
| **Stages per session** | 8 (restatement, frame, assumptions, hypotheses, analyses, updates, conclusion, additional insights) |
| **Stages with coach feedback** | ~5 out of 8 (roughly 60%, based on 50-75% range) |
| **User response length (single-field)** | ~100-200 words (~135-270 tokens) |
| **User response length (multi-item)** | ~50-100 words per item, ~3 items avg (~200-400 tokens total per stage) |
| **Token conversion** | 1 token ~ 0.75 words |
| **Prompt caching** | Not assumed (conservative estimate) |

### Stage types in the codebase

- **Single-field stages (4):** restatement, frame, conclusion, additional_insights
- **Multi-item stages (4):** assumptions, hypotheses, analyses, updates (user enters multiple items per stage)

---

## 2. Per-Stage Token Estimates

Each coach API call includes all prior context so the coach can give informed feedback. The input payload grows as the session progresses.

### Fixed components (included in every call)

| Component | Estimated Tokens |
|---|---|
| System prompt (coaching persona, rules, output format) | ~400 |
| Case prompt + context (varies by case; median estimate) | ~300 |
| Current stage instructions | ~50 |
| **Subtotal (fixed)** | **~750** |

> **Note on case context size:** Cases in `sample_cases.json` range from ~40 tokens (simple prompt, short context) to ~550 tokens (Diconsa case with detailed data tables). The median is approximately 250-350 tokens. We use 300 as a representative midpoint.

### Variable component: accumulated user responses

User responses accumulate across stages. The coach needs prior responses for context.

| Stage # | Stage Name | New User Input (tokens) | Accumulated Context (tokens) | Total Input (tokens) |
|---|---|---|---|---|
| 1 | Restatement | ~200 | 0 | 750 + 200 = **950** |
| 2 | Frame | ~200 | 200 | 750 + 400 = **1,150** |
| 3 | Assumptions | ~300 (3 items) | 400 | 750 + 700 = **1,450** |
| 4 | Hypotheses | ~300 (3 items) | 700 | 750 + 1,000 = **1,750** |
| 5 | Analyses | ~350 (3 items) | 1,000 | 750 + 1,350 = **2,100** |
| 6 | Updates | ~250 (3 items) | 1,350 | 750 + 1,600 = **2,350** |
| 7 | Conclusion | ~200 | 1,600 | 750 + 1,800 = **2,550** |
| 8 | Additional Insights | ~200 | 1,800 | 750 + 2,000 = **2,750** |

### Coach output per call

The current heuristic stub returns three sections (strengths, gaps, suggested questions), each roughly 30-50 words. A real LLM coach would provide richer, more tailored feedback.

| Component | Estimated Tokens |
|---|---|
| Strengths section | ~80 |
| Gaps section | ~100 |
| Suggested questions section | ~70 |
| **Total output per call** | **~250** |

---

## 3. Per-Session Total

Assuming the user requests coach feedback on **5 out of 8 stages** (stages 1, 3, 4, 5, 7 as a representative pattern):

### Input tokens

| Feedback Call | Stage | Input Tokens |
|---|---|---|
| 1 | Restatement (stage 1) | 950 |
| 2 | Assumptions (stage 3) | 1,450 |
| 3 | Hypotheses (stage 4) | 1,750 |
| 4 | Analyses (stage 5) | 2,100 |
| 5 | Conclusion (stage 7) | 2,550 |
| **Total input** | | **8,800** |

### Output tokens

| Calls | Tokens per call | Total |
|---|---|---|
| 5 | 250 | **1,250** |

### Per-session totals

| Metric | Tokens |
|---|---|
| Total input tokens | ~8,800 |
| Total output tokens | ~1,250 |
| **Combined tokens** | **~10,050** |

---

## 4. Cost Per Session

### Claude Sonnet 4

| | Tokens | Rate | Cost |
|---|---|---|---|
| Input | 8,800 | $3.00 / MTok | $0.0264 |
| Output | 1,250 | $15.00 / MTok | $0.0188 |
| **Session total** | | | **$0.045** |

### Claude Haiku 4.5

| | Tokens | Rate | Cost |
|---|---|---|---|
| Input | 8,800 | $0.80 / MTok | $0.0070 |
| Output | 1,250 | $4.00 / MTok | $0.0050 |
| **Session total** | | | **$0.012** |

---

## 5. Hourly Estimate

Assuming a user completes **2-3 full sessions per hour** of practice (midpoint: 2.5):

| Model | Cost/Session | Sessions/Hour | Cost/Hour |
|---|---|---|---|
| Claude Sonnet 4 | $0.045 | 2.5 | **$0.11** |
| Claude Haiku 4.5 | $0.012 | 2.5 | **$0.03** |

---

## 6. Summary Table

| Metric | Claude Sonnet 4 | Claude Haiku 4.5 |
|---|---|---|
| Cost per session | $0.045 | $0.012 |
| Cost per hour of practice | $0.11 | $0.03 |
| Cost for 10 hours of practice | **$1.13** | **$0.30** |
| Cost for 100 hours (power user) | $11.25 | $3.00 |

---

## 7. Key Takeaways

- **API costs are very low** for this use case. Even with Claude Sonnet 4 (higher-quality feedback), a full hour of practice costs roughly eleven cents.
- **Haiku is viable** for budget-sensitive deployments. At $0.03/hour, cost is essentially negligible. Quality of coaching feedback should be tested to ensure it meets the bar.
- **Context window growth is modest.** Even at stage 8, total input is under 3,000 tokens per call -- well within efficient ranges and far below context window limits.
- **Prompt caching could reduce costs further.** The system prompt and case context (~750 tokens) are repeated across calls in a session. With Anthropic's prompt caching, these tokens would be charged at a reduced rate on subsequent calls, lowering input costs by roughly 20-30%.
- **The main cost driver is output tokens**, not input. Output pricing is 5x input pricing for Sonnet and 5x for Haiku, and output tokens account for about 40-45% of total cost despite being only ~12% of total token volume.

---

*Estimates based on Anthropic API pricing as of early 2026. Actual costs may vary based on response lengths, caching behavior, and usage patterns.*
