import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from threading import Lock

ENV_ABS_PATH = Path(__file__).parent.parent  # project root
_log = logging.getLogger(__name__)

if sys.platform == "win32":  # pragma: no cover
    _BASE_DIR = (
        Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Lyrix"
    )
else:
    _BASE_DIR = Path.home() / ".lyrix"

CATALOG_PATH = _BASE_DIR / "lyrics_catalog.json"

SONGS_CATEGORY = "Songs"
_SORT_LAST = 9999  # sentinel: sort unknown/missing values to the end


def _year_sort(year_str: str) -> int:
    """Convert a year string to a sort key. Unknown/missing years sort last."""
    try:
        return int(year_str or 0) or _SORT_LAST
    except (ValueError, TypeError):
        return _SORT_LAST


def get_resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", None)
    return (Path(base_path) if base_path else ENV_ABS_PATH) / relative_path


def _release_year(album_data) -> str:
    """Extract a 4-digit year string from a Genius album dict or object."""
    if album_data is None:
        return ""
    # Prefer release_date_components (datetime or dict with 'year')
    rdc = (
        album_data.get("release_date_components")
        if isinstance(album_data, dict)
        else getattr(album_data, "release_date_components", None)
    )
    if rdc is not None:
        if isinstance(rdc, dict):
            year = rdc.get("year")
            if year:
                return str(year)
        else:
            year = getattr(rdc, "year", None)
            if year:
                return str(year)
    # Fallback: release_date_for_display string
    if isinstance(album_data, dict):
        release_date = album_data.get("release_date_for_display", "") or ""
    else:
        release_date = getattr(album_data, "release_date_for_display", "") or ""
    if not release_date:
        return ""
    if len(release_date) == 4 and release_date.isdigit():
        return release_date
    for fmt in ("%B %d, %Y", "%B %Y"):
        try:
            # Genius release dates carry no timezone; only the year is used.
            return str(datetime.strptime(release_date, fmt).year)  # noqa: DTZ007
        except ValueError:
            continue
    return ""


def _entries_or_raise(raw) -> dict:
    """Return the entries mapping of a parsed catalog, rejecting any other shape."""
    if not isinstance(raw, dict):
        raise TypeError(f"catalog root is {type(raw).__name__}, expected object")
    entries = raw.get("entries", {})
    if not isinstance(entries, dict):
        raise TypeError(f"catalog entries is {type(entries).__name__}, expected object")
    return entries


def _extract_name(obj, fallback="Unknown"):
    if isinstance(obj, dict):
        return obj.get("name") or fallback
    return getattr(obj, "name", None) or fallback


# ── Catalog ───────────────────────────────────────────────────────────────────


class Catalog:
    """Persistent JSON-backed store keyed by (artist, title, album)."""

    def __init__(self, path: Path = CATALOG_PATH):
        self._path = path
        self._data: dict = {}
        self._lock = Lock()
        self._artist_album_index: dict[tuple[str, str], list[str]] = {}
        self._file_mtime: int = 0
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                data = _entries_or_raise(raw)
                needs_save = False
                for old_key in [k for k in data if k.count("\t") == 1]:
                    entry = data.pop(old_key)
                    album_lower = (entry.get("album") or "").lower().strip()
                    data[f"{old_key}\t{album_lower}"] = entry
                    needs_save = True
                self._data = data
                self._rebuild_index()
                if needs_save:
                    try:
                        self._save()
                    except Exception as exc:
                        _log.warning("Migration save failed: %s", exc)
                try:
                    self._file_mtime = self._path.stat().st_mtime_ns
                except OSError:
                    pass
            except Exception as exc:
                _log.error(
                    "Catalog at %s is unreadable (%s) — starting empty; "
                    "original preserved as %s",
                    self._path,
                    exc,
                    self._path.with_suffix(".corrupt"),
                )
                try:
                    self._path.with_suffix(".corrupt").write_bytes(
                        self._path.read_bytes()
                    )
                except OSError:
                    pass
                self._data = {}

    def _save(self):
        content = json.dumps(
            {"version": 1, "entries": self._data}, ensure_ascii=False, indent=2
        )
        tmp = self._path.with_suffix(".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with tmp.open("w", encoding="utf-8") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            tmp.replace(self._path)
            try:
                self._file_mtime = self._path.stat().st_mtime_ns
            except OSError:
                pass
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    @staticmethod
    def _key(artist: str, title: str, album: str = "") -> str:
        return f"{artist.lower().strip()}\t{title.lower().strip()}\t{(album or '').lower().strip()}"

    @staticmethod
    def _index_remove_key(index: dict, lookup: tuple, key: str) -> None:
        if lookup not in index:
            return
        try:
            index[lookup].remove(key)
        except ValueError:
            pass
        if not index[lookup]:
            del index[lookup]

    def _rebuild_index(self):
        """Rebuild the (artist, album) index for fast lookups."""
        self._artist_album_index.clear()
        for key in self._data:
            parts = key.split("\t")
            if len(parts) >= 3:
                self._artist_album_index.setdefault((parts[0], parts[2]), []).append(
                    key
                )

    def add(
        self,
        artist: str,
        title: str,
        album: str,
        year: str,
        lyrics: str,
        track: int = 0,
    ):
        with self._lock:
            key = self._key(artist, title, album)
            existing_added = self._data.get(key, {}).get("added", "")
            is_new = key not in self._data
            self._data[key] = {
                "artist": artist,
                "title": title,
                "album": album or "",
                "year": year or "",
                "track": track,  # track number within album; 0 = unknown
                "lyrics": lyrics,
                "added": existing_added
                or datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            if is_new:
                parts = key.split("\t")
                self._artist_album_index.setdefault((parts[0], parts[2]), []).append(
                    key
                )
            self._save()

    def add_many(self, entries: list[dict]):
        """Add multiple entries in a single save, avoiding per-track JSON writes."""
        if not entries:
            return
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._lock:
            for e in entries:
                key = self._key(e["artist"], e["title"], e.get("album", ""))
                existing_added = self._data.get(key, {}).get("added", "")
                is_new = key not in self._data
                self._data[key] = {
                    "artist": e["artist"],
                    "title": e["title"],
                    "album": e.get("album") or "",
                    "year": e.get("year") or "",
                    "track": e.get("track", 0),
                    "lyrics": e["lyrics"],
                    "added": existing_added or e.get("added") or now,
                }
                if is_new:
                    parts = key.split("\t")
                    self._artist_album_index.setdefault(
                        (parts[0], parts[2]), []
                    ).append(key)
            self._save()

    def get(self, artist: str, title: str, album: str = ""):
        with self._lock:
            return self._data.get(self._key(artist, title, album))

    def find_album(self, artist: str, album: str) -> list[dict]:
        """Return all entries for a given (artist, album) pair."""
        al = artist.lower().strip()
        alb = album.lower().strip()
        with self._lock:
            keys = self._artist_album_index.get((al, alb), [])
            return [self._data[k] for k in keys if k in self._data]

    def remove(self, artist: str, title: str, album: str):
        with self._lock:
            key = self._key(artist, title, album)
            if key in self._data:
                parts = key.split("\t")
                self._index_remove_key(
                    self._artist_album_index, (parts[0], parts[2]), key
                )
                del self._data[key]
                self._save()

    def remove_album_entries(self, triples: list) -> int:
        """Remove entries by exact (artist, title, album) triples in a single save."""
        removed = 0
        with self._lock:
            for artist, title, album in triples:
                key = self._key(artist, title, album)
                if key in self._data:
                    parts = key.split("\t")
                    self._index_remove_key(
                        self._artist_album_index, (parts[0], parts[2]), key
                    )
                    del self._data[key]
                    removed += 1
            if removed:
                self._save()
        return removed

    def remove_album(self, artist: str, album: str) -> int:
        """Remove every entry of one album, resolving keys under a single lock."""
        aa = (artist.lower().strip(), album.lower().strip())
        with self._lock:
            keys = [k for k in self._artist_album_index.get(aa, []) if k in self._data]
            for k in keys:
                del self._data[k]
            self._artist_album_index.pop(aa, None)
            if keys:
                self._save()
            return len(keys)

    def remove_artist(self, artist: str) -> int:
        artist_lower = artist.lower().strip()
        with self._lock:
            aa_pairs = [aa for aa in self._artist_album_index if aa[0] == artist_lower]
            keys = [
                k
                for aa in aa_pairs
                for k in self._artist_album_index[aa]
                if k in self._data
            ]
            for k in keys:
                del self._data[k]
            for aa in aa_pairs:
                del self._artist_album_index[aa]
            if keys:
                self._save()
            return len(keys)

    def reload(self):
        """Re-read the catalog file if it has changed on disk since last load/save."""
        with self._lock:
            try:
                mtime = self._path.stat().st_mtime_ns
            except OSError:
                return
            if mtime <= self._file_mtime:
                return
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                data = _entries_or_raise(raw)
            except Exception as exc:
                _log.warning(
                    "Catalog reload failed (%s) — keeping existing in-memory data",
                    exc,
                )
                return
            for old_key in [k for k in data if k.count("\t") == 1]:
                entry = data.pop(old_key)
                album_lower = (entry.get("album") or "").lower().strip()
                data[f"{old_key}\t{album_lower}"] = entry
            self._data = data
            self._rebuild_index()
            self._file_mtime = mtime

    def find_by_artist(self, artist: str) -> list[dict]:
        """Return all entries for a given artist."""
        al = artist.lower().strip()
        with self._lock:
            result = []
            for (a, _), keys in self._artist_album_index.items():
                if a == al:
                    result.extend(self._data[k] for k in keys if k in self._data)
            return result

    def all_artist_album_pairs(self) -> set[tuple[str, str]]:
        """Return a set of (artist_lower, album_lower) pairs across all entries."""
        with self._lock:
            return set(self._artist_album_index.keys())

    def all_entries(self) -> list[dict]:
        with self._lock:
            return list(self._data.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
