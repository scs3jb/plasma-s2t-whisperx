import struct
import numpy as np
from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, QIODevice
from PyQt6.QtMultimedia import QAudioSource, QAudioFormat, QMediaDevices

class AudioAnalyzer(QObject):
    levelChanged = pyqtSignal(float)
    audioDataReady = pyqtSignal(object)  # Emits numpy array

    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = 0.0
        self._is_recording = False
        
        self.format = QAudioFormat()
        self.format.setSampleRate(16000) # WhisperX prefers 16kHz
        self.format.setChannelCount(1)
        self.format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        self.audio_source = QAudioSource(QMediaDevices.defaultAudioInput(), self.format)
        self.io_device = None

    @pyqtProperty(float, notify=levelChanged)
    def level(self):
        return self._level

    def start_recording(self):
        self.io_device = self.audio_source.start()
        self.io_device.readyRead.connect(self._read_data)
        self._is_recording = True

    def stop_recording(self):
        if self._is_recording:
            self.audio_source.stop()
            self._is_recording = False

    def _read_data(self):
        qbyte_array = self.io_device.readAll()
        if not qbyte_array.isEmpty():
            data = qbyte_array.data()
            
            # Convert to numpy array (Int16 -> Float32)
            # count = len(data) // 2
            # shorts = struct.unpack(f"<{count}h", data)
            
            # Faster numpy conversion
            audio_chunk = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # DEBUG: Print max amplitude occasionally
            # if np.max(np.abs(audio_chunk)) > 0.1:
            #    print(".", end="", flush=True)

            if self._is_recording:
                self.audioDataReady.emit(audio_chunk)
            
            # Peak level for UI
            if len(audio_chunk) > 0:
                self._level = float(np.max(np.abs(audio_chunk)))
                self.levelChanged.emit(self._level)