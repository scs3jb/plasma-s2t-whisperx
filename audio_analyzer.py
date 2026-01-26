import wave
from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, QIODevice
from PyQt6.QtMultimedia import QAudioSource, QAudioFormat, QMediaDevices

class AudioAnalyzer(QObject):
    levelChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = 0.0
        self._is_recording = False
        self._wav_file = None
        
        self.format = QAudioFormat()
        self.format.setSampleRate(16000) # WhisperX prefers 16kHz
        self.format.setChannelCount(1)
        self.format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        self.audio_source = QAudioSource(QMediaDevices.defaultAudioInput(), self.format)
        self.io_device = None

    @pyqtProperty(float, notify=levelChanged)
    def level(self):
        return self._level

    def start_recording(self, file_path):
        self._wav_file = wave.open(file_path, 'wb')
        self._wav_file.setnchannels(1)
        self._wav_file.setsampwidth(2) # 16-bit
        self._wav_file.setframerate(16000)
        
        self.io_device = self.audio_source.start()
        self.io_device.readyRead.connect(self._read_data)
        self._is_recording = True

    def stop_recording(self):
        if self._is_recording:
            self.audio_source.stop()
            self._is_recording = False
            if self._wav_file:
                self._wav_file.close()
                self._wav_file = None

    def _read_data(self):
        qbyte_array = self.io_device.readAll()
        if not qbyte_array.isEmpty():
            data = qbyte_array.data()
            if self._is_recording and self._wav_file:
                self._wav_file.writeframes(data)
            
            # Simple peak level calculation
            import struct
            count = len(data) // 2
            if count > 0:
                shorts = struct.unpack(f"<{count}h", data)
                max_val = max(abs(s) for s in shorts)
                self._level = max_val / 32768.0
                self.levelChanged.emit(self._level)