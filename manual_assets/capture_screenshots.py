from __future__ import annotations

import os
import subprocess
import sys
import time
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageGrab


ROOT = Path(__file__).resolve().parent.parent
LATEST_ROOT = ROOT / ".worktrees" / "grouped-pwm-measurement"
OUTPUT_DIR = ROOT / "manual_assets" / "screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _window_rect(hwnd: int) -> tuple[int, int, int, int]:
    import ctypes
    import ctypes.wintypes

    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def _print_window(hwnd: int) -> Image.Image:
    import ctypes
    import ctypes.wintypes

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32),
            ("biWidth", ctypes.c_long),
            ("biHeight", ctypes.c_long),
            ("biPlanes", ctypes.c_ushort),
            ("biBitCount", ctypes.c_ushort),
            ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32),
            ("biXPelsPerMeter", ctypes.c_long),
            ("biYPelsPerMeter", ctypes.c_long),
            ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ("bmiHeader", BITMAPINFOHEADER),
            ("bmiColors", ctypes.c_uint32 * 3),
        ]

    left, top, right, bottom = _window_rect(hwnd)
    width = right - left
    height = bottom - top
    hwnd_dc = ctypes.windll.user32.GetWindowDC(hwnd)
    mfc_dc = ctypes.windll.gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = ctypes.windll.gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
    ctypes.windll.gdi32.SelectObject(mfc_dc, bitmap)

    PW_RENDERFULLCONTENT = 0x00000002
    ok = ctypes.windll.user32.PrintWindow(hwnd, mfc_dc, PW_RENDERFULLCONTENT)
    if ok != 1:
        ctypes.windll.user32.PrintWindow(hwnd, mfc_dc, 0)

    bmpinfo = BITMAPINFO()
    bmpinfo.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmpinfo.bmiHeader.biWidth = width
    bmpinfo.bmiHeader.biHeight = -height
    bmpinfo.bmiHeader.biPlanes = 1
    bmpinfo.bmiHeader.biBitCount = 32
    bmpinfo.bmiHeader.biCompression = 0

    buffer_len = width * height * 4
    buffer = (ctypes.c_byte * buffer_len)()
    ctypes.windll.gdi32.GetDIBits(
        mfc_dc,
        bitmap,
        0,
        height,
        ctypes.byref(buffer),
        ctypes.byref(bmpinfo),
        0,
    )

    image = Image.frombuffer(
        "RGBA",
        (width, height),
        bytes(buffer),
        "raw",
        "BGRA",
        0,
        1,
    )

    ctypes.windll.gdi32.DeleteObject(bitmap)
    ctypes.windll.gdi32.DeleteDC(mfc_dc)
    ctypes.windll.user32.ReleaseDC(hwnd, hwnd_dc)
    return image.convert("RGB")


def capture_widget(widget: tk.Misc, output_path: Path) -> None:
    widget.update_idletasks()
    widget.update()
    widget.lift()
    widget.attributes("-topmost", True)
    widget.update()
    time.sleep(0.6)
    try:
        image = _print_window(widget.winfo_id())
    except Exception:
        x = widget.winfo_rootx()
        y = widget.winfo_rooty()
        width = widget.winfo_width()
        height = widget.winfo_height()
        image = ImageGrab.grab((x, y, x + width, y + height))
    finally:
        widget.attributes("-topmost", False)
        widget.update()
    image.save(output_path)


def capture_process_window(title_keyword: str, output_path: Path, proc: subprocess.Popen[str]) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    deadline = time.time() + 20
    matched_hwnd = None

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd, _lparam):
        nonlocal matched_hwnd
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        if title_keyword in title:
            matched_hwnd = hwnd
            return False
        return True

    while time.time() < deadline and proc.poll() is None:
        matched_hwnd = None
        user32.EnumWindows(enum_proc, 0)
        if matched_hwnd:
            user32.ShowWindow(matched_hwnd, 9)
            user32.SetForegroundWindow(matched_hwnd)
            time.sleep(0.8)
            try:
                image = _print_window(matched_hwnd)
            except Exception:
                image = ImageGrab.grab(_window_rect(matched_hwnd))
            image.save(output_path)
            return
        time.sleep(0.4)
    raise RuntimeError(f"Could not find window containing title: {title_keyword}")


def build_live_plot_demo() -> None:
    os.environ["SERIAL_LOGGER_MPL_BACKEND"] = "TkAgg"
    sys.path.insert(0, str(LATEST_ROOT))
    from scripts import serial_logger_with_plot as liveplot  # type: ignore

    plotter = liveplot.LivePlotter(
        ["weight_ch1", "weight_ch2", "weight_ch3"],
        window_seconds=60,
        smooth=False,
    )
    plotter.tare_done = True

    base = datetime(2026, 7, 5, 12, 0, 0)
    samples = [
        {"weight_ch1": 2.0, "weight_ch2": 6.0, "weight_ch3": 4.0},
        {"weight_ch1": 2.5, "weight_ch2": 6.5, "weight_ch3": 4.2},
        {"weight_ch1": 3.0, "weight_ch2": 7.0, "weight_ch3": 4.4},
    ]
    for index, sample in enumerate(samples):
        plotter.add_point(base + timedelta(milliseconds=500 * index), sample)

    plotter.measurement_pwm_var.set("1200")
    plotter.start_measurement()
    for index, sample in enumerate(samples):
        plotter.add_point(base + timedelta(seconds=1, milliseconds=500 * index), sample)
    plotter.measurement_current_var.set("2.50")
    plotter.finish_measurement()
    plotter.set_status("演示界面：已完成一组测量")

    if plotter.measurement_formula_figure is not None:
        plotter.measurement_formula_figure.savefig(
            OUTPUT_DIR / "moment_formula_panel.png",
            dpi=180,
            bbox_inches="tight",
        )

    manager = getattr(plotter.fig.canvas, "manager", None)
    window = getattr(manager, "window", None)
    if window is None:
        raise RuntimeError("Live plot window is unavailable")
    window.update_idletasks()
    window.update()
    capture_widget(window, OUTPUT_DIR / "live_plot_moment_panel.png")
    plotter.close()


def build_launcher_demo() -> None:
    sys.path.insert(0, str(LATEST_ROOT))
    import app_launcher  # type: ignore

    root = tk.Tk()
    app_launcher.configure_default_fonts(root)
    app = app_launcher.ToolLauncherApp(root)
    root.update_idletasks()
    root.update()
    capture_widget(root, OUTPUT_DIR / "launcher_main.png")
    root.destroy()


def capture_portable_exe() -> None:
    exe_path = LATEST_ROOT / "dist" / "实验软件" / "实验软件.exe"
    if not exe_path.exists():
        return
    proc = subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
    try:
        capture_process_window("实验软件便携版", OUTPUT_DIR / "portable_exe_main.png", proc)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    build_launcher_demo()
    build_live_plot_demo()
    capture_portable_exe()
    print("Saved screenshots to", OUTPUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
