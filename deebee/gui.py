"""Basic Tkinter-based graphical interface for DeeBee."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .imdb_client import IMDBClient, IMDBMovie
from .renamer import (
    DEFAULT_RENAME_FORMAT_KEY,
    MovieCandidate,
    MovieRenamer,
)


LogCallback = Callable[[str], None]


class GUIMovieRenamer(MovieRenamer):
    """Movie renamer that interacts with a Tkinter UI instead of the console."""

    def __init__(
        self,
        imdb_client: IMDBClient,
        root: tk.Misc,
        log_callback: Optional[LogCallback] = None,
        *,
        rename_format: str = DEFAULT_RENAME_FORMAT_KEY,
    ) -> None:
        super().__init__(imdb_client, console=None, rename_format=rename_format)
        self._root = root
        self._log = log_callback or (lambda message: None)
        self._stop_requested = False

    def process_directory(
        self,
        directory: Path,
        *,
        dry_run: bool = True,
        search_limit: int = 10,
    ) -> List[MovieCandidate]:
        self._stop_requested = False
        movie_files = list(self._discover_movie_files(directory))
        if not movie_files:
            self._log("No supported movie files were found in the selected directory.")
            return []

        self._log(f"Processing {len(movie_files)} file(s) in {directory}.")
        selected_candidates: List[MovieCandidate] = []

        for movie_file in movie_files:
            self._log(f"Searching matches for {movie_file.name}...")
            results = self._imdb_client.search(self._guess_search_query(movie_file), limit=search_limit)
            if not results:
                self._log(f"No matches found for {movie_file.name}.")
                continue

            chosen = self._prompt_for_choice(movie_file, results)
            if self._stop_requested:
                self._log("Processing stopped by user.")
                break
            if chosen is None:
                self._log(f"Skipped {movie_file.name}.")
                continue

            candidate = MovieCandidate(movie_file, chosen, self._format_spec)
            selected_candidates.append(candidate)

            if dry_run:
                self._log(f"DRY RUN: {movie_file.name} -> {candidate.proposed_filename}")
            else:
                try:
                    movie_file.rename(candidate.proposed_path)
                except OSError as exc:
                    self._log(f"Failed to rename {movie_file.name}: {exc}")
                else:
                    self._log(f"Renamed {movie_file.name} -> {candidate.proposed_filename}")

        return selected_candidates

    def _prompt_for_choice(self, file_path: Path, matches: List[IMDBMovie]) -> Optional[IMDBMovie]:
        dialog = tk.Toplevel(self._root)
        dialog.title(f"Matches for {file_path.name}")
        dialog.transient(self._root)
        dialog.grab_set()

        ttk.Label(dialog, text=f"Select the correct match for {file_path.name}").pack(padx=10, pady=10)

        listbox = tk.Listbox(dialog, width=60, height=8, exportselection=False)
        for movie in matches:
            year = movie.year or "?"
            listbox.insert(tk.END, f"{movie.title} ({year})")
        listbox.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(padx=10, pady=(0, 10))

        selection: dict[str, Optional[IMDBMovie]] = {"value": None}

        def on_select() -> None:
            chosen = listbox.curselection()
            if not chosen:
                messagebox.showwarning("Selection required", "Please pick a movie from the list.", parent=dialog)
                return
            selection["value"] = matches[chosen[0]]
            dialog.destroy()

        def on_skip() -> None:
            selection["value"] = None
            dialog.destroy()

        def on_stop() -> None:
            self._stop_requested = True
            selection["value"] = None
            dialog.destroy()

        ttk.Button(button_frame, text="Select", command=on_select).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Skip", command=on_skip).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Stop", command=on_stop).pack(side=tk.LEFT, padx=(5, 0))

        listbox.focus_set()
        if listbox.size() > 0:
            listbox.selection_set(0)

        self._root.wait_window(dialog)
        return selection["value"]


class DeeBeeApp:
    """Container for the DeeBee Tkinter interface."""

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        root.title("DeeBee")
        root.geometry("600x400")

        self._path_var = tk.StringVar(value=str(Path.cwd()))
        self._limit_var = tk.IntVar(value=10)
        self._dry_run_var = tk.BooleanVar(value=True)
        self._format_options = [
            (spec.key, spec.label) for spec in MovieRenamer.available_formats()
        ]
        default_label = next(
            (label for key, label in self._format_options if key == DEFAULT_RENAME_FORMAT_KEY),
            self._format_options[0][1],
        )
        self._format_var = tk.StringVar(value=default_label)

        self._build_widgets()

    def _build_widgets(self) -> None:
        main_frame = ttk.Frame(self._root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Directory:").grid(row=0, column=0, sticky=tk.W)
        path_entry = ttk.Entry(main_frame, textvariable=self._path_var, width=40)
        path_entry.grid(row=0, column=1, sticky=tk.EW, pady=2)
        ttk.Button(main_frame, text="Browse", command=self._choose_directory).grid(row=0, column=2, padx=(5, 0))

        ttk.Label(main_frame, text="Result limit:").grid(row=1, column=0, sticky=tk.W)
        limit_spin = ttk.Spinbox(main_frame, from_=1, to=50, textvariable=self._limit_var, width=5)
        limit_spin.grid(row=1, column=1, sticky=tk.W, pady=2)

        dry_run_check = ttk.Checkbutton(main_frame, text="Dry run (no changes)", variable=self._dry_run_var)
        dry_run_check.grid(row=1, column=2, sticky=tk.W)

        ttk.Label(main_frame, text="Filename format:").grid(row=2, column=0, sticky=tk.W)
        format_combo = ttk.Combobox(
            main_frame,
            textvariable=self._format_var,
            values=[label for _, label in self._format_options],
            state="readonly",
            width=20,
        )
        format_combo.grid(row=2, column=1, sticky=tk.W, pady=2)

        self._log_widget = tk.Text(main_frame, height=12, state=tk.DISABLED)
        self._log_widget.grid(row=3, column=0, columnspan=3, sticky=tk.NSEW, pady=(10, 0))

        scrollbar = ttk.Scrollbar(main_frame, command=self._log_widget.yview)
        scrollbar.grid(row=3, column=3, sticky=tk.NS)
        self._log_widget.configure(yscrollcommand=scrollbar.set)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)

        ttk.Button(button_frame, text="Start", command=self._start_processing).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

    def _choose_directory(self) -> None:
        directory = filedialog.askdirectory(initialdir=self._path_var.get() or None)
        if directory:
            self._path_var.set(directory)

    def _append_log(self, message: str) -> None:
        self._log_widget.configure(state=tk.NORMAL)
        self._log_widget.insert(tk.END, message + "\n")
        self._log_widget.configure(state=tk.DISABLED)
        self._log_widget.see(tk.END)
        self._root.update_idletasks()

    def _start_processing(self) -> None:
        directory = Path(self._path_var.get()).expanduser()

        if not directory.exists() or not directory.is_dir():
            messagebox.showerror("Invalid directory", f"{directory} is not a valid directory.")
            return

        try:
            limit = int(self._limit_var.get())
        except (TypeError, ValueError):
            messagebox.showerror("Invalid limit", "Result limit must be a number.")
            return

        self._append_log(f"Starting scan in {directory}...")
        imdb_client = IMDBClient()
        try:
            rename_format = next(
                key for key, label in self._format_options if label == self._format_var.get()
            )
        except StopIteration:  # pragma: no cover - safeguarded UI state
            messagebox.showerror("Invalid format", "Selected filename format is not valid.")
            return

        renamer = GUIMovieRenamer(
            imdb_client,
            self._root,
            self._append_log,
            rename_format=rename_format,
        )

        try:
            renamer.process_directory(directory, dry_run=self._dry_run_var.get(), search_limit=limit)
        except Exception as exc:  # pragma: no cover - user feedback path
            messagebox.showerror("Error", f"An error occurred: {exc}")
        else:
            self._append_log("Done.")


def main() -> None:
    root = tk.Tk()
    DeeBeeApp(root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover - manual invocation
    main()
