# Case‑Study

Case‑Study is a command‑line application for practising structured
analytical reasoning.  It guides users through a five‑stage reasoning
loop modelled after consulting style case interviews:

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

## Installation

Case‑Study is delivered as a Python package.  You need Python 3.11
or later installed.  Clone or unpack this repository, then run the
commands from the project root.

```sh
python -m pip install -r requirements.txt  # if future dependencies are added
```

For the MVP no additional dependencies beyond the standard library are required.

## Usage

Invoke the program using the `-m` switch and specify one of the
subcommands:

```sh
python -m case_study start     # start a new case study session
python -m case_study resume <path/to/session.json>  # resume a saved session
python -m case_study list      # list saved sessions
```

### Starting a Session

When you start a new session you will be shown the available cases
from the `cases/sample_cases.json` file and prompted to pick one by
number or identifier.  The program displays the case prompt and
context and then walks you through each reasoning stage.  Your
responses must contain at least ten characters; the tool will ask you
to expand very short answers.

For stages that involve lists (Hypotheses, Analyses and Updates) you
enter one item at a time and decide whether to add another.  All
responses are saved to a JSON file in the `sessions/` directory after
each stage to prevent data loss.

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

Sessions are stored in the `sessions/` directory with filenames of the
form:

```text
<case_id>_<YYYY-MM-DD>_<HH-MM-SS>.json
```

Each file contains a JSON object with the fields `case_id`,
`timestamp`, `frame`, `hypotheses`, `analyses`, `updates` and
`conclusion`.  You can list existing sessions using `python -m
case_study list`.

## Sample Cases

The repository includes a small set of sample cases in
`cases/sample_cases.json`.  Each case entry contains an ID, a prompt,
optional context and a difficulty rating.  You can add your own cases
by editing this file or pointing the loader at a different JSON file.

## Extending the MVP

This MVP focuses on clarity, reasoning traceability and simplicity.  In
the future you could extend it by:

* Implementing a web interface or GUI.
* Adding more sophisticated AI coaching via API integration.
* Exporting sessions as nicely formatted reports.
* Introducing difficulty progression or practice curricula.
* Analysing reasoning quality (automated MECE scoring is an open
  research problem and not included here).

Contributions and suggestions are welcome!