# Weather Reporter Plus

极简扁平风格天气报告生成器——从数据采集到可视化背景图，全自动一条龙。

## 功能

- 采集天气数据（Open-Meteo + met.no + nmc.cn，全部免费零 API Key）
- AI 生成天气背景图（智谱 CogView / OpenAI DALL-E）
- 自动生成毛玻璃圆角 UI 面板
- 24 小时天气概览图表
- 日月之行轨迹图
- 湿度 / 温度 / 预警等可视化组件

## 依赖

```bash
pip install pillow matplotlib numpy requests
```

## 快速开始

1. 复制 `config.example.json` 为 `config.json`
2. 填写 `city`（城市名）和智谱 `api_key`
3. 运行：

```bash
python main.py
```

输出：`output.png`（6738×3467 天气背景图）

## 单独运行各组件

```bash
python weather_get.py          # 仅采集天气数据 → weather.json
python chart_weather.py         # 生成 24h 天气图表
python sun_moon.py              # 日月之行轨迹图
python humidity_bar.py          # 湿度进度条
python temp_bar.py              # 温度区间条
python warning_panel.py         # 预警面板
```

## 配置说明 (config.json)

```json
{
  "city": "南京",
  "image_gen": {
    "api_key": "你的智谱API Key",
    "model": "cogview-3-flash",
    "size": "1152x864",
    "style": "漫画风格"
  },
  "ui": {
    "blur_radius": 18,
    "corner_radius": 50,
    "border_width": 2
  }
}
```

## 项目结构

```
├── main.py              # 主流程（进度条 + 全自动生成）
├── weather_get.py       # 天气数据采集
├── background.py        # AI 文生图
├── frame.py             # 圆角矩形毛玻璃效果
├── chart_weather.py     # 24h 天气图表
├── chart_wind.py        # 风向风速图标
├── sun_moon.py          # 日月之行轨迹图
├── humidity_bar.py      # 湿度进度条
├── temp_bar.py          # 温度区间条
├── warning_panel.py     # 预警面板
├── chart.py             # 温度/降水图表
├── icons/               # 天气图标集
└── config.example.json  # 配置模板
```

## 数据源

| 数据 | 来源 | 需要 Key |
|---|---|---|
| 天气 / 空气质量 | Open-Meteo | 否 |
| 日出日落 | Open-Meteo | 否 |
| 月出月落 / 月相 | met.no | 否 |
| 气象预警 | nmc.cn（中央气象台） | 否 |
| 背景图生成 | 智谱 AI | **是** |

## License

MIT
