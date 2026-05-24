# Lyrix

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-72%20passed-green.svg)](https://github.com/sreckoskocilic/Lyrix/actions)
[![Coverage](https://img.shields.io/badge/coverage-100%25-green.svg)](https://github.com/sreckoskocilic/Lyrix/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Desktop lyrics manager. Pulls lyrics from the [Genius API](https://genius.com/api-clients), stores them locally, lets you browse and edit. Built with ttkbootstrap.

## Apps

**Lyrics Search** — type an artist + song or artist + album, get lyrics back. Everything you fetch gets saved to the local catalog.

**Lyrics Browser** — the full catalog. Tree view by artist, album, song. Search Genius, import whole discographies, re-fetch stale lyrics, fill in gaps across the catalog, edit inline, filter by name, delete stuff. Undo for deletions goes 20 deep (Cmd+Z). Comes with a few color schemes and themes.

Shortcuts: Cmd+F (filter), Cmd+E (export), Cmd+M (fetch missing), Cmd+I (stats), Cmd+Z (undo), Cmd+/- (font size), Esc (clear filter or cancel edit), ? (shortcut help).

## Setup

```sh
pip install -r requirements.txt
cp .env.example .env  # then add your token
```

Get a Genius API token at https://genius.com/api-clients and put it in `.env`:

```
GENIUS_TOKEN=your_token_here
```

If you drop **Roboto Mono for Powerline** (`Roboto Mono for Powerline.ttf`) in the project directory, the app picks it up. Otherwise it uses whatever monospace font your system has.

## Running

```sh
python -m lyrix            # Lyrics Browser (default)
python -m lyrix.search     # Lyrics Search
python menu.py             # macOS menu bar launcher (needs rumps)
```

## Testing

```sh
pip install -r requirements-dev.txt
pytest
```

100% coverage on core code (catalog, helpers). UI is excluded from coverage and tested by hand.

## Data

Everything lives in `~/.lyrix/` (macOS/Linux) or `%APPDATA%\Lyrix\` (Windows):

| File | What it is |
|------|------------|
| `lyrics_catalog.json` | All fetched lyrics |
| `settings.json` | Window state, theme, colors, font size |
| `lyrix.log` | Warnings and errors |

## Building

```sh
pip install pyinstaller
pyinstaller LyricsBrowser.spec          # Windows → dist/LyricsBrowser.exe
pyinstaller LyricsBrowser-macOS.spec    # macOS → dist/LyricsBrowser.app
```

If `.env` exists at build time, the token gets baked into the binary. Otherwise set `GENIUS_TOKEN` as an env var at runtime.
