"""
humidity_bar.py — 湿度可视化进度条 (简约现代风格, 标准圆角矩形)

依赖:  pip install pillow
运行:  python humidity_bar.py
输入:  weather.json
输出:  humidity_bar.png  (2000x500, 透明背景)
"""

import json, os
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(__file__)
WEATHER_JSON = os.path.join(BASE_DIR, "weather.json")
OUTPUT_PNG = os.path.join(BASE_DIR, "humidity_bar.png")

# ---- 体感标签 ----
def comfort_label(h):
    if h < 30:  return "干燥", (91, 160, 208)
    if h < 50:  return "舒适", (95, 186, 138)
    if h < 70:  return "适中", (192, 176, 64)
    if h < 85:  return "微潮", (224, 144, 64)
    return "闷热", (208, 85, 80)

# ---- 中文字体 ----
def _font(size):
    for p in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def draw_humidity_bar():
    # ---- 读取数据 ----
    with open(WEATHER_JSON, "r", encoding="utf-8") as f:
        d = json.load(f)
    vals = [h["weather"]["humidity"] for h in d.get("hours", [])
            if h["weather"].get("humidity") is not None]
    humidity = sum(vals) / len(vals) if vals else 50

    label, rgb = comfort_label(humidity)
    color_hex = "#{:02x}{:02x}{:02x}".format(*rgb)

    # ---- 2000x500 透明画布 ----
    W, H = 2000, 500
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ---- 顶部居中标题 ----
    font_title = _font(72)
    title_text = "湿度"
    tbox = draw.textbbox((0, 0), title_text, font=font_title)
    tw = tbox[2] - tbox[0]
    draw.text((W//2 - tw//2, 30), title_text, font=font_title, fill=(44, 44, 44, 255))

    # ---- 湿度百分比 ----
    font_pct = _font(58)
    pct_text = f"{humidity:.0f}%"
    bbox = draw.textbbox((0, 0), pct_text, font=font_pct)
    pct_w = bbox[2] - bbox[0]
    draw.text((W//2 - pct_w//2, 120), pct_text, font=font_pct, fill=(*rgb, 255))

    # ---- 体感标签 ----
    font_feel = _font(30)
    feel_text = f"体感 {label}"
    bbox = draw.textbbox((0, 0), feel_text, font=font_feel)
    feel_w = bbox[2] - bbox[0]
    draw.text((W//2 - feel_w//2, 195), feel_text, font=font_feel,
              fill=(100, 100, 100, 255))

    # ---- 标准圆角矩形进度条 ----
    bar_x, bar_y = 100, 290
    bar_w, bar_h = 1800, 50
    radius = 25   # 圆角半径 = bar_h/2, 两端呈半圆形

    # 灰色背景条 (完整圆角矩形)
    draw.rounded_rectangle(
        [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
        radius=radius, fill=(232, 232, 234, 255),
    )

    # 浅蓝色填充条: 在独立层画完整圆角矩形, 然后裁切到填充宽度
    fill_w = int(bar_w * humidity / 100)
    if fill_w > 0:
        fill_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fill_draw = ImageDraw.Draw(fill_layer)
        fill_draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
            radius=radius, fill=(126, 184, 218, 255),
        )
        # 裁切: 只保留填充宽度部分
        fill_layer = fill_layer.crop((0, 0, bar_x + fill_w, H))
        img.paste(fill_layer, (0, 0), fill_layer)

    # ---- 保存 ----
    img.save(OUTPUT_PNG)
    print(f"湿度进度条已保存: {OUTPUT_PNG}")
    print(f"  平均湿度: {humidity:.1f}%  体感: {label}")


if __name__ == "__main__":
    draw_humidity_bar()
