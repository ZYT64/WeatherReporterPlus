"""
sun_moon.py — 「日月之行」简约扁平风格轨迹图

依赖:  pip install matplotlib numpy
运行:  python sun_moon.py
输入:  weather.json  (weather_get.py 生成)
输出:  sun_moon.png  (4000×900 px)
"""

import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

BASE_DIR = os.path.dirname(__file__)
WEATHER_JSON = os.path.join(BASE_DIR, "weather.json")
OUTPUT_PNG = os.path.join(BASE_DIR, "sun_moon.png")
MOON_ICONS = os.path.join(BASE_DIR, "icons", "MoonPhasesIconPack_MarkieAnnCreative", "PNGs")

# 月相中文名 → 图标文件名
MOON_PHASE_ICON = {
    "新月":   "MoonPhases-05_NewMoon.png",
    "蛾眉月": "MoonPhases-06_WaxingCrescent.png",
    "上弦月": "MoonPhases-07_FirstQuarter.png",
    "盈凸月": "MoonPhases-08_WaxingCrescent.png",
    "满月":   "MoonPhases-01_FullMoon.png",
    "亏凸月": "MoonPhases-02_WaningBiggous.png",
    "下弦月": "MoonPhases-03_ThirdQuarter.png",
    "残月":   "MoonPhases-04_WaningCrescent2.png",
}

# ============================================================
# HH:MM → X 轴数值
# ============================================================
def t2x(s):
    if not s: return 0.0
    a, b = s.strip().split(":")
    return float(a) + float(b) / 60.0

# ============================================================
# 抛物线点列
# ============================================================
def para(x0, x1, apex, n=300):
    x = np.linspace(x0, x1, n)
    mid = (x0 + x1) / 2; hw = (x1 - x0) / 2
    if hw <= 0: return x, np.zeros_like(x)
    return x, apex * (1 - ((x - mid) / hw) ** 2)

# ============================================================
# 主函数
# ============================================================
def draw_sun_moon():
    with open(WEATHER_JSON, "r", encoding="utf-8") as f:
        d = json.load(f)

    sr_str = d.get("sunrise", "06:00")
    ss_str = d.get("sunset",  "18:00")
    mr_str = d.get("moonrise", "")
    ms_str = d.get("moonset",  "")
    mphase = d.get("moon_phase", "满月")
    millum_str = d.get("moon_illumination", "50") or "50"
    millum = float(millum_str) if millum_str else 50.0

    sr = t2x(sr_str); ss = t2x(ss_str)
    mr = t2x(mr_str) if mr_str else 0
    ms = t2x(ms_str) if ms_str else 0

    # ---- 画布 2000×900 (20"×9" @ 100dpi) ----
    fig = plt.figure(figsize=(20, 9), dpi=100, facecolor="none")
    ax = fig.add_axes([0.05, 0.18, 0.90, 0.65])
    ax.set_facecolor("none")
    ax.set_xlim(0, 24)
    ax.set_ylim(-1.6, 1.6)
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])

    # ---- 标题 (figure坐标, 左上角) ----
    fig.text(0.5, 0.93, "日月之行", fontsize=58, fontweight="bold",
             fontfamily="SimHei", color="#2c2c2c", va="top", ha="center")

    # ---- 右上角月相图标 ----
    icon_file = MOON_PHASE_ICON.get(mphase, "moon_full.png")
    icon_path = os.path.join(MOON_ICONS, icon_file)
    if os.path.exists(icon_path):
        moon_img = plt.imread(icon_path)
        imagebox = OffsetImage(moon_img, zoom=0.22)
        ab = AnnotationBbox(imagebox, (22.3, 1.25), frameon=False,
                            xycoords="data", box_alignment=(0.5, 0.5))
        ax.add_artist(ab)
    fig.text(0.84, 0.93, mphase, fontsize=26, fontfamily="SimHei",
             color="#555555", va="top", ha="left")
    fig.text(0.84, 0.86, f"{millum:.0f}%", fontsize=18, fontfamily="SimHei",
             color="#666666", va="top", ha="left")

    # ---- 地平线 ----
    ax.axhline(y=0, color="#cccccc", linewidth=1.5, zorder=1)

    # ---- 太阳轨迹: 橙黄实线, 日出→日落, 地平线上方 ----
    sx, sy = para(sr, ss, 1.15)
    ax.plot(sx, sy, color="#f5a623", lw=4, solid_capstyle="round", zorder=3)

    # ---- 月亮轨迹: 跨午夜完整弧, 月出→月落 ----
    if mr > 0 and ms > 0:
        # 月出~月落+24 完整抛物线, 午夜左右为弧顶
        moon_span = (ms + 24) - mr          # 总时长
        moon_mid = (mr + (ms + 24)) / 2     # 弧顶时间 (在午夜附近)
        apex_y = 0.75

        # 完整抛物线点列 (从月出到月落+24h)
        mx_full, my_full = para(mr, ms + 24, apex_y)
        # 拆分成两段: 月出→24h  和  0h→月落, 在午夜处等高衔接
        mask_rise = mx_full <= 24
        mask_set  = mx_full >= 24

        # 上升段: 月出→24h (x在[mr, 24])
        if mx_full[mask_rise].size > 1:
            ax.plot(mx_full[mask_rise], my_full[mask_rise],
                    color="#2c5f8a", lw=3.5, solid_capstyle="round", zorder=3)
        # 下落段: 24h→月落+24h, 映射为 0h→月落
        if mx_full[mask_set].size > 1:
            ax.plot(mx_full[mask_set] - 24, my_full[mask_set],
                    color="#2c5f8a", lw=3.5, solid_capstyle="round", zorder=3)

    # ---- 底部标记: 三角 + 时间 + 标签 (防重叠: 间距<1h则错开) ----
    tri_y = -0.45;  time_y = -0.75;  tag_y = -1.05;  hw = 0.18

    marks = [
        (ms, ms_str, "月落", "#2c5f8a", "down"),
        (sr, sr_str, "日出", "#f5a623", "up"),
        (mr, mr_str, "月出", "#2c5f8a", "up"),
        (ss, ss_str, "日落", "#f5a623", "down"),
    ]
    # 按时间排序后，相邻且间距<1.5h的，后者右移0.4h避免重叠
    valid = [m for m in marks if m[0] > 0 and m[1]]
    valid.sort(key=lambda m: m[0])
    for i in range(1, len(valid)):
        if valid[i][0] - valid[i-1][0] < 1.5:
            valid[i] = (valid[i-1][0] + 1.5,) + valid[i][1:]  # 往后挪

    for mx, tl, tag, color, direc in valid:
        if direc == "up":
            v = [(mx, tri_y), (mx-hw, tri_y-hw*1.4), (mx+hw, tri_y-hw*1.4)]
        else:
            v = [(mx, tri_y-hw*1.4), (mx-hw, tri_y), (mx+hw, tri_y)]
        ax.add_patch(mpatches.Polygon(v, fc=color, ec="none", zorder=5))
        ax.text(mx, time_y, tl, fontsize=22, fontfamily="SimHei",
                color="#333333", ha="center", va="top")
        ax.text(mx, tag_y, tag, fontsize=18, fontfamily="SimHei",
                color="#666666", ha="center", va="top")

    # ---- 正下方日照时长 ----
    daylight_h = ss - sr
    daylight_text = f"日照时长  {int(daylight_h)}h{int((daylight_h%1)*60):02d}m"
    fig.text(0.5, 0.04, daylight_text, fontsize=24, fontfamily="SimHei",
             color="#555555", va="center", ha="center")

    # ---- 保存 ----
    fig.savefig(OUTPUT_PNG, dpi=100, facecolor="none", edgecolor="none",
                transparent=True)
    plt.close(fig)
    print(f"日月之行图已保存: {OUTPUT_PNG}")
    print(f"  日出:{sr_str}  日落:{ss_str}  月出:{mr_str}  月落:{ms_str}")
    print(f"  月相:{mphase} ({millum:.0f}%)")

if __name__ == "__main__":
    draw_sun_moon()
