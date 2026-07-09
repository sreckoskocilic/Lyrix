import json
import unittest
import urllib.error
from unittest import mock

from lyrix import discovery


class IsStudioTests(unittest.TestCase):
    def test_plain_album_is_studio(self):
        self.assertTrue(
            discovery._is_studio({"primary-type": "Album", "title": "In Absentia"})
        )

    def test_non_album_primary_type_rejected(self):
        self.assertFalse(
            discovery._is_studio({"primary-type": "Single", "title": "Trains"})
        )

    def test_secondary_types_rejected(self):
        self.assertFalse(
            discovery._is_studio(
                {
                    "primary-type": "Album",
                    "secondary-types": ["Live"],
                    "title": "Octane Twisted",
                }
            )
        )

    def test_demo_title_rejected(self):
        self.assertFalse(
            discovery._is_studio(
                {"primary-type": "Album", "title": "Stupid Dream Demos 1998/1999"}
            )
        )

    def test_missing_title_treated_as_studio(self):
        self.assertTrue(discovery._is_studio({"primary-type": "Album"}))


class GetJsonTests(unittest.TestCase):
    def _resp(self, payload):
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps(payload).encode("utf-8")
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        return resp

    def test_decodes_json_with_user_agent(self):
        payload = {"hello": "world"}
        with mock.patch.object(
            discovery.urllib.request, "urlopen", return_value=self._resp(payload)
        ) as op:
            out = discovery._get_json("http://x", "UA/1.0")
        self.assertEqual(out, payload)
        req = op.call_args[0][0]
        self.assertEqual(req.headers["User-agent"], "UA/1.0")

    def test_retries_then_succeeds(self):
        payload = {"ok": True}
        with (
            mock.patch.object(discovery.time, "sleep") as slept,
            mock.patch.object(
                discovery.urllib.request,
                "urlopen",
                side_effect=[TimeoutError("slow"), self._resp(payload)],
            ),
        ):
            out = discovery._get_json("http://x", "UA", backoff=0)
        self.assertEqual(out, payload)
        slept.assert_called_once()

    def test_raises_after_exhausting_retries(self):
        with (
            mock.patch.object(discovery.time, "sleep"),
            mock.patch.object(
                discovery.urllib.request,
                "urlopen",
                side_effect=urllib.error.URLError("down"),
            ),
        ):
            with self.assertRaises(urllib.error.URLError):
                discovery._get_json("http://x", "UA", retries=1, backoff=0)


class ResolveArtistTests(unittest.TestCase):
    def test_no_match_returns_none(self):
        with mock.patch.object(discovery, "_get_json", return_value={"artists": []}):
            self.assertEqual(discovery._resolve_artist("Nobody", "UA"), (None, None))


class StudioAlbumsTests(unittest.TestCase):
    def _rg(self, title, date="", **extra):
        return {
            "primary-type": "Album",
            "title": title,
            "first-release-date": date,
            **extra,
        }

    def test_no_artist_returns_input_and_empty(self):
        with mock.patch.object(discovery, "_get_json", return_value={"artists": []}):
            name, albums = discovery.studio_albums("Ghost Band")
        self.assertEqual(name, "Ghost Band")
        self.assertEqual(albums, [])

    def test_filters_dedups_and_sorts(self):
        pages = [
            {"artists": [{"id": "MBID", "name": "Porcupine Tree"}]},
            {
                "release-group-count": 4,
                "release-groups": [
                    self._rg("Deadwing", "2005-03-25"),
                    self._rg("Signify", "1996-09-30"),
                    self._rg("Signify", "1996-09-30"),  # duplicate title
                    self._rg("", "2000-01-01"),  # empty title skipped
                    {"primary-type": "Live", "title": "Octane Twisted"},  # filtered
                ],
            },
        ]
        with mock.patch.object(discovery, "_get_json", side_effect=pages):
            name, albums = discovery.studio_albums(
                "porcupine tree", user_agent="UA/1.0"
            )
        self.assertEqual(name, "Porcupine Tree")
        self.assertEqual(
            albums,
            [
                {"title": "Signify", "year": "1996"},
                {"title": "Deadwing", "year": "2005"},
            ],
        )

    def test_pagination_stops_on_empty_page(self):
        pages = [
            {"artists": [{"id": "MBID", "name": "Band"}]},
            {"release-group-count": 300, "release-groups": [self._rg("First", "1990")]},
            {"release-group-count": 300, "release-groups": []},  # empty -> break
        ]
        with mock.patch.object(discovery, "_get_json", side_effect=pages):
            name, albums = discovery.studio_albums("Band")
        self.assertEqual([a["title"] for a in albums], ["First"])

    def test_cancelled_before_fetch(self):
        pages = [{"artists": [{"id": "MBID", "name": "Band"}]}]
        with mock.patch.object(discovery, "_get_json", side_effect=pages):
            name, albums = discovery.studio_albums("Band", is_cancelled=lambda: True)
        self.assertEqual(albums, [])

    def test_missing_canonical_name_falls_back_to_input(self):
        pages = [
            {"artists": [{"id": "MBID"}]},  # no name
            {"release-group-count": 1, "release-groups": [self._rg("Only", "2001")]},
        ]
        with mock.patch.object(discovery, "_get_json", side_effect=pages):
            name, albums = discovery.studio_albums("typedname")
        self.assertEqual(name, "typedname")
        self.assertEqual([a["title"] for a in albums], ["Only"])


if __name__ == "__main__":
    unittest.main()
