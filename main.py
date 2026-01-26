import sys
import os

# Suppress Qt warnings
os.environ["QT_LOGGING_RULES"] = "qt.core.qfuture.continuations=false"

import subprocess
import threading
from PyQt6.QtGui import QGuiApplication, QWindow
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QIODevice, Qt, QTimer
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from audio_analyzer import AudioAnalyzer

class Controller(QObject):
    statusChanged = pyqtSignal(str)
# ... (rest of class unchanged, I need to match context for replace)
    finished = pyqtSignal()

    def __init__(self, engine, analyzer):
        super().__init__()
        self.engine = engine
        self.analyzer = analyzer
        self.is_recording = False
        self.is_processing = False
        self.audio_path = "/tmp/whisper_recording.wav"
        self.transcript_dir = "/tmp/whisper_transcript"
        
    @pyqtSlot()
    def toggle_recording(self):
        if self.is_processing:
            return

        root = self.engine.rootObjects()[0]
        
        if not self.is_recording:
            # Start recording
            print("Starting recording...")
            if os.path.exists(self.audio_path):
                os.remove(self.audio_path)
            
            self.analyzer.start_recording(self.audio_path)
            self.is_recording = True
            root.setProperty("recording", True)
            self.statusChanged.emit("Recording...")
        else:
            # Stop recording and start transcription
            print("Stopping recording, starting transcription...")
            self.analyzer.stop_recording()
            self.is_recording = False
            self.is_processing = True
            root.setProperty("recording", False)
            self.statusChanged.emit("Transcribing...")
            
            # Run transcription in a separate thread
            threading.Thread(target=self.run_transcription, daemon=True).start()

    def run_transcription(self):
        try:
            if not os.path.exists(self.transcript_dir):
                os.makedirs(self.transcript_dir, exist_ok=True)
            
            # WhisperX command
            cmd = [
                "uvx", "--quiet", "whisperx", self.audio_path,
                "--model", "base",
                "--language", "en",
                "--device", "cpu",
                "--compute_type", "int8",
                "--output_dir", self.transcript_dir,
                "--output_format", "txt",
                "--batch_size", "8",
                "--beam_size", "3",
                "--best_of", "3",
                "--temperature", "0.1",
                "--no_align",
                "--suppress_numerals",
                "--threads", "10",
                "--print_progress", "False"
            ]
            
            env = os.environ.copy()
            env["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "true"
            env["PYTHONWARNINGS"] = "ignore"
            
            subprocess.run(cmd, env=env, check=True, capture_output=True)
            
            # Find the transcript file (WhisperX names it after the input file)
            txt_path = os.path.join(self.transcript_dir, "whisper_recording.txt")
            if os.path.exists(txt_path):
                with open(txt_path, "r") as f:
                    text = f.read().strip()
                
                if text:
                    print(f"Typing: {text}")
                    subprocess.run(["/usr/bin/ydotool", "type", text])
            
            # Cleanup
            if os.path.exists(self.audio_path):
                os.remove(self.audio_path)
            if os.path.exists(txt_path):
                os.remove(txt_path)
                
        except Exception as e:
            print(f"Error during transcription: {e}")
        finally:
            self.is_processing = False
            self.finished.emit()

def main():
    app = QGuiApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    
    server_name = "plasma-s2t-whisperx-server"
    
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if socket.waitForConnected(500):
        socket.write(b"toggle")
        socket.waitForBytesWritten()
        socket.disconnectFromServer()
        sys.exit(0)
    
    server = QLocalServer()
    if not server.listen(server_name):
        QLocalServer.removeServer(server_name)
        server.listen(server_name)
    
    analyzer = AudioAnalyzer()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("audioAnalyzer", analyzer)
    
    engine.load(os.path.join(os.path.dirname(__file__), "ui.qml"))
    
    if not engine.rootObjects():
        sys.exit(-1)
        
    window = engine.rootObjects()[0]
    
    # Create a dummy parent window for ToolTip behavior on Wayland
    dummy_window = QWindow()
    dummy_window.setFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnBottomHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowDoesNotAcceptFocus)
    dummy_window.resize(1, 1)
    dummy_window.setPosition(-100, -100)
    dummy_window.setOpacity(0)
    dummy_window.setVisible(True)
    
    window.setTransientParent(dummy_window)
    
    # Force visibility
    window.setVisible(True)
    
    controller = Controller(engine, analyzer)
    engine.rootContext().setContextProperty("controller", controller)
    
    # Connect signals to QML
    root = engine.rootObjects()[0]
    controller.statusChanged.connect(lambda s: root.setProperty("statusText", s))
    controller.finished.connect(lambda: root.setProperty("finishedProcessing", True))

    def handle_new_connection():
        client_socket = server.nextPendingConnection()
        if client_socket.waitForReadyRead(500):
            msg = client_socket.readAll().data().decode()
            if msg == "toggle":
                controller.toggle_recording()
        client_socket.disconnectFromServer()

    server.newConnection.connect(handle_new_connection)
    
    # Start recording immediately
    controller.toggle_recording()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()