import requests
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(override=False)


DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
LOCATION = os.getenv("LOCATION", "Kuala Lumpur")

## Thresholds for recommendations so like it uses to calculate the recommendation to bring an umbrella or not, what time you should head home to avoid heavy rain, etc. You can adjust these based on your preferences or local weather patterns.
RAIN_CHANCE_THRESHOLD = 40      # %
HEAVY_RAIN_THRESHOLD = 70       # %
HOT_TEMP_THRESHOLD = 33         # °C
UV_HIGH_THRESHOLD = 6           # Index
AQI_WARNING_THRESHOLD = 101     # US-EPA (101+ is Unhealthy for Sensitive Groups)
CO_HIGH_THRESHOLD = 4400        # μg/m³

def get_coordinates():
    """Uses Open-Meteo's Geocoding API to find Lat/Long."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": LOCATION, "count": 1, "language": "en", "format": "json"}
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    if not data.get("results"):
        raise ValueError(f"Location '{LOCATION}' not found by Open-Meteo.")
    
    result = data["results"][0]
    return result["latitude"], result["longitude"], result.get("name", LOCATION)

def get_weather_data(lat, lon):
    """Fetches Weather and Air Quality data from Open-Meteo."""
    # Forecast URL (Weather, UV, Precipitation)
    w_url = "https://api.open-meteo.com/v1/forecast"
    w_params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,precipitation_probability,precipitation,uv_index",
        "daily": "temperature_2m_max,temperature_2m_min,uv_index_max,precipitation_probability_max,precipitation_sum",
        "timezone": "auto", "forecast_days": 2
    }
    
    # Air Quality URL (AQI, CO, PM2.5)
    a_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    a_params = {
        "latitude": lat, "longitude": lon,
        "hourly": "pm2_5,carbon_monoxide,us_aqi",
        "timezone": "auto", "forecast_days": 2
    }

    w_res = requests.get(w_url, params=w_params, timeout=10).json()
    a_res = requests.get(a_url, params=a_params, timeout=10).json()
    return w_res, a_res

def format_time_str(iso_str):
    dt = datetime.fromisoformat(iso_str)
    return dt.strftime("%I:%M %p").lstrip("0")

def analyze_rain_windows(hourly_w):
    """Identifies blocks of heavy rain for tomorrow (indices 24-47)."""
    windows = []
    current = None
    
    for i in range(24, 48):
        prob = hourly_w["precipitation_probability"][i]
        precip = hourly_w["precipitation"][i]
        time_val = hourly_w["time"][i]
        hour_int = datetime.fromisoformat(time_val).hour

        if (prob >= HEAVY_RAIN_THRESHOLD or precip >= 1.5) and 7 <= hour_int <= 23:
            if current is None:
                current = {"start": time_val, "end": time_val, "probs": [prob]}
            else:
                current["end"] = time_val
                current["probs"].append(prob)
        else:
            if current:
                current["avg"] = round(sum(current["probs"]) / len(current["probs"]))
                windows.append(current)
                current = None
    return windows

def build_discord_payload(w_data, a_data, final_loc):
    # Tomorrow is Index 1 in daily arrays
    daily = {k: v[1] for k, v in w_data["daily"].items()}
    hourly_w = w_data["hourly"]
    hourly_a = a_data["hourly"]
    
    date_str = datetime.fromisoformat(daily["time"]).strftime("%A, %d %b %Y")
    
    tips = []
    color = 0x57F287

    # Logic & Alerts
    if daily["precipitation_probability_max"] >= RAIN_CHANCE_THRESHOLD:
        tips.append("🌂 **Bring an umbrella** — rain is likely.")
        color = 0x5865F2
    
    if daily["temperature_2m_max"] >= HOT_TEMP_THRESHOLD:
        tips.append("😎 **Sunglasses recommended** — stay cool!")

    if daily["uv_index_max"] >= UV_HIGH_THRESHOLD:
        tips.append(f"🧴 UV Index is **{daily['uv_index_max']}** — wear sunscreen.")

    # Rain Analysis
    rain_windows = analyze_rain_windows(hourly_w)
    timing_lines = []
    suggested_exit = False

    for win in rain_windows:
        s_time = format_time_str(win["start"])
        e_time = format_time_str(win["end"])
        timing_lines.append(f"• {'At' if s_time == e_time else f'Between {s_time} and'} **{e_time}**: Heavy rain ({win['avg']}% avg)")
        
        start_hour = datetime.fromisoformat(win["start"]).hour
        if 15 <= start_hour <= 20 and not suggested_exit:
            tips.append(f"🚗 **Head home by {format_time_str(win['start'].replace(win['start'][-5:], f'{start_hour-1:02d}:00'))}** to avoid becoming 落汤鸡!")
            suggested_exit = True

    # AQI Data (Tomorrow at Noon = Index 36)
    aqi_val = hourly_a["us_aqi"][36] 
    co_val = hourly_a["carbon_monoxide"][36]

    if aqi_val >= AQI_WARNING_THRESHOLD:
        tips.append(f"😷 AQI is **{aqi_val}** — consider a mask outside.")

    # Chart (10 AM to 10 PM)
    chart = []
    for i in range(34, 47): 
        p = hourly_w["precipitation_probability"][i]
        if p >= 25:
            bar = "█" * (p // 10) + "░" * (10 - (p // 10))
            chart.append(f"`{format_time_str(hourly_w['time'][i]):>8}` {bar} {p}%")

    fields = [
        {"name": "🌡️ Temp", "value": f"{daily['temperature_2m_min']}°C – {daily['temperature_2m_max']}°C", "inline": True},
        {"name": "🌧️ Rain", "value": f"{daily['precipitation_probability_max']}% ({daily['precipitation_sum']}mm)", "inline": True},
        {"name": "☀️ UV Max", "value": str(daily["uv_index_max"]), "inline": True},
        {"name": "💨 AQI", "value": f"{aqi_val} (US-EPA)", "inline": True},
    ]

    if timing_lines:
        fields.append({"name": "⏰ Heavy Rain Forecast", "value": "\n".join(timing_lines), "inline": False})
    if chart:
        fields.append({"name": "📊 Rain Probability (10am-10pm)", "value": "\n".join(chart), "inline": False})

    return {
        "username": "Weather-Chan 🌤️",
        "embeds": [{
            "title": f"Tomorrow's Forecast — {final_loc}",
            "description": "\n".join(tips) if tips else "✅ Looks like a great day!",
            "color": color,
            "fields": fields,
            "footer": {"text": f"{date_str} • Pure Open-Meteo Engine"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }

def main():
    try:
        print(f"Locating {LOCATION}...")
        lat, lon, final_name = get_coordinates()
        
        print(f"Fetching Open-Meteo data for {final_name}...")
        weather, aqi = get_weather_data(lat, lon)
        
        payload = build_discord_payload(weather, aqi, final_name)
        
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        res.raise_for_status()
        print(f"✅ Success! Notification sent for {final_name}.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
