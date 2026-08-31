import QtQuick

Rectangle {
    id: button

    property string label: ""
    property bool primary: false

    signal activated

    implicitWidth: caption.implicitWidth + 20
    implicitHeight: 24
    color: Theme.sunk
    border.width: 1
    border.color: primary ? Theme.accent : Theme.line_strong
    opacity: enabled ? (hover.hovered ? 0.8 : 1.0) : 0.35

    Text {
        id: caption

        anchors.centerIn: parent
        text: button.label
        color: button.primary ? Theme.accent : (hover.hovered ? Theme.text : Theme.dim)
        font.family: FontFamily
        font.pixelSize: Metrics.ui - 2
    }

    HoverHandler {
        id: hover

        enabled: button.enabled
        cursorShape: Qt.PointingHandCursor
    }

    TapHandler {
        enabled: button.enabled
        onTapped: button.activated()
    }
}
