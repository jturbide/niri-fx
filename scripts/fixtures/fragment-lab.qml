// SPDX-License-Identifier: MIT
// Synthetic preview only. Selection requests go to the owning demo process;
// this UI never writes compositor configuration or connects to the host session.
import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
    id: root

    property var state: ({
        "name": "Loading",
        "preset": "",
        "particles": 0,
        "description": "",
        "hint": ""
    })

    function choose(name) {
        console.log("NIRIFX_PRESET " + name);
    }

    FileView {
        id: stateFile

        path: Quickshell.env("NIRIFX_DEMO_STATE")
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                root.state = JSON.parse(text());
            } catch (error) {
                console.warn("Could not read owned preview state: " + error);
            }
        }
    }

    FloatingWindow {
        id: window

        readonly property color accent: Quickshell.env("NIRIFX_COLOR")
        readonly property string label: Quickshell.env("NIRIFX_LABEL")
        property int clicks: 0

        title: "NiriFX Fragment Lab / " + label + " / " + root.state.name + " / clicks " + clicks
        implicitWidth: 500
        implicitHeight: 720
        color: "#182735"

        Shortcut {
            sequence: "Alt+1"
            onActivated: root.choose("gentle")
        }

        Shortcut {
            sequence: "Alt+2"
            onActivated: root.choose("tear")
        }

        Shortcut {
            sequence: "Alt+3"
            onActivated: root.choose("cascade")
        }

        Shortcut {
            sequence: "Alt+0"
            onActivated: root.choose("off")
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: 10
            radius: 22
            color: window.accent

            Rectangle {
                x: 14
                y: 14
                width: parent.width - 28
                height: 56
                radius: 14
                color: "#182735"

                Text {
                    anchors.centerIn: parent
                    text: root.state.name + "  ·  hold, then pull down"
                    color: window.accent
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                }

                MouseArea {
                    anchors.fill: parent
                    onPressed: window.startSystemMove()
                }

            }

            Column {
                x: 22
                y: 92
                width: parent.width - 44
                spacing: 18

                Row {
                    spacing: 6

                    Repeater {
                        model: [{
                            "key": "gentle",
                            "label": "Gentle · 1"
                        }, {
                            "key": "tear",
                            "label": "Tear · 2"
                        }, {
                            "key": "cascade",
                            "label": "Cascade · 3"
                        }, {
                            "key": "off",
                            "label": "Off · 0"
                        }]

                        Rectangle {
                            required property var modelData

                            width: (window.width - 82) / 4
                            height: 38
                            radius: 10
                            color: root.state.preset === modelData.key ? "#182735" : "#f6f8fc"

                            Text {
                                anchors.centerIn: parent
                                text: parent.modelData.label
                                color: root.state.preset === parent.modelData.key ? window.accent : "#182735"
                                font.pixelSize: 13
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.choose(parent.modelData.key)
                            }

                        }

                    }

                }

                Text {
                    width: parent.width
                    text: root.state.description
                    wrapMode: Text.WordWrap
                    color: "#182735"
                    font.pixelSize: 18
                }

                Text {
                    width: parent.width
                    text: root.state.particles ? root.state.particles + " particles · drag, pause, reverse, release" : "Effects disabled in this preview"
                    wrapMode: Text.WordWrap
                    color: "#415260"
                    font.pixelSize: 14
                }

                Repeater {
                    model: 3

                    Rectangle {
                        required property int index

                        width: parent.width
                        height: 45
                        radius: 9
                        color: "#f6f8fc"

                        Rectangle {
                            x: 15
                            y: 20
                            width: parent.width * (0.75 - parent.index * 0.16)
                            height: 5
                            radius: 3
                            color: "#b1bac8"
                        }

                    }

                }

                Text {
                    width: parent.width
                    text: "Alt+F: float · Alt+←/→: reorder · Alt+Q: exit\n" + root.state.hint
                    wrapMode: Text.WordWrap
                    color: "#415260"
                    font.pixelSize: 13
                }

            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 28
                height: 44
                radius: 12
                color: "#182735"

                Text {
                    anchors.centerIn: parent
                    text: window.clicks ? "Input received · " + window.clicks : "Click to check input"
                    color: window.accent
                    font.pixelSize: 14
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: window.clicks++
                }

            }

        }

    }

}
