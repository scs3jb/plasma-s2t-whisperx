import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: root
    width: 350
    height: 120
    visible: true
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput | Qt.Tool
    color: "transparent"
    opacity: 0

    property real audioLevel: audioAnalyzer.level
    property bool recording: false
    property string statusText: "Recording..."
    property bool finishedProcessing: false

    onRecordingChanged: {
        if (!recording) {
            // We wait for finishedProcessing to fade out
        } else {
            opacity = 1
        }
    }

    onFinishedProcessingChanged: {
        if (finishedProcessing) {
            opacity = 0
            timer.start()
        }
    }

    // Position in the bottom center of the screen
    Component.onCompleted: {
        x = (Screen.width - width) / 2
        y = Screen.height - height - 150
    }

    Rectangle {
        id: container
        anchors.fill: parent
        radius: 20
        color: Qt.rgba(0.1, 0.1, 0.1, 0.9)
        border.color: recording ? "#ff4444" : "#4444ff"
        border.width: 3

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 10

            // Microphone icon / button
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: 60
                height: 60
                radius: 30
                color: recording ? "#ff4444" : "#333333"
                
                Text {
                    anchors.centerIn: parent
                    text: "🎤"
                    font.pixelSize: 30
                }

                SequentialAnimation on scale {
                    running: recording
                    loops: Animation.Infinite
                    NumberAnimation { from: 1.0; to: 1.1; duration: 500; easing.type: Easing.InOutQuad }
                    NumberAnimation { from: 1.1; to: 1.0; duration: 500; easing.type: Easing.InOutQuad }
                }
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root.statusText
                color: "white"
                font.pixelSize: 12
                font.bold: true
                opacity: 0.8
            }

            // Simple Soundwave (Bars)
            Row {
                Layout.alignment: Qt.AlignHCenter
                spacing: 6
                height: 50
                
                Repeater {
                    model: 20
                    Rectangle {
                        id: bar
                        width: 6
                        // Smooth the height changes
                        property real targetHeight: 5 + (root.audioLevel * 45 * (1 - Math.abs(index - 9.5) / 10))
                        height: targetHeight
                        radius: 3
                        color: recording ? "#ff4444" : "#4444ff"
                        anchors.verticalCenter: parent.verticalCenter
                        
                        Behavior on height {
                            NumberAnimation { 
                                duration: 80
                                easing.type: Easing.OutQuad
                            }
                        }
                    }
                }
            }
        }
    }

    Behavior on opacity {
        NumberAnimation { duration: 300 }
    }

    Timer {
        id: timer
        interval: 350
        onTriggered: Qt.quit()
    }
}
