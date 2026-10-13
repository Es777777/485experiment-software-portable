"""Annotate screenshots with red rectangles, arrows, and Chinese labels
for the user manual."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "manual_assets" / "screenshots"
OUTPUT_DIR = ROOT / "manual_assets" / "annotated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]


def find_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, 26)
            except OSError:
                continue
    return ImageFont.load_default()


FONT = find_font()
FONT_SMALL = find_font()
try:
    FONT_SMALL = ImageFont.truetype(FONT.path, 20)
except AttributeError:
    pass

RED = (220, 38, 38)
DARK_RED = (160, 20, 20)
WHITE = (255, 255, 255)
SHADOW = (0, 0, 0, 90)


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    if hasattr(draw, "textbbox"):
        l, t, r, b = draw.textbbox((0, 0), text, font=font)
        return r - l, b - t
    return draw.textsize(text, font=font)


def annotate(
    input_name: str,
    output_name: str,
    boxes: list[tuple[int, int, int, int, str]],
    arrows: list[tuple[int, int, int, int, str]] | None = None,
    title: str | None = None,
):
    """Draw outlined boxes with Chinese labels, and optional arrow callouts.

    boxes: list of (x1, y1, x2, y2, label) tuples in image coordinates.
    arrows: list of (target_x, target_y, label_x, label_y, label).
    """
    src = Image.open(INPUT_DIR / input_name).convert("RGBA")
    overlay = Image.new("RGBA", src.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for box in boxes:
        x1, y1, x2, y2, label = box
        draw.rectangle([x1, y1, x2, y2], outline=RED, width=4)

    if title:
        # Render title bar at top
        title_h = 56
        draw.rectangle([0, 0, src.width, title_h], fill=(0, 0, 0, 180))
        title_font = FONT
        try:
            title_font = ImageFont.truetype(FONT.path, 30)
        except AttributeError:
            pass
        tw, th = _text_size(draw, title, title_font)
        draw.text(((src.width - tw) // 2, (title_h - th) // 2 - 2), title,
                  fill=WHITE, font=title_font)

    # Draw labels (with shadow for readability)
    label_overlay = Image.new("RGBA", src.size, (0, 0, 0, 0))
    label_draw = ImageDraw.Draw(label_overlay)
    for box in boxes:
        x1, y1, x2, y2, label = box
        lw, lh = _text_size(label_draw, label, FONT)
        pad = 6
        lx = x1
        ly = max(0, y1 - lh - 2 * pad)
        # Background pill
        label_draw.rectangle(
            [lx, ly, lx + lw + 2 * pad, ly + lh + 2 * pad],
            fill=(220, 38, 38, 235),
        )
        label_draw.text((lx + pad, ly + pad), label, fill=WHITE, font=FONT)

    if arrows:
        for arrow in arrows:
            tx, ty, lx, ly, label = arrow
            # Arrow line
            ax, ay = lx + 60, ly + 30  # source near label
            # Draw a line + arrowhead
            draw.line([(ax, ay), (tx, ty)], fill=DARK_RED, width=4)
            # Arrowhead
            import math
            angle = math.atan2(ty - ay, tx - ax)
            head_len = 18
            h1 = (tx - head_len * math.cos(angle - math.pi / 7),
                  ty - head_len * math.sin(angle - math.pi / 7))
            h2 = (tx - head_len * math.cos(angle + math.pi / 7),
                  ty - head_len * math.sin(angle + math.pi / 7))
            draw.polygon([(tx, ty), h1, h2], fill=DARK_RED)

            # Label background
            lw, lh = _text_size(label_draw, label, FONT)
            label_draw.rectangle(
                [lx, ly, lx + lw + 12, ly + lh + 12],
                fill=(220, 38, 38, 235),
            )
            label_draw.text((lx + 6, ly + 6), label, fill=WHITE, font=FONT)

    out = Image.alpha_composite(src, overlay)
    out = Image.alpha_composite(out, label_overlay)
    out.convert("RGB").save(OUTPUT_DIR / output_name, "PNG", optimize=True)


def main() -> int:
    # 1) Launcher main
    # NOTE: 红框坐标基于 v1.0.3 启动器布局（双 COM：485 串口 + PWM 串口）。
    # 修改启动器布局后请重新执行 `py manual_assets/capture_screenshots.py`
    # 重拍 launcher_main.png，再让本脚本重画红框。
    annotate(
        "launcher_main.png",
        "launcher_main_annotated.png",
        boxes=[
            (480, 110, 1310, 175, "顶部 Tab 栏: 选择功能模块"),
            (480, 200, 1310, 380, "485 采集配置区: 配置文件 / 串口"),
            (480, 400, 1310, 560, "PWM 串口: 独立 COM 口（v1.0.3 新增）"),
            (480, 580, 1310, 720, "采集选项: 一次性 / 平滑 / 实时窗口"),
            (480, 740, 1310, 870, "启动按钮: 普通采集 / 实时曲线 / 停止"),
        ],
        title="启动器主界面 (图 1)",
    )

    # 2) Live plot with measurement panel
    annotate(
        "live_plot_moment_panel.png",
        "live_plot_moment_panel_annotated.png",
        boxes=[
            (50, 60, 1380, 600, "实时曲线窗口: ch1/ch2/ch3 与 total_force"),
            (1480, 60, 1900, 600, "测量操作面板: PWM / 电流 / 开始·结束"),
            (50, 640, 1900, 950, "历史测量记录 (序号·PWM·电流·力矩)"),
        ],
        title="实时曲线与分组测量界面 (图 2)",
    )

    # 3) Moment formula panel
    annotate(
        "moment_formula_panel.png",
        "moment_formula_panel_annotated.png",
        boxes=[
            (200, 220, 1280, 500, "力矩公式区: M_y / M_x / M / θ"),
        ],
        title="力矩公式显示区 (图 3)",
    )

    # 4) Portable exe main
    annotate(
        "portable_exe_main.png",
        "portable_exe_main_annotated.png",
        boxes=[
            (60, 60, 1380, 1100, "便携版主窗口: 解压后双击运行"),
        ],
        title="便携版软件主界面 (图 4)",
    )

    print("Saved annotated screenshots to", OUTPUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
