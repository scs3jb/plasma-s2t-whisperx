# Plasma S2T WhisperX

A Speech-to-Text utility for Linux (specifically targeted at KDE Plasma users) that uses **WhisperX** for fast, local, real-time transcription and `ydotool` to type the text into the active window.

## Features
*   **Real-time Transcription:** Keeps the Whisper model loaded for instant response.
*   **Multithreaded Architecture:** Prevents audio loss and UI freezes by separating audio capture, VAD analysis, and model inference into dedicated threads.
*   **Automatic VAD (Voice Activity Detection):** Detects pauses in speech and automatically transcribes/types while you continue to record the next sentence.
*   **Manual Toggle:** Optional manual control to force a final transcription and stop the service.
*   **Minimal UI:** An unobtrusive overlay that visualizes your audio levels and provides clear status feedback.

## Architecture & Lessons Learned

During development, several key architectural decisions were made to ensure high performance:

1.  **Concurrency is Key:** To avoid "Audio Loss" (dropped samples), audio capture must happen in a high-priority thread (the Main Thread in this case, tied to the Qt Event Loop). Heavy operations like Model Inference and simulating keyboard input (`ydotool`) are moved to a background `TranscriberThread`.
2.  **VAD Pipeline:** A dedicated `AudioProcessor` thread handles energy-based endpointing. This allows the system to buffer audio continuously without blocking the capture pipeline.
3.  **PyTorch Compatibility:** Modern PyTorch (2.6+) defaults to `weights_only=True` for security, which blocks many WhisperX/Pyannote checkpoints. This is bypassed using the `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` environment variable.
4.  **UI States:**
    *   **Red / "Listening":** Active recording. Stays active during automatic (VAD) transcription to provide a seamless dictation experience.
    *   **Blue / "Transcribing":** Triggered only on manual stop to show the user that the final buffer is being processed before the app goes Idle.
    *   **Blue / "Idle":** Standby mode.

## Prerequisites (Arch Linux)

### 1. System Tools
*   **uv**: Python package manager.
*   **ydotool**: For keyboard simulation.
*   **ffmpeg**: Required by WhisperX.

```bash
sudo pacman -S uv ydotool ffmpeg
```

### 2. Configure ydotool
`ydotool` requires a background daemon.
```bash
systemctl --user enable ydotool.service
systemctl --user start ydotool.service
```

## Setup & Build

This project uses `uv` for dependency management.

1.  Clone this repository.
2.  Sync dependencies into the virtual environment:
```bash
uv sync
```

## Running the Application

Launch the application using the provided script:

```bash
./launch.sh [profile]
```

### Transcription Profiles
*   `ultrafast` / `fast` (Tiny model)
*   `balanced` (Base model) - **Default**
*   `accurate` (Small model)
*   `high_accuracy` (Large-v2 model)

## Usage & Shortcuts

### Configuring Profiles in KDE Plasma

1.  Open **System Settings** -> **Shortcuts** -> **Custom Shortcuts**.
2.  Create a **New Global Shortcut** (Command/URL).
3.  **Toggle Recording:** Set the command to `/path/to/launch.sh balanced` (e.g., bind to `Meta+R`).
4.  **Quit App:** Set the command to `/path/to/launch.sh quit` (e.g., bind to `Meta+Shift+Q`).

### Workflow
1.  **Start:** Press your hotkey. The UI appears Red and begins "Listening".
2.  **Dictate:** Speak naturally. When you pause, the app automatically types in the background.
3.  **Stop/Flush:** Press the hotkey again. The UI turns Blue, processes any remaining audio, and goes Idle.
4.  **Exit:** Use the dedicated quit shortcut or run `./launch.sh quit`.

## Troubleshooting
*   **Audio Loss:** If soundwaves freeze, ensure no other process is blocking the Python interpreter. The current architecture minimizes this by using separate threads.
*   **Typing Fails:** Verify `ydotool` permissions. Your user must have access to the ydotool socket.