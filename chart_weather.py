"""
chart_weather.py — 天气图标映射 & 精灵图生成

功能:
  1. WMO 天气码 → Dalte123 彩色 PNG 图标 映射表
  2. 月相 → 图标 映射表
  3. 生成 4338×64 水平精灵图（所有图标等距平铺）

用法:
    python chart_weather.py          # 生成 icons/sprite_sheet.png
"""

from __future__ import annotations

import os
from typing import Dict, Optional

from PIL import Image, ImageDraw, ImageFont

# chart_wind 的函数（避免循环导入）
def _lazy_import_wind():
    from chart_wind import (
        wind_direction_name,
        beaufort_label,
        ARROW_DIR as _ARROW_DIR,
        WIND_DIR_ORDER as _WDO,
        WIND_DIRECTION_MAP as _WDM,
        generate_wind_arrows as _gen_arrows,
    )
    return _ARROW_DIR, _WDO, _WDM, _gen_arrows, wind_direction_name, beaufort_label

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
ICONS_PNG = os.path.join(BASE_DIR, "icons", "dalte123", "png", "set1")
OUTPUT_SPRITE = os.path.join(BASE_DIR, "sprite_sheet.png")

# ---------------------------------------------------------------------------
# WMO 天气码 → Dalte123 图标文件名
# ---------------------------------------------------------------------------
WMO_ICON_MAP: Dict[int, str] = {
    # ── 晴 / 云 ──
    0: "clear-day.png",        # 晴天
    1: "partly-cloudy-day.png",# 少云
    2: "cloudy.png",            # 多云
    3: "cloudy.png",            # 阴天

    # ── 雾 ──
    45: "fog.png",              # 雾
    48: "fog.png",              # 冻雾

    # ── 毛毛雨 ──
    51: "rain.png",             # 小毛毛雨
    53: "rain.png",             # 中毛毛雨
    55: "rain.png",             # 大毛毛雨

    # ── 冻毛毛雨 ──
    56: "sleet.png",            # 小冻毛毛雨
    57: "sleet.png",            # 大冻毛毛雨

    # ── 雨 ──
    61: "rain.png",             # 小雨
    63: "rain.png",             # 中雨
    65: "rain.png",             # 大雨

    # ── 冻雨 ──
    66: "sleet.png",            # 小冻雨
    67: "sleet.png",            # 大冻雨

    # ── 雪 ──
    71: "snow.png",             # 小雪
    73: "snow.png",             # 中雪
    75: "snow.png",             # 大雪
    77: "snow.png",             # 雪粒

    # ── 阵雨 ──
    80: "showers-day.png",      # 小阵雨
    81: "showers-day.png",      # 中阵雨
    82: "showers-day.png",      # 大阵雨

    # ── 阵雪 ──
    85: "snow-showers-day.png", # 小阵雪
    86: "snow-showers-day.png", # 大阵雪

    # ── 雷暴 ──
    95: "thunder.png",          # 雷暴
    96: "thunder-rain.png",     # 雷暴伴小冰雹
    99: "thunder-rain.png",     # 雷暴伴大冰雹
}

# 夜间 WMO 码 → 对应夜间图标
WMO_ICON_MAP_NIGHT: Dict[int, str] = {
    0:  "clear-night.png",
    1:  "partly-cloudy-night.png",
    2:  "cloudy.png",
    3:  "cloudy.png",
    45: "fog.png",
    48: "fog.png",
    51: "rain.png",
    53: "rain.png",
    55: "rain.png",
    56: "sleet.png",
    57: "sleet.png",
    61: "rain.png",
    63: "rain.png",
    65: "rain.png",
    66: "sleet.png",
    67: "sleet.png",
    71: "snow.png",
    73: "snow.png",
    75: "snow.png",
    77: "snow.png",
    80: "showers-night.png",
    81: "showers-night.png",
    82: "showers-night.png",
    85: "snow-showers-night.png",
    86: "snow-showers-night.png",
    95: "thunder.png",
    96: "thunder-rain.png",
    99: "thunder-rain.png",
}

# ---------------------------------------------------------------------------
# 月相 → 图标
# ---------------------------------------------------------------------------
MOON_ICON_MAP: Dict[str, Optional[str]] = {
    "新月":      "moon-new.png",
    "蛾眉月":    "moon-waxing-crescent.png",
    "上弦月":    "moon-first-quarter.png",
    "盈凸月":    "moon-waxing-gibbous.png",
    "满月":      "moon-full.png",
    "亏凸月":    "moon-waning-gibbous.png",
    "下弦月":    "moon-last-quarter.png",
    "残月":      "moon-waning-crescent.png",
}

# ---------------------------------------------------------------------------
# 图标文件名 → 中文名称
# ---------------------------------------------------------------------------
ICON_LABEL_MAP: Dict[str, str] = {
    "clear-day.png":           "晴天",
    "clear-night.png":         "晴天",
    "cloudy.png":              "多云",
    "fog.png":                 "雾",
    "partly-cloudy-day.png":   "少云",
    "partly-cloudy-night.png": "少云",
    "rain.png":                "雨",
    "showers-day.png":         "阵雨",
    "showers-night.png":       "阵雨",
    "sleet.png":               "冻雨",
    "snow-showers-day.png":    "阵雪",
    "snow-showers-night.png":  "阵雪",
    "snow.png":                "雪",
    "thunder-rain.png":        "雷暴",
    "thunder.png":             "雷暴",
}


def _find_chinese_font(size: int) -> ImageFont.FreeTypeFont:
    """查找系统中可用的中文字体，找不到则回退到默认字体。"""
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------
def wmo_icon(wmo_code: int, is_night: bool = False) -> str:
    """根据 WMO 天气码返回对应的 Dalte123 图标文件名。"""
    table = WMO_ICON_MAP_NIGHT if is_night else WMO_ICON_MAP
    return table.get(wmo_code, "cloudy.png")


def all_unique_icons() -> list[str]:
    """返回映射表中所有用到的去重图标文件名（日夜合并）。"""
    day = set(WMO_ICON_MAP.values())
    night = set(WMO_ICON_MAP_NIGHT.values())
    return sorted(day | night)


# ---------------------------------------------------------------------------
# 精灵图生成：4338×64 画布，图标等距平铺
# ---------------------------------------------------------------------------
def generate_sprite_sheet(
    icon_names: Optional[list[str]] = None,
    canvas_width: int = 4338,
    canvas_height: int = 100,
    icon_height: int = 52,
    font_size: int = 14,
    text_color=(255, 255, 255, 220),
    output_path: Optional[str] = None,
    background_color=(0, 0, 0, 0),
) -> Image.Image:
    """将图标列表在画布上等距平铺，图标下方显示中文名称，生成水平精灵图。

    Parameters
    ----------
    icon_names : list[str]
        图标文件名列表。为 None 则使用映射表中所有去重图标。
    canvas_width : int
        画布宽度（默认 4338）。
    canvas_height : int
        画布高度（默认 100，包含图标 + 文字空间）。
    icon_height : int
        图标缩放后的高度（保持宽高比），默认 52px。
    font_size : int
        中文标签字号，默认 14。
    text_color : tuple
        文字颜色 RGBA，默认白色半透明。
    output_path : str, optional
        保存路径。为 None 则不保存。
    background_color : tuple
        画布背景色 RGBA，默认全透明。

    Returns
    -------
    PIL.Image — RGBA 精灵图。
    """
    if icon_names is None:
        icon_names = all_unique_icons()

    n = len(icon_names)
    if n == 0:
        raise ValueError("图标列表为空")

    # 透明画布
    canvas = Image.new("RGBA", (canvas_width, canvas_height), background_color)
    draw = ImageDraw.Draw(canvas)
    font = _find_chinese_font(font_size)

    # 每个图标的槽位宽度
    slot_width = canvas_width // n

    # 图标区域顶部距离
    icon_area_top = 4
    icon_area_bottom = icon_area_top + icon_height

    for i, fname in enumerate(icon_names):
        path = os.path.join(ICONS_PNG, fname)
        if not os.path.exists(path):
            print(f"  [WARN] 图标不存在: {fname}")
            continue

        icon = Image.open(path).convert("RGBA")

        # 缩放到目标高度，保持宽高比
        w, h = icon.size
        scale = icon_height / h
        new_w, new_h = int(w * scale), icon_height
        icon = icon.resize((new_w, new_h), Image.LANCZOS)

        # 图标居中放置在槽位上半部分
        slot_center_x = slot_width * i + slot_width // 2
        icon_x = slot_center_x - new_w // 2
        icon_y = icon_area_top

        canvas.paste(icon, (icon_x, icon_y), icon)

        # ---- 文字标签：图标下方居中 ----
        label = ICON_LABEL_MAP.get(fname, fname.replace(".png", ""))
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # 文字放在图标底部下方，居中
        text_x = slot_center_x - text_w // 2
        text_y = icon_area_bottom + 2  # 图标底部留 2px 间距

        # 文字阴影（黑色，略微偏移）
        draw.text((text_x + 1, text_y + 1), label, font=font, fill=(0, 0, 0, 180))
        # 文字本体
        draw.text((text_x, text_y), label, font=font, fill=text_color)

    if output_path is not None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        canvas.save(output_path)
        print(f"精灵图已保存: {output_path}")
        print(f"  画布: {canvas_width}×{canvas_height}")
        print(f"  图标数: {n}  |  每槽宽: {slot_width}px  |  图标高: {icon_height}px  |  字号: {font_size}px")

    return canvas


# ---------------------------------------------------------------------------
# 数据驱动天气图表：读取 weather.json，每列放置真实图标+文字
# ---------------------------------------------------------------------------
WEATHER_JSON = os.path.join(BASE_DIR, "weather.json")


def _is_daytime(hour_str: str, sunrise: str, sunset: str) -> bool:
    """根据日出日落判断当前小时是白天还是夜间。"""
    try:
        h = int(hour_str.split(":")[0])
        sr = int(sunrise.split(":")[0])
        ss = int(sunset.split(":")[0])
        return sr <= h < ss
    except (ValueError, AttributeError):
        return True  # 默认白天


def generate_data_chart(
    canvas_width: int = 4338,
    canvas_height: int = 680,
    output_path: Optional[str] = None,
    supersample: int = 2,
) -> Image.Image:
    """读取 weather.json，为每个小时绘制真实天气数据图表。

    每列从上到下: 时间 / 天气图标 / 天气名称 / 温度 / 风向 / 风速

    使用超采样抗锯齿 (SSAA): supersample× 分辨率渲染再 LANCZOS 缩回。
    """
    import json

    # 加载数据
    with open(WEATHER_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    hours = data["hours"]
    sunrise = data.get("sunrise", "06:00")
    sunset = data.get("sunset", "18:00")
    n = len(hours)

    # 超采样
    ss = max(1, min(supersample, 4))
    rw, rh = canvas_width * ss, canvas_height * ss

    canvas = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # 字体（超采样分辨率）
    font_temp = _find_chinese_font(38 * ss)
    font_wind = _find_chinese_font(30 * ss)
    font_spd  = _find_chinese_font(26 * ss)
    font_vis  = _find_chinese_font(26 * ss)
    font_time = _find_chinese_font(30 * ss)

    slot = rw // n
    icon_size = 56 * ss
    arrow_size = 40 * ss

    # 各行 Y 坐标（超采样）
    margin_top = 12 * ss
    y_time   = margin_top
    y_icon   = y_time + 40 * ss
    y_wxname = y_icon + icon_size + 14 * ss
    y_temp   = y_wxname + 44 * ss
    y_wind   = y_temp + 44 * ss
    y_wind_text = y_wind + arrow_size + 16 * ss
    y_spd       = y_wind_text + 36 * ss
    y_vis       = y_spd + 36 * ss
    y_pres      = y_vis + 36 * ss

    # 确保箭头存在
    (_ARROW_DIR, WIND_DIRS, _WDM, _gen_arrows,
     wind_direction_name, _) = _lazy_import_wind()
    if not os.path.isdir(_ARROW_DIR) or not os.listdir(_ARROW_DIR):
        _gen_arrows()

    for i, hour in enumerate(hours):
        cx = slot * i + slot // 2
        wmo = hour["weather"]["code"]
        temp = hour["weather"]["temp"]
        w_dir = hour["wind"]["direction"]
        w_spd = hour["wind"]["speed"]
        time_str = hour["time"]

        daytime = _is_daytime(time_str, sunrise, sunset)

        # ── 时间 ──
        bbox_t = draw.textbbox((0, 0), time_str, font=font_time)
        draw.text((cx - (bbox_t[2]-bbox_t[0])//2, y_time),
                  time_str, font=font_time, fill=(60, 60, 60, 255))

        # ── 天气图标 ──
        icon_fname = wmo_icon(wmo, is_night=not daytime)
        icon_path = os.path.join(ICONS_PNG, icon_fname)
        if os.path.exists(icon_path):
            icon = Image.open(icon_path).convert("RGBA")
            icon = icon.resize((icon_size, icon_size), Image.LANCZOS)
            canvas.paste(icon, (cx - icon_size//2, y_icon), icon)

        # ── 天气名称 ──
        wx_text = hour["weather"]["text"]
        bbox_n = draw.textbbox((0, 0), wx_text, font=font_spd)
        tw_n = bbox_n[2] - bbox_n[0]
        draw.text((cx - tw_n//2, y_wxname), wx_text, font=font_spd, fill=(50, 50, 50, 255))

        # ── 温度 ──
        temp_text = f"{temp:.0f}°"
        bbox = draw.textbbox((0, 0), temp_text, font=font_temp)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw//2, y_temp), temp_text, font=font_temp, fill=(40, 40, 40, 255))

        # ── 风向箭头 ──
        idx = round(w_dir / 45) % 8
        wind_key = WIND_DIRS[idx]
        arr_path = os.path.join(_ARROW_DIR, f"wind_{wind_key.lower()}.png")
        if os.path.exists(arr_path):
            arrow = Image.open(arr_path).convert("RGBA")
            arrow = arrow.resize((arrow_size, arrow_size), Image.LANCZOS)
            canvas.paste(arrow, (cx - arrow_size//2, y_wind - 2), arrow)

        # ── 风向文字 ──
        dir_text = wind_direction_name(w_dir)
        bbox_w = draw.textbbox((0, 0), dir_text, font=font_wind)
        tw_w = bbox_w[2] - bbox_w[0]
        draw.text((cx - tw_w//2, y_wind_text),
                  dir_text, font=font_wind, fill=(50, 80, 120, 255))

        # ── 风速: 只显示 X级 ──
        thresholds = [0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7, 999]
        spd_level = 0
        for lv, limit in enumerate(thresholds):
            if w_spd < limit:
                spd_level = lv
                break
        spd_text = f"{spd_level}级"
        bbox_s = draw.textbbox((0, 0), spd_text, font=font_spd)
        tw_s = bbox_s[2] - bbox_s[0]
        draw.text((cx - tw_s//2, y_spd), spd_text, font=font_spd, fill=(80, 80, 80, 255))

        # ── 能见度 (km) ──
        vis_m = hour["weather"].get("visibility")
        if vis_m is not None and vis_m > 0:
            vis_text = f"{vis_m/1000:.1f}km"
        else:
            vis_text = "—"
        bbox_v = draw.textbbox((0, 0), vis_text, font=font_vis)
        tw_v = bbox_v[2] - bbox_v[0]
        draw.text((cx - tw_v//2, y_vis), vis_text, font=font_vis, fill=(80, 100, 120, 255))

        # ── 大气压 (hPa) ──
        pres = hour["weather"].get("pressure")
        if pres is not None:
            pres_text = f"{pres:.0f}hPa"
        else:
            pres_text = "—"
        bbox_p = draw.textbbox((0, 0), pres_text, font=font_vis)
        tw_p = bbox_p[2] - bbox_p[0]
        draw.text((cx - tw_p//2, y_pres), pres_text, font=font_vis, fill=(80, 100, 120, 255))

    # 超采样：缩回目标分辨率
    if ss > 1:
        canvas = canvas.resize((canvas_width, canvas_height), Image.LANCZOS)

    if output_path is not None:
        canvas.save(output_path)
        print(f"天气图表已保存: {output_path}")
        print(f"  画布: {canvas_width}x{canvas_height}  |  {n} 小时  |  SSAA: {ss}x")
        print(f"  城市: {data.get('city','?')}  |  日出: {sunrise}  日落: {sunset}")

    return canvas


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    generate_data_chart(output_path=os.path.join(BASE_DIR, "weather_chart.png"))
