"""Controller: catalog tree, lyrics display, Genius searches and batch actions.

Worker threads touch only the catalog (which locks internally) and report back
through signals, so every model mutation happens on the GUI thread.
"""

from __future__ import annotations

import difflib
import html
import logging
import os
import threading
from collections import Counter
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

from .. import discovery
from ..catalog import (
    _SORT_LAST,
    CATALOG_PATH,
    SONGS_CATEGORY,
    Catalog,
    _extract_name,
    _release_year,
    _year_sort,
)
from . import state
from .models import CatalogModel, Node
from .theme import (
    LYRICS_SIZE_DEFAULT,
    LYRICS_SIZE_MAX,
    LYRICS_SIZE_MIN,
    PALETTE,
)

_log = logging.getLogger(__name__)

# Album names that stand for "not on an album" and must never be searched as one.
_PSEUDO_ALBUMS = {"", SONGS_CATEGORY.lower()}
_FUZZY_THRESHOLD = 0.6
_FUZZY_MIN_QUERY = 3
_PLACEHOLDER = "← Odaberi pjesmu iz kataloga"


def _fuzzy_match(query: str, text: str) -> bool:
    return (
        difflib.SequenceMatcher(None, query, text, autojunk=False).ratio()
        >= _FUZZY_THRESHOLD
    )


def _is_section(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("[") and stripped.endswith("]")


def _lyrics_html(text: str, size: int, line_height: float) -> str:
    """Render lyrics as paragraphs so section headers get their own colour.

    Qt's rich text has no line-height, so the spacing is a per-paragraph margin.
    """
    gap = max(0, round(size * (line_height - 1)))
    body = PALETTE["text"]
    section = PALETTE["section"]
    small = max(LYRICS_SIZE_MIN, size - 2)
    parts = []
    for line in text.splitlines():
        if _is_section(line):
            style = f"color:{section}; font-size:{small}px;"
        else:
            style = f"color:{body}; font-size:{size}px;"
        content = html.escape(line) or "&nbsp;"
        parts.append(f'<p style="margin:0 0 {gap}px 0; {style}">{content}</p>')
    return "".join(parts)


def _build_track_entries(
    tracks, artist_name: str, album_name: str, album_year: str
) -> list[dict]:
    """Build catalog entry dicts from a Genius album tracks list."""
    entries = []
    for num, track in tracks:
        entries.append(
            {
                "artist": artist_name,
                "title": track.title.strip(),
                "album": album_name,
                "year": album_year,
                "lyrics": track.to_text(),
                "track": num if isinstance(num, int) else 0,
            }
        )
    return entries


class Controller(QObject):
    statusChanged = Signal(str)
    countsChanged = Signal(str)
    busyChanged = Signal(bool)
    songLoaded = Signal(dict)
    errorRaised = Signal(str, str)
    geniusReady = Signal(bool)
    currentIndexChanged = Signal(int)
    editingChanged = Signal(bool)

    _refreshRequested = Signal()
    _showRequested = Signal(str, str, str)

    def __init__(self, model: CatalogModel, path: Path = CATALOG_PATH) -> None:
        super().__init__()
        self._model = model
        self.catalog = Catalog(path)
        self.genius = self._create_genius_client()

        saved = state.read_state()
        self._filter = ""
        self._expanded: set[str] = {
            raw.lower().strip()
            for raw in (saved.get("expanded_artists") or [])
            if isinstance(raw, str)
        }
        self._expanded_albums: set[tuple[str, str]] = {
            (parts[0], parts[1])
            for raw in (saved.get("expanded_albums") or [])
            if isinstance(raw, str) and len(parts := raw.split("\t")) == 2
        }
        self._current: dict | None = None
        self._pending_restore: dict | None = saved.get("last_selected") or None
        if self._pending_restore:
            self._expanded.add(
                self._pending_restore.get("artist", "").lower().strip()
            )
            self._expanded_albums.add(
                (
                    self._pending_restore.get("artist", "").lower().strip(),
                    self._pending_restore.get("album", "").lower().strip(),
                )
            )
        self._pending_remove: dict | None = None
        self._editing = False
        self._busy = False
        self._closing = False
        size = saved.get("lyrics_size")
        self._lyrics_size = (
            size
            if isinstance(size, int) and LYRICS_SIZE_MIN <= size <= LYRICS_SIZE_MAX
            else LYRICS_SIZE_DEFAULT
        )

        self._refreshRequested.connect(self.refresh)
        self._showRequested.connect(self._show_key)

    # ── Genius ────────────────────────────────────────────────────────────────

    def _create_genius_client(self):
        token = os.getenv("GENIUS_TOKEN", "").strip()
        if not token:
            return None
        from lyricsgenius import Genius

        return Genius(token, timeout=10)

    def _require_genius(self) -> bool:
        if self.genius is None:
            self.errorRaised.emit(
                "Genius", "GENIUS_TOKEN is missing, so Genius searches are disabled."
            )
            return False
        return True

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @Slot()
    def start(self) -> None:
        self.geniusReady.emit(self.genius is not None)
        self.refresh()

    @Slot()
    def shutdown(self) -> None:
        self._closing = True
        patch: dict[str, object] = {
            "expanded_artists": sorted(self._expanded),
            "expanded_albums": sorted(
                f"{artist}\t{album}" for artist, album in self._expanded_albums
            ),
            "lyrics_size": self._lyrics_size,
        }
        if self._current:
            patch["last_selected"] = {
                "artist": self._current["artist"],
                "title": self._current["title"],
                "album": self._current.get("album", ""),
            }
        state.write_state(patch)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy and self._editing:
            self.cancel_edit()
        self.busyChanged.emit(busy)

    def _idle(self) -> None:
        """Clear the busy flag from a worker thread."""
        self._busy = False
        self.busyChanged.emit(False)

    # ── Tree ──────────────────────────────────────────────────────────────────

    @Slot(str)
    def set_filter(self, text: str) -> None:
        self._filter = text.strip().lower()
        self.refresh()

    @Slot()
    def refresh(self) -> None:
        self.catalog.reload()
        raw_entries = self.catalog.all_entries()
        total = len(raw_entries)

        keyed = [
            (
                e,
                e["artist"].lower().strip(),
                e["title"].lower().strip(),
                (e.get("album") or "").lower().strip(),
            )
            for e in raw_entries
        ]
        artist_total = len({t[1] for t in keyed})

        if self._filter:
            use_fuzzy = len(self._filter) >= _FUZZY_MIN_QUERY
            keyed = [
                t
                for t in keyed
                if self._filter in t[1]
                or self._filter in t[2]
                or self._filter in t[3]
                or (
                    use_fuzzy
                    and (
                        _fuzzy_match(self._filter, t[1])
                        or _fuzzy_match(self._filter, t[2])
                        or _fuzzy_match(self._filter, t[3])
                    )
                )
            ]

        canon_year: dict[tuple, str] = {}
        tagged = []
        for entry, al, tl, alb in keyed:
            bucket = (al, alb)
            if not canon_year.get(bucket):
                canon_year[bucket] = entry.get("year", "")
            tagged.append((entry, al, tl, alb, bucket))

        tagged.sort(
            key=lambda x: (
                x[1],
                _year_sort(canon_year.get(x[4], "")),
                x[3],
                x[0].get("track") or _SORT_LAST,
                x[2],
            )
        )

        artist_counts = Counter(t[1] for t in tagged)
        album_counts = Counter(t[4] for t in tagged)

        rows: list[Node] = []
        seen_artists: set[str] = set()
        seen_albums: set[tuple] = set()
        filtering = bool(self._filter)

        for entry, al, _tl, _alb, bucket in tagged:
            artist = entry["artist"] or "Unknown Artist"
            album = entry.get("album") or SONGS_CATEGORY
            year = canon_year.get(bucket, "")
            # A filter is a search: open everything it matched.
            artist_open = filtering or al in self._expanded
            album_open = filtering or bucket in self._expanded_albums

            if al not in seen_artists:
                seen_artists.add(al)
                rows.append(
                    {
                        "kind": "artist",
                        "depth": 0,
                        "name": artist,
                        "meta": str(artist_counts[al]),
                        "num": "",
                        "expanded": artist_open,
                        "artist": artist,
                        "title": "",
                        "album": "",
                    }
                )
            if not artist_open:
                continue
            if bucket not in seen_albums:
                seen_albums.add(bucket)
                # Pad to two digits so the year column lines up across albums.
                count = str(album_counts[bucket]).rjust(2)
                rows.append(
                    {
                        "kind": "album",
                        "depth": 1,
                        "name": album,
                        "meta": f"{year} · {count}" if year else count,
                        "num": "",
                        "expanded": album_open,
                        "artist": artist,
                        "title": "",
                        "album": entry.get("album") or "",
                    }
                )
            if not album_open:
                continue
            track = entry.get("track", 0)
            rows.append(
                {
                    "kind": "song",
                    "depth": 2,
                    "name": entry["title"],
                    "meta": "",
                    "num": str(track) if track else "",
                    "expanded": False,
                    "artist": entry["artist"],
                    "title": entry["title"],
                    "album": entry.get("album") or "",
                }
            )

        self._model.set_rows(rows)
        if not filtering:
            # Drop artists/albums that no longer exist. Never do this while
            # filtering: the filtered-out ones are hidden, not gone.
            self._expanded &= {t[1] for t in tagged}
            self._expanded_albums &= {t[4] for t in tagged}

        if self._filter:
            shown = sum(1 for r in rows if r["kind"] == "song")
            self.countsChanged.emit(f"{shown} of {total} songs")
        else:
            self.countsChanged.emit(f"{artist_total} artists · {total} songs")

        self._restore_selection()

    def _restore_selection(self) -> None:
        restore = self._pending_restore
        self._pending_restore = None
        if restore is None and self._current:
            restore = {
                "artist": self._current["artist"],
                "title": self._current["title"],
                "album": self._current.get("album", ""),
            }
        if restore is None:
            if self._current is None and not self._editing:
                self._show_placeholder()
            return
        entry = self.catalog.get(
            restore.get("artist", ""),
            restore.get("title", ""),
            restore.get("album", ""),
        )
        if entry is None:
            self._current = None
            self._show_placeholder()
            return
        self._current = entry
        self._emit_song(entry)
        index = self._model.index_of_song(
            entry["artist"], entry["title"], entry.get("album", "")
        )
        self.currentIndexChanged.emit(index)

    @Slot(int)
    def toggle(self, index: int) -> None:
        row = self._model.row_at(index)
        if row is None:
            return
        if row["kind"] == "artist":
            name = str(row["artist"]).lower().strip()
            if name in self._expanded:
                self._expanded.discard(name)
            else:
                self._expanded.add(name)
            self.refresh()
        elif row["kind"] == "album":
            bucket = (
                str(row["artist"]).lower().strip(),
                str(row["album"]).lower().strip(),
            )
            if bucket in self._expanded_albums:
                self._expanded_albums.discard(bucket)
            else:
                self._expanded_albums.add(bucket)
            self.refresh()

    @Slot(int)
    def expand(self, index: int) -> None:
        row = self._model.row_at(index)
        if row is not None and not row["expanded"] and row["kind"] != "song":
            self.toggle(index)

    @Slot(int)
    def collapse(self, index: int) -> None:
        row = self._model.row_at(index)
        if row is not None and row["expanded"] and row["kind"] != "song":
            self.toggle(index)

    @Slot(int)
    def click(self, index: int) -> None:
        row = self._model.row_at(index)
        if row is None or row["kind"] != "song":
            return
        entry = self.catalog.get(
            str(row["artist"]), str(row["title"]), str(row["album"])
        )
        if entry is None:
            return
        if self._editing:
            self.cancel_edit()
        self._current = entry
        self._emit_song(entry)

    # ── Lyrics display ────────────────────────────────────────────────────────

    def _emit_song(self, entry: dict) -> None:
        lyrics = entry.get("lyrics", "")
        self.songLoaded.emit(
            {
                "empty": False,
                "title": entry["title"],
                "lyrics": lyrics,
                "html": _lyrics_html(lyrics, self._lyrics_size, 1.30),
            }
        )

    def _show_placeholder(self) -> None:
        self.songLoaded.emit(
            {
                "empty": True,
                "title": "",
                "lyrics": "",
                "html": (
                    f'<p style="margin:0; color:{PALETTE["faint"]};">{_PLACEHOLDER}</p>'
                ),
            }
        )

    @Slot(str, str, str)
    def _show_key(self, artist: str, title: str, album: str) -> None:
        entry = self.catalog.get(artist, title, album)
        if entry is None:
            return
        self._current = entry
        self._emit_song(entry)

    @Slot(int, result=int)
    def change_lyrics_size(self, delta: int) -> int:
        size = max(
            LYRICS_SIZE_MIN, min(LYRICS_SIZE_MAX, self._lyrics_size + delta)
        )
        if size != self._lyrics_size:
            self._lyrics_size = size
            if self._current is not None:
                self._emit_song(self._current)
        return self._lyrics_size

    # ── Edit ──────────────────────────────────────────────────────────────────

    @Slot()
    def start_edit(self) -> None:
        if self._current is None or self._busy:
            return
        self._editing = True
        self.editingChanged.emit(True)

    @Slot()
    def cancel_edit(self) -> None:
        if not self._editing:
            return
        self._editing = False
        self.editingChanged.emit(False)
        if self._current is not None:
            self._emit_song(self._current)

    @Slot(str)
    def save_edit(self, lyrics: str) -> None:
        if self._current is None:
            self.cancel_edit()
            return
        entry = self._current
        try:
            self.catalog.add(
                entry["artist"],
                entry["title"],
                entry.get("album", ""),
                entry.get("year", ""),
                lyrics,
                track=entry.get("track", 0),
            )
        except Exception as exc:
            self.errorRaised.emit(
                "Save Error", f"Could not save lyrics to catalog:\n{exc}"
            )
            return
        self._current = self.catalog.get(
            entry["artist"], entry["title"], entry.get("album", "")
        )
        self._editing = False
        self.editingChanged.emit(False)
        self.refresh()
        self.statusChanged.emit(f"Saved: {entry['title']}")

    # ── Clipboard & file ──────────────────────────────────────────────────────

    @Slot()
    def copy_lyrics(self) -> None:
        if self._current is None:
            return
        text = self._current.get("lyrics", "")
        if not text.strip():
            return
        QGuiApplication.clipboard().setText(text)
        self.statusChanged.emit("Copied to clipboard.")

    @Slot(str)
    def save_lyrics_to(self, url: str) -> None:
        if self._current is None:
            return
        lyrics = self._current.get("lyrics", "").strip()
        if not lyrics:
            self.errorRaised.emit("Save", "There are no lyrics to save.")
            return
        path = Path(QUrl(url).toLocalFile() or url)
        try:
            path.write_text(lyrics, encoding="utf-8")
        except OSError as exc:
            self.errorRaised.emit("Save Error", f"Could not write file:\n{exc}")
            return
        self.statusChanged.emit(f"Saved: {path.name}")

    # ── Remove ────────────────────────────────────────────────────────────────

    @Slot(int, result=str)
    def remove_prompt(self, index: int) -> str:
        row = self._model.row_at(index)
        self._pending_remove = None
        if row is None:
            return ""
        self._pending_remove = {
            "kind": str(row["kind"]),
            "artist": str(row["artist"]),
            "title": str(row["title"]),
            "album": str(row["album"]),
        }
        if row["kind"] == "song":
            return f'Remove "{row["title"]}" from catalog?'
        if row["kind"] == "album":
            count = len(
                self.catalog.find_album(str(row["artist"]), str(row["album"]))
            )
            return f"Remove all {count} song(s) in this album from the catalog?"
        count = len(self.catalog.find_by_artist(str(row["artist"])))
        return f'Remove all {count} song(s) by "{row["artist"]}" from the catalog?'

    @Slot()
    def remove_confirmed(self) -> None:
        row = self._pending_remove
        self._pending_remove = None
        if row is None:
            return
        artist, title, album = row["artist"], row["title"], row["album"]
        kind = row["kind"]
        if kind == "song":
            self.catalog.remove(artist, title, album)
            if self._current and (
                self._current["artist"],
                self._current["title"],
                self._current.get("album", ""),
            ) == (artist, title, album):
                self._current = None
            self.statusChanged.emit(f"Removed: {title}")
        elif kind == "album":
            removed = self.catalog.remove_album(artist, album)
            self._expanded_albums.discard(
                (artist.lower().strip(), album.lower().strip())
            )
            self._current = None
            self.statusChanged.emit(f"Removed {removed} songs")
        else:
            artist_lower = artist.lower().strip()
            removed = self.catalog.remove_artist(artist)
            self._expanded_albums -= {
                key for key in self._expanded_albums if key[0] == artist_lower
            }
            self._current = None
            self.statusChanged.emit(f"Removed {removed} songs")
        self.refresh()

    # ── Genius search ─────────────────────────────────────────────────────────

    @Slot(str, str)
    def search_song(self, artist: str, song: str) -> None:
        artist, song = artist.strip(), song.strip()
        if self._busy or not self._require_genius():
            return
        if not artist:
            self.errorRaised.emit("Error", "Artist is required!")
            return
        if not song:
            self.errorRaised.emit("Error", "Song is required!")
            return
        self._set_busy(True)
        self.statusChanged.emit(f"Searching: {artist} — {song}…")
        self._spawn(self._run_search_song, artist, song)

    def _run_search_song(self, artist: str, song: str) -> None:
        try:
            ss = self.genius.search_song(song, artist)
        except Exception as exc:
            self._idle()
            self.errorRaised.emit("Error", f"Search failed:\n{exc}")
            return
        if not ss:
            self._idle()
            self.statusChanged.emit(f"Not found: {song}")
            return
        title = ss.title.strip()
        album_data = getattr(ss, "album", {}) or {}
        album_name = (album_data.get("name") or "").strip() or SONGS_CATEGORY
        year = _release_year(album_data)
        try:
            self.catalog.add(ss.artist, title, album_name, year, ss.to_text())
        except Exception as exc:
            self._idle()
            self.errorRaised.emit("Error", f"Could not save to catalog:\n{exc}")
            return
        self._idle()
        self.statusChanged.emit(f"Found and imported: {title}")
        self._showRequested.emit(ss.artist, title, album_name)
        self._refreshRequested.emit()

    @Slot(str, str)
    def search_album(self, artist: str, album: str) -> None:
        artist, album = artist.strip(), album.strip()
        if self._busy or not self._require_genius():
            return
        if not artist:
            self.errorRaised.emit("Error", "Artist is required!")
            return
        if not album:
            self.errorRaised.emit("Error", "Album is required!")
            return
        self._set_busy(True)
        self.statusChanged.emit(f"Searching: {artist} — {album}…")
        self._spawn(self._run_search_album, artist, album)

    def _run_search_album(self, artist: str, album: str) -> None:
        try:
            ss = self.genius.search_album(album, artist)
        except Exception as exc:
            self._idle()
            self.errorRaised.emit("Error", f"Search failed:\n{exc}")
            return
        if not ss or not ss.tracks:
            self._idle()
            self.statusChanged.emit(f"Album not found: {album}")
            return
        artist_name = _extract_name(getattr(ss, "artist", None), artist)
        album_name = getattr(ss, "name", "").strip() or album
        year = _release_year(ss)
        try:
            self.catalog.add_many(
                _build_track_entries(ss.tracks, artist_name, album_name, year)
            )
        except Exception as exc:
            self._idle()
            self.errorRaised.emit(
                "Error", f"Failed to save album to catalog:\n{exc}"
            )
            return
        self._idle()
        self.statusChanged.emit(
            f"Found and imported: {album_name} ({len(ss.tracks)} tracks)"
        )
        self._refreshRequested.emit()

    @Slot(str)
    def search_artist(self, artist: str) -> None:
        artist = artist.strip()
        if self._busy or not self._require_genius():
            return
        if not artist:
            self.errorRaised.emit("Error", "Artist is required!")
            return
        self._set_busy(True)
        self.statusChanged.emit(f"Searching releases for: {artist}…")
        self._spawn(self._run_import_albums, artist)

    # ── Update ────────────────────────────────────────────────────────────────

    @Slot(int)
    def update_selected(self, index: int) -> None:
        row = self._model.row_at(index)
        if row is None or not self._require_genius() or self._busy:
            return
        kind = row["kind"]
        if kind == "song":
            self._set_busy(True)
            self.statusChanged.emit(f"Updating: {row['title']}…")
            self._spawn(
                self._run_update_song,
                str(row["artist"]),
                str(row["title"]),
                str(row["album"]),
            )
        elif kind == "album":
            self._set_busy(True)
            self.statusChanged.emit(f"Updating album: {row['album']}…")
            self._spawn(
                self._run_update_album, str(row["artist"]), str(row["album"])
            )
        else:
            artist_name = str(row["artist"])
            album_map: dict[str, list] = {}
            for entry in self.catalog.find_by_artist(artist_name):
                album_map.setdefault(entry.get("album") or "", []).append(
                    (entry["artist"], entry["title"])
                )
            if not album_map:
                return
            total = sum(len(songs) for songs in album_map.values())
            self._set_busy(True)
            self.statusChanged.emit(f"Updating {total} songs…")
            self._spawn(self._run_update_artist, artist_name, album_map)

    def _run_update_song(self, artist: str, title: str, album: str) -> None:
        try:
            ss = self.genius.search_song(title, artist)
        except Exception as exc:
            self._idle()
            self.errorRaised.emit("Error", f"Could not fetch lyrics:\n{exc}")
            return
        if not ss:
            self._idle()
            self.statusChanged.emit(f"Not found: {title}")
            return
        if self._closing:
            self._idle()
            return
        existing = self.catalog.get(artist, title, album)
        album_data = getattr(ss, "album", {}) or {}
        album_name = (
            album_data.get("name")
            or (existing or {}).get("album", "")
            or album
            or SONGS_CATEGORY
        )
        year = _release_year(album_data) or (existing or {}).get("year", "")
        track = (existing or {}).get("track", 0)
        ss_title = ss.title.strip()
        try:
            # Write the replacement first: a failure then leaves the old entry
            # intact instead of losing the song.
            self.catalog.add(
                artist, ss_title, album_name, year, ss.to_text(), track=track
            )
            if ss_title != title or album_name != album:
                self.catalog.remove(artist, title, album)
        except Exception as exc:
            self._idle()
            self.errorRaised.emit("Error", f"Could not save lyrics:\n{exc}")
            return
        self._idle()
        self.statusChanged.emit(f"Updated: {ss_title}")
        self._showRequested.emit(artist, ss_title, album_name)
        self._refreshRequested.emit()

    def _run_update_album(self, artist: str, album: str) -> None:
        try:
            ss = self.genius.search_album(album, artist)
        except Exception as exc:
            self._idle()
            self.errorRaised.emit("Error", f"Could not fetch album:\n{exc}")
            return
        if not ss or not ss.tracks:
            self._idle()
            self.statusChanged.emit(f"Album not found: {album}")
            return
        artist_name = _extract_name(getattr(ss, "artist", None), artist)
        album_name = getattr(ss, "name", "").strip() or album
        year = _release_year(ss)
        try:
            entries = _build_track_entries(ss.tracks, artist_name, album_name, year)
            self.catalog.add_many(entries)
        except Exception as exc:
            self._idle()
            self.errorRaised.emit("Error", f"Could not update album:\n{exc}")
            return
        self._idle()
        self.statusChanged.emit(
            f"Updated album: {album_name} ({len(ss.tracks)} tracks)"
        )
        self._refreshRequested.emit()

    def _run_update_artist(self, artist: str, album_map: dict) -> None:
        updated = failed = 0
        for album_name, songs in album_map.items():
            if self._closing:
                break
            self.statusChanged.emit(
                f"Updating: {artist} — {album_name or 'singles'}…"
            )
            if album_name.lower() not in _PSEUDO_ALBUMS:
                try:
                    ss = self.genius.search_album(album_name, artist)
                except Exception as exc:
                    _log.warning(
                        "Album fetch failed for %s / %s: %s", artist, album_name, exc
                    )
                    ss = None
                if ss and ss.tracks:
                    name = _extract_name(getattr(ss, "artist", None), artist)
                    alb = getattr(ss, "name", "").strip() or album_name
                    try:
                        self.catalog.add_many(
                            _build_track_entries(
                                ss.tracks, name, alb, _release_year(ss)
                            )
                        )
                    except Exception as exc:
                        _log.warning(
                            "Album update failed for %s / %s: %s",
                            artist,
                            album_name,
                            exc,
                        )
                        failed += len(ss.tracks)
                        continue
                    updated += len(ss.tracks)
                    self._refreshRequested.emit()
                    continue
            # Singles and albums Genius has no page for fall back to per-song
            # lookups below.
            song_entries: list[dict] = []
            title_changes: list[tuple] = []
            for song_artist, title in songs:
                if self._closing:
                    break
                existing = self.catalog.get(song_artist, title, album_name)
                try:
                    ss = self.genius.search_song(title, song_artist)
                except Exception as exc:
                    _log.warning(
                        "Song fetch failed for %s / %s: %s", song_artist, title, exc
                    )
                    failed += 1
                    continue
                if not ss:
                    failed += 1
                    continue
                album_data = getattr(ss, "album", {}) or {}
                ss_title = ss.title.strip()
                if ss_title != title:
                    title_changes.append((song_artist, title, album_name))
                song_entries.append(
                    {
                        "artist": song_artist,
                        "title": ss_title,
                        "album": album_data.get("name")
                        or (existing or {}).get("album", "")
                        or album_name,
                        "year": _release_year(album_data)
                        or (existing or {}).get("year", ""),
                        "lyrics": ss.to_text(),
                        "track": (existing or {}).get("track", 0),
                    }
                )
                updated += 1
            if song_entries:
                self.catalog.add_many(song_entries)
            if title_changes:
                self.catalog.remove_album_entries(title_changes)
            if song_entries or title_changes:
                self._refreshRequested.emit()
        self._idle()
        message = f"Updated {updated} songs" + (
            f", {failed} failed" if failed else ""
        )
        self.statusChanged.emit(message)
        self._refreshRequested.emit()

    # ── Artist import (MusicBrainz + Genius) ──────────────────────────────────

    def _run_import_albums(self, artist: str) -> None:
        """Discover studio albums via MusicBrainz, import each via Genius."""
        self.statusChanged.emit(f"Finding studio albums for: {artist}…")
        try:
            artist_name, albums = discovery.studio_albums(
                artist, is_cancelled=lambda: self._closing
            )
        except Exception as exc:
            self._idle()
            self.errorRaised.emit("Error", f"Could not fetch album list:\n{exc}")
            return
        if not albums:
            self._idle()
            self.statusChanged.emit(f"No studio albums found for: {artist_name}")
            return

        existing = self.catalog.all_artist_album_pairs()
        _log.info("Discovered %d studio albums for %s", len(albums), artist_name)
        added = skipped = failed = 0
        for i, album in enumerate(albums, 1):
            if self._closing:
                break
            album_name = album["title"]
            key = (artist_name.lower().strip(), album_name.lower().strip())
            if key in existing:
                skipped += 1
                continue
            self.statusChanged.emit(
                f"[{i}/{len(albums)}] Importing: {album_name}…"
            )
            try:
                ss = self.genius.search_album(album_name, artist_name)
            except Exception as exc:
                _log.warning(
                    "Album fetch failed for %s / %s: %s", artist_name, album_name, exc
                )
                failed += 1
                continue
            if not ss or not ss.tracks:
                failed += 1
                continue
            year = _release_year(ss) or album.get("year") or ""
            entries = _build_track_entries(ss.tracks, artist_name, album_name, year)
            if entries:
                self.catalog.add_many(entries)
                added += len(entries)
                existing.add(key)
                self._refreshRequested.emit()

        self._idle()
        message = f"Imported {added} songs"
        if skipped:
            message += f", {skipped} albums skipped"
        if failed:
            message += f", {failed} failed"
        self.statusChanged.emit(message)
        self._refreshRequested.emit()

    # ── Threads ───────────────────────────────────────────────────────────────

    def _spawn(self, target, *args) -> None:
        threading.Thread(target=target, args=args, daemon=True).start()
