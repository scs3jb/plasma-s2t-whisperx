# Plasma S2T WhisperX

A Speech-to-Text utility for Linux (specifically targeted at KDE Plasma users, but works elsewhere) that uses `uvx` to run [WhisperX](https://github.com/m-bain/whisperX) for fast, local transcription and `ydotool` to type the text into the active window.

## Prerequisites (Arch Linux)

To run this application, you need several system dependencies installed via `pacman`.

### 1. System Tools
*   **uv**: The modern Python package manager used to run this project and manage the WhisperX environment.
*   **ydotool**: Used to simulate keyboard input to type the transcribed text.
*   **ffmpeg**: Required by WhisperX for audio processing.

```bash
sudo pacman -S uv ydotool ffmpeg
```

### 2. Configure ydotool
`ydotool` requires a background daemon to function without root privileges for the client.

1.  Start the daemon (usually requires root or a systemd user service):
    ```bash
    sudo systemctl enable --now ydotool
    ```
2.  Ensure your user has permission to write to the ydotool socket (typically `/run/ydotool/socket`).

## Build Instructions

This project uses `uv` for dependency management. To "build" (setup) the environment:

1.  Clone this repository.
2.  Sync the dependencies to create the virtual environment:

```bash
uv sync
```

This installs `PyQt6` into a local `.venv` directory.

**Note:** `whisperx` is **not** installed in this virtual environment. The application uses `uvx` (part of `uv`) to download and run `whisperx` in its own isolated environment automatically when you transcribe audio.

## Test Instructions

To verify the installation and dependencies:

```bash
uv run python test_app.py
```

*Note: The test checks if the application can initialize. If running in a headless environment (no audio/display), it might timeout or fail to initialize Audio/GUI subsystems.*

## Running the Application

You can launch the application using the provided script (recommended):

```bash
./launch.sh
```

Or manually using the virtual environment python:

```bash
.venv/bin/python main.py
```

## Usage

1.  **Launch:** Run the script. It runs in the background/overlay.
2.  **Toggle Recording:** Run the script *again* (or send "toggle" to its local socket). Ideally, bind `./launch.sh` to a global custom shortcut in KDE Plasma (e.g., `Meta+R`).
3.  **Speak:** Speak into your microphone.
4.  **Transcribe:** Trigger the shortcut again to stop recording.
    *   The app will invoke `whisperx` via `uvx` to transcribe the audio.
    *   Once finished, it uses `ydotool` to type the text into your active window.

## Troubleshooting

*   **First Run Delay:** The first time you transcribe, `uvx` will download `whisperx` and its dependencies (PyTorch, etc.). This may take a while. Subsequent runs will be faster.
*   **Typing Fails:** Verify `ydotool` works by running `ydotool type "test"` in a terminal.
*   **Audio Issues:** Ensure PipeWire/PulseAudio is running and configured.