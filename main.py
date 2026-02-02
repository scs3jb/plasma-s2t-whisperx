import sys
import os

# CRITICAL: Fix for PyTorch 2.6+ loading older checkpoints (WhisperX/Pyannote)
# Must be set before torch is imported anywhere
os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"

import argparse
import time
import queue
import threading
import numpy as np
import warnings

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Suppress Qt warnings
os.environ["QT_LOGGING_RULES"] = "qt.core.qfuture.continuations=false"

import subprocess
from PyQt6.QtGui import QGuiApplication, QWindow
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, pyqtProperty, Qt, QThread
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from audio_analyzer import AudioAnalyzer

class TranscriberThread(QThread):
    statusUpdate = pyqtSignal(str)
    # textReady removed, we type directly
    
    def __init__(self, profile, device="cpu"):
        super().__init__()
        self.profile = profile
        self.device = device
        self.queue = queue.Queue()
        self.running = True
        self.model = None

    def run(self):
        try:
            import whisperx
        except ImportError:
            self.statusUpdate.emit("Error: whisperx not found")
            return

        self.statusUpdate.emit("Loading Model...")
        
        models = {
            "ultrafast": "tiny", "fast": "tiny",
            "balanced": "base",
            "accurate": "small", "high_accuracy": "large-v2"
        }
        model_size = models.get(self.profile, "base")
        
        try:
            self.model = whisperx.load_model(
                model_size, 
                self.device, 
                compute_type="int8",
                language="en"
            )
            print("Model loaded successfully")
            self.statusUpdate.emit("Idle")
        except Exception as e:
            print(f"Model Load Error: {e}")
            self.statusUpdate.emit(f"Load Error: {e}")
            return

        while self.running:
            try:
                # Wait for audio task
                task = self.queue.get()
                if task is None: # Sentinel to stop
                    break
                
                audio_data, notify = task
                
                if notify:
                    self.statusUpdate.emit("Transcribing...")
                
                print(f"Processing buffer: {len(audio_data)} samples")
                
                try:
                    result = self.model.transcribe(audio_data, batch_size=1)
                    text = ""
                    for segment in result["segments"]:
                        text += segment["text"] + " "
                    
                    text = text.strip()
                    if text:
                        print(f"Transcribed: '{text}'")
                        # Type directly in this thread to avoid blocking Main Thread
                        subprocess.run(["ydotool", "type", text + " "])
                    
                    if notify:
                        self.statusUpdate.emit("Listening...")
                        
                except Exception as e:
                    print(f"Inference Error: {e}")
                
            except Exception as e:
                print(f"Transcriber Loop Error: {e}")

    def submit(self, audio_data, notify=False):
        self.queue.put((audio_data, notify))
        
    def stop(self):
        self.running = False
        self.queue.put(None)
        self.wait()

class AudioProcessor(QThread):
    # This thread handles VAD and buffering ONLY. Never blocks.
    
    def __init__(self, transcriber):
        super().__init__()
        self.transcriber = transcriber
        self.audio_queue = queue.Queue()
        self.running = True
        self.buffer = np.array([], dtype=np.float32)
        
        # VAD parameters
        self.silence_threshold = 0.002
        self.silence_duration = 1.0
        self.max_duration = 15.0
        
        self.last_speech_time = time.time()
        self.is_speaking = False

    def run(self):
        while self.running:
            try:
                try:
                    chunk = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Check for special commands
                if isinstance(chunk, str) and chunk == "FORCE":
                    self.flush_buffer(notify=True)
                    continue

                self.buffer = np.concatenate((self.buffer, chunk))
                
                # VAD Logic
                energy = np.mean(np.abs(chunk))
                current_time = time.time()
                
                if energy > self.silence_threshold:
                    if not self.is_speaking:
                        self.is_speaking = True
                    self.last_speech_time = current_time
                
                buffer_duration = len(self.buffer) / 16000.0
                time_since_speech = current_time - self.last_speech_time
                
                should_transcribe = False
                
                if self.is_speaking and time_since_speech > self.silence_duration and buffer_duration > 0.5:
                    print(f"VAD: Silence detected ({time_since_speech:.2f}s)")
                    should_transcribe = True
                    self.is_speaking = False
                    
                if buffer_duration > self.max_duration:
                    print("VAD: Max duration reached")
                    should_transcribe = True
                    self.is_speaking = False
                    
                if should_transcribe:
                    self.flush_buffer(notify=False)
                    
            except Exception as e:
                print(f"AudioProcessor Error: {e}")

    def flush_buffer(self, notify=False):
        if len(self.buffer) < 4000:
            if notify:
                # Need to reset UI if forced stop on empty buffer
                self.transcriber.statusUpdate.emit("Listening...") 
            self.buffer = np.array([], dtype=np.float32)
            return

        # Copy and submit to transcriber
        self.transcriber.submit(self.buffer.copy(), notify=notify)
        self.buffer = np.array([], dtype=np.float32)

    def add_audio(self, chunk):
        self.audio_queue.put(chunk)
        
    def force_transcribe(self):
        self.audio_queue.put("FORCE")
        
    def stop(self):
        self.running = False
        self.wait()

class Controller(QObject):
    statusChanged = pyqtSignal(str)
    finished = pyqtSignal()
    transcribingChanged = pyqtSignal(bool)

    def __init__(self, engine, analyzer, profile="balanced"):
        super().__init__()
        self.engine = engine
        self.analyzer = analyzer
        self.is_recording = False
        self._transcribing = False
        
        # Connect analyzer to us
        self.analyzer.audioDataReady.connect(self.handle_audio)
        
        # Start Threads
        self.transcriber = TranscriberThread(profile)
        self.processor = AudioProcessor(self.transcriber)
        
        self.transcriber.statusUpdate.connect(self.handle_worker_status)
        
        self.transcriber.start()
        self.processor.start()
        
    @pyqtProperty(bool, notify=transcribingChanged)
    def transcribing(self):
        return self._transcribing

    def _set_transcribing(self, val):
        if self._transcribing != val:
            self._transcribing = val
            self.transcribingChanged.emit(val)

    def handle_worker_status(self, status):
        # We only want to show "Transcribing..." (Blue UI) if we are NOT recording (Manual Stop).
        # If we are recording (VAD), we should keep the UI Red ("Listening...") to be transparent.
        
        real_status = status
        
        if status == "Transcribing...":
            if self.is_recording:
                # VAD Mode: Hide "Transcribing...", pretend we are still Listening
                self._set_transcribing(False)
                real_status = "Listening..."
            else:
                # Manual Mode: Show "Transcribing..."
                self._set_transcribing(True)
                real_status = "Transcribing..."
        else:
            # Not transcribing (e.g. "Listening...", "Idle", "Loading...")
            self._set_transcribing(False)
            
            # Fix up mismatching states
            if status == "Idle" and self.is_recording:
                real_status = "Listening..."
            elif status == "Listening..." and not self.is_recording:
                real_status = "Idle"
            else:
                real_status = status
                
        self.statusChanged.emit(real_status)

    @pyqtSlot()
    def toggle_recording(self):
        root = self.engine.rootObjects()[0]
        
        if not self.is_recording:
            # Start recording
            print("Starting recording...")
            self.analyzer.start_recording()
            self.is_recording = True
            root.setProperty("recording", True)
            self._set_transcribing(False) 
            self.statusChanged.emit("Listening...")
        else:
            # Stop recording
            print("Stopping recording...")
            self.analyzer.stop_recording()
            self.is_recording = False
            root.setProperty("recording", False)
            
            # Show Transcribing immediately
            self._set_transcribing(True)
            self.statusChanged.emit("Transcribing...")
            
            # Force transcribe remaining buffer
            self.processor.force_transcribe()

    def handle_audio(self, chunk):
        if self.is_recording:
            self.processor.add_audio(chunk)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="balanced", help="Transcription profile")
    args, unknown = parser.parse_known_args()
    
    app = QGuiApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    
    server_name = "plasma-s2t-whisperx-server"
    
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if socket.waitForConnected(500):
        if args.profile == "quit":
            socket.write(b"quit")
        else:
            socket.write(b"toggle")
        socket.waitForBytesWritten()
        socket.disconnectFromServer()
        sys.exit(0)
    
    # If we are here, we are starting the server.
    # If the user intended to quit, but it wasn't running, just exit.
    if args.profile == "quit":
        print("Application is not running.")
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
    
    controller = Controller(engine, analyzer, args.profile)
    engine.rootContext().setContextProperty("controller", controller)
    
    # Connect signals to QML
    root = engine.rootObjects()[0]
    controller.statusChanged.connect(lambda s: root.setProperty("statusText", s))
    
    # Initial state
    controller.statusChanged.emit("Idle")

    def handle_new_connection():
        client_socket = server.nextPendingConnection()
        if client_socket.waitForReadyRead(500):
            msg = client_socket.readAll().data().decode()
            if msg == "toggle":
                controller.toggle_recording()
            elif msg == "quit":
                QGuiApplication.quit()
        client_socket.disconnectFromServer()

    server.newConnection.connect(handle_new_connection)
    
    # Start recording immediately
    controller.toggle_recording()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()