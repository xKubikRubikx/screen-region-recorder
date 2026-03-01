import ctypes
import math
import tkinter as tk


class DrawOverlay:
    """Transparent overlay for drawing annotations during recording."""

    TOOLS = {"freehand": "Freehand (F)", "arrow": "Arrow (A)", "rect": "Rectangle (R)"}

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        self.root.configure(bg="black")

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"{screen_w}x{screen_h}+0+0")

        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.tool = "freehand"
        self.color = "#ff3333"
        self.line_width = 3
        self.start_x = None
        self.start_y = None
        self.preview_id = None
        self.drawn_ids = []

        # Toolbar background
        bar_w, bar_h = 360, 32
        bar_x = (screen_w - bar_w) // 2
        bar_y = 6
        self.canvas.create_rectangle(
            bar_x, bar_y, bar_x + bar_w, bar_y + bar_h,
            fill="#1a1a2e", outline="#333355", width=1,
        )
        self.tool_label = self.canvas.create_text(
            screen_w // 2, bar_y + bar_h // 2,
            text="[F] Freehand  [A] Arrow  [R] Rect  [C] Clear  [Esc] Close",
            fill="#cccccc", font=("Segoe UI", 9),
        )

        # Bindings
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("f", lambda e: self._set_tool("freehand"))
        self.root.bind("a", lambda e: self._set_tool("arrow"))
        self.root.bind("r", lambda e: self._set_tool("rect"))
        self.root.bind("c", lambda e: self._clear_all())
        self.root.bind("1", lambda e: self._set_color("#ff3333"))
        self.root.bind("2", lambda e: self._set_color("#33ff33"))
        self.root.bind("3", lambda e: self._set_color("#3399ff"))
        self.root.bind("4", lambda e: self._set_color("#ffff33"))
        self.root.bind("5", lambda e: self._set_color("#ffffff"))

    def _set_tool(self, tool):
        self.tool = tool

    def _set_color(self, color):
        self.color = color

    def _clear_all(self):
        for item_id in self.drawn_ids:
            self.canvas.delete(item_id)
        self.drawn_ids.clear()

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.tool == "freehand":
            # start freehand path
            pass

    def on_drag(self, event):
        if self.tool == "freehand":
            if self.start_x is not None:
                line_id = self.canvas.create_line(
                    self.start_x, self.start_y, event.x, event.y,
                    fill=self.color, width=self.line_width, smooth=True,
                    capstyle=tk.ROUND, joinstyle=tk.ROUND,
                )
                self.drawn_ids.append(line_id)
                self.start_x = event.x
                self.start_y = event.y
        elif self.tool in ("arrow", "rect"):
            if self.preview_id:
                self.canvas.delete(self.preview_id)
            if self.tool == "rect":
                self.preview_id = self.canvas.create_rectangle(
                    self.start_x, self.start_y, event.x, event.y,
                    outline=self.color, width=self.line_width,
                )
            else:
                self.preview_id = self._draw_arrow(
                    self.start_x, self.start_y, event.x, event.y,
                )

    def on_release(self, event):
        if self.tool in ("arrow", "rect"):
            if self.preview_id:
                self.drawn_ids.append(self.preview_id)
                self.preview_id = None
        self.start_x = None
        self.start_y = None

    def _draw_arrow(self, x1, y1, x2, y2):
        angle = math.atan2(y2 - y1, x2 - x1)
        head_len = 18
        head_angle = math.pi / 7

        # Arrow head points
        lx = x2 - head_len * math.cos(angle - head_angle)
        ly = y2 - head_len * math.sin(angle - head_angle)
        rx = x2 - head_len * math.cos(angle + head_angle)
        ry = y2 - head_len * math.sin(angle + head_angle)

        # Draw line + head as one polygon
        arrow_id = self.canvas.create_line(
            x1, y1, x2, y2,
            fill=self.color, width=self.line_width,
            arrow=tk.LAST, arrowshape=(head_len, head_len + 4, 6),
        )
        return arrow_id

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    DrawOverlay().run()
