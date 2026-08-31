import json
import os
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lyrix.catalog import Catalog


class CatalogTests(unittest.TestCase):
    def test_add_get_remove(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add("A", "Song", "Album", "2020", "lyrics", track=1)
            self.assertEqual(len(cat), 1)
            entry = cat.get("A", "Song", "Album")
            self.assertIsNotNone(entry)
            self.assertEqual(entry["track"], 1)
            cat.remove("A", "Song", "Album")
            self.assertEqual(len(cat), 0)

    def test_add_to_new_album_removes_old_entry(self):
        """Simulates the update-song flow: when album changes, old entry must be removed."""
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add("A", "Song", "OldAlbum", "2020", "lyrics")
            self.assertEqual(len(cat), 1)

            # Simulate what browser_actions does: remove old, add with new album
            cat.remove("A", "Song", "OldAlbum")
            cat.add("A", "Song", "NewAlbum", "2021", "updated")
            self.assertEqual(len(cat), 1)
            self.assertIsNone(cat.get("A", "Song", "OldAlbum"))
            entry = cat.get("A", "Song", "NewAlbum")
            self.assertIsNotNone(entry)
            self.assertEqual(entry["album"], "NewAlbum")

    def test_remove_artist(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add("Artist", "One", "Album", "", "lyrics")
            cat.add("Artist", "Two", "Album", "", "lyrics")
            removed = cat.remove_artist("Artist")
            self.assertEqual(removed, 2)
            self.assertEqual(len(cat), 0)

    def test_remove_artist_ignores_unindexed_data(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add("Artist", "One", "Album", "", "lyrics")
            # Inject a malformed key directly into _data (bypasses the index)
            cat._data["malformed"] = {
                "artist": "Artist",
                "title": "Bad",
                "album": "",
                "year": "",
                "track": 0,
                "lyrics": "",
                "added": "",
            }
            # Should not raise; only the indexed entry is removed — the unindexed
            # malformed key is invisible to the index-based remove_artist.
            removed = cat.remove_artist("Artist")
            self.assertEqual(removed, 1)
            self.assertIn("malformed", cat._data)

    def test_thread_safety_under_parallel_adds(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)

            def add_batch(offset):
                for i in range(50):
                    idx = offset + i
                    cat.add("Artist", f"Song {idx}", "Album", "", f"lyrics {idx}")

            threads = [
                threading.Thread(target=add_batch, args=(50 * t,)) for t in range(10)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(len(cat), 500)

    def test_load_handles_bad_json(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat_path.write_text("{bad json")
            cat = Catalog(cat_path)
            self.assertEqual(len(cat), 0)

    def test_load_reads_existing_entries(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat_path.write_text(
                json.dumps(
                    {
                        "entries": {
                            "a\tb\t": {
                                "artist": "A",
                                "title": "B",
                                "album": "",
                                "lyrics": "x",
                                "year": "",
                                "track": 0,
                                "added": "2024-01-01T00:00:00",
                            }
                        }
                    }
                )
            )
            cat = Catalog(cat_path)
            self.assertEqual(len(cat), 1)
            self.assertIsNotNone(cat.get("A", "B", ""))

    def test_add_many_indexes_new_entries(self):
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            cat.add_many(
                [
                    {"artist": "A", "title": "One", "album": "Album", "lyrics": "x"},
                    {"artist": "A", "title": "Two", "album": "Album", "lyrics": "y"},
                ]
            )
            self.assertEqual(len(cat.find_album("A", "Album")), 2)
            self.assertEqual(len(cat.find_by_artist("A")), 2)

    def test_add_many_empty_list_is_noop(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add_many([])
            self.assertEqual(len(cat), 0)

    def test_save_cleans_up_on_failure(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add("A", "Song", "Album", "", "lyrics")

            with patch.object(Path, "write_text", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    cat._save()

    def test_load_corrupt_copy_oserror_is_swallowed(self):
        """OSError when writing the .corrupt backup must not propagate."""
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat_path.write_text("{bad json")
            with patch.object(Path, "write_bytes", side_effect=OSError("disk full")):
                cat = Catalog(cat_path)
            self.assertEqual(len(cat), 0)

    def test_reload_picks_up_external_changes(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add("A", "Song", "Album", "2020", "lyrics")

            # Simulate another process writing a new entry directly to the file
            data = json.loads(cat_path.read_text())
            data["entries"][Catalog._key("B", "Other")] = {
                "artist": "B",
                "title": "Other",
                "album": "",
                "year": "",
                "track": 0,
                "lyrics": "x",
                "added": "2024-01-01T00:00:00",
            }
            cat_path.write_text(json.dumps(data))

            self.assertEqual(len(cat), 1)  # stale before reload
            cat.reload()
            self.assertEqual(len(cat), 2)  # picks up new entry

    def test_reload_keeps_data_on_parse_error(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add("A", "Song", "Album", "", "lyrics")

            cat_path.write_text("{bad json")
            cat.reload()
            self.assertEqual(len(cat), 1)  # in-memory data preserved

    def test_reload_noop_when_file_missing(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add("A", "Song", "Album", "", "lyrics")

            cat_path.unlink()
            cat.reload()
            self.assertEqual(len(cat), 1)  # in-memory data preserved

    def test_reload_migrates_old_two_tab_keys(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add("A", "Song", "Album", "2020", "lyrics")

            # Simulate external process writing old 2-tab format
            data = json.loads(cat_path.read_text())
            data["entries"]["b\tother"] = {
                "artist": "B",
                "title": "Other",
                "album": "Disc",
                "year": "",
                "track": 0,
                "lyrics": "x",
                "added": "2024-01-01T00:00:00",
            }
            cat_path.write_text(json.dumps(data))

            cat.reload()
            self.assertEqual(len(cat), 2)
            entry = cat.get("B", "Other", "Disc")
            self.assertIsNotNone(entry)
            self.assertEqual(entry["lyrics"], "x")

    def test_reload_skips_when_mtime_unchanged(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add("A", "Song", "Album", "2020", "lyrics")

            # Tamper with the file without changing mtime
            original_mtime = cat_path.stat().st_mtime_ns
            data = json.loads(cat_path.read_text())
            data["entries"][Catalog._key("B", "Other")] = {
                "artist": "B",
                "title": "Other",
                "album": "",
                "year": "",
                "track": 0,
                "lyrics": "x",
                "added": "2024-01-01T00:00:00",
            }
            cat_path.write_text(json.dumps(data))
            # Restore original mtime so reload skips
            os.utime(cat_path, ns=(original_mtime, original_mtime))

            cat.reload()
            self.assertEqual(len(cat), 1)  # reload was skipped

    def test_reload_skips_when_in_memory_newer_than_disk(self):
        """reload() does not overwrite in-memory state when _file_mtime is ahead of disk mtime."""
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add("A", "Song", "Album", "2020", "lyrics")
            # Bump _file_mtime past what is on disk (simulates a concurrent _save())
            cat._file_mtime = cat_path.stat().st_mtime_ns + 1_000_000_000
            cat.reload()
            self.assertEqual(len(cat), 1)  # stale disk version not applied

    def test_add_preserves_added_timestamp_on_update(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add("A", "Song", "Album", "2020", "original lyrics")
            original_added = cat.get("A", "Song", "Album")["added"]

            cat.add("A", "Song", "Album", "2020", "updated lyrics")
            self.assertEqual(cat.get("A", "Song", "Album")["added"], original_added)
            self.assertEqual(cat.get("A", "Song", "Album")["lyrics"], "updated lyrics")

    def test_add_many_preserves_added_timestamp_on_update(self):
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat = Catalog(cat_path)
            cat.add("A", "Song", "Album", "2020", "original lyrics")
            original_added = cat.get("A", "Song", "Album")["added"]

            cat.add_many(
                [
                    {
                        "artist": "A",
                        "title": "Song",
                        "album": "Album",
                        "year": "2020",
                        "lyrics": "updated lyrics",
                        "track": 0,
                    }
                ]
            )
            self.assertEqual(cat.get("A", "Song", "Album")["added"], original_added)
            self.assertEqual(cat.get("A", "Song", "Album")["lyrics"], "updated lyrics")

    def test_same_song_different_albums_are_separate_entries(self):
        """Same (artist, title) under two albums must be stored as independent entries."""
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            cat.add(
                "Suffocation", "Infecting the Crypts", "Human Waste", "1991", "lyrics A"
            )
            cat.add(
                "Suffocation",
                "Infecting the Crypts",
                "Effigy of the Forgotten",
                "1991",
                "lyrics B",
            )
            self.assertEqual(len(cat), 2)
            a = cat.get("Suffocation", "Infecting the Crypts", "Human Waste")
            b = cat.get(
                "Suffocation", "Infecting the Crypts", "Effigy of the Forgotten"
            )
            self.assertEqual(a["lyrics"], "lyrics A")
            self.assertEqual(b["lyrics"], "lyrics B")

    def test_get_exact_album_only(self):
        """get must match exactly by (artist, title, album) — no cross-album fallback."""
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            cat.add("Artist", "Song", "Album X", "", "lyrics")
            self.assertIsNotNone(cat.get("Artist", "Song", "Album X"))
            self.assertIsNone(cat.get("Artist", "Song", "Album Y"))
            self.assertIsNone(cat.get("Artist", "Song"))

    def test_remove_album_entries_does_not_touch_other_albums(self):
        """remove_album_entries must only delete the exact (artist, title, album) triple."""
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            cat.add(
                "Suffocation", "Infecting the Crypts", "Human Waste", "1991", "lyrics A"
            )
            cat.add(
                "Suffocation",
                "Infecting the Crypts",
                "Effigy of the Forgotten",
                "1991",
                "lyrics B",
            )
            removed = cat.remove_album_entries(
                [("Suffocation", "Infecting the Crypts", "Human Waste")]
            )
            self.assertEqual(removed, 1)
            self.assertEqual(len(cat), 1)
            # Effigy entry must still exist
            entry = cat.get(
                "Suffocation", "Infecting the Crypts", "Effigy of the Forgotten"
            )
            self.assertIsNotNone(entry)
            self.assertEqual(entry["lyrics"], "lyrics B")

    def test_migration_two_tab_keys(self):
        """Old 2-tab keys (artist\\ttitle) must be migrated to 3-tab keys on load."""
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": {
                            "artist\tsong": {
                                "artist": "Artist",
                                "title": "Song",
                                "album": "My Album",
                                "year": "2000",
                                "track": 0,
                                "lyrics": "old lyrics",
                                "added": "2024-01-01T00:00:00",
                            }
                        },
                    }
                )
            )
            cat = Catalog(cat_path)
            # Entry should be accessible and key migrated to 3-tab form
            entry = cat.get("Artist", "Song", "My Album")
            self.assertIsNotNone(entry)
            self.assertEqual(entry["lyrics"], "old lyrics")

    def test_load_already_migrated_keys(self):
        """Keys already in 3-tab format must be preserved as-is (no double migration)."""
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            key = Catalog._key("Artist", "Song", "Album")
            cat_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": {
                            key: {
                                "artist": "Artist",
                                "title": "Song",
                                "album": "Album",
                                "year": "2000",
                                "track": 0,
                                "lyrics": "lyrics",
                                "added": "2024-01-01T00:00:00",
                            }
                        },
                    }
                )
            )
            cat = Catalog(cat_path)
            self.assertEqual(len(cat), 1)
            entry = cat.get("Artist", "Song", "Album")
            self.assertIsNotNone(entry)

    def test_migration_save_failure_preserves_data(self):
        """If _save() fails during migration, data stays loaded in memory."""
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            cat_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": {
                            "artist\tsong": {
                                "artist": "Artist",
                                "title": "Song",
                                "album": "My Album",
                                "year": "2000",
                                "track": 0,
                                "lyrics": "lyrics",
                                "added": "2024-01-01T00:00:00",
                            }
                        },
                    }
                )
            )
            with patch.object(Catalog, "_save", side_effect=OSError("disk full")):
                cat = Catalog(cat_path)
            self.assertEqual(len(cat), 1)
            entry = cat.get("Artist", "Song", "My Album")
            self.assertIsNotNone(entry)

    def test_remove_with_album_specific(self):
        """remove(artist, title, album) must delete only the exact album variant."""
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            cat.add("Artist", "Song", "Album A", "", "lyrics A")
            cat.add("Artist", "Song", "Album B", "", "lyrics B")
            cat.remove("Artist", "Song", "Album A")
            self.assertEqual(len(cat), 1)
            # Album B entry must survive
            remaining = cat.get("Artist", "Song", "Album B")
            self.assertIsNotNone(remaining)
            self.assertEqual(remaining["album"], "Album B")

    def test_all_entries_returns_all(self):
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            cat.add("A", "One", "Album", "", "lyrics1")
            cat.add("B", "Two", "Album", "", "lyrics2")
            entries = cat.all_entries()
            self.assertEqual(len(entries), 2)
            self.assertEqual({e["title"] for e in entries}, {"One", "Two"})

    def test_index_remove_key_missing_lookup_is_noop(self):
        """_index_remove_key does nothing when the lookup key is absent."""
        index: dict = {}
        Catalog._index_remove_key(index, ("x", "y"), "some_key")
        self.assertEqual(index, {})

    def test_index_remove_key_absent_entry_is_noop(self):
        """_index_remove_key does nothing when the entry key is not in the list."""
        index: dict = {("x", "y"): ["other_key"]}
        Catalog._index_remove_key(index, ("x", "y"), "missing_key")
        self.assertEqual(index, {("x", "y"): ["other_key"]})

    def test_find_album_returns_all_entries(self):
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            cat.add("Artist", "One", "Album", "2020", "lyrics1")
            cat.add("Artist", "Two", "Album", "2020", "lyrics2")
            cat.add("Artist", "Three", "Other", "2020", "lyrics3")
            results = cat.find_album("Artist", "Album")
            self.assertEqual(len(results), 2)
            self.assertEqual({e["title"] for e in results}, {"One", "Two"})

    def test_find_album_case_insensitive(self):
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            cat.add("Artist", "Song", "Album", "", "lyrics")
            results = cat.find_album("artist", "album")
            self.assertEqual(len(results), 1)

    def test_find_album_empty_when_not_found(self):
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            cat.add("Artist", "Song", "Album", "", "lyrics")
            results = cat.find_album("Other", "Album")
            self.assertEqual(len(results), 0)

    def test_find_by_artist(self):
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            cat.add("Artist A", "Song 1", "Album 1", "2020", "lyrics1")
            cat.add("Artist A", "Song 2", "Album 1", "2020", "lyrics2")
            cat.add("Artist B", "Song 3", "Album 2", "2021", "lyrics3")
            results = cat.find_by_artist("Artist A")
            self.assertEqual(len(results), 2)
            titles = {e["title"] for e in results}
            self.assertEqual(titles, {"Song 1", "Song 2"})

    def test_find_by_artist_case_insensitive(self):
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            cat.add("Artist A", "Song 1", "Album 1", "2020", "lyrics")
            results = cat.find_by_artist("artist a")
            self.assertEqual(len(results), 1)

    def test_find_by_artist_not_found(self):
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            cat.add("Artist A", "Song 1", "Album", "2020", "lyrics")
            self.assertEqual(cat.find_by_artist("Unknown"), [])

    def test_all_artist_album_pairs(self):
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            cat.add("Artist A", "Song 1", "Album 1", "2020", "lyrics1")
            cat.add("Artist A", "Song 2", "Album 2", "2021", "lyrics2")
            cat.add("Artist B", "Song 3", "Album 1", "2020", "lyrics3")
            pairs = cat.all_artist_album_pairs()
            self.assertIn(("artist a", "album 1"), pairs)
            self.assertIn(("artist a", "album 2"), pairs)
            self.assertIn(("artist b", "album 1"), pairs)
            self.assertEqual(len(pairs), 3)

    def test_all_artist_album_pairs_empty(self):
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            self.assertEqual(cat.all_artist_album_pairs(), set())

    def test_load_stat_oserror_is_swallowed(self):
        """OSError on stat() after loading the catalog file must not propagate."""
        with TemporaryDirectory() as tmp:
            cat_path = Path(tmp) / "catalog.json"
            key = Catalog._key("A", "Song", "Album")
            cat_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": {
                            key: {
                                "artist": "A",
                                "title": "Song",
                                "album": "Album",
                                "year": "",
                                "track": 0,
                                "lyrics": "x",
                                "added": "2024-01-01T00:00:00",
                            },
                        },
                    }
                )
            )
            with patch.object(Path, "stat", side_effect=OSError("no stat")):
                cat = Catalog(cat_path)
            self.assertEqual(len(cat), 1)

    def test_save_stat_oserror_is_swallowed(self):
        """OSError on stat() after writing the catalog file must not propagate."""
        with TemporaryDirectory() as tmp:
            cat = Catalog(Path(tmp) / "catalog.json")
            with patch.object(Path, "stat", side_effect=OSError("no stat")):
                cat._save()  # must not raise


if __name__ == "__main__":
    unittest.main()
