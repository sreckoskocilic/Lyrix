# Lyrix

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-68%20passed-green.svg)](https://github.com/skocho/lyrix/actions)
[![Coverage](https://img.shields.io/badge/coverage-100%25-green.svg)](https://github.com/skocho/lyrix/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A ttkbootstrap app for fetching and managing song lyrics via the [Genius API](https://genius.com/api-clients).

## Apps

### Lyrics Search
Simple search interface. Enter artist + song or artist + album, fetch lyrics, and optionally save to a text file. Results are automatically added to the local catalog.

### Lyrics Browser
Full catalog manager with a tree view (artist → album → song). Supports:
- **Song / Album / Artist search** — fetch and import lyrics directly from the browser
- **Import All Releases** — import every album for a selected artist
- **Update** — re-fetch lyrics for a selected song, album, or artist
- **Fetch Missing Lyrics** — fill in lyrics for catalog entries that have none
- **Remove** — remove a song, album, or artist from the catalog
- **Edit / Copy** — inline-edit or copy lyrics to clipboard
- Filter box for searching the catalog by artist, album, or title

## Setup

```sh
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development/testing
```

Copy `.env.example` to `.env` and add your token:

```
GENIUS_TOKEN=your_token_here
```

Get a token at https://genius.com/api-clients.

The optional font **Roboto Mono for Powerline** (`Roboto Mono for Powerline.ttf`) can be placed in the project directory for a nicer UI. The apps fall back to the system monospace font if it's absent.

## Running

```sh
python -m lyrix.browser   # Lyrics Browser
python -m lyrix.search    # Lyrics Search
python -m lyrix            # Lyrics Browser (default)
python run.py             # Alias for default app
```

On macOS, `menu.py` provides a menu bar launcher (requires `pip install rumps`):

```sh
python menu.py
```

## Testing

```sh
pip install -r requirements-dev.txt
pytest
```

## Data

| File | Purpose |
|------|---------|
| `lyrics_catalog.json` | Persistent catalog of fetched lyrics (gitignored) |
| `settings.json` | Window geometry and sash position (gitignored) |
| `lyrix.log` | Application log file (warnings and errors) |

**Data locations:**
- **macOS/Linux**: `~/.lyrix/`
- **Windows**: `%APPDATA%\Lyrix\`

## Project structure

```
lyrix/
├── __init__.py           # Package init
├── __main__.py           # Entry point
├── browser.py            # Lyrics Browser app
├── browser_actions.py    # Browser action methods (update, import, fetch)
├── browser_search.py    # Browser search methods
├── search.py            # Lyrics Search app
├── catalog.py           # Persistent catalog and helpers
└── base_app.py          # Shared base class and settings
tests/
├── conftest.py           # pytest path setup
├── test_catalog.py      # Catalog tests (56)
└── test_helpers.py     # Helper function tests (12)
.env                    # API token (gitignored)
.env.example
menu.py                 # macOS menu bar launcher
run.py                 # Simple entry point
LyricsBrowser.spec     # PyInstaller spec (Windows)
LyricsBrowser-macOS.spec # PyInstaller spec (macOS)
requirements.txt
requirements-dev.txt  # Dev dependencies
```

## Windows Build

```sh
pip install pyinstaller
pyinstaller LyricsBrowser.spec
```

Produces a single `dist/LyricsBrowser.exe`. If a `.env` file exists in the project directory at build time it is bundled into the executable; otherwise set `GENIUS_TOKEN` as an environment variable at runtime.

## macOS Build

```sh
pip install pyinstaller
pyinstaller LyricsBrowser-macOS.spec
```

Produces `dist/LyricsBrowser.app`.

The catalog and settings files are stored in the standard data directory (`~/.lyrix/` on macOS/Linux, `%APPDATA%\Lyrix\` on Windows).
