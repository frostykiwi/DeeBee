# DeeBee

DeeBee is a Python 3.10+ toolkit that tidies movie and TV show folders by matching each file against imdbapi.dev metadata and renaming it with clean, human-friendly titles. Out of the box, you can install it in editable mode and launch it as a simple db command-line utility or as an experimental db-gui desktop app built with Tkinter.

Key Features:

Guided command-line workflow. DeeBee scans any folder you point it at, presents matching IMDb results in an interactive console table, and only renames files after you confirm the right choice—perfect for batch cleanup without unwanted surprises.
Safe-by-default execution. Runs start in dry-run mode so you can preview proposed filenames; add --execute when you’re ready to commit the changes for real.
Fine-grained controls. Adjust how many IMDb matches appear with --limit, pick from multiple rename formats, and set the logging level to trace normalization and API calls when troubleshooting.
Rich metadata handling. Behind the scenes, DeeBee’s IMDb client normalizes titles, years, and episode data, retries flaky network calls, and gracefully deals with imperfect API payloads to keep the renaming experience smooth.
Optional desktop experience. Prefer a visual review? The Tkinter GUI lets you browse to a folder, sift through matches in dialog windows, skip or stop at any point, and apply renames with a click—still honoring dry-run previews for safety.



## Requirements

* Python 3.10+

## Installation

1. Clone the repository and move into the project directory:

   ```bash
   git clone https://github.com/frostykiwi/DeeBee.git
   cd DeeBee
   ```

2. (Optional) Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install DeeBee in editable mode so command-line changes are immediately
   reflected:

   ```bash
   pip install -e .
   ```

## Usage

```bash
# Dry run (default):
db /path/to/movies

# Apply the changes to disk:
db /path/to/movies --execute
```

For each movie file DeeBee will fetch potential matches, display them in an
interactive table, and prompt you to pick the correct movie. Selecting `0`
leaves the file untouched.

## Graphical interface

Prefer a windowed interface? Launch the experimental Tkinter application:

```bash
db-gui
```

Use the **Browse** button to pick a folder, adjust the result limit if needed,
and click **Start** to review rename suggestions.
