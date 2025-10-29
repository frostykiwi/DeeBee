# DeeBee

DeeBee is a command-line assistant that helps you clean up movie folders by
looking up titles on [imdbapi.dev](https://imdbapi.dev/) and renaming the files
accordingly.

## Requirements

* Python 3.10+
* An imdbapi.dev API key

## Installation

```bash
pip install -e .
```

## Usage

```bash
export IMDB_API_KEY="your-api-key"
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
export IMDB_API_KEY="your-api-key"
db-gui
```

Use the **Browse** button to pick a folder, adjust the result limit if needed,
and click **Start** to review rename suggestions.
