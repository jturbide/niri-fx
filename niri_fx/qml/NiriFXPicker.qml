// SPDX-License-Identifier: MIT
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Pane {
    id: root

    required property NiriFXController controller

    padding: 24
    palette.window: "#11171c"
    palette.base: "#1b262d"
    palette.alternateBase: "#24343d"
    palette.button: "#25353e"
    palette.buttonText: "#e5edea"
    palette.text: "#e5edea"
    palette.placeholderText: "#a2b3bb"
    palette.windowText: "#e5edea"
    palette.highlight: "#b7e8db"
    palette.highlightedText: "#102820"
    palette.mid: "#40515a"
    font.pixelSize: 14

    FileDialog {
        id: fileDialog

        title: "Load a NiriFX style or profile"
        nameFilters: ["NiriFX JSON (*.json)"]
        onAccepted: root.controller.loadUrl(selectedFile)
    }

    Shortcut {
        sequence: "Ctrl+F"
        onActivated: search.forceActiveFocus()
    }

    Shortcut {
        sequence: "Ctrl+O"
        enabled: !root.controller.busy
        onActivated: fileDialog.open()
    }

    Shortcut {
        sequence: "Ctrl+R"
        onActivated: root.controller.review()
    }

    Shortcut {
        sequence: "Ctrl+Return"
        onActivated: root.controller.apply()
    }

    Shortcut {
        // Leave Ctrl+Z available for editing the search field.
        sequence: "Ctrl+Alt+U"
        onActivated: root.controller.undo()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            spacing: 14

            Grid {
                columns: 2
                spacing: 4
                Layout.preferredWidth: 42
                Layout.preferredHeight: 42

                Repeater {
                    model: ["#b7e8db", "#d6c5ef", "#739b92", "#b7e8db"]

                    Rectangle {
                        required property string modelData

                        width: 19
                        height: 19
                        radius: 3
                        color: modelData
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Label {
                    text: "NiriFX Picker"
                    font.pixelSize: 26
                    font.weight: Font.DemiBold
                }

                Label {
                    text: "Choose a style. Review the changes. Make it yours."
                    color: "#a2b3bb"
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }

            Item {
                Layout.fillWidth: true
            }

            Button {
                text: "Load JSON"
                objectName: "load"
                enabled: !root.controller.busy
                onClicked: fileDialog.open()
            }

            Button {
                text: "Refresh"
                enabled: !root.controller.busy
                onClicked: root.controller.reload()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 22

            ColumnLayout {
                Layout.preferredWidth: 260
                Layout.maximumWidth: 310
                Layout.fillHeight: true
                spacing: 10

                TextField {
                    id: search

                    objectName: "search"
                    Layout.fillWidth: true
                    placeholderText: "Search styles or families…"
                    text: root.controller.query
                    onTextEdited: root.controller.query = text
                    onAccepted: {
                        if (root.controller.items.length)
                            root.controller.select(root.controller.items[0].id);
                    }
                    Component.onCompleted: forceActiveFocus()
                }

                ComboBox {
                    Layout.fillWidth: true
                    model: root.controller.families.map(name => {
                        return name ? root.controller.title(name) : "All families";
                    })
                    currentIndex: root.controller.families.indexOf(root.controller.family)
                    onActivated: root.controller.family = root.controller.families[currentIndex]
                }

                Label {
                    text: root.controller.items.length + " results"
                    color: "#a2b3bb"
                }

                ListView {
                    id: list

                    objectName: "styles"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 6
                    model: root.controller.items

                    ScrollBar.vertical: ScrollBar {}

                    delegate: ItemDelegate {
                        id: row

                        required property var modelData

                        width: ListView.view.width
                        height: 62
                        enabled: !root.controller.busy
                        highlighted: root.controller.selectedPreset === modelData.id || (!root.controller.selectedPreset && modelData.id === "custom")
                        onClicked: root.controller.select(modelData.id)

                        contentItem: Column {
                            spacing: 5

                            Label {
                                text: row.modelData.name
                                textFormat: Text.PlainText
                                font.weight: Font.DemiBold
                                color: row.highlighted ? "#102820" : "#e5edea"
                            }

                            Label {
                                text: row.modelData.comment
                                color: row.highlighted ? "#244639" : "#a2b3bb"
                                font.pixelSize: 12
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                color: "#2d3b44"
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: availableWidth

                ColumnLayout {
                    width: parent.width
                    spacing: 16

                    Label {
                        text: root.controller.selectedPreset ? "BUILT-IN STYLE" : "CUSTOM JSON"
                        color: "#b7e8db"
                        font.pixelSize: 12
                        font.letterSpacing: 1.6
                    }

                    Label {
                        text: root.controller.selectedName
                        textFormat: Text.PlainText
                        font.pixelSize: 30
                        font.weight: Font.DemiBold
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }

                    Label {
                        text: root.controller.selectedPreset ? "Tune the look in Studio, or apply its current settings here." : root.controller.displayPath(root.controller.customPath)
                        textFormat: Text.PlainText
                        color: "#a2b3bb"
                        wrapMode: Text.WrapAnywhere
                        Layout.fillWidth: true
                    }

                    GridLayout {
                        columns: 2
                        columnSpacing: 28
                        rowSpacing: 10

                        Label {
                            text: "Opening"
                            color: "#a2b3bb"
                        }

                        Label {
                            text: root.controller.actions.open ? root.controller.title(root.controller.actions.open.family) + " · " + root.controller.actions.open.open_ms + " ms" : "—"
                        }

                        Label {
                            text: "Closing"
                            color: "#a2b3bb"
                        }

                        Label {
                            text: root.controller.actions.close ? root.controller.title(root.controller.actions.close.family) + " · " + root.controller.actions.close.close_ms + " ms" : "—"
                        }

                        Label {
                            text: "Resize"
                            color: "#a2b3bb"
                        }

                        Label {
                            text: root.controller.changesResize ? root.controller.title(root.controller.actions.resize.family) + " · explicit override" : "Keep existing behavior"
                            color: root.controller.changesResize ? "#d6c5ef" : "#b7e8db"
                        }
                    }

                    CheckBox {
                        objectName: "resize-consent"
                        visible: root.controller.changesResize
                        text: "Allow this selection to change resize effects"
                        checked: root.controller.allowResize
                        onToggled: root.controller.allowResize = checked
                    }

                    Label {
                        visible: !!root.controller.actions.movement
                        text: "This file also contains experimental movement settings. This picker applies its stock Niri actions only."
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                        color: "#a2b3bb"
                    }

                    RowLayout {
                        Button {
                            text: "Preview in Studio"
                            objectName: "studio"
                            enabled: !root.controller.busy && !!root.controller.selectedDocument
                            onClicked: root.controller.openStudio()
                        }

                        Button {
                            text: "Review changes"
                            objectName: "review"
                            enabled: !root.controller.busy && !!root.controller.selectedDocument
                            onClicked: root.controller.review()
                        }
                    }

                    Label {
                        text: "Applies to standalone Niri"
                        font.weight: Font.DemiBold
                    }

                    Label {
                        text: root.controller.displayPath(root.controller.configPath)
                        textFormat: Text.PlainText
                        wrapMode: Text.WrapAnywhere
                        color: "#a2b3bb"
                        Layout.fillWidth: true
                    }

                    Label {
                        text: "The managed include overrides earlier open/close effects. Use one animation picker at a time."
                        wrapMode: Text.Wrap
                        color: "#a2b3bb"
                        Layout.fillWidth: true
                    }

                    Frame {
                        visible: !!root.controller.reviewPlan
                        Layout.fillWidth: true

                        ColumnLayout {
                            anchors.fill: parent

                            Label {
                                text: "Reviewed changes"
                                font.weight: Font.DemiBold
                            }

                            Repeater {
                                model: root.controller.reviewPlan ? root.controller.reviewPlan.changes : []

                                Label {
                                    required property var modelData

                                    text: root.controller.title(modelData.action) + " · " + root.controller.displayPath(modelData.path)
                                    textFormat: Text.PlainText
                                    wrapMode: Text.WrapAnywhere
                                    Layout.fillWidth: true
                                    color: "#a2b3bb"
                                }
                            }

                            Label {
                                visible: root.controller.reviewPlan ? root.controller.reviewPlan.changes.length === 0 : false
                                text: "Already matches this selection."
                            }
                        }
                    }

                    Button {
                        text: "Apply reviewed changes"
                        objectName: "apply"
                        highlighted: true
                        enabled: root.controller.canApply
                        onClicked: root.controller.apply()
                    }

                    Label {
                        text: root.controller.status
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                        color: "#b7e8db"
                    }

                    Label {
                        visible: !!root.controller.error
                        text: root.controller.error
                        textFormat: Text.PlainText
                        wrapMode: Text.WrapAnywhere
                        Layout.fillWidth: true
                        color: "#f3b6c5"
                    }

                    BusyIndicator {
                        running: root.controller.busy
                        visible: running
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: "#2d3b44"
        }

        RowLayout {
            Button {
                text: "Undo last change"
                objectName: "undo"
                enabled: !root.controller.busy && !!root.controller.undoTransaction
                onClicked: root.controller.undo()
            }

            Label {
                text: root.controller.undoStatus
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                color: "#a2b3bb"
            }

            Label {
                text: "Resize stays opt-in"
                color: "#d6c5ef"
            }
        }
    }

    background: Rectangle {
        color: root.palette.window
    }
}
