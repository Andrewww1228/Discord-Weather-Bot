import requests
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(override=False)

# ── CONFIGURATION ──────────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
LOCATION = os.getenv("LOCATION", "Kuala Lumpur")

# ── THRESHOLDS ─────────────────────────────────────────────────────────────
RAIN_CHANCE_THRESHOLD = 40      # % chance of rain to trigger umbrella warning
HEAVY_RAIN_THRESHOLD = 70       # % chance of rain considered "heavy rain risk"
HOT_TEMP_THRESHOLD = 33         # °C — recommend sunglasses above this
UV_HIGH_THRESHOLD = 6           # UV index considered high
AQI_WARNING_THRESHOLD = 101     # AQI — recommend mask above this
CO_HIGH_THRESHOLD = 4400        # μg/m³ -CO level considered high (US EPA standard)
WIND_SPEED_THRESHOLD = 30       # km/h for a warning

# ── AQI LABELS ──
aqi_labels = {
    1: ("Good", "🟢"),
    2: ("Moderate", "🟡"),
    3: ("Unhealthy for sensitive groups", "🟠"),
    4: ("Unhealthy", "🔴"),
    5: ("Very Unhealthy", "🟣"),
    6: ("Hazardous", "⚫"),
}

def get_aqi_info(aqi_value):
    """Maps raw AQI number to the 1-6 label system"""
    if aqi_value <= 50: return aqi_labels[1]
    if aqi_value <= 100: return aqi_labels[2]
    if aqi_value <= 150: return aqi_labels[3]
    if aqi_value <= 200: return aqi_labels[4]
    if aqi_value <= 300: return aqi_labels[5]
    return aqi_labels[6]

def get_coordinates():
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": LOCATION, "count": 1, "language": "en", "format": "json"}
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    if not data.get("results"):
        raise ValueError(f"Location '{LOCATION}' not found.")
    result = data["results"][0]
    return result["latitude"], result["longitude"], result.get("name", LOCATION)

def get_weather_data(lat, lon):
    # Forecast URL (Added wind_speed_10m)
    w_url = "https://api.open-meteo.com/v1/forecast"
    w_params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,precipitation_probability,precipitation,uv_index,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,uv_index_max,precipitation_probability_max,precipitation_sum,wind_speed_10m_max",
        "timezone": "auto", "forecast_days": 2
    }
    
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
    windows = []
    current = None
    for i in range(0, 24):
        prob = hourly_w["precipitation_probability"][i]
        precip = hourly_w["precipitation"][i]
        time_val = hourly_w["time"][i]
        hour_int = datetime.fromisoformat(time_val).hour

        if (prob >= HEAVY_RAIN_THRESHOLD or precip >= 1.5) and 7 <= hour_int <= 23:
            if current is None:
                current = {"start": time_val, "end": time_val, "probs": [prob], "start_hour": hour_int}
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
    daily = {k: v[0] for k, v in w_data["daily"].items()}
    hourly_w = w_data["hourly"]
    hourly_a = a_data["hourly"]
    date_str = datetime.fromisoformat(daily["time"]).strftime("%A, %d %b %Y")
    
    tips = []
    color = 0x57F287

    # ── Logic & Alerts ──
    if daily["precipitation_probability_max"] >= RAIN_CHANCE_THRESHOLD:
        tips.append("🌂 **Bring an umbrella** — rain is likely.")
        color = 0x5865F2
    
    if daily["temperature_2m_max"] >= HOT_TEMP_THRESHOLD:
        tips.append("😎 **Sunglasses recommended** — stay cool!")

    if daily["uv_index_max"] >= UV_HIGH_THRESHOLD:
        tips.append(f"🧴 UV Index is **{daily['uv_index_max']}** — wear sunscreen.")

    if daily["wind_speed_10m_max"] >= WIND_SPEED_THRESHOLD:
        tips.append(f"💨 **Windy day** — gusts up to {daily['wind_speed_10m_max']} km/h.")

    # ── Rain Timing & Work Schedule (Ends at 6 PM) ──
    rain_windows = analyze_rain_windows(hourly_w)
    timing_lines = []
    suggested_exit = False

    for win in rain_windows:
        s_time = format_time_str(win["start"])
        e_time = format_time_str(win["end"])
        timing_lines.append(f"• {'At' if s_time == e_time else f'Between {s_time} and'} **{e_time}**: Heavy rain ({win['avg']}% avg)")
        
        # Logic: If heavy rain starts between 3 PM (15) and 6 PM (18)
        if 15 <= win["start_hour"] <= 18 and not suggested_exit:
            safe_hour_int = win["start_hour"] - 1
            # Create a readable time for the suggestion
            safe_time = f"{safe_hour_int - 12 if safe_hour_int > 12 else safe_hour_int}:00 PM"
            tips.append(f"🚗 **BB🥰! Head home by {safe_time}** to avoid becoming 落汤鸡 during your commute!")
            suggested_exit = True



    # ── AQI & CO (Mapping the labels) ──
    aqi_val = hourly_a["us_aqi"][12] 
    co_val = hourly_a["carbon_monoxide"][12]
    
    # Use the mapping function to get the status and emoji
    aqi_status, aqi_emoji = get_aqi_info(aqi_val)
    
    if aqi_val >= AQI_WARNING_THRESHOLD:
        tips.append(f"😷 AQI is **{aqi_val}** — BB please consider wearing a mask ❤️🥰.")
    
    if co_val >= CO_HIGH_THRESHOLD:
        tips.append("🚨 **High CO levels** — BB please stay indoors if possible 🥰.")

    # ── Hourly Chart ──
    chart = []
    for i in range(10, 23): 
        p = hourly_w["precipitation_probability"][i]
        if p >= 25:
            bar = "█" * (p // 10) + "░" * (10 - (p // 10))
            chart.append(f"`{format_time_str(hourly_w['time'][i]):>8}` {bar} {p}%")

    fields = [
        {
            "name": "🌡️ Temp", 
            "value": f"{daily['temperature_2m_min']}°C – {daily['temperature_2m_max']}°C", 
            "inline": True
         },

        {
            "name": "🌧️ Rain", 
            "value": f"{daily['precipitation_probability_max']}% ({daily['precipitation_sum']}mm)", 
            "inline": True
        },

        {
            "name": "☀️ UV Max", 
            "value": str(daily["uv_index_max"]), 
            "inline": True
        },

        {
            "name": "🧪 Air Quality", 
            "value": f"{aqi_emoji} **{aqi_status}**\nAQI: {aqi_val}\nCO: {co_val:.0f} μg/m³", 
            "inline": True
        },

        {
            "name": "💨 Wind Max", 
            "value": f"{daily['wind_speed_10m_max']} km/h", 
            "inline": True
        },
    ]

    if timing_lines:
        fields.append({"name": "⏰ Heavy Rain Forecast", "value": "\n".join(timing_lines), "inline": False})
    if chart:
        fields.append({"name": "📊 Rain Probability (10am-10pm)", "value": "\n".join(chart), "inline": False})

    return {
        "username": "Weather-Chan 🌤️",
        "embeds": [{
            "title": f"Today's Forecast — {final_loc}",
            "description": "\n".join(tips) if tips else "✅ Looks like a great day!",
            "color": color,
            "fields": fields,
            "footer": {"text": f"{date_str} • Pure Open-Meteo Engine"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }

def main():
    try:
        lat, lon, final_name = get_coordinates()
        weather, aqi = get_weather_data(lat, lon)
        payload = build_discord_payload(weather, aqi, final_name)
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15).raise_for_status()
        print(f"✅ Success! Notification sent.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
