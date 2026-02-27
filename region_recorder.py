import ctypes
from ctypes import wintypes
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

HOTKEY_TOGGLE_TEXT = "Ctrl+X"
HOTKEY_RESELECT_TEXT = "Ctrl+Shift+R"
HOTKEY_QUIT_TEXT = "Ctrl+Shift+Q"
FPS = 30
OUTPUT_DIR = Path(__file__).resolve().parent / "recordings"
FFMPEG_BIN = "ffmpeg"
SELECTOR_SCRIPT = Path(__file__).resolve().parent / "select_region.py"
POST_SAVE_SCRIPT = Path(__file__).resolve().parent / "post_save_dialog.py"
OVERLAY_SCRIPT = Path(__file__).resolve().parent / "recording_overlay.py"
LOG_FILE = Path(__file__).resolve().parent / "recorder.log"
AUDIO_KEYWORDS = [
    "virtual-audio-capturer",
    "stereo mix",
    "wave out mix",
    "what u hear",
    "cable output",
    "\u0441\u0442\u0435\u0440\u0435\u043e \u043c\u0438\u043a\u0448\u0435\u0440",
]

# WinAPI hotkey constants
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
WM_HOTKEY = 0x0312
VK_X = 0x58
VK_R = 0x52
VK_Q = 0x51
ID_TOGGLE = 1
ID_RESELECT = 2
ID_QUIT = 3
SINGLETON_NAME = "Global\\ScreenRegionRecorderSingleton"


def ensure_single_instance():
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, SINGLETON_NAME)
    already_exists = kernel32.GetLastError() == 183
    return handle, already_exists


class Recorder:
    def __init__(self):
        self.region = None
        self.proc = None
        self.lock = threading.Lock()
        self.audio_device = None
        self.ffmpeg_log = None
        self.overlay_proc = None
        self.last_hotkey_time = {}
        self.record_started_at = 0.0
        self.current_output_path = None

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        LOG_FILE.touch(exist_ok=True)

    def _log(self, text):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {text}\n")

    def _notify(self, text):
        self._log(text)

    def choose_region(self):
        if not SELECTOR_SCRIPT.exists():
            self._notify("select_region.py not found")
            return False

        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            res = subprocess.run(
                [sys.executable, str(SELECTOR_SCRIPT)],
                capture_output=True,
                text=True,
                timeout=120,
                creationflags=flags,
                check=False,
            )
        except Exception as ex:
            self._notify(f"Region selection error: {ex}")
            return False

        if res.returncode != 0:
            self._notify(f"Region selection failed: rc={res.returncode}; {res.stderr.strip()}")
            return False

        out = (res.stdout or "").strip()
        if not out:
            self._notify("Region selection cancelled")
            return False

        try:
            region = json.loads(out)
        except json.JSONDecodeError:
            self._notify(f"Region data error: {out[:200]}")
            return False

        if not region:
            self._notify("Region selection cancelled")
            return False

        self.region = region
        self._notify(f"Region selected: {region['width']}x{region['height']}")
        return True

    def _build_ffmpeg_cmd(self, output_file, with_audio):
        region = self.region
        cmd = [
            FFMPEG_BIN,
            "-y",
            "-f",
            "gdigrab",
            "-framerate",
            str(FPS),
            "-offset_x",
            str(region["left"]),
            "-offset_y",
            str(region["top"]),
            "-video_size",
            f"{region['width']}x{region['height']}",
            "-i",
            "desktop",
        ]

        if with_audio and self.audio_device:
            cmd.extend(
                [
                    "-f",
                    "dshow",
                    "-thread_queue_size",
                    "1024",
                    "-i",
                    f"audio={self.audio_device}",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                ]
            )

        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                str(output_file),
            ]
        )
        return cmd

    def _start_ffmpeg(self, cmd):
        self.ffmpeg_log = LOG_FILE.open("a", encoding="utf-8")
        self.ffmpeg_log.write("\n----- ffmpeg start -----\n")
        self.ffmpeg_log.flush()
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = None
        if hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=self.ffmpeg_log,
            creationflags=creation_flags,
            startupinfo=startupinfo,
        )

    def _start_overlay(self):
        if self.overlay_proc is not None:
            return
        if not OVERLAY_SCRIPT.exists():
            return
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        args = [
            sys.executable,
            str(OVERLAY_SCRIPT),
        ]
        try:
            self.overlay_proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
        except Exception as ex:
            self.overlay_proc = None
            self._notify(f"Failed to show recording border: {ex}")

    def _stop_overlay(self):
        if self.overlay_proc is None:
            return
        try:
            self.overlay_proc.terminate()
            self.overlay_proc.wait(timeout=1.5)
        except Exception:
            try:
                self.overlay_proc.kill()
            except Exception:
                pass
        self.overlay_proc = None

    def start_recording(self):
        with self.lock:
            if self.proc is not None:
                return
            if self.region is None and not self.choose_region():
                return
            if self.audio_device is None:
                self.audio_device = self._choose_system_audio_device()

            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            out = OUTPUT_DIR / f"capture_{ts}.mp4"
            self.current_output_path = out

            try:
                cmd = self._build_ffmpeg_cmd(out, with_audio=True)
                self._start_ffmpeg(cmd)
                time.sleep(0.7)

                if self.proc.poll() is not None and self.audio_device:
                    if self.ffmpeg_log:
                        self.ffmpeg_log.close()
                    self.proc = None
                    cmd = self._build_ffmpeg_cmd(out, with_audio=False)
                    self._start_ffmpeg(cmd)
                    time.sleep(0.5)

                if self.proc.poll() is not None:
                    self._notify("Failed to start recording. Check recorder.log")
                    if self.ffmpeg_log:
                        self.ffmpeg_log.close()
                        self.ffmpeg_log = None
                    self.proc = None
                    return

                if self.audio_device:
                    self._notify("Recording started (screen + system audio)")
                else:
                    self._notify("Recording started (no system audio)")
                self._start_overlay()
                self.record_started_at = time.monotonic()
            except FileNotFoundError:
                self.proc = None
                if self.ffmpeg_log:
                    self.ffmpeg_log.close()
                    self.ffmpeg_log = None
                self._notify("ffmpeg not found. Install ffmpeg and add it to PATH.")

    def stop_recording(self):
        with self.lock:
            if self.proc is None:
                return
            try:
                if self.proc.stdin:
                    self.proc.stdin.write(b"q\n")
                    self.proc.stdin.flush()
            except Exception:
                pass
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.proc = None
            self.record_started_at = 0.0
            self._stop_overlay()
            if self.ffmpeg_log:
                self.ffmpeg_log.write("----- ffmpeg stop -----\n")
                self.ffmpeg_log.close()
                self.ffmpeg_log = None
            self._notify("Recording stopped")
            self._handle_post_save()

    def toggle(self):
        if self.proc is None:
            if self.region is None:
                if self.choose_region():
                    self._notify("Region selected. Press Ctrl+X again to start recording")
                return
            self.start_recording()
        else:
            if time.monotonic() - self.record_started_at < 1.2:
                return
            self.stop_recording()

    def reselect_region(self):
        with self.lock:
            if self.proc is not None:
                self._notify("Stop recording before selecting a new region")
                return
            self.choose_region()

    def _list_dshow_audio_devices(self):
        cmd = [FFMPEG_BIN, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []

        names = []
        text = f"{res.stdout}\n{res.stderr}"
        for line in text.splitlines():
            match = re.search(r'"(.+?)"\s+\(audio\)', line)
            if match:
                names.append(match.group(1))
        return names

    def _choose_system_audio_device(self):
        devices = self._list_dshow_audio_devices()
        if not devices:
            self._notify("No ffmpeg audio devices found. Recording will be without system audio.")
            return None

        for keyword in AUDIO_KEYWORDS:
            for name in devices:
                if keyword in name.lower():
                    self._notify(f"System audio: {name}")
                    return name

        self._notify("No loopback device found (Stereo Mix/Virtual Audio). Recording will be without system audio.")
        return None

    def _handle_post_save(self):
        output_path = self.current_output_path
        self.current_output_path = None
        if not output_path:
            return
        if not output_path.exists() or not POST_SAVE_SCRIPT.exists():
            return

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            res = subprocess.run(
                [sys.executable, str(POST_SAVE_SCRIPT), str(output_path)],
                capture_output=True,
                text=True,
                timeout=300,
                creationflags=creation_flags,
                check=False,
            )
        except Exception as ex:
            self._notify(f"Post-save dialog failed: {ex}")
            return

        if res.returncode != 0:
            return

        payload_raw = (res.stdout or "").strip()
        if not payload_raw:
            return

        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            return

        target = payload.get("path")
        if target:
            target_path = Path(target)
            try:
                if target_path.resolve() != output_path.resolve():
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(output_path), str(target_path))
                    output_path = target_path
            except Exception as ex:
                self._notify(f"Failed to move file: {ex}")
                return

        if payload.get("copied"):
            self._notify(f"Path copied to clipboard: {output_path}")

    def run(self):
        user32 = ctypes.windll.user32

        ok1 = user32.RegisterHotKey(None, ID_TOGGLE, MOD_CONTROL, VK_X)
        ok2 = user32.RegisterHotKey(None, ID_RESELECT, MOD_CONTROL | MOD_SHIFT, VK_R)
        ok3 = user32.RegisterHotKey(None, ID_QUIT, MOD_CONTROL | MOD_SHIFT, VK_Q)

        if not (ok1 and ok2 and ok3):
            self._notify("Failed to register hotkeys. They may already be in use.")
            if ok1:
                user32.UnregisterHotKey(None, ID_TOGGLE)
            if ok2:
                user32.UnregisterHotKey(None, ID_RESELECT)
            if ok3:
                user32.UnregisterHotKey(None, ID_QUIT)
            return

        self._notify(
            f"Background mode enabled. {HOTKEY_TOGGLE_TEXT} cycle: region -> start -> stop, {HOTKEY_RESELECT_TEXT} new region, {HOTKEY_QUIT_TEXT} quit"
        )

        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == WM_HOTKEY:
                    hotkey_id = msg.wParam
                    now = time.monotonic()
                    last = self.last_hotkey_time.get(hotkey_id, 0.0)
                    if now - last < 0.6:
                        continue
                    self.last_hotkey_time[hotkey_id] = now
                    if hotkey_id == ID_TOGGLE:
                        self.toggle()
                    elif hotkey_id == ID_RESELECT:
                        self.reselect_region()
                    elif hotkey_id == ID_QUIT:
                        self.stop_recording()
                        self._stop_overlay()
                        break
        finally:
            self._stop_overlay()
            user32.UnregisterHotKey(None, ID_TOGGLE)
            user32.UnregisterHotKey(None, ID_RESELECT)
            user32.UnregisterHotKey(None, ID_QUIT)


if __name__ == "__main__":
    _mutex_handle, _already_exists = ensure_single_instance()
    if _already_exists:
        sys.exit(0)
    Recorder().run()
