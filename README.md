# Hidding-video-record

Hidding video recording. Captures the full screen + microphone + system audio at the same time. Output is an `.mp4` file (H.264 + AAC).

## Getting started

Easiest way is to run `start.bat` — it sets up the venv, installs dependencies and launches the app.

Or manually:
```
python hrec.py
```

## How to record

1. A window appears where you pick your audio devices
2. Select a microphone from the top list, system audio from the bottom
3. Click **Nagraj** — the window closes and recording starts
4. To stop: `Alt + L`

## Where recordings are saved

```
C:\Users\<your name>\Videos\Nagrania\
```

Files are named `rec_YYYYMMDD_HHMMSS.mp4`.

## Requirements

- Python 3.10+
- Windows (WASAPI for system audio capture)

## How detected

A few ways someone could spot that a recording is in progress:

- **Task Manager** - process runs as `hrec.exe` or `pythonw.exe`, no window visible
- **No tray icon** - there's no system tray icon or indicator while recording
- **File output** - new `.mp4` files appearing in `Videos\Nagrania\` after sessions
- **Audio device usage** - microphone and loopback device are both active, which is visible in Windows sound settings (`Win + I → System → Sound → Volume mixer`)

To stay undetected longer: rename the exe, move output folder somewhere less obvious, and avoid running it while someone checks Task Manager.
