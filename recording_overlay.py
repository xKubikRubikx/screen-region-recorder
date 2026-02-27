import ctypes
import math
import tkinter as tk


def set_exclude_from_capture(hwnd):
    user32 = ctypes.windll.user32
    # WDA_EXCLUDEFROMCAPTURE = 0x00000011 (Win10 2004+)
    return user32.SetWindowDisplayAffinity(hwnd, 0x11)


def main():
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", "black")
    root.configure(bg="black")

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    root.geometry(f"{screen_w}x{screen_h}+0+0")

    canvas = tk.Canvas(root, bg="black", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    border_size = 3
    top_edge = canvas.create_rectangle(0, 0, screen_w, border_size, fill="#551018", outline="")
    bottom_edge = canvas.create_rectangle(
        0,
        screen_h - border_size,
        screen_w,
        screen_h,
        fill="#551018",
        outline="",
    )
    left_edge = canvas.create_rectangle(0, 0, border_size, screen_h, fill="#551018", outline="")
    right_edge = canvas.create_rectangle(
        screen_w - border_size,
        0,
        screen_w,
        screen_h,
        fill="#551018",
        outline="",
    )

    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        set_exclude_from_capture(hwnd)
    except Exception:
        pass

    phase = 0.0

    def animate():
        nonlocal phase
        phase += 0.12
        # Subtle pulse: dark red -> slightly brighter red.
        wave = (math.sin(phase) + 1.0) / 2.0
        r = int(70 + 70 * wave)
        g = int(10 + 22 * wave)
        b = int(16 + 20 * wave)
        color = f"#{r:02x}{g:02x}{b:02x}"

        canvas.itemconfig(top_edge, fill=color)
        canvas.itemconfig(bottom_edge, fill=color)
        canvas.itemconfig(left_edge, fill=color)
        canvas.itemconfig(right_edge, fill=color)

        root.after(45, animate)

    animate()
    root.mainloop()


if __name__ == "__main__":
    main()
