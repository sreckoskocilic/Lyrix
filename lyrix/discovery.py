import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

_log = logging.getLogger(__name__)

__version__ = "1.6.0"
_DEFAULT_UA = f"Lyrix/{__version__} ( https://github.com/sreckoskocilic/Lyrix )"
_MB_BASE = "https://musicbrainz.org/ws/2"
_PAGE = 100

_DEMO_MARKERS = frozenset({"demo", "demos"})


def _is_studio(rg: dict) -> bool:
    if rg.get("primary-type") != "Album":
        return False
    if rg.get("secondary-types"):
        return False
    title_words = {w.lower() for w in (rg.get("title") or "").split()}
    return not (title_words & _DEMO_MARKERS)


def _get_json(
    url: str, user_agent: str, timeout: int = 20, retries: int = 2, backoff: float = 1.0
) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            _log.warning("Request failed (attempt %d): %s", attempt + 1, exc)
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
    raise last_exc


def _resolve_artist(artist: str, user_agent: str):
    q = urllib.parse.quote(artist)
    url = f"{_MB_BASE}/artist?query={q}&fmt=json&limit=1"
    artists = _get_json(url, user_agent).get("artists") or []
    if not artists:
        return None, None
    top = artists[0]
    return top.get("id"), top.get("name")


def studio_albums(artist: str, user_agent: str | None = None, is_cancelled=None):
    ua = user_agent or _DEFAULT_UA
    mbid, name = _resolve_artist(artist, ua)
    if not mbid:
        return artist, []

    _log.info("MusicBrainz: %s -> %s (%s)", artist, name, mbid)
    albums: list[dict] = []
    seen: set = set()
    offset = 0
    while True:
        if is_cancelled and is_cancelled():
            break
        url = (
            f"{_MB_BASE}/release-group?artist={mbid}"
            f"&type=album&fmt=json&limit={_PAGE}&offset={offset}"
        )
        data = _get_json(url, ua)
        groups = data.get("release-groups") or []
        for rg in groups:
            if not _is_studio(rg):
                continue
            title = (rg.get("title") or "").strip()
            key = title.lower()
            if not title or key in seen:
                continue
            seen.add(key)
            albums.append(
                {"title": title, "year": (rg.get("first-release-date") or "")[:4]}
            )
        offset += _PAGE
        if not groups or offset >= data.get("release-group-count", 0):
            break

    albums.sort(key=lambda a: a["year"] or "9999")
    return name or artist, albums
