import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d
import pandas as pd
import json

plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

def plot_temp_precip(
    temp_data,
    prec_data=None,
    components=('temp',),
    enable_adaptive=True,
    min_data_range=0.5,
    figsize=None,
    point_size=None,
    point_halo_factor=None,
    point_halo_alpha=0.25,
    label_fontsize=None,
    label_offset=None,
    temp_color='#e53e3e',
    prec_color='#3182ce',
    bar_width=0.6,
    temp_window=5,
    temp_polyorder=2,
    smooth_points=400,
    label_temp_format=None,      # 若为 None，则使用原始值并自动添加 °C
    label_prec_format=None,      # 若为 None，则使用原始值并自动添加 mm
    title='',
    save_path=None,
    bar_downward_shift=0.0,
    bar_alpha=0.5,
    bar_edgecolor='white',
    bar_edgewidth=1.2,
    curve_linewidth=2.8,
    curve_alpha=0.9,
    fill_alpha=0,
    point_edgecolor='white',
    point_edgewidth=1.5,
    label_color='#2d3748',
    bg_color='#f7f9fc',
    show_legend=False,
    legend_loc='upper left',
    transparent=False,
):
    # 标准化 components
    if isinstance(components, str):
        components = (components,)
    draw_temp = 'temp' in components
    dual_mode = prec_data is not None
    draw_precip = dual_mode and ('precip' in components)

    labels = list(temp_data.keys())
    n_points = len(labels)
    x_idx = np.arange(n_points)
    y_temp_raw = np.array([temp_data[k] for k in labels])
    if dual_mode:
        y_prec = np.array([prec_data.get(k, 0) for k in labels])
    else:
        y_prec = None
        draw_precip = False

    # 自适应尺寸等
    if enable_adaptive:
        if figsize is None:
            width = max(8, min(16, n_points * 0.6))
            height = 7.5 if draw_precip else 5.5
            figsize = (width, height)
        if point_size is None:
            point_size = max(40, min(80, int(80 * (12 / max(n_points, 1)))))
        if point_halo_factor is None:
            point_halo_factor = 1.8 + (40 / max(n_points, 1)) * 0.5
        if label_fontsize is None:
            label_fontsize = max(6, min(10, int(10 * (15 / max(n_points, 1)))))
        if label_offset is None:
            label_offset = 0.04 + (5 / max(n_points, 1)) * 0.02
    else:
        if figsize is None:
            figsize = (12, 7.5) if draw_precip else (12, 5.5)
        point_size = point_size or 80
        point_halo_factor = point_halo_factor or 2.2
        label_fontsize = label_fontsize or 9
        label_offset = label_offset or 0.06

    # 气温平滑
    if draw_temp:
        win = temp_window
        if win % 2 == 0:
            win += 1
        win = min(win, len(y_temp_raw) if len(y_temp_raw) % 2 == 1 else len(y_temp_raw) - 1)
        if win < 3:
            win = 3
        if win <= len(y_temp_raw):
            y_temp_smooth = savgol_filter(y_temp_raw, win, temp_polyorder, mode='nearest')
        else:
            y_temp_smooth = y_temp_raw
        if len(x_idx) >= 4:
            interp = interp1d(x_idx, y_temp_smooth, kind='cubic', fill_value='extrapolate')
        else:
            interp = interp1d(x_idx, y_temp_smooth, kind='linear', fill_value='extrapolate')
        x_dense = np.linspace(x_idx.min(), x_idx.max(), smooth_points)
        y_dense = interp(x_dense)

    # 创建上下两个子图
    if draw_precip:
        fig, (ax_temp, ax_precip) = plt.subplots(
            2, 1, figsize=figsize,
            sharex=True,
            gridspec_kw={'hspace': 0, 'height_ratios': [2.5, 1]},
            facecolor='none' if transparent else bg_color
        )
    else:
        fig, ax_temp = plt.subplots(figsize=figsize,
                                    facecolor='none' if transparent else bg_color)
        ax_precip = None

    if not transparent:
        ax_temp.set_facecolor(bg_color)
        if ax_precip is not None:
            ax_precip.set_facecolor(bg_color)

    # ---------- 上方子图：温度曲线 ----------
    if draw_temp:
        ax_temp.fill_between(x_dense, y_dense, alpha=fill_alpha, color=temp_color, zorder=2)
        ax_temp.plot(x_dense, y_dense, color=temp_color, linewidth=curve_linewidth,
                     alpha=curve_alpha, solid_capstyle='round', zorder=3)
        ax_temp.scatter(x_idx, y_temp_smooth, s=point_size * point_halo_factor,
                        facecolor=temp_color, edgecolor='none', alpha=point_halo_alpha, zorder=4)
        ax_temp.scatter(x_idx, y_temp_smooth, s=point_size, facecolor=temp_color,
                        edgecolor=point_edgecolor, linewidth=point_edgewidth, zorder=5)

        y_min, y_max = y_temp_smooth.min(), y_temp_smooth.max()
        y_range = y_max - y_min
        if y_range < min_data_range:
            data_avg = (y_min + y_max) / 2
            y_min = data_avg - min_data_range / 2
            y_max = data_avg + min_data_range / 2
            y_range = min_data_range
        bottom_pad = y_range * 0.12 if y_range > 0 else 0.5
        top_pad = y_range * 0.08 if y_range > 0 else 0.5
        offset_temp = y_range * label_offset if y_range > 0 else 0.5

        for xi, yi_raw, yi_smooth in zip(x_idx, y_temp_raw, y_temp_smooth):
            if label_temp_format is None:
                # 默认：智能保留小数 + 单位 °C
                if yi_raw == int(yi_raw):
                    text = str(int(yi_raw))
                else:
                    text = f"{yi_raw:.2f}".rstrip('0').rstrip('.')
                text += '°C'          # ← 添加温度单位
            else:
                text = label_temp_format.format(yi_raw)
            ax_temp.text(xi, yi_smooth + offset_temp, text,
                         ha='center', va='bottom', fontsize=label_fontsize,
                         fontweight='medium', color=label_color, zorder=6)

        ax_temp.set_ylim(y_min - bottom_pad, y_max + top_pad)

    # 隐藏温度子图坐标轴
    ax_temp.set_xticks([])
    ax_temp.set_yticks([])
    ax_temp.set_xticklabels([])
    ax_temp.set_yticklabels([])
    for spine in ax_temp.spines.values():
        spine.set_visible(False)
    ax_temp.set_xlabel('')
    ax_temp.set_ylabel('')

    # ---------- 下方子图：降水柱状图 ----------
    if draw_precip and y_prec is not None:
        bottom = 0.0
        ax_precip.bar(x_idx, y_prec, width=bar_width,
                      color=prec_color, alpha=bar_alpha,
                      edgecolor=bar_edgecolor, linewidth=bar_edgewidth,
                      bottom=bottom, zorder=0)

        max_prec = y_prec.max() if y_prec.max() > 0 else 1
        y_top_prec = max_prec * 1.2 if max_prec > 0 else 1.2
        y_bottom_prec = -max_prec * 0.1 if max_prec > 0 else -0.1
        ax_precip.set_ylim(y_bottom_prec, y_top_prec)

        label_y_offset = max_prec * 0.08 if max_prec > 0 else 0.08
        for xi, yi in zip(x_idx, y_prec):
            if label_prec_format is None:
                # 默认：智能保留小数 + 单位 mm
                if yi == int(yi):
                    text = str(int(yi))
                else:
                    text = f"{yi:.2f}".rstrip('0').rstrip('.')
                text += ' mm'         # ← 添加降水单位
            else:
                text = label_prec_format.format(yi)
            ax_precip.text(xi, yi + label_y_offset, text,
                           ha='center', va='bottom', fontsize=label_fontsize,
                           fontweight='medium', color=label_color, zorder=10)

    # 隐藏降水子图坐标轴
    if ax_precip is not None:
        ax_precip.set_xticks([])
        ax_precip.set_yticks([])
        ax_precip.set_xticklabels([])
        ax_precip.set_yticklabels([])
        for spine in ax_precip.spines.values():
            spine.set_visible(False)
        ax_precip.set_xlabel('')
        ax_precip.set_ylabel('')

    # 统一横轴范围
    margin = 0.6 if n_points < 10 else 0.4
    ax_temp.set_xlim(-margin, n_points - 1 + margin)
    if ax_precip is not None:
        ax_precip.set_xlim(-margin, n_points - 1 + margin)

    # 图例
    if show_legend:
        from matplotlib.lines import Line2D
        legend_elements = []
        if draw_temp:
            label_name = '气温曲线' if draw_precip else (title if title else '曲线')
            legend_elements.append(Line2D([0], [0], color=temp_color, lw=curve_linewidth,
                                          alpha=curve_alpha, label=label_name))
        if draw_precip:
            legend_elements.append(Line2D([0], [0], color=prec_color, lw=bar_edgewidth * 2,
                                          alpha=bar_alpha, label='降水量'))
        if legend_elements:
            ax_temp.legend(handles=legend_elements, loc=legend_loc,
                           frameon=True, fancybox=True, edgecolor='none',
                           facecolor='white', framealpha=0.7, fontsize=label_fontsize)

    # 总标题
    fig.suptitle(title, fontsize=16, fontweight='bold', color='#1a202c', y=0.98)
    plt.tight_layout(pad=0.5)
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight',
                    facecolor='none' if transparent else bg_color,
                    transparent=transparent)
        print(f"✅ 图表已保存至: {save_path}")
    plt.close(fig)


if __name__ == "__main__":
    # 解析json
    with open("weather.json", "r", encoding="utf-8") as f:
        weather_data = json.load(f)
    temp_list = [hour["weather"]["temp"] for hour in weather_data["hours"]]
    precip_list = [hour["weather"]["precip"] for hour in weather_data["hours"]]
    time_list = [hour["time"] for hour in weather_data["hours"]]

    temp_dict = {time: temp for time, temp in zip(time_list, temp_list)}
    prec_dict = {time: precip for time, precip in zip(time_list, precip_list)}

    plot_temp_precip(
        temp_dict, prec_dict,
        components=('temp', 'precip'),
        bar_downward_shift=0.0,
        enable_adaptive=True,
        min_data_range=0.5,
        save_path='temp_rain.png',
        transparent=True
    )