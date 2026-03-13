import os
import sys
import time
import queue
import threading
import datetime
import ctypes
import fractions

import tkinter as tk
import numpy as np
import mss
import av
import soundcard as sc
from pynput import keyboard

FPS = 60
SAMPLE_RATE = 44100
CHANNELS = 2
STOP = threading.Event()

if sys.platform == "win32":
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)


def get_output_path():
    folder = os.path.join(os.path.expanduser("~"), "Videos", "Nagrania")
    os.makedirs(folder, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return os.path.join(folder, f"rec_{ts}.mp4")


def pick_two_devices():
    all_devs = sc.all_microphones(include_loopback=True)

    mic_devs = [d for d in all_devs if "[Loopback]" not in d.name]
    sys_devs = [d for d in all_devs if "[Loopback]" in d.name]
    if not mic_devs:
        mic_devs = all_devs
    if not sys_devs:
        sys_devs = all_devs

    chosen_mic = [None]
    chosen_sys = [None]
    live_dev = [None]
    live_level = [0.0]
    preview_stop = threading.Event()

    def live_reader():
        while not preview_stop.is_set():
            dev = live_dev[0]
            if dev is None:
                time.sleep(0.05)
                continue
            try:
                with dev.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS, blocksize=256) as mic:
                    watching = dev
                    while not preview_stop.is_set() and live_dev[0] is watching:
                        data = mic.record(numframes=256)
                        live_level[0] = float(np.abs(data).mean()) * 50
            except Exception:
                pass
            live_level[0] = 0.0

    threading.Thread(target=live_reader, daemon=True).start()

    root = tk.Tk()
    root.title("Wybierz urzadzenia audio")
    root.configure(bg="#111111")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()

    def make_section(parent, label, devs, chosen_ref):
        tk.Label(parent, text=label, bg="#111111", fg="#555555",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=20, pady=(14, 2))

        lb = tk.Listbox(
            parent,
            bg="#1a1a1a", fg="#cccccc",
            selectbackground="#2c2c2c", selectforeground="#ffffff",
            font=("Segoe UI", 10),
            bd=0, highlightthickness=1, highlightcolor="#2a2a2a", highlightbackground="#1a1a1a",
            width=56, height=min(len(devs), 5),
            activestyle="none",
        )
        lb.pack(padx=20, fill="x")

        for dev in devs:
            lb.insert("end", f"  {dev.name[:54]}")

        if devs:
            lb.selection_set(0)
            chosen_ref[0] = devs[0]

        def on_sel(evt):
            sel = lb.curselection()
            if sel:
                chosen_ref[0] = devs[sel[0]]
                live_dev[0] = devs[sel[0]]
                live_level[0] = 0.0

        lb.bind("<<ListboxSelect>>", on_sel)
        return lb

    mic_lb = make_section(root, "Mikrofo", mic_devs, chosen_mic)
    sys_lb = make_section(root, "Audio komputera", sys_devs, chosen_sys)

    bar_frame = tk.Frame(root, bg="#111111")
    bar_frame.pack(padx=20, pady=(10, 4), fill="x")
    tk.Label(bar_frame, text="skala dzwieku:", bg="#111111", fg="#444444",
             font=("Segoe UI", 9)).pack(side="left")
    bar_canvas = tk.Canvas(bar_frame, bg="#1a1a1a", height=14,
                           highlightthickness=0, bd=0)
    bar_canvas.pack(side="left", fill="x", expand=True, padx=(8, 0))

    confirmed = [False]

    def _confirm():
        confirmed[0] = True
        preview_stop.set()
        root.destroy()

    def _on_close():
        preview_stop.set()
        root.destroy()

    btn = tk.Button(
        root, text="  Nagraj  ",
        bg="#1a1a1a", fg="#00e676",
        activebackground="#222222", activeforeground="#00e676",
        font=("Segoe UI", 11, "bold"),
        relief="flat", bd=0, padx=24, pady=10,
        cursor="hand2",
        command=_confirm
    )
    btn.pack(pady=(6, 20))
    root.protocol("WM_DELETE_WINDOW", _on_close)

    bar_running = [True]

    def update_bar():
        if not bar_running[0]:
            return
        try:
            w = bar_canvas.winfo_width()
            h = bar_canvas.winfo_height()
            bar_canvas.delete("all")
            fill = min(1.0, live_level[0])
            if fill > 0.005:
                color = "#00e676" if fill < 0.75 else "#ff5252"
                bar_canvas.create_rectangle(0, 0, int(w * fill), h, fill=color, outline="")
            root.after(40, update_bar)
        except Exception:
            bar_running[0] = False

    root.after(40, update_bar)
    root.update_idletasks()
    ww = root.winfo_width()
    wh = root.winfo_height()
    root.geometry(f"+{(sw - ww) // 2}+{(sh - wh) // 2}")
    root.mainloop()

    preview_stop.set()
    if not confirmed[0]:
        sys.exit(0)
    return chosen_mic[0], chosen_sys[0]


def record(out_path, stop_event, mic_dev, sys_dev, fps=FPS):
    with mss.mss() as sct:
        mon = sct.monitors[0]
        W = mon["width"] - (mon["width"] % 2)
        H = mon["height"] - (mon["height"] % 2)

    container = av.open(out_path, mode="w")
    vid_stream = container.add_stream("libx264", rate=fps)
    vid_stream.width = W
    vid_stream.height = H
    vid_stream.pix_fmt = "yuv420p"
    vid_stream.options = {"preset": "ultrafast", "crf": "18", "tune": "zerolatency"}

    aud_stream = container.add_stream("aac", rate=SAMPLE_RATE)
    aud_stream.codec_context.layout = "stereo"

    frame_duration = 1.0 / fps
    encode_q = queue.Queue(maxsize=128)
    mux_lock = threading.Lock()
    start_time = [None]

    def encoder():
        prev_pts = -1
        while True:
            item = encode_q.get()
            if item is None:
                break
            rgb, now = item
            pts = int((now - start_time[0]) * fps)
            if pts <= prev_pts:
                pts = prev_pts + 1
            prev_pts = pts
            av_frame = av.VideoFrame.from_ndarray(rgb, format="rgb24")
            av_frame.pts = pts
            for pkt in vid_stream.encode(av_frame):
                with mux_lock:
                    container.mux(pkt)

    encoder_t = threading.Thread(target=encoder, daemon=True)
    encoder_t.start()

    mic_q = queue.Queue(maxsize=64)
    sys_q = queue.Queue(maxsize=64)

    def capture(dev, out_q):
        if dev is None:
            return
        try:
            chunk = 1024
            with dev.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS, blocksize=chunk) as mic:
                while not stop_event.is_set():
                    data = mic.record(numframes=chunk)
                    if data.shape[0] == 0:
                        continue
                    if data.shape[1] != CHANNELS:
                        data = np.mean(data, axis=1, keepdims=True).repeat(CHANNELS, axis=1)
                    out_q.put(data.astype(np.float32))
        except Exception:
            import traceback; traceback.print_exc()

    mic_cap_t = threading.Thread(target=capture, args=(mic_dev, mic_q), daemon=True)
    sys_cap_t = threading.Thread(target=capture, args=(sys_dev, sys_q), daemon=True)
    mic_cap_t.start()
    sys_cap_t.start()

    def audio_mix():
        aud_pts = 0
        while not stop_event.is_set():
            mic_data = None
            sys_data = None
            try:
                mic_data = mic_q.get(timeout=0.1)
            except queue.Empty:
                pass
            try:
                sys_data = sys_q.get_nowait()
            except queue.Empty:
                pass
            if mic_data is None and sys_data is None:
                continue
            ref = mic_data if mic_data is not None else sys_data
            n = ref.shape[0]
            mixed = np.zeros((n, CHANNELS), dtype=np.float32)
            if mic_data is not None:
                mixed += mic_data[:n]
            if sys_data is not None:
                mixed += sys_data[:n]
            if mic_data is not None and sys_data is not None:
                mixed *= 0.5
            mixed = np.clip(mixed, -1.0, 1.0)
            pcm = np.ascontiguousarray(mixed.T)
            av_frame = av.AudioFrame.from_ndarray(pcm, format="fltp", layout="stereo")
            av_frame.sample_rate = SAMPLE_RATE
            av_frame.pts = aud_pts
            av_frame.time_base = fractions.Fraction(1, SAMPLE_RATE)
            aud_pts += n
            for pkt in aud_stream.encode(av_frame):
                with mux_lock:
                    container.mux(pkt)

    audio_t = threading.Thread(target=audio_mix, daemon=True)
    audio_t.start()

    if sys.platform == "win32":
        ctypes.windll.winmm.timeBeginPeriod(1)

    try:
        with mss.mss() as sct:
            mon = sct.monitors[0]
            start = time.perf_counter()
            start_time[0] = start
            frame_idx = 0

            while not stop_event.is_set():
                target = start + frame_idx * frame_duration
                wait = target - time.perf_counter()
                if wait > 0.002:
                    time.sleep(wait - 0.001)
                while time.perf_counter() < target:
                    pass

                now = time.perf_counter()
                img = sct.grab(mon)
                bgr = np.frombuffer(img.raw, dtype=np.uint8).reshape(
                    (img.height, img.width, 4))[:H, :W, :3]
                rgb = np.ascontiguousarray(bgr[:, :, ::-1])
                encode_q.put((rgb, now))
                frame_idx += 1

    finally:
        if sys.platform == "win32":
            ctypes.windll.winmm.timeEndPeriod(1)
        encode_q.put(None)
        encoder_t.join(timeout=30)
        audio_t.join(timeout=3)
        mic_cap_t.join(timeout=3)
        sys_cap_t.join(timeout=3)
        for pkt in vid_stream.encode():
            with mux_lock:
                container.mux(pkt)
        for pkt in aud_stream.encode():
            with mux_lock:
                container.mux(pkt)
        container.close()


def main():
    mic_dev, sys_dev = pick_two_devices()
    out = get_output_path()

    vid_t = threading.Thread(target=record, args=(out, STOP, mic_dev, sys_dev, FPS), daemon=True)
    vid_t.start()

    alt_held = threading.Event()

    def on_press(key):
        if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
            alt_held.set()
        try:
            if alt_held.is_set() and key.char == "l":
                STOP.set()
                return False
        except AttributeError:
            pass

    def on_release(key):
        if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
            alt_held.clear()

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    STOP.wait()
    listener.stop()
    vid_t.join(timeout=60)
    _show_toast()


def _show_toast():
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.92)
    root.configure(bg="#1e1e1e")

    lbl = tk.Label(
        root,
        text="  Nagranie zakończone  ",
        bg="#1e1e1e",
        fg="#00e676",
        font=("Segoe UI", 13, "bold"),
        pady=14,
        padx=20
    )
    lbl.pack()

    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{sh - h - 60}")

    root.after(2500, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()

