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

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
OUTPUT_DIR = BASE_DIR / "recordings"
FFMPEG_BIN = "ffmpeg"
SELECTOR_SCRIPT = BASE_DIR / "select_region.py"
POST_SAVE_SCRIPT = BASE_DIR / "post_save_dialog.py"
OVERLAY_SCRIPT = BASE_DIR / "recording_overlay.py"
DRAW_SCRIPT = BASE_DIR / "draw_overlay.py"
LOG_FILE = BASE_DIR / "recorder.log"
AUDIO_KEYWORDS = [
    "virtual-audio-capturer",
    "stereo mix",
    "wave out mix",
    "what u hear",
    "cable output",
    "\u0441\u0442\u0435\u0440\u0435\u043e \u043c\u0438\u043a\u0448\u0435\u0440",
]

# WinAPI hotkey constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
WM_HOTKEY = 0x0312
ID_TOGGLE = 1
ID_RESELECT = 2
ID_QUIT = 3
ID_DRAW = 4
SINGLETON_NAME = "Global\\ScreenRegionRecorderSingleton"

DEFAULT_CONFIG = {
    "hotkeys": {
        "toggle": "ctrl+x",
        "reselect": "ctrl+shift+r",
        "quit": "ctrl+shift+q",
        "draw": "ctrl+shift+d",
    },
    "recording": {
        "fps": 30,
        "crf": 18,
        "preset": "veryfast",
    },
}

# Map key names to VK codes
VK_MAP = {
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59,
    "z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B,
    "space": 0x20, "enter": 0x0D, "tab": 0x09,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "printscreen": 0x2C, "pause": 0x13, "numlock": 0x90,
}

MOD_MAP = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "alt": MOD_ALT,
    "win": MOD_WIN,
}


def parse_hotkey(hotkey_str):
    """Parse a hotkey string like 'ctrl+shift+x' into (modifiers, vk_code)."""
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    modifiers = 0
    vk_code = 0
    for part in parts:
        if part in MOD_MAP:
            modifiers |= MOD_MAP[part]
        elif part in VK_MAP:
            vk_code = VK_MAP[part]
        else:
            raise ValueError(f"Unknown key: '{part}' in hotkey '{hotkey_str}'")
    if vk_code == 0:
        raise ValueError(f"No key specified in hotkey '{hotkey_str}'")
    return modifiers, vk_code


def load_config():
    """Load config from config.json or create default."""
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            # Merge with defaults
            cfg = dict(DEFAULT_CONFIG)
            if "hotkeys" in user_cfg:
                cfg["hotkeys"] = {**DEFAULT_CONFIG["hotkeys"], **user_cfg["hotkeys"]}
            if "recording" in user_cfg:
                cfg["recording"] = {**DEFAULT_CONFIG["recording"], **user_cfg["recording"]}
            return cfg
        except Exception:
            return dict(DEFAULT_CONFIG)
    else:
        # Create default config file
        try:
            with CONFIG_FILE.open("w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return dict(DEFAULT_CONFIG)


def ensure_single_instance():
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, SINGLETON_NAME)
    already_exists = kernel32.GetLastError() == 183
    return handle, already_exists


class Recorder:
    def __init__(self, config):
        self.config = config
        self.region = None
        self.proc = None
        self.lock = threading.Lock()
        self.audio_device = None
        self.ffmpeg_log = None
        self.overlay_proc = None
        self.draw_proc = None
        self.last_hotkey_time = {}
        self.record_started_at = 0.0
        self.current_output_path = None

        self.fps = config["recording"].get("fps", 30)
        self.crf = config["recording"].get("crf", 18)
        self.preset = config["recording"].get("preset", "veryfast")

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
            str(self.fps),
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
                self.preset,
                "-crf",
                str(self.crf),
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

    def _toggle_draw_overlay(self):
        """Toggle drawing overlay on/off during recording."""
        if self.proc is None:
            self._notify("Start recording before drawing")
            return
        if self.draw_proc is not None and self.draw_proc.poll() is None:
            # Close existing draw overlay
            try:
                self.draw_proc.terminate()
                self.draw_proc.wait(timeout=1.5)
            except Exception:
                try:
                    self.draw_proc.kill()
                except Exception:
                    pass
            self.draw_proc = None
            self._notify("Drawing overlay closed")
            return

        if not DRAW_SCRIPT.exists():
            self._notify("draw_overlay.py not found")
            return

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.draw_proc = subprocess.Popen(
                [sys.executable, str(DRAW_SCRIPT)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
            self._notify("Drawing overlay opened. F=Freehand, A=Arrow, R=Rect, C=Clear, Esc=Close")
        except Exception as ex:
            self.draw_proc = None
            self._notify(f"Failed to open drawing overlay: {ex}")

    def _stop_draw_overlay(self):
        if self.draw_proc is None:
            return
        try:
            self.draw_proc.terminate()
            self.draw_proc.wait(timeout=1.5)
        except Exception:
            try:
                self.draw_proc.kill()
            except Exception:
                pass
        self.draw_proc = None

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
                    self._notify(f"Recording started (screen + system audio) [CRF {self.crf}, {self.fps} fps]")
                else:
                    self._notify(f"Recording started (no system audio) [CRF {self.crf}, {self.fps} fps]")
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
            self._stop_draw_overlay()
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
                    self._notify("Region selected. Press hotkey again to start recording")
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
        hotkeys_cfg = self.config["hotkeys"]

        # Parse hotkeys from config
        hotkey_defs = {}
        for name, hk_id in [("toggle", ID_TOGGLE), ("reselect", ID_RESELECT),
                             ("quit", ID_QUIT), ("draw", ID_DRAW)]:
            try:
                mods, vk = parse_hotkey(hotkeys_cfg[name])
                hotkey_defs[hk_id] = (mods, vk, hotkeys_cfg[name])
            except (ValueError, KeyError) as ex:
                self._notify(f"Invalid hotkey '{name}': {ex}. Using default.")
                mods, vk = parse_hotkey(DEFAULT_CONFIG["hotkeys"][name])
                hotkey_defs[hk_id] = (mods, vk, DEFAULT_CONFIG["hotkeys"][name])

        # Register hotkeys
        registered = {}
        all_ok = True
        for hk_id, (mods, vk, text) in hotkey_defs.items():
            ok = user32.RegisterHotKey(None, hk_id, mods, vk)
            if ok:
                registered[hk_id] = True
            else:
                all_ok = False
                self._notify(f"Failed to register hotkey {text}. It may already be in use.")

        if not registered:
            self._notify("No hotkeys could be registered. Exiting.")
            return

        hotkey_texts = {hk_id: text for hk_id, (_, _, text) in hotkey_defs.items()}
        self._notify(
            f"Background mode enabled. "
            f"{hotkey_texts[ID_TOGGLE]} cycle: region -> start -> stop, "
            f"{hotkey_texts[ID_RESELECT]} new region, "
            f"{hotkey_texts[ID_DRAW]} draw, "
            f"{hotkey_texts[ID_QUIT]} quit"
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
                    elif hotkey_id == ID_DRAW:
                        self._toggle_draw_overlay()
                    elif hotkey_id == ID_QUIT:
                        self.stop_recording()
                        self._stop_overlay()
                        self._stop_draw_overlay()
                        break
        finally:
            self._stop_overlay()
            self._stop_draw_overlay()
            for hk_id in registered:
                user32.UnregisterHotKey(None, hk_id)


if __name__ == "__main__":
    _mutex_handle, _already_exists = ensure_single_instance()
    if _already_exists:
        sys.exit(0)
    _config = load_config()
    Recorder(_config).run()
