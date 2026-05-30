"""
temp_bar.py — 温度区间条 (标注最高/最低温度)

依赖:  pip install pillow numpy
运行:  python temp_bar.py
输入:  weather.json
输出:  temp_bar.png  (1000x150, 透明背景)
"""

import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(__file__)
WEATHER_JSON = os.path.join(BASE_DIR, "weather.json")
OUTPUT_PNG = os.path.join(BASE_DIR, "temp_bar.png")
W, H = 1000, 150


def _font(size):
    for p in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def interp_color(t):
    """温度色: 0=蓝 → 0.5=绿/黄 → 1=橙/红"""
    if t < 0.25:
        s = t / 0.25; return int(70+100*s), int(130+100*s), int(220-30*s)
    elif t < 0.5:
        s = (t-0.25)/0.25; return int(170+85*s), int(230-60*s), int(190-100*s)
    elif t < 0.75:
        s = (t-0.5)/0.25; return int(255), int(170-70*s), int(90-30*s)
    else:
        s = (t-0.75)/0.25; return int(255), int(100-70*s), int(60-30*s)


def generate_temp_bar():
    with open(WEATHER_JSON, "r", encoding="utf-8") as f:
        d = json.load(f)
    temps = [h["weather"]["temp"] for h in d.get("hours", [])
             if h["weather"].get("temp") is not None]
    if not temps:
        return
    t_min = min(temps)
    t_max = max(temps)

    # 扩展 2°C 作为视觉边距
    t_low = int(t_min - 2)
    t_high = int(t_max + 2)
    t_range = t_high - t_low

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ---- 渐变温度条 ----
    bar_x, bar_w = 80, 840
    bar_y, bar_h = 60, 30
    radius = 15

    # 逐像素绘制渐变
    for px in range(bar_w):
        t = px / bar_w                         # [0, 1]
        r, g, b = interp_color(t)
        x = bar_x + px
        for dy in range(bar_h):
            # 圆角: 检查是否在圆角区域内
            rel_y = dy
            if rel_y < radius:
                edge = radius - (radius**2 - (radius - rel_y)**2)**0.5 if radius > rel_y else 0
                if px < edge or px > bar_w - edge:
                    continue
            elif rel_y > bar_h - radius:
                from_bottom = bar_h - rel_y
                edge = radius - (radius**2 - (radius - from_bottom)**2)**0.5 if radius > from_bottom else 0
                if px < edge or px > bar_w - edge:
                    continue
            img.putpixel((x, bar_y + dy), (r, g, b, 255))

    # ---- 最低温标记 (左侧蓝点) ----
    min_x = bar_x + int(bar_w * (t_min - t_low) / t_range)
    r_min = 10
    draw.ellipse([min_x-r_min, bar_y-r_min, min_x+r_min, bar_y-r_min],
                 fill=(70, 160, 230, 255))
    font_v = _font(28)
    label_min = f"{t_min:.0f}°"
    bbox = draw.textbbox((0, 0), label_min, font=font_v)
    tw = bbox[2] - bbox[0]
    tx = max(10, min(min_x - tw//2, W - tw - 10))
    draw.text((tx, 16), label_min, font=font_v, fill=(40, 40, 40, 255))
    draw.text((tx, 100), "最低", font=_font(20), fill=(100, 100, 100, 255))

    # ---- 最高温标记 (右侧红点) ----
    max_x = bar_x + int(bar_w * (t_max - t_low) / t_range)
    draw.ellipse([max_x-r_min, bar_y-r_min, max_x+r_min, bar_y-r_min],
                 fill=(230, 80, 50, 255))
    label_max = f"{t_max:.0f}°"
    bbox2 = draw.textbbox((0, 0), label_max, font=font_v)
    tw2 = bbox2[2] - bbox2[0]
    tx2 = max(10, min(max_x - tw2//2, W - tw2 - 10))
    draw.text((tx2, 16), label_max, font=font_v, fill=(40, 40, 40, 255))
    draw.text((tx2, 100), "最高", font=_font(20), fill=(100, 100, 100, 255))

    img.save(OUTPUT_PNG)
    print(f"温度区间条已保存: {OUTPUT_PNG}")
    print(f"  范围: {t_min:.1f}°C ~ {t_max:.1f}°C")


if __name__ == "__main__":
    generate_temp_bar()
