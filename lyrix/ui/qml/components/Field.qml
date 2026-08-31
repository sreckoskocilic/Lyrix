import QtQuick

Rectangle {
    id: field

    property alias text: input.text
    property alias input: input
    property string placeholder: ""

    signal accepted

    implicitHeight: Metrics.ui + 11
    color: Theme.sunk
    border.width: 1
    border.color: input.activeFocus ? Theme.line_strong : Theme.line

    TextInput {
        id: input

        anchors.fill: parent
        anchors.leftMargin: 7
        anchors.rightMargin: 7
        verticalAlignment: TextInput.AlignVCenter
        color: Theme.text
        selectionColor: Theme.select
        selectedTextColor: Theme.text
        selectByMouse: true
        clip: true
        font.family: FontFamily
        font.pixelSize: Metrics.ui - 1
        onAccepted: field.accepted()
    }

    Text {
        anchors.left: parent.left
        anchors.leftMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        visible: input.text === "" && !input.activeFocus
        text: field.placeholder
        color: Theme.faint
        font.family: FontFamily
        font.pixelSize: Metrics.ui - 1
    }
}
