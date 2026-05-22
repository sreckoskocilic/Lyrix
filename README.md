# Lyrix

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-72%20passed-green.svg)](https://github.com/sreckoskocilic/Lyrix/actions)
[![Coverage](https://img.shields.io/badge/coverage-100%25-green.svg)](https://github.com/sreckoskocilic/Lyrix/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A desktop app for fetching and managing song lyrics via the [Genius API](https://genius.com/api-clients). Built with ttkbootstrap.

## Apps

**Lyrics Search** — enter artist + song or artist + album, get lyrics. Results go into the local catalog automatically.

**Lyrics Browser** — the full catalog manager. Tree view organized by artist, album, and song. You can search and import from Genius, re-fetch outdated lyrics, import an artist's entire discography, fill in missing lyrics across the catalog, edit lyrics inline, filter by name, and remove entries. Undo works for deletions (Cmd+Z, 20-item stack). A few color schemes and themes to pick from.

Keyboard shortcuts: Cmd+F (filter), Cmd+E (export), Cmd+M (fetch missing), Cmd+I (stats), Cmd+Z (undo), Cmd+/- (font size), Esc (clear filter or cancel edit), ? (shortcut help).

## Setup

```sh
pip install -r requirements.txt
cp .env.example .env  # then add your token
```

Get a Genius API token at https://genius.com/api-clients and put it in `.env`:

```
GENIUS_TOKEN=your_token_here
```

If you have **Roboto Mono for Powerline** (`Roboto Mono for Powerline.ttf`) in the project directory, the app uses it. Otherwise it falls back to the system monospace font.

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

100% coverage on core code (catalog, helpers). UI files are excluded from coverage and tested manually.

## Data

All data lives in `~/.lyrix/` (macOS/Linux) or `%APPDATA%\Lyrix\` (Windows):

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
