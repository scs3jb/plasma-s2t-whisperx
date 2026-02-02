import unittest
import sys
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import pyqtSignal, QObject

# Mock dependencies before imports
sys.modules['PyQt6.QtMultimedia'] = MagicMock()
sys.modules['whisperx'] = MagicMock()
sys.modules['numpy'] = MagicMock()

class TestApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_analyzer_init(self):
        with patch('audio_analyzer.QAudioSource') as mock_source, \
             patch('audio_analyzer.QMediaDevices') as mock_devices:
            
            from audio_analyzer import AudioAnalyzer
            analyzer = AudioAnalyzer()
            self.assertIsNotNone(analyzer)
            self.assertEqual(analyzer.level, 0.0)
            
            mock_devices.defaultAudioInput.assert_called()
            mock_source.assert_called()

    def test_controller_logic(self):
        # We need to import Controller after mocking
        # But Controller imports AudioProcessor/TranscriberThread which imports whisperx (handled above)
        from main import Controller
        
        mock_engine = MagicMock()
        mock_root = MagicMock()
        mock_engine.rootObjects.return_value = [mock_root]
        
        # Mock Analyzer
        mock_analyzer = MagicMock()
        mock_analyzer.audioDataReady.connect = MagicMock()
        
        # Mock Threads
        with patch('main.TranscriberThread') as MockTranscriber, \
             patch('main.AudioProcessor') as MockProcessor:
            
            mock_transcriber_instance = MockTranscriber.return_value
            mock_transcriber_instance.statusUpdate = MagicMock()
            mock_transcriber_instance.textReady = MagicMock()
            
            mock_processor_instance = MockProcessor.return_value
            
            controller = Controller(mock_engine, mock_analyzer)
            
            # Verify threads started
            mock_transcriber_instance.start.assert_called()
            mock_processor_instance.start.assert_called()
            
            # Test initial state
            self.assertFalse(controller.is_recording)
            
            # Test toggle recording (Start)
            controller.toggle_recording()
            
            self.assertTrue(controller.is_recording)
            mock_analyzer.start_recording.assert_called()
            mock_root.setProperty.assert_called_with("recording", True)

            # Test toggle recording (Stop)
            controller.toggle_recording()
            
            self.assertFalse(controller.is_recording)
            mock_analyzer.stop_recording.assert_called()
            mock_root.setProperty.assert_called_with("recording", False)
            
            # Should force transcribe
            mock_processor_instance.force_transcribe.assert_called()

if __name__ == '__main__':
    unittest.main()
