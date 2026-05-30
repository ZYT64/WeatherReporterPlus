"""
warning_panel.py — 预警信息面板

依赖:  pip install pillow
运行:  python warning_panel.py
输入:  weather.json
输出:  warning_panel.png  (2000x1167, 透明背景)
"""

import json, os
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(__file__)
WEATHER_JSON = os.path.join(BASE_DIR, "weather.json")
OUTPUT_PNG = os.path.join(BASE_DIR, "warning_panel.png")
W, H = 2000, 1167


def _font(size):
    for p in [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _draw_centered_text(draw, text, y, font, fill, max_width=1800):
    """在 y 处居中绘制文字，自动换行以适应 max_width。返回占用的总高度。"""
    lines = []
    # 按字符逐行拆分
    current = ""
    for ch in text:
        test = current + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)

    total_h = 0
    line_h = font.size + 8
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((W // 2 - tw // 2, y + total_h), line, font=font, fill=fill)
        total_h += line_h
    return total_h


def generate_warning_panel():
    with open(WEATHER_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    warnings = data.get("warnings", [])
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ---- 标题: 居中 ----
    font_title = _font(64)
    title = "预警信息"
    tbox = draw.textbbox((0, 0), title, font=font_title)
    tw = tbox[2] - tbox[0]
    draw.text((W // 2 - tw // 2, 60), title, font=font_title, fill=(44, 44, 44, 255))

    # ---- 分隔线 ----
    line_y = 150
    draw.line([(W // 2 - 200, line_y), (W // 2 + 200, line_y)],
              fill=(150, 150, 150, 180), width=2)

    if not warnings:
        # ---- 暂无预警 ----
        font_none = _font(48)
        none_text = "暂无预警"
        nbox = draw.textbbox((0, 0), none_text, font=font_none)
        nw = nbox[2] - nbox[0]
        draw.text((W // 2 - nw // 2, H // 2 - 40), none_text,
                  font=font_none, fill=(100, 100, 100, 255))
    else:
        # ---- 有预警: 逐条显示 ----
        y = 220
        max_w = W - 200  # 左右各留100px边距

        for i, w in enumerate(warnings):
            title_text = w.get("title", "未知预警")
            issued = w.get("issued", "")

            # 预警标题 (较大字号)
            font_warn = _font(32)
            if len(warnings) <= 3:
                font_warn = _font(40)
            elif len(warnings) <= 6:
                font_warn = _font(34)

            # 序号 + 标题
            prefix = f"{i + 1}. "
            full_text = prefix + title_text

            text_h = _draw_centered_text(draw, full_text, y, font_warn,
                                         fill=(200, 60, 50, 255),
                                         max_width=max_w)
            y += text_h + 4

            # 发布时间
            if issued:
                font_time = _font(22)
                time_text = f"发布时间: {issued}"
                tbox = draw.textbbox((0, 0), time_text, font=font_time)
                tw_t = tbox[2] - tbox[0]
                draw.text((W // 2 - tw_t // 2, y), time_text,
                          font=font_time, fill=(100, 100, 100, 255))
                y += 36

            y += 24  # 条间距

            # 防止溢出
            if y > H - 80:
                break

    img.save(OUTPUT_PNG)
    count = len(warnings)
    print(f"预警面板已保存: {OUTPUT_PNG}  ({W}x{H})")
    print(f"  预警: {count} 条" if count else "  预警: 无")


if __name__ == "__main__":
    generate_warning_panel()
