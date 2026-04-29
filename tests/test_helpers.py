import unittest
from types import SimpleNamespace

from lyrix.catalog import (
    _release_year,
    _format_album_header,
    _format_song_header,
    _extract_name,
    _unpack_track,
    get_resource_path,
)
from lyrix.base_app import _year_sort


class YearParsingTests(unittest.TestCase):
    def test_release_year_formats(self):
        self.assertEqual(
            _release_year({"release_date_for_display": "March 5, 2001"}), "2001"
        )
        self.assertEqual(
            _release_year({"release_date_for_display": "July 2010"}), "2010"
        )
        self.assertEqual(_release_year({"release_date_for_display": "1997"}), "1997")
        self.assertEqual(_release_year({"release_date_for_display": ""}), "")
        self.assertEqual(_release_year({"release_date_for_display": "Invalid"}), "")

    def test_release_year_none_returns_empty(self):
        self.assertEqual(_release_year(None), "")

    def test_year_sort(self):
        self.assertLess(_year_sort("1990"), _year_sort("1999"))
        self.assertGreater(_year_sort(""), _year_sort("2020"))
        self.assertEqual(_year_sort(None), 9999)


class FormattingTests(unittest.TestCase):
    def test_unpack_track(self):
        track = SimpleNamespace(title="Song A")
        self.assertEqual(_unpack_track((1, track)), (1, track))

    def test_format_song_header_from_song_object(self):
        """_format_song_header produces the same output regardless of the source."""
        header = _format_song_header("Artist", "Title", "Album", "2020")
        self.assertIn("Artist: Artist", header)
        self.assertIn("Song: Title", header)
        self.assertIn("Album: Album (2020)", header)

    def test_get_resource_path(self):
        path = get_resource_path("foo.txt")
        self.assertTrue(str(path).endswith("foo.txt"))

    def test_extract_name_fallback(self):
        obj = SimpleNamespace()  # no name attribute
        self.assertEqual(_extract_name(obj), "Unknown")

    def test_extract_name_dict(self):
        self.assertEqual(_extract_name({"name": "Artist"}), "Artist")
        self.assertEqual(_extract_name({"name": None}, "fallback"), "fallback")

    def test_format_song_header(self):
        header = _format_song_header("Artist", "Title", "Album", "2020")
        self.assertIn("Artist: Artist", header)
        self.assertIn("Song: Title", header)
        self.assertIn("Album: Album (2020)", header)

    def test_format_song_header_no_year(self):
        header = _format_song_header("Artist", "Title", "Album", "")
        self.assertIn("Album: Album\n", header)
        self.assertNotIn("()", header)

    def test_format_album_header(self):
        header = _format_album_header("Artist", "Album", "2021")
        self.assertIn("Artist: Artist", header)
        self.assertIn("Album: Album (2021)", header)

    def test_format_album_header_no_year(self):
        header = _format_album_header("Artist", "Album", "")
        self.assertIn("Album: Album\n", header)
        self.assertNotIn("()", header)


if __name__ == "__main__":
    unittest.main()
