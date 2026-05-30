"""
chart_wind.py — 风向风速图标映射 & 精灵图生成

功能:
  1. PIL 程序化绘制 8 个风向箭头（北/东北/东/东南/南/西南/西/西北）
  2. 风向角度 → 中文名称 映射表
  3. 风速 m/s → 蒲福风级中文名
  4. 生成 4338×100 水平精灵图（箭头等距平铺 + 中文标签）

用法:
    python chart_wind.py          # 生成 sprite_wind.png
"""

from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
OUTPUT_SPRITE = os.path.join(BASE_DIR, "sprite_wind.png")
ARROW_DIR = os.path.join(BASE_DIR, "icons", "wind_arrows")
ARROW_SIZE = 128  # 箭头图标正方形边长 (高分辨率渲染)


# ---------------------------------------------------------------------------
# 风向映射：角度 → (中文名, 英文名, 角度)
# ---------------------------------------------------------------------------
WIND_DIRECTION_MAP: Dict[str, Tuple[str, str, float]] = {
    #  key       (中文,   英文,        角度)
    "N":   ("北风",   "North",       0),
    "NE":  ("东北风", "Northeast",   45),
    "E":   ("东风",   "East",        90),
    "SE":  ("东南风", "Southeast",   135),
    "S":   ("南风",   "South",       180),
    "SW":  ("西南风", "Southwest",   225),
    "W":   ("西风",   "West",        270),
    "NW":  ("西北风", "Northwest",   315),
}

WIND_DIR_ORDER = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def wind_direction_name(degrees: float) -> str:
    """将风向角度 (0=北, 顺时针) 转为中文名称。"""
    idx = round(degrees / 45) % 8
    key = WIND_DIR_ORDER[idx]
    return WIND_DIRECTION_MAP[key][0]


# ---------------------------------------------------------------------------
# 风速 → 蒲福风级
# ---------------------------------------------------------------------------
BEAUFORT_LABELS: Dict[int, str] = {
    0: "无风", 1: "软风", 2: "轻风", 3: "微风",
    4: "和风", 5: "清风", 6: "强风", 7: "疾风",
    8: "大风", 9: "烈风", 10: "狂风", 11: "暴风", 12: "飓风",
}


def beaufort_label(speed_ms: float) -> str:
    """将风速 (m/s) 转为蒲福风级中文名。"""
    thresholds = [0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7, 999]
    for level, limit in enumerate(thresholds):
        if speed_ms < limit:
            return BEAUFORT_LABELS.get(level, f"{level}级")
    return "飓风"


# ---------------------------------------------------------------------------
# 中文字体
# ---------------------------------------------------------------------------
def _find_chinese_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# 程序化绘制风向箭头
# ---------------------------------------------------------------------------
def _draw_arrow(
    size: int,
    angle_deg: float,
    fg: Tuple[int, int, int, int] = (100, 180, 255, 255),
    bg: Tuple[int, int, int, int] = (0, 0, 0, 0),
) -> Image.Image:
    """绘制指向指定角度的箭头图标。

    0°=上(北), 90°=右(东), 顺时针。
    """
    img = Image.new("RGBA", (size, size), bg)
    draw = ImageDraw.Draw(img)

    cx, cy = size / 2, size / 2
    margin = 4
    arrow_len = size / 2 - margin
    head_len = arrow_len * 0.45
    stem_hw = 6  # 箭杆半宽（加粗）
    wing = head_len * 0.8    # 箭头翼展（加大）

    rad = math.radians(-angle_deg + 90)

    # 尖端
    tip_x = cx + arrow_len * math.cos(rad)
    tip_y = cy - arrow_len * math.sin(rad)
    # 尾部
    stem_len = arrow_len - head_len * 0.5
    tail_x = cx - stem_len * math.cos(rad)
    tail_y = cy + stem_len * math.sin(rad)
    # 箭头基部
    base_x = tip_x - head_len * math.cos(rad)
    base_y = tip_y + head_len * math.sin(rad)

    perp = rad + math.pi / 2
    wing1_x = base_x + wing * math.cos(perp)
    wing1_y = base_y - wing * math.sin(perp)
    wing2_x = base_x - wing * math.cos(perp)
    wing2_y = base_y + wing * math.sin(perp)

    b1_x = base_x + stem_hw * math.cos(perp)
    b1_y = base_y - stem_hw * math.sin(perp)
    b2_x = base_x - stem_hw * math.cos(perp)
    b2_y = base_y + stem_hw * math.sin(perp)
    t1_x = tail_x + stem_hw * math.cos(perp)
    t1_y = tail_y - stem_hw * math.sin(perp)
    t2_x = tail_x - stem_hw * math.cos(perp)
    t2_y = tail_y + stem_hw * math.sin(perp)

    polygon = [
        (tip_x, tip_y),
        (wing1_x, wing1_y), (b1_x, b1_y), (t1_x, t1_y),
        (tail_x, tail_y),
        (t2_x, t2_y), (b2_x, b2_y), (wing2_x, wing2_y),
    ]
    draw.polygon(polygon, fill=fg, outline=(0, 0, 0, 80))

    return img


def generate_wind_arrows(
    size: int = ARROW_SIZE,
    output_dir: Optional[str] = None,
) -> list[str]:
    """生成全部 8 个风向箭头 PNG。"""
    if output_dir is None:
        output_dir = ARROW_DIR
    os.makedirs(output_dir, exist_ok=True)

    filenames = []
    for key in WIND_DIR_ORDER:
        _, _, angle = WIND_DIRECTION_MAP[key]
        img = _draw_arrow(size, angle)
        fname = f"wind_{key.lower()}.png"
        img.save(os.path.join(output_dir, fname))
        filenames.append(fname)

    return filenames


def all_wind_icons() -> list[str]:
    """返回所有风向箭头文件名（按角度排序）。"""
    if not os.path.exists(ARROW_DIR) or not os.listdir(ARROW_DIR):
        generate_wind_arrows()
    return [f"wind_{k.lower()}.png" for k in WIND_DIR_ORDER]


# ---------------------------------------------------------------------------
# 风速文字图标 (X级)
# ---------------------------------------------------------------------------
SPEED_DIR = os.path.join(BASE_DIR, "icons", "wind_speeds")


def _make_speed_text_icon(size: int, level: int) -> Image.Image:
    """生成纯文字图标：'X级' 居中。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _find_chinese_font(size // 3)
    text = f"{level}级"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cx, cy = size // 2, size // 2
    draw.text((cx - tw//2 + 1, cy - th//2 + 1), text, font=font, fill=(0,0,0,120))
    draw.text((cx - tw//2, cy - th//2), text, font=font, fill=(255,255,255,230))
    return img


def all_speed_icons() -> list[str]:
    """生成 0~12 级风速文字图标。"""
    os.makedirs(SPEED_DIR, exist_ok=True)
    filenames = []
    for lv in range(13):
        fname = f"speed_{lv:02d}.png"
        path = os.path.join(SPEED_DIR, fname)
        if not os.path.exists(path):
            _make_speed_text_icon(128, lv).save(path)
        filenames.append(fname)
    return filenames


# ---------------------------------------------------------------------------
# 图标 → 中文标签
# ---------------------------------------------------------------------------
def _wind_icon_label(fname: str) -> str:
    for key in WIND_DIRECTION_MAP:
        if key.lower() in fname.lower():
            return WIND_DIRECTION_MAP[key][0]
    if fname.startswith("speed_"):
        lv = int(fname.replace("speed_", "").replace(".png", ""))
        return f"{lv}级"
    return fname.replace(".png", "")


# ---------------------------------------------------------------------------
# 精灵图生成
# ---------------------------------------------------------------------------
def generate_wind_sprite_sheet(
    icon_names: Optional[list[str]] = None,
    canvas_width: int = 4338,
    canvas_height: int = 100,
    icon_size: int = 48,
    font_size: int = 16,
    text_color=(255, 255, 255, 230),
    output_path: Optional[str] = None,
    background_color=(0, 0, 0, 0),
) -> Image.Image:
    """生成风向精灵图：箭头 + 中文标签，等距平铺。

    参数同 chart_weather.generate_sprite_sheet()。
    """
    if icon_names is None:
        icon_names = all_wind_icons()

    if not os.path.isdir(ARROW_DIR) or not os.listdir(ARROW_DIR):
        generate_wind_arrows()
    missing = [n for n in icon_names
               if not os.path.exists(os.path.join(ARROW_DIR, n))]
    if missing:
        generate_wind_arrows()

    n = len(icon_names)
    if n == 0:
        raise ValueError("图标列表为空")

    canvas = Image.new("RGBA", (canvas_width, canvas_height), background_color)
    draw = ImageDraw.Draw(canvas)
    font = _find_chinese_font(font_size)

    slot_width = canvas_width // n
    icon_area_top = 4

    for i, fname in enumerate(icon_names):
        path = os.path.join(ARROW_DIR, fname)
        icon = Image.open(path).convert("RGBA")
        if icon.size != (icon_size, icon_size):
            icon = icon.resize((icon_size, icon_size), Image.LANCZOS)

        slot_center_x = slot_width * i + slot_width // 2
        icon_x = slot_center_x - icon_size // 2
        canvas.paste(icon, (icon_x, icon_area_top), icon)

        label = _wind_icon_label(fname)
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_x = slot_center_x - text_w // 2
        text_y = icon_area_top + icon_size + 2

        draw.text((text_x + 1, text_y + 1), label, font=font, fill=(0, 0, 0, 180))
        draw.text((text_x, text_y), label, font=font, fill=text_color)

    if output_path is not None:
        canvas.save(output_path)
        print(f"精灵图已保存: {output_path}")
        print(f"  画布: {canvas_width}x{canvas_height}")
        print(f"  图标数: {n}  |  每槽宽: {slot_width}px  |  图标尺寸: {icon_size}px")

    return canvas


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from PIL import Image as PILImage

    dir_icons = all_wind_icons()
    spd_icons = all_speed_icons()
    all_icons = dir_icons + spd_icons  # 8 方向 + 13 风速 = 21

    print("风向箭头 + 风速等级:")
    for fname in all_icons:
        label = _wind_icon_label(fname)
        print(f"  {fname}  ->  {label}")

    n = len(all_icons)
    canvas = PILImage.new("RGBA", (4338, 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font_dir = _find_chinese_font(15)
    font_spd = _find_chinese_font(13)

    slot = 4338 // n
    icon_size = 42
    icon_y = 4
    dir_y = icon_y + icon_size + 4
    spd_y = dir_y + 17

    for i, fname in enumerate(all_icons):
        if fname.startswith("speed_"):
            path = os.path.join(SPEED_DIR, fname)
        else:
            path = os.path.join(ARROW_DIR, fname)

        icon = PILImage.open(path).convert("RGBA")
        icon = icon.resize((icon_size, icon_size), PILImage.LANCZOS)
        cx = slot * i + slot // 2

        # 图标
        canvas.paste(icon, (cx - icon_size // 2, icon_y), icon)

        # 风向名
        if fname.startswith("speed_"):
            dir_label = "—"
        else:
            dir_label = _wind_icon_label(fname)
        bbox = draw.textbbox((0, 0), dir_label, font=font_dir)
        dw = bbox[2] - bbox[0]
        draw.text((cx - dw//2 + 1, dir_y + 1), dir_label, font=font_dir, fill=(0,0,0,180))
        draw.text((cx - dw//2, dir_y), dir_label, font=font_dir, fill=(255,255,255,230))

        # 风速: 统一 "X级"
        if fname.startswith("speed_"):
            lv = int(fname.replace("speed_", "").replace(".png", ""))
            spd_label = f"{lv}级"
        else:
            spd_label = f"{i}级"
        bbox2 = draw.textbbox((0, 0), spd_label, font=font_spd)
        sw = bbox2[2] - bbox2[0]
        draw.text((cx - sw//2 + 1, spd_y + 1), spd_label, font=font_spd, fill=(0,0,0,130))
        draw.text((cx - sw//2, spd_y), spd_label, font=font_spd, fill=(200,200,200,210))

    canvas.save(OUTPUT_SPRITE)
    print(f"\n精灵图已保存: {OUTPUT_SPRITE}")
    print(f"  画布: 4338x120  |  槽数: {n}  |  每槽: {slot}px")
    print(f"  格式: [图标] / 风向 / X级")
    print(f"  风向: {len(dir_icons)} 个  +  风速: {len(spd_icons)} 个 (0~12级)")
