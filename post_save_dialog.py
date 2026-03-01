import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox


def _ps_escape(value: str) -> str:
    return value.replace("'", "''")


def copy_file_to_clipboard(path: str) -> bool:
    p = _ps_escape(path)
    cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$col = New-Object System.Collections.Specialized.StringCollection; "
        f"[void]$col.Add('{p}'); "
        "[System.Windows.Forms.Clipboard]::SetFileDropList($col)"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", cmd],
            check=False,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return False


def copy_text_to_clipboard(root: tk.Tk, text: str) -> bool:
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update_idletasks()
        root.update()
        return True
    except Exception:
        pass

    p = _ps_escape(text)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{p}'"],
            check=False,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return False


def main():
    if len(sys.argv) < 2:
        print("{}")
        return

    src = Path(sys.argv[1]).resolve()
    default_name = src.name
    default_dir = src.parent

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    target = filedialog.asksaveasfilename(
        title="Save recording as...",
        initialdir=str(default_dir),
        initialfile=default_name,
        defaultextension=".mp4",
        filetypes=[("MP4 video", "*.mp4"), ("All files", "*.*")],
    )

    if target:
        target_path = str(Path(target).resolve())
    else:
        # User cancelled — ask if they want to discard
        discard = messagebox.askyesno(
            "Discard recording?",
            "No save location selected. Delete this recording?",
            parent=root,
        )
        if discard:
            try:
                src.unlink(missing_ok=True)
            except Exception:
                pass
            print(json.dumps({"path": "", "copied": False}), flush=True)
            root.destroy()
            return
        target_path = str(src)

    copied = False

    copy_file_choice = messagebox.askyesno(
        "Copy video",
        "Copy video file to clipboard for quick paste in chat?",
        parent=root,
    )

    if copy_file_choice:
        copied = copy_file_to_clipboard(target_path)
        if not copied:
            copy_path_choice = messagebox.askyesno(
                "Copy path",
                "File copy failed. Copy file path instead?",
                parent=root,
            )
            if copy_path_choice:
                copied = copy_text_to_clipboard(root, target_path)
    else:
        copy_path_choice = messagebox.askyesno(
            "Copy path",
            "Copy saved file path to clipboard?",
            parent=root,
        )
        if copy_path_choice:
            copied = copy_text_to_clipboard(root, target_path)

    print(json.dumps({"path": target_path, "copied": copied}), flush=True)
    root.destroy()


if __name__ == "__main__":
    main()
