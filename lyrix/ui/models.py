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


def _key(row: Node) -> tuple[object, ...]:
    return (row["kind"], row["artist"], row["album"], row["title"])


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
        # Expanding or collapsing a node inserts or removes one contiguous
        # block, so replace only the rows between the common head and tail.
        # A full reset would throw the view back to the top.
        old = self._rows
        limit = min(len(old), len(rows))
        head = 0
        while head < limit and _key(old[head]) == _key(rows[head]):
            head += 1
        tail = 0
        while tail < limit - head and _key(old[-1 - tail]) == _key(rows[-1 - tail]):
            tail += 1
        if len(old) - tail > head:
            self.beginRemoveRows(NO_PARENT, head, len(old) - tail - 1)
            self._rows = old[:head] + old[len(old) - tail :]
            self.endRemoveRows()
        if len(rows) - tail > head:
            self.beginInsertRows(NO_PARENT, head, len(rows) - tail - 1)
            self._rows = rows
            self.endInsertRows()
        self._rows = rows
        # Kept rows can still change: the toggled node's arrow, counts, years.
        for i in [*range(head), *range(len(rows) - tail, len(rows))]:
            j = i if i < head else i - len(rows) + len(old)
            if old[j] != rows[i]:
                self.dataChanged.emit(self.index(i), self.index(i))

    def row_at(self, index: int) -> Node | None:
        return self._rows[index] if 0 <= index < len(self._rows) else None

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
