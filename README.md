# DeeBee

DeeBee is a command-line assistant that helps you clean up movie and TV show
folders by looking up titles on [imdbapi.dev](https://imdbapi.dev/) and
renaming the files accordingly.

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
