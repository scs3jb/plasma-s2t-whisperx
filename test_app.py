import unittest
import sys
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication

# Mock audio components before importing audio_analyzer
sys.modules['PyQt6.QtMultimedia'] = MagicMock()

# Now we can import, but we need to ensure the real QObject is available if needed, 
# or we just mock the whole AudioAnalyzer for logic tests.
# However, if we want to test AudioAnalyzer logic, we need to be careful.

# Let's use patch in the test methods instead of global mocking if possible, 
# but the import itself might trigger things if not careful. 
# audio_analyzer.py imports QAudioSource, etc. at top level.

class TestApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_analyzer_init(self):
        # We need to re-import or use patch to mock the QtMultimedia components used inside AudioAnalyzer
        with patch('audio_analyzer.QAudioSource') as mock_source, \
             patch('audio_analyzer.QMediaDevices') as mock_devices:
            
            from audio_analyzer import AudioAnalyzer
            analyzer = AudioAnalyzer()
            self.assertIsNotNone(analyzer)
            self.assertEqual(analyzer.level, 0.0)
            
            # Verify mock interaction
            mock_devices.defaultAudioInput.assert_called()
            mock_source.assert_called()

    def test_controller_logic(self):
        # Test Controller logic without running the full app
        # We need to mock AudioAnalyzer and QQmlApplicationEngine
        from main import Controller
        
        mock_engine = MagicMock()
        mock_root = MagicMock()
        mock_engine.rootObjects.return_value = [mock_root]
        
        mock_analyzer = MagicMock()
        
        controller = Controller(mock_engine, mock_analyzer)
        
        # Test initial state
        self.assertFalse(controller.is_recording)
        self.assertFalse(controller.is_processing)
        
        # Test toggle recording (Start)
        with patch('os.remove') as mock_remove, \
             patch('os.path.exists', return_value=False):
            
            controller.toggle_recording()
            
            self.assertTrue(controller.is_recording)
            mock_analyzer.start_recording.assert_called()
            mock_root.setProperty.assert_called_with("recording", True)

        # Test toggle recording (Stop)
        with patch('threading.Thread') as mock_thread:
            controller.toggle_recording()
            
            self.assertFalse(controller.is_recording)
            self.assertTrue(controller.is_processing)
            mock_analyzer.stop_recording.assert_called()
            mock_root.setProperty.assert_called_with("recording", False)
            mock_thread.assert_called()

if __name__ == '__main__':
    unittest.main()
