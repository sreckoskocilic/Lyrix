import QtQuick

Item {
    id: menu

    property var items: []
    property int rowHeight: Metrics.ui + 11

    signal triggered(string action)

    anchors.fill: parent
    visible: false
    z: 100

    function popup(px, py, list) {
        menu.items = list;
        var w = Math.min(px, menu.width - box.width - 4);
        var h = Math.min(py, menu.height - box.height - 4);
        box.x = Math.max(4, w);
        box.y = Math.max(4, h);
        menu.visible = true;
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onPressed: menu.visible = false
    }

    Rectangle {
        id: box

        width: 210
        height: column.implicitHeight + 8
        color: Theme.panel
        border.width: 1
        border.color: Theme.line_strong

        Column {
            id: column

            anchors.fill: parent
            anchors.margins: 4

            Repeater {
                model: menu.items

                Item {
                    required property int index
                    required property var modelData

                    width: column.width
                    height: modelData.separator === true ? 5 : menu.rowHeight

                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 6
                        height: 1
                        visible: parent.modelData.separator === true
                        color: Theme.line
                    }

                    Rectangle {
                        anchors.fill: parent
                        visible: parent.modelData.separator !== true && hover.hovered
                        color: Theme.select
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 9
                        anchors.verticalCenter: parent.verticalCenter
                        visible: parent.modelData.separator !== true
                        text: parent.modelData.label === undefined ? "" : parent.modelData.label
                        color: Theme.text
                        font.family: FontFamily
                        font.pixelSize: Metrics.ui - 1
                    }

                    HoverHandler {
                        id: hover

                        enabled: parent.modelData.separator !== true
                        cursorShape: Qt.PointingHandCursor
                    }

                    TapHandler {
                        enabled: parent.modelData.separator !== true
                        onTapped: {
                            menu.visible = false;
                            menu.triggered(parent.modelData.action);
                        }
                    }
                }
            }
        }
    }
}
