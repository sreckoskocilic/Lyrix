"""Flat list model backing the catalog tree.

Artists, albums and songs live in one list; `depth` and `kind` carry the
hierarchy, `expanded` says whether a node's children are present.
"""

from __future__ import annotations

from typing import override

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)

NO_PARENT = QModelIndex()

ROLES: tuple[str, ...] = (
    "kind",
    "depth",
    "name",
    "meta",
    "num",
    "expanded",
    "artist",
    "title",
    "album",
)

Node = dict[str, object]


class CatalogModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self._rows: list[Node] = []
        self._roles = {
            Qt.ItemDataRole.UserRole + 1 + i: name for i, name in enumerate(ROLES)
        }

    @override
    def roleNames(self) -> dict[int, QByteArray]:
        return {role: QByteArray(name.encode()) for role, name in self._roles.items()}

    @override
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = NO_PARENT) -> int:
        return 0 if parent.isValid() else len(self._rows)

    @override
    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = 0
    ) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        name = self._roles.get(role)
        return self._rows[index.row()].get(name) if name is not None else None

    def set_rows(self, rows: list[Node]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_at(self, index: int) -> Node | None:
        return self._rows[index] if 0 <= index < len(self._rows) else None

    def rows(self) -> list[Node]:
        return self._rows

    def index_of_song(self, artist: str, title: str, album: str) -> int:
        for i, row in enumerate(self._rows):
            if (
                row.get("kind") == "song"
                and row.get("artist") == artist
                and row.get("title") == title
                and row.get("album") == album
            ):
                return i
        return -1

    def first_song_index(self) -> int:
        for i, row in enumerate(self._rows):
            if row.get("kind") == "song":
                return i
        return -1
