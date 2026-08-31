import unittest
from types import SimpleNamespace

from lyrix.catalog import (
    _extract_name,
    _release_year,
    _year_sort,
    get_resource_path,
)


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

    def test_rdc_dict_with_year(self):
        album = {"release_date_components": {"year": 1994}}
        self.assertEqual(_release_year(album), "1994")

    def test_rdc_dict_with_no_year(self):
        album = {"release_date_components": {}, "release_date_for_display": "2001"}
        self.assertEqual(_release_year(album), "2001")

    def test_rdc_object_with_year(self):
        rdc = SimpleNamespace(year=2001)
        album = SimpleNamespace(
            release_date_components=rdc, release_date_for_display=""
        )
        self.assertEqual(_release_year(album), "2001")

    def test_rdc_object_with_no_year(self):
        rdc = SimpleNamespace(year=None)
        album = SimpleNamespace(
            release_date_components=rdc, release_date_for_display="January 01, 2005"
        )
        self.assertEqual(_release_year(album), "2005")

    def test_year_sort(self):
        self.assertLess(_year_sort("1990"), _year_sort("1999"))
        self.assertGreater(_year_sort(""), _year_sort("2020"))
        self.assertEqual(_year_sort(None), 9999)

    def test_year_sort_non_numeric_sorts_last(self):
        self.assertEqual(_year_sort("nineteen"), 9999)


class FormattingTests(unittest.TestCase):
    def test_get_resource_path(self):
        path = get_resource_path("foo.txt")
        self.assertTrue(str(path).endswith("foo.txt"))

    def test_extract_name_fallback(self):
        obj = SimpleNamespace()  # no name attribute
        self.assertEqual(_extract_name(obj), "Unknown")

    def test_extract_name_dict(self):
        self.assertEqual(_extract_name({"name": "Artist"}), "Artist")
        self.assertEqual(_extract_name({"name": None}, "fallback"), "fallback")

if __name__ == "__main__":
    unittest.main()
