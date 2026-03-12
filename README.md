# Case‑Study

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

Case‑Study is a command‑line application for practising structured
analytical reasoning.  It guides users through a five‑stage reasoning
loop modelled after consulting‑style case interviews:

1. **Frame** – define the problem structure and objectives.
2. **Hypothesize** – generate potential explanations or strategic options.
3. **Analyze** – outline analyses you would perform to test hypotheses.
4. **Update** – refine or discard hypotheses based on your analysis.
5. **Conclude** – summarise your recommendation with supporting rationale and risks.

Unlike a chatbot that attempts to answer cases for you, Case‑Study
provides a structured environment that encourages you to think
critically, document your reasoning and iterate as new insights
emerge.  An optional AI coach offers generic feedback on the quality
of your thought process without giving away answers.

## Quick Start

```sh
git clone https://github.com/violethawk/Case-Study.git
cd Case-Study
python -m case_study start
```

Example session flow:

```text
$ python -m case_study start
Available cases:
  1. bank_growth_001 – Regional Bank Growth Strategy (medium)
  ...
Select a case [1]: 1
Enable AI coach? [y/N]: y

=== Stage 1: Frame ===
Define the problem structure and objectives.
> ...
```

## Installation

Case‑Study requires **Python 3.11+** and uses only the standard
library — no additional dependencies are needed.

```sh
git clone https://github.com/violethawk/Case-Study.git
cd Case-Study
```

## Usage

Invoke the program using the `-m` switch and specify one of the
subcommands:

```sh
python -m case_study start                          # start a new session
python -m case_study resume <path/to/session.json>  # resume a saved session
python -m case_study list                            # list saved sessions
```

### Starting a Session

When you start a new session you will be shown the available cases
from `data/sample_cases.json` and prompted to pick one by number or
identifier.  The program displays the case prompt and context and then
walks you through each reasoning stage.  Your responses must contain
at least ten characters; the tool will ask you to expand very short
answers.

For stages that involve lists (Hypotheses, Analyses and Updates) you
enter one item at a time and decide whether to add another.  All
responses are saved to a JSON file in `sessions/` after each stage to
prevent data loss.

At the start of a session you can choose whether to enable the AI
coach.  If enabled you will have the option after each stage to
receive feedback.  The MVP coach implementation uses simple
heuristics: it does **not** solve the case or provide answers, but
critiques the clarity and completeness of your reasoning and suggests
questions to consider.

### Resuming a Session

To continue working on an unfinished session use the `resume`
subcommand with the path to the saved JSON file.  The tool will show
your completed stages and prompt you to:

1. Continue from the next incomplete stage.
2. Edit the most recent completed stage (which will also clear later stages).
3. Exit without changes.

If the session is already complete you may review it or duplicate it
and revise your reasoning.

### Session Persistence

Sessions are stored in `sessions/` with filenames of the form:

```text
<case_id>_<YYYY-MM-DD>_<HH-MM-SS>.json
```

Each file contains a JSON object with the fields `case_id`,
`timestamp`, `frame`, `hypotheses`, `analyses`, `updates` and
`conclusion`.  You can list existing sessions with `python -m
case_study list`.

## Project Structure

```text
Case-Study/
├── case_study/
│   ├── __init__.py      # package marker
│   ├── __main__.py      # entry point (python -m case_study)
│   ├── cases.py         # case loader
│   ├── cli.py           # argument parsing and subcommands
│   ├── coach.py         # AI coach heuristics
│   ├── engine.py        # reasoning‑loop orchestration
│   ├── session.py       # session persistence
│   └── validation.py    # input validation helpers
├── data/
│   └── sample_cases.json
├── sessions/            # saved session files (gitignored)
├── tests/               # test suite
├── .gitignore
├── pyproject.toml
├── LICENSE
└── README.md
```

## Sample Cases

The repository includes a small set of sample cases in
`data/sample_cases.json`.  Each case entry contains an ID, a prompt,
optional context and a difficulty rating.  You can add your own cases
by editing this file or pointing the loader at a different JSON file.

## Extending the MVP

This MVP focuses on clarity, reasoning traceability and simplicity.
Future directions include:

* A web interface or GUI.
* More sophisticated AI coaching via API integration.
* Exporting sessions as formatted reports.
* Difficulty progression or practice curricula.

Contributions and suggestions are welcome — feel free to open an issue
or submit a pull request.

## License

This project is licensed under the [MIT License](LICENSE).