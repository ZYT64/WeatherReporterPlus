#!/usr/bin/env python3
"""
天气综合采集器 — 全部免费，零 API Key

数据源:
  Open-Meteo — 地理编码 + 当天 0:00~24:00 逐小时天气 + 日出日落 + 空气质量
  wttr.in    — 月相 / 月出 / 月落
  nmc.cn     — 气象预警（中央气象台）

用法:
    python weather_get.py
"""

import json
import os
import re
from datetime import datetime

import requests

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "weather.json")
TIMEOUT = 30

UV_LEVEL_CN = {
    0: "无", 1: "低", 2: "低", 3: "中等", 4: "中等", 5: "中等",
    6: "高", 7: "高", 8: "很高", 9: "很高", 10: "很高",
    11: "极高", 12: "极高", 13: "极高", 14: "极高", 15: "极高",
}


def uv_level(uv: float) -> str:
    """将 UV 指数转为中文等级。"""
    return UV_LEVEL_CN.get(int(uv), "极高") if uv >= 0 else ""


WMO_TEXT = {
    0: "晴天", 1: "少云", 2: "多云", 3: "阴天",
    45: "雾", 48: "冻雾",
    51: "小毛毛雨", 53: "中毛毛雨", 55: "大毛毛雨",
    56: "小冻毛毛雨", 57: "大冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "小冻雨", 67: "大冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "小阵雨", 81: "中阵雨", 82: "大阵雨",
    85: "小阵雪", 86: "大阵雪",
    95: "雷暴", 96: "雷暴伴小冰雹", 99: "雷暴伴大冰雹",
}

MOON_PHASE_CN = {
    "New Moon": "新月", "Waxing Crescent": "蛾眉月",
    "First Quarter": "上弦月", "Waxing Gibbous": "盈凸月",
    "Full Moon": "满月", "Waning Gibbous": "亏凸月",
    "Last Quarter": "下弦月", "Waning Crescent": "残月",
}


def _moon_phase_name(phase_val: float) -> tuple[str, float]:
    """Open-Meteo moon_phase (0~1) → (中文名, 亮度%)
    0=新月, 0.25=上弦月, 0.5=满月, 0.75=下弦月"""
    names = ["新月", "蛾眉月", "上弦月", "盈凸月", "满月", "亏凸月", "下弦月", "残月"]
    idx = round(phase_val * 8) % 8
    # 亮度: 新月=0, 满月=100, 弦月=50
    illum = round(abs(phase_val - 0.25) * 200)
    if illum > 100:
        illum = 200 - illum
    return names[idx], max(0, min(100, illum))


def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise SystemExit(f"config.json not found at {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if "city" not in cfg:
        raise SystemExit("config.json missing field: city")
    return cfg


# ── Open-Meteo（天气 + 空气质量 + 地理编码）───────────
class OpenMeteo:
    GEO = "https://geocoding-api.open-meteo.com/v1/search"
    WX  = "https://api.open-meteo.com/v1/forecast"
    AQ  = "https://air-quality-api.open-meteo.com/v1/air-quality"

    def geocode(self, city: str) -> dict:
        print(f"[Open-Meteo] Geocoding: {city}")
        r = requests.get(self.GEO, params={"name": city, "language": "zh", "count": 1}, timeout=TIMEOUT)
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            raise SystemExit(f"City not found: {city}")
        loc = results[0]
        print(f"            {loc['name']}  ({loc['latitude']},{loc['longitude']})  {loc.get('timezone','')}")
        return loc

    def weather(self, lat: float, lon: float, tz: str) -> dict:
        print("[Open-Meteo] Weather + sunrise/sunset...")
        return self._get(self.WX, {
            "latitude": lat, "longitude": lon, "timezone": tz, "forecast_days": 1,
            "hourly": "temperature_2m,relative_humidity_2m,dew_point_2m,"
                       "precipitation,precipitation_probability,weather_code,"
                       "pressure_msl,cloud_cover,visibility,"
                       "wind_speed_10m,wind_direction_10m,wind_gusts_10m,"
                       "uv_index,uv_index_clear_sky",
            "daily": "sunrise,sunset,temperature_2m_max,temperature_2m_min,precipitation_sum",
        })

    def air_quality(self, lat: float, lon: float, tz: str) -> dict:
        print("[Open-Meteo] Air quality...")
        return self._get(self.AQ, {
            "latitude": lat, "longitude": lon, "timezone": tz, "forecast_days": 1,
            "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,"
                       "sulphur_dioxide,ozone,european_aqi,us_aqi",
        })

    def _get(self, url, params):
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        d = r.json()
        if d.get("error"):
            raise SystemExit(f"Open-Meteo error: {d['reason']}")
        return d


# ── wttr.in（月相）────────────────────────────────────
def fetch_moon(lat: float, lon: float, tz: str) -> dict:
    """从 met.no 免费 API 获取月相、月出月落 (无需 API key)。"""
    import math
    today = datetime.now().strftime("%Y-%m-%d")
    offset = tz.replace("Asia/Shanghai", "+08:00").replace("Asia/", "+0")
    if not offset.startswith("+"): offset = "+08:00"
    try:
        url = f"https://api.met.no/weatherapi/sunrise/3.0/moon"
        r = requests.get(url, params={
            "lat": lat, "lon": lon, "date": today, "offset": offset,
        }, headers={"User-Agent": "WeatherReporter/1.0"}, timeout=TIMEOUT)
        r.raise_for_status()
        props = r.json()["properties"]

        # 月相角度 → 中文名 + 亮度
        phase_deg = props.get("moonphase", 0)
        # 0°=新月, 90°=上弦, 180°=满月, 270°=下弦
        names = ["新月", "蛾眉月", "上弦月", "盈凸月", "满月", "亏凸月", "下弦月", "残月"]
        idx = round(phase_deg / 45) % 8
        # 亮度: (1 - cos(角度)) / 2
        illum = round((1 - math.cos(math.radians(phase_deg))) * 50)

        def _extract_time(t):
            return t["time"].split("T")[1][:5] if t.get("time") else ""

        return {
            "moon_phase": names[idx],
            "moon_phase_en": "",
            "moon_illumination": str(illum),
            "moonrise": _extract_time(props.get("moonrise", {})),
            "moonset": _extract_time(props.get("moonset", {})),
        }
    except Exception:
        return {
            "moon_phase": "满月", "moon_illumination": "50",
            "moonrise": "", "moonset": "", "moon_phase_en": "",
        }


# ── nmc.cn（中央气象台预警）────────────────────────────
def fetch_warnings(province: str, city: str = "") -> list[dict]:
    print(f"[nmc.cn] Weather warnings (province={province}, city={city})...")
    try:
        r = requests.get("http://www.nmc.cn/rest/findAlarm", params={
            "pageNo": 1, "pageSize": 200,
            "signaltype": "", "signallevel": "", "province": province,
        }, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        items = data["data"]["page"]["list"]

        # 过滤：只保留本市的预警 (标题中包含城市名即匹配)
        if city:
            city_clean = city.rstrip("市县区")
            filtered = [item for item in items
                        if city_clean in item.get("title", "") or city in item.get("title", "")]
            print(f"          {len(items)} province warnings -> {len(filtered)} city warnings")
            return filtered
        print(f"          {len(items)} active warnings")
        return items
    except Exception as e:
        print(f"  Warning: nmc.cn failed ({e})")
        return []


# ── 时间格式化 ─────────────────────────────────────────
def to_hhmm(s: str) -> str:
    """将各种时间字符串统一转为 24h 制的 HH:MM。"""
    if not s:
        return ""
    s = s.strip()
    # "2026-05-30T04:49" or "2026-05-30T04:49+08:00"
    m = re.match(r".*T(\d{2}:\d{2})", s)
    if m:
        return m.group(1)
    # "04:49 AM" / "06:57 PM" (wttr.in 12h 格式)
    m = re.match(r"(\d{2}):(\d{2})\s*(AM|PM)", s, re.I)
    if m:
        hh, mm, ap = int(m.group(1)), m.group(2), m.group(3).upper()
        if ap == "PM" and hh != 12:
            hh += 12
        if ap == "AM" and hh == 12:
            hh = 0
        return f"{hh:02d}:{mm}"
    # "2026/05/30 11:34" (nmc.cn)
    m = re.match(r"\d{4}/\d{2}/\d{2}\s+(\d{2}:\d{2})", s)
    if m:
        return m.group(1)
    # "HH:MM" already
    if re.match(r"^\d{2}:\d{2}$", s):
        return s
    return s


# ── 组装 ─────────────────────────────────────────────
def build(om_wx, om_aq, moon, alarms, loc):
    today = datetime.now().strftime("%Y%m%d")
    hw = om_wx["hourly"]
    ha = om_aq.get("hourly", {})
    times = hw["time"]
    air_map = {t: i for i, t in enumerate(ha.get("time", []))}

    hours = []
    for i, t in enumerate(times):
        wmo = hw["weather_code"][i]
        entry = {
            "time": to_hhmm(t),
            "weather": {
                "text": WMO_TEXT.get(wmo, f"code_{wmo}"),
                "code": wmo,
                "temp": hw["temperature_2m"][i],
                "humidity": hw["relative_humidity_2m"][i],
                "precip": hw["precipitation"][i],
                "precip_prob": hw["precipitation_probability"][i],
                "pressure": hw["pressure_msl"][i],
                "cloud": hw["cloud_cover"][i],
                "dew": hw["dew_point_2m"][i],
                "visibility": hw["visibility"][i],
            },
            "wind": {
                "speed": hw["wind_speed_10m"][i],
                "direction": hw["wind_direction_10m"][i],
                "gusts": hw["wind_gusts_10m"][i],
            },
            "uv": {
                "index": hw["uv_index"][i],
                "clear_sky": hw["uv_index_clear_sky"][i],
                "level": uv_level(hw["uv_index"][i]),
            },
            "moon_phase": {
                "name": moon.get("moon_phase", ""),
                "name_en": moon.get("moon_phase_en", ""),
                "illumination": moon.get("moon_illumination", ""),
            } if moon else None,
        }
        if t in air_map:
            j = air_map[t]
            entry["air_quality"] = {
                "pm10": ha["pm10"][j], "pm2_5": ha["pm2_5"][j],
                "co": ha["carbon_monoxide"][j], "no2": ha["nitrogen_dioxide"][j],
                "so2": ha["sulphur_dioxide"][j], "o3": ha["ozone"][j],
                "european_aqi": ha.get("european_aqi", [None])[j],
                "us_aqi": ha.get("us_aqi", [None])[j],
            }
        hours.append(entry)

    dw = om_wx.get("daily", {})
    sunrise = to_hhmm(dw["sunrise"][0]) if dw.get("sunrise") else ""
    sunset  = to_hhmm(dw["sunset"][0])  if dw.get("sunset") else ""

    return {
        "update_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "city": loc.get("name", ""),
        "country": loc.get("country", ""),
        "admin1": loc.get("admin1", ""),
        "latitude": loc.get("latitude"),
        "longitude": loc.get("longitude"),
        "timezone": loc.get("timezone", ""),
        "date": today,
        "sunrise": sunrise,
        "sunset": sunset,
        "moonrise": to_hhmm(moon.get("moonrise", "")),
        "moonset": to_hhmm(moon.get("moonset", "")),
        "moon_phase": moon.get("moon_phase", ""),
        "moon_illumination": moon.get("moon_illumination", ""),
        "warnings": [
            {
                "id": a["alertid"],
                "title": a["title"],
                "issued": to_hhmm(a["issuetime"]),
            }
            for a in alarms
        ],
        "warning_count": len(alarms),
        "data_source": "Open-Meteo + wttr.in + nmc.cn",
        "hours": hours,
        "hour_count": len(hours),
    }


def get(city: str = ""):
    """获取天气数据。

    Parameters
    ----------
    city : str
        城市名。为空则从 config.json 读取。
    """
    cfg = load_config()
    om = OpenMeteo()
    city = city or cfg["city"]

    # 1. 地理编码
    loc = om.geocode(city)
    lat, lon = loc["latitude"], loc["longitude"]
    tz = loc.get("timezone", "Asia/Shanghai")
    # admin1 like "北京市" → strip "市" for nmc.cn province param
    admin1 = loc.get("admin1", city)
    province = admin1.rstrip("市") if admin1 else city

    # 2. Open-Meteo 天气 + 空气质量
    om_wx = om.weather(lat, lon, tz)
    om_aq = om.air_quality(lat, lon, tz)

    # 3. 月相 (skyfield 本地高精度计算, 无需网络)
    moon = fetch_moon(lat, lon, tz)

    # 4. nmc.cn 预警
    alarms = fetch_warnings(province, city)

    # 组装
    result = build(om_wx, om_aq, moon, alarms, loc)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys
    city = sys.argv[1] if len(sys.argv) > 1 else ""
    get()
