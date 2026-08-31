# Lyrix

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Coverage](https://img.shields.io/badge/coverage-100%25-green.svg)](https://github.com/sreckoskocilic/Lyrix/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Desktop lyrics manager. Pulls lyrics from the [Genius API](https://genius.com/api-clients), stores them locally, lets you browse and edit. Built with PySide6 + QML.

## What it does

The full catalog in one window: tree by artist, album, song. Search Genius for a song, an album, or a whole discography; re-fetch stale lyrics; edit inline; filter by name; delete.

Shortcuts: Cmd+F (filter), Cmd+/- (lyrics font size), Esc (clear filter or cancel edit). Typing anywhere in the tree jumps to the filter.

## Setup

```sh
pip install -r requirements.txt
cp .env.example .env  # then add your token
```

Get a Genius API token at https://genius.com/api-clients and put it in `.env`:

```
GENIUS_TOKEN=your_token_here
```

Roboto Mono for Powerline ships in `lyrix/ui/fonts/` and is loaded at startup.

## Running

```sh
python -m lyrix
python run.py     # same thing
```

## Testing

```sh
pip install -r requirements-dev.txt
pytest
```

100% coverage on core code (catalog, discovery). UI is excluded from coverage and tested by hand.

## Data

Everything lives in `~/.lyrix/` (macOS/Linux) or `%APPDATA%\Lyrix\` (Windows):

| File | What it is |
|------|------------|
| `lyrics_catalog.json` | All fetched lyrics |
| `settings-qt.json` | Window geometry, sash position, expanded artists, font size |
| `lyrix.log` | Warnings and errors |

## Building

```sh
pip install pyinstaller
pyinstaller LyricsBrowser-macOS.spec    # macOS → dist/LyricsBrowser.app
```

If `.env` exists at build time, the token gets baked into the binary. Otherwise set `GENIUS_TOKEN` as an env var at runtime.
