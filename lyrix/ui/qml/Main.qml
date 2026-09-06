import QtQuick
import QtQuick.Dialogs
import "components"

Window {
    id: root

    property string counts: ""
    property string status: ""
    property bool busy: false
    property bool geniusOk: false
    property bool editing: false
    property var song: ({
        empty: true,
        title: "",
        lyrics: "",
        html: ""
    })
    property int currentIndex: -1
    property real sashPos: Metrics.sidebar

    width: Metrics.windowWidth
    height: Metrics.windowHeight
    minimumWidth: Metrics.minWidth
    minimumHeight: Metrics.minHeight
    visible: true
    title: root.song.empty ? "Lyrics Browser" : root.song.title + " — Lyrics Browser"
    color: Theme.ground

    Component.onCompleted: {
        var g = WindowState.geometry();
        if (g.width !== undefined) {
            root.width = g.width;
            root.height = g.height;
            root.x = g.x;
            root.y = g.y;
        }
        var s = WindowState.sash();
        if (s > 0)
            root.sashPos = s;
        Controller.start();
    }

    onClosing: {
        WindowState.save_geometry(root.width, root.height, root.x, root.y);
        WindowState.save_sash(root.sashPos);
    }

    Connections {
        target: Controller

        function onCountsChanged(text) {
            root.counts = text;
        }

        function onStatusChanged(text) {
            root.status = text;
        }

        function onBusyChanged(running) {
            root.busy = running;
        }

        function onGeniusReady(ok) {
            root.geniusOk = ok;
        }

        function onCurrentIndexChanged(index) {
            root.currentIndex = index;
            // The list has no geometry yet on startup; centre once it is laid out.
            if (index >= 0)
                Qt.callLater(() => tree.positionViewAtIndex(index, ListView.Center));
        }

        function onEditingChanged(on) {
            root.editing = on;
            if (on) {
                lyrics.textFormat = TextEdit.PlainText;
                lyrics.text = root.song.lyrics;
                lyrics.forceActiveFocus();
            }
        }

        function onSongLoaded(payload) {
            root.song = payload;
            lyrics.textFormat = TextEdit.RichText;
            lyrics.text = payload.html;
        }

        function onErrorRaised(title, message) {
            errorDialog.title = title;
            errorDialog.text = message;
            errorDialog.open();
        }
    }

    MessageDialog {
        id: errorDialog

        buttons: MessageDialog.Ok
    }

    MessageDialog {
        id: confirmDialog

        title: "Remove"
        buttons: MessageDialog.Yes | MessageDialog.No
        onAccepted: {
            Controller.remove_confirmed();
        }
    }

    FileDialog {
        id: saveDialog

        fileMode: FileDialog.SaveFile
        defaultSuffix: "txt"
        nameFilters: ["Text files (*.txt)", "All files (*)"]
        onAccepted: Controller.save_lyrics_to(selectedFile)
    }

    Shortcut {
        sequence: "Ctrl+F"
        onActivated: filterField.input.forceActiveFocus()
    }

    Shortcut {
        sequences: ["Ctrl+=", "Ctrl++"]
        onActivated: Controller.change_lyrics_size(1)
    }

    Shortcut {
        sequence: "Ctrl+-"
        onActivated: Controller.change_lyrics_size(-1)
    }

    Shortcut {
        sequence: "Escape"
        onActivated: {
            if (root.editing)
                Controller.cancel_edit();
            else if (filterField.text !== "")
                filterField.text = "";
        }
    }

    // ── Top bar ───────────────────────────────────────────────────────────────

    Rectangle {
        id: topbar

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 34
        color: Theme.panel

        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: Theme.line
        }

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 11
            anchors.verticalCenter: parent.verticalCenter
            spacing: 12

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "LYRIX"
                color: Theme.accent
                font.family: FontFamily
                font.pixelSize: Metrics.ui - 3
                font.bold: true
                font.letterSpacing: 1.8
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: root.counts
                color: Theme.dim
                font.family: FontFamily
                font.pixelSize: Metrics.ui - 2
            }
        }
    }

    // ── Sidebar ───────────────────────────────────────────────────────────────

    Rectangle {
        id: sidebar

        anchors.top: topbar.bottom
        anchors.bottom: statusbar.top
        anchors.left: parent.left
        width: root.sashPos
        color: Theme.panel

        Column {
            id: searchForm

            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 8
            spacing: 4
            enabled: root.geniusOk && !root.busy
            opacity: enabled ? 1.0 : 0.4

            Row {
                width: parent.width
                spacing: 7

                Kicker {
                    width: 42
                    height: artistField.height
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                    text: "Artist"
                }

                Field {
                    id: artistField

                    width: parent.width - 49
                    onAccepted: Controller.search_song(artistField.text, songField.text)
                }
            }

            Row {
                width: parent.width
                spacing: 7

                Kicker {
                    width: 42
                    height: songField.height
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                    text: "Song"
                }

                Field {
                    id: songField

                    width: parent.width - 49
                    onAccepted: Controller.search_song(artistField.text, songField.text)
                }
            }

            Row {
                width: parent.width
                spacing: 7

                Kicker {
                    width: 42
                    height: albumField.height
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                    text: "Album"
                }

                Field {
                    id: albumField

                    width: parent.width - 49
                    onAccepted: Controller.search_album(artistField.text, albumField.text)
                }
            }

            Item {
                width: parent.width
                height: 3
            }

            Row {
                width: parent.width
                spacing: 4

                FlatButton {
                    width: (parent.width - 8) / 3
                    label: "Song"
                    primary: true
                    onActivated: Controller.search_song(artistField.text, songField.text)
                }

                FlatButton {
                    width: (parent.width - 8) / 3
                    label: "Album"
                    onActivated: Controller.search_album(artistField.text, albumField.text)
                }

                FlatButton {
                    width: (parent.width - 8) / 3
                    label: "Artist"
                    onActivated: Controller.search_artist(artistField.text)
                }
            }
        }

        Rectangle {
            id: formLine

            anchors.top: searchForm.bottom
            anchors.topMargin: 8
            width: parent.width
            height: 1
            color: Theme.line
        }

        Field {
            id: filterField

            anchors.top: formLine.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 8
            placeholder: "filter catalog…"
            onTextChanged: debounce.restart()
        }

        Timer {
            id: debounce

            interval: 300
            onTriggered: Controller.set_filter(filterField.text)
        }

        Rectangle {
            id: treeHeader

            anchors.top: filterField.bottom
            anchors.topMargin: 8
            anchors.left: parent.left
            anchors.right: parent.right
            height: 20
            color: Theme.sunk

            Rectangle {
                anchors.top: parent.top
                width: parent.width
                height: 1
                color: Theme.line
            }

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Theme.line
            }

            Kicker {
                anchors.left: parent.left
                anchors.leftMargin: 11
                anchors.verticalCenter: parent.verticalCenter
                text: "Catalog"
            }

            Kicker {
                anchors.right: parent.right
                anchors.rightMargin: 11
                anchors.verticalCenter: parent.verticalCenter
                text: "#"
            }
        }

        ListView {
            id: tree

            anchors.top: treeHeader.bottom
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: CatalogRows
            currentIndex: root.currentIndex
            highlightMoveDuration: 0
            focus: true

            Keys.onPressed: event => {
                if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) {
                    if (tree.count === 0)
                        return;
                    var step = event.key === Qt.Key_Down ? 1 : -1;
                    var next = Math.max(0, Math.min(tree.count - 1, root.currentIndex + step));
                    root.currentIndex = next;
                    Controller.click(next);
                    tree.positionViewAtIndex(next, ListView.Contain);
                    event.accepted = true;
                } else if (event.key === Qt.Key_Right) {
                    Controller.expand(root.currentIndex);
                    event.accepted = true;
                } else if (event.key === Qt.Key_Left) {
                    Controller.collapse(root.currentIndex);
                    event.accepted = true;
                } else if (event.text.length === 1 && event.text >= " " && !(event.modifiers & (Qt.ControlModifier | Qt.MetaModifier | Qt.AltModifier))) {
                    filterField.input.forceActiveFocus();
                    filterField.text += event.text;
                    event.accepted = true;
                }
            }

            Text {
                anchors.centerIn: parent
                width: parent.width - 40
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                visible: tree.count === 0
                text: filterField.text === "" ? "Katalog je prazan." : "Ništa ne odgovara filteru."
                color: Theme.faint
                font.family: FontFamily
                font.pixelSize: Metrics.ui - 1
            }

            delegate: Rectangle {
                id: node

                required property int index
                required property string kind
                required property int depth
                required property string name
                required property string meta
                required property string num
                required property bool expanded

                readonly property bool selected: root.currentIndex === index
                readonly property color tint: kind === "artist" ? Theme.artist : (kind === "album" ? Theme.album : Theme.song)

                width: tree.width
                height: Metrics.rowHeight
                color: selected ? Theme.select : (hover.hovered ? Theme.sunk : "transparent")

                HoverHandler {
                    id: hover
                }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: mouse => {
                        root.currentIndex = node.index;
                        tree.forceActiveFocus();
                        if (mouse.button === Qt.RightButton) {
                            var point = mapToItem(contextMenu, mouse.x, mouse.y);
                            contextMenu.popup(point.x, point.y, root.menuItems(node.kind));
                        } else {
                            Controller.click(node.index);
                        }
                    }
                    onDoubleClicked: Controller.toggle(node.index)
                }

                Row {
                    anchors.fill: parent
                    anchors.leftMargin: 11 + node.depth * 17
                    anchors.rightMargin: 11
                    spacing: 7

                    Text {
                        width: 9
                        height: parent.height
                        verticalAlignment: Text.AlignVCenter
                        visible: node.kind !== "song"
                        text: node.expanded ? "▾" : "▸"
                        color: Theme.faint
                        font.family: FontFamily
                        font.pixelSize: Metrics.ui - 4

                        TapHandler {
                            onTapped: Controller.toggle(node.index)
                        }
                    }

                    Text {
                        width: 20
                        height: parent.height
                        horizontalAlignment: Text.AlignRight
                        verticalAlignment: Text.AlignVCenter
                        visible: node.kind === "song"
                        text: node.num
                        color: Theme.faint
                        font.family: FontFamily
                        font.pixelSize: Metrics.ui - 3
                    }

                    Text {
                        width: parent.width - (node.kind === "song" ? 27 : 16) - metaText.width - 7
                        height: parent.height
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        text: node.name
                        color: node.tint
                        font.family: FontFamily
                        font.pixelSize: Metrics.ui
                        font.bold: node.kind === "artist"
                    }

                    Text {
                        id: metaText

                        height: parent.height
                        verticalAlignment: Text.AlignVCenter
                        textFormat: Text.PlainText  // keep the alignment padding
                        text: node.meta
                        color: Theme.faint
                        font.family: FontFamily
                        font.pixelSize: Metrics.ui - 3
                    }
                }
            }
        }
    }

    // ── Sash ──────────────────────────────────────────────────────────────────

    Rectangle {
        id: sash

        anchors.top: topbar.bottom
        anchors.bottom: statusbar.top
        anchors.left: sidebar.right
        width: 6
        color: dragArea.pressed ? Theme.accent : Theme.line

        MouseArea {
            id: dragArea

            property real grabX: 0
            property real grabPos: 0

            anchors.fill: parent
            cursorShape: Qt.SplitHCursor
            onPressed: mouse => {
                grabX = mapToItem(null, mouse.x, 0).x;
                grabPos = root.sashPos;
            }
            onPositionChanged: mouse => {
                var delta = mapToItem(null, mouse.x, 0).x - grabX;
                root.sashPos = Math.max(240, Math.min(root.width - 380, grabPos + delta));
            }
            onReleased: WindowState.save_sash(root.sashPos)
        }
    }

    // ── Lyrics ────────────────────────────────────────────────────────────────

    Item {
        id: viewer

        anchors.top: topbar.bottom
        anchors.bottom: statusbar.top
        anchors.left: sash.right
        anchors.right: parent.right

        Rectangle {
            id: header

            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 36
            color: Theme.panel

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Theme.line
            }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 15
                anchors.verticalCenter: parent.verticalCenter
                text: root.song.title
                color: Theme.accent
                font.family: FontFamily
                font.pixelSize: Metrics.lyrics
                font.bold: true
            }

            Row {
                id: actions

                anchors.right: parent.right
                anchors.rightMargin: 11
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4

                FlatButton {
                    label: root.editing ? "Save edit" : "Edit"
                    primary: root.editing
                    enabled: !root.song.empty && !root.busy
                    onActivated: {
                        if (root.editing)
                            Controller.save_edit(lyrics.text);
                        else
                            Controller.start_edit();
                    }
                }

                FlatButton {
                    label: "Copy"
                    enabled: !root.song.empty && !root.editing
                    onActivated: Controller.copy_lyrics()
                }

                FlatButton {
                    label: "Update"
                    enabled: root.geniusOk && !root.busy && root.currentIndex >= 0
                    onActivated: Controller.update_selected(root.currentIndex)
                }

                FlatButton {
                    label: "Save"
                    enabled: !root.song.empty && !root.editing
                    onActivated: saveDialog.open()
                }
            }
        }

        Flickable {
            id: scroller

            anchors.top: header.bottom
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            clip: true
            contentWidth: width
            contentHeight: lyrics.contentHeight + 38
            boundsBehavior: Flickable.StopAtBounds

            TextEdit {
                id: lyrics

                x: 18
                y: 14
                width: scroller.width - 36
                readOnly: !root.editing
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                textFormat: TextEdit.RichText
                color: Theme.text
                selectionColor: Theme.select
                selectedTextColor: Theme.text
                font.family: FontFamily
                font.pixelSize: Metrics.lyrics
            }
        }
    }

    // ── Status bar ────────────────────────────────────────────────────────────

    Rectangle {
        id: statusbar

        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: 22
        color: Theme.panel

        Rectangle {
            anchors.top: parent.top
            width: parent.width
            height: 1
            color: Theme.line
        }

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 11
            anchors.right: busyText.left
            anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            elide: Text.ElideRight
            text: root.status
            color: Theme.dim
            font.family: FontFamily
            font.pixelSize: Metrics.ui - 2
        }

        Text {
            id: busyText

            anchors.right: parent.right
            anchors.rightMargin: 11
            anchors.verticalCenter: parent.verticalCenter
            text: root.busy ? "working…" : ""
            color: Theme.accent
            font.family: FontFamily
            font.pixelSize: Metrics.ui - 2
        }
    }

    ContextMenu {
        id: contextMenu

        onTriggered: action => {
            if (action === "update")
                Controller.update_selected(root.currentIndex);
            else if (action === "remove") {
                var prompt = Controller.remove_prompt(root.currentIndex);
                if (prompt !== "") {
                    confirmDialog.text = prompt;
                    confirmDialog.open();
                }
            }
        }
    }

    function menuItems(kind) {
        var list = [];
        var live = root.geniusOk && !root.busy;
        if (kind === "artist") {
            if (live) {
                list.push({
                    "label": "Update Artist",
                    "action": "update"
                });
                list.push({
                    "separator": true
                });
            }
            list.push({
                "label": "Remove Artist",
                "action": "remove"
            });
        } else if (kind === "album") {
            if (live) {
                list.push({
                    "label": "Update Album",
                    "action": "update"
                });
                list.push({
                    "separator": true
                });
            }
            list.push({
                "label": "Remove Album",
                "action": "remove"
            });
        } else {
            if (live) {
                list.push({
                    "label": "Update Lyrics",
                    "action": "update"
                });
                list.push({
                    "separator": true
                });
            }
            list.push({
                "label": "Remove Song",
                "action": "remove"
            });
        }
        return list;
    }
}
