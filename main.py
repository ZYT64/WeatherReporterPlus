from weather_get import get
from background import generate_with_zhipu, get_image_gen_config
import json
from PIL import Image, ImageDraw, ImageFont
from frame import blur_rect
from chart import plot_temp_precip
from chart_weather import generate_data_chart
import os
from sun_moon import draw_sun_moon
from humidity_bar import draw_humidity_bar
from temp_bar import generate_temp_bar
from warning_panel import generate_warning_panel


def generate_background(prompt):
    """使用智谱AI生成天气背景图。"""
    img_cfg = get_image_gen_config()
    gen_kwargs = {k: v for k, v in img_cfg.items()
                  if k not in ("api_base", "quality", "style")}
    result = generate_with_zhipu(prompt, **gen_kwargs)
    result.save("output.png")

def make_charts():
    # 温度和降水图
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
    # 天气概览图
    generate_data_chart(output_path=os.path.join(os.path.dirname(__file__), "weather_chart.png"))
    # 日月之行
    draw_sun_moon()
    # 湿度
    draw_humidity_bar()
    # 温度条
    generate_temp_bar()
    # 预警信息
    generate_warning_panel()

if __name__ == "__main__":
    import sys, io
    real_stdout = sys.stdout
    sys.stdout = io.StringIO()
    steps = 8

    def progress(i, label):
        sys.stdout = real_stdout
        bar = "█" * i + "░" * (steps - i)
        print(f"\r[{bar}] {i}/{steps}  {label}", end="", flush=True)
        sys.stdout = io.StringIO()

    progress(1, "获取天气数据...")
    get()

    with open("weather.json", "r", encoding="utf-8") as f:
        weather_data = json.load(f)
    weather_list = [hour["weather"]["text"] for hour in weather_data["hours"]]

    progress(2, "AI 生成背景图...")
    generate_background(
        "请你根据以下天气描述生成一张背景图，适合用作天气预报的背景：\n" +
        "\n".join(weather_list)
    )
    progress(3, "裁切图片...")
    img = Image.open("output.png")
    factor = 6738 / img.width
    big = img.resize((6738, int(img.height * factor)), Image.LANCZOS)
    y0 = (big.height - 3467) // 2
    big.crop((0, y0, 6738, y0 + 3467)).save("output.png")

    progress(4, "生成天气图表...")
    make_charts()

    progress(5, "叠加毛玻璃框...")
    img = Image.open("output.png")
    result = blur_rect(img, x=2769, y=100, w=1000, h=400, corner_radius=80, blur_radius=40, border_width=0, border_color="grey", fill_color="white", fill_opacity=0.3)
    result = blur_rect(result, x=100, y=600, w=4438, h=2767, corner_radius=80, blur_radius=18, border_width=0, border_color="grey", fill_color="white", fill_opacity=0.3)
    result = blur_rect(result, x=4638, y=600, w=2000, h=900, corner_radius=80, blur_radius=18, border_width=0, border_color="grey", fill_color="white", fill_opacity=0.3)
    result = blur_rect(result, x=4638, y=1600, w=2000, h=500, corner_radius=80, blur_radius=18, border_width=0, border_color="grey", fill_color="white", fill_opacity=0.3)
    result = blur_rect(result, x=4638, y=2200, w=2000, h=1167, corner_radius=80, blur_radius=18, border_width=0, border_color="grey", fill_color="white", fill_opacity=0.3)

    progress(6, "合成图表...")
    rain = Image.open("temp_rain.png").convert("RGBA")
    result.paste(rain, (100, 600), rain)
    sun_moon_img = Image.open("sun_moon.png").convert("RGBA")
    result.paste(sun_moon_img, (4638, 600), sun_moon_img)
    humidity_img = Image.open("humidity_bar.png").convert("RGBA")
    result.paste(humidity_img, (4638, 1600), humidity_img)
    warning_img = Image.open("warning_panel.png").convert("RGBA")
    result.paste(warning_img, (4638, 2200), warning_img)
    weather_chart_img = Image.open("weather_chart.png").convert("RGBA")
    result.paste(weather_chart_img, (100, 2847), weather_chart_img)
    temp_bar_img = Image.open("temp_bar.png").convert("RGBA")
    result.paste(temp_bar_img, (2769, 350), temp_bar_img)

    progress(7, "写入城市名...")
    draw = ImageDraw.Draw(result)
    font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 250)
    with open("weather.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    city = data.get("city", "未知城市")
    bbox = draw.textbbox((0, 0), city, font=font)
    tw = bbox[2] - bbox[0]
    center_x = 2469 + 1600 // 2
    draw.text((center_x - tw // 2, 120), city, font=font, fill=(40, 40, 40, 255))

    progress(8, "保存...")
    result.save("output.png")
    sys.stdout = real_stdout
    print(f"\r[{'█' * steps}] {steps}/{steps}  完成! output.png 已生成")