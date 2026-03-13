# Case‑Study

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A case interview practice tool that guides you through structured
problem-solving stages modelled after MBB consulting interviews. Includes
a Streamlit web app, optional AI coaching via Gemini, timed mental math
drills, scoring, and progress tracking across sessions.

**Try it now:** [case-study.streamlit.app](https://case-study.streamlit.app/)

## Quick Start

### Web App (recommended)

Use the hosted version at **[case-study.streamlit.app](https://case-study.streamlit.app/)**, or run locally:

```sh
git clone https://github.com/violethawk/Case-Study.git
cd Case-Study
pip install streamlit
streamlit run app.py
```

### CLI

```sh
python -m case_study start              # start a new session
python -m case_study start --coach      # with heuristic coaching
python -m case_study resume <session>   # resume a saved session
python -m case_study list               # list saved sessions
```

## What It Does

You pick a case, then work through a category-specific stage flow — restating
the problem, structuring your approach, making assumptions, calculating, and
delivering a recommendation. The tool evaluates each stage, tracks attempts,
and scores your session on completion.

**25 cases** across three categories and three difficulty levels:

| Category | Cases | Stages |
|---|---|---|
| **Strategy** (10) | Market entry, growth, pricing | Restatement → Clarifying Questions → Framework → Frame → Assumptions → Hypotheses → Equation → Calculation → Conclusion → Additional Insights |
| **Market Sizing** (8) | TAM estimation, sizing | Restatement → Clarifying Questions → Framework → Structure → Assumptions → Calculation → Sanity Check → Conclusion |
| **Quantitative** (7) | Break-even, unit economics | Restatement → Clarifying Questions → Setup → Assumptions → Calculation → Sensitivity → Conclusion |

Each case has a difficulty rating (easy / medium / hard) that affects the
depth expected in your responses.

## Coaching

Two coaching modes are available:

- **Heuristic (default)** — deterministic feedback based on word count,
  keyword patterns, and structural checks. No API key needed.
- **AI (Gemini)** — set `GEMINI_API_KEY` to get stage-specific feedback
  from Gemini Flash. Evaluates your actual reasoning, not just structure.

Coaching adapts to three difficulty levels:

| Level | Style |
|---|---|
| **Beginner** | Supportive, hints provided, lenient pass threshold |
| **Intermediate** | Balanced, honest feedback, fair passing bar |
| **Advanced** | MBB-style, sharp on errors, rigorous standards |

## Session Features

- **Time pressure** — per-stage and total time limits with warnings
- **Multi-attempt stages** — retry stages that don't pass the quality bar
- **Interviewer data reveals** — mid-case data drops that force you to adapt
- **Exhibit interpretation** — data exhibits to analyze with headline-first format
- **Clarifying questions** — practice scoping the problem before structuring

## Mental Math Drills

Case interviews require fast, accurate arithmetic under pressure. The
Mental Math Drills module builds that speed with timed problem sets across
five categories:

| Category | Examples |
|---|---|
| **Percentages** | What is 12% of 240 million? |
| **Growth & CAGR** | What CAGR takes 100 to 150 in 3 years? |
| **Market Sizing Math** | 330M people x 70% adults x $120 avg spend |
| **Breakeven** | Fixed costs $2M, margin $50/unit — breakeven volume? |
| **Unit Economics** | Monthly ARPU $45, churn 8% — what is the LTV? |

Each drill is **10 timed problems** (target: 30 seconds each). You get a
score (0–100) based on accuracy (70%) and speed (30%), with a
problem-by-problem breakdown showing tips and correct answers. Problems
scale with your difficulty setting and you can run mixed drills that pull
from all categories.

## Scoring & Review

On completion, each session gets:

- **Overall score (0–100)** — computed from per-stage attempts, pass/fail
  rates, and time management
- **Stage-by-stage breakdown** — green/yellow/red indicators with
  collapsible detail and feedback
- **Strongest stage & focus area** — highlights where to improve
- **Key metrics** — total time, first-try pass rate, average attempts

## Progress Tracking

The analytics system tracks performance across sessions:

- Time trends (getting faster or slower)
- First-attempt rate changes
- Per-stage performance history
- Difficulty progression recommendations

## Frameworks

A reference library of 12 common business frameworks is available during
the Framework Selection stage: 3C's, 4P's, Cost vs Benefit,
Fixed vs Variable Costs, Internal vs External, McKinsey 7-S, Porter's
Five Forces, Profitability, STP, Supply vs Demand, SWOT, and Value Chain.

## Installation

Requires **Python 3.11+**.

```sh
pip install -e ".[ui]"        # Streamlit web app
pip install -e ".[ai]"        # Gemini AI coaching
pip install -e ".[ui,ai]"     # both
pip install -e ".[dev]"       # pytest for running tests
```

Or install dependencies directly:

```sh
pip install streamlit                  # for the web app
pip install google-genai               # for AI coaching (optional)
```

The CLI works with no extra dependencies — only the standard library.

## Project Structure

```text
Case-Study/
├── app.py                 # Streamlit web app
├── case_study/
│   ├── __main__.py        # CLI entry point
│   ├── cases.py           # case loader
│   ├── cli.py             # argument parsing and subcommands
│   ├── coach.py           # heuristic + Gemini AI coaching
│   ├── engine.py          # stage flows, time limits, data reveals
│   ├── session.py         # session persistence
│   ├── analytics.py       # portfolio analytics and trends
│   ├── mental_math.py     # timed mental math drill engine
│   └── validation.py      # input validation
├── data/
│   ├── frameworks.json    # 12 business frameworks
│   └── sample_cases.json  # 25 cases across 3 categories
├── sessions/              # saved session files (gitignored)
├── tests/                 # test suite
├── pyproject.toml
├── LICENSE
└── README.md
```

## License

[MIT](LICENSE)
