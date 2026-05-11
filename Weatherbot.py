import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv(override=False)

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
LOCATION = os.getenv("LOCATION", "Kuala Lumpur")  # default location to KL

## Thresholds for recommendations so like it uses to calculate the recommendation to bring an umbrella or not, what time you should head home to avoid heavy rain, etc. You can adjust these based on your preferences or local weather patterns.
RAIN_CHANCE_THRESHOLD = 40      # % chance of rain to trigger umbrella warning
HEAVY_RAIN_THRESHOLD = 55       # % chance of rain considered "heavy rain risk"
HOT_TEMP_THRESHOLD = 33         # °C — recommend sunglasses above this
UV_HIGH_THRESHOLD = 6           # UV index considered high
AQI_WARNING_THRESHOLD = 3         # AQI — recommend mask above this
CO_HIGH_THRESHOLD = 4400            # μg/m³ — high air pollution level


def get_weather():
    """Fetch today + tomorrow forecast from WeatherAPI."""
    url = "http://api.weatherapi.com/v1/forecast.json"
    params = {
        "key": WEATHER_API_KEY,
        "q": LOCATION,
        "days": 2, # keep it as 2 if not we will receive a index error when trying to access tomorrow's data        
        "aqi": "yes",       # include air quality data
        "alerts": "yes",    # include any weather alerts
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def pick_emoji(condition_text, chance_of_rain):
    """Pick a weather emoji based on condition."""
    c = condition_text.lower()
    if "thunder" in c:
        return "⛈️"
    elif "heavy rain" in c or chance_of_rain >= 80:
        return "🌧️"
    elif "rain" in c or "drizzle" in c or chance_of_rain >= 40:
        return "🌦️"
    elif "cloud" in c or "overcast" in c:
        return "☁️"
    elif "sun" in c or "clear" in c:
        return "☀️"
    elif "fog" in c or "mist" in c:
        return "🌫️"
    else:
        return "🌤️"


def analyze_hourly(hourly_data):
    rain_windows = []
    current_window = None

    for hour in hourly_data:
        time_str = hour["time"] 
        hour_dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        hour_num = hour_dt.hour
        rain_chance = hour["chance_of_rain"]
        precip_mm = hour["precip_mm"]

        # If it's heavy rain and during "active" hours
        if (rain_chance >= HEAVY_RAIN_THRESHOLD or precip_mm >= 2.0) and 7 <= hour_num <= 23:
            if current_window is None:
                current_window = {"start": hour_num, "end": hour_num, "total_chance": rain_chance, "count": 1}
            else:
                current_window["end"] = hour_num
                current_window["total_chance"] += rain_chance
                current_window["count"] += 1
        else:
            if current_window is not None:
                current_window["avg_chance"] = round(current_window["total_chance"] / current_window["count"])
                rain_windows.append(current_window)
                current_window = None

    if current_window: # Catch window ending at 11 PM
        current_window["avg_chance"] = round(current_window["total_chance"] / current_window["count"])
        rain_windows.append(current_window)

    return rain_windows


def format_time(hour_num):
    """Convert 24h int to readable string like '3:00 PM'."""
    dt = datetime.now().replace(hour=hour_num, minute=0)
    return dt.strftime("%-I:%M %p") if os.name != "nt" else dt.strftime("%I:%M %p").lstrip("0")


def build_discord_payload(data):
    """Build the Discord embed payload from weather data."""
    tomorrow = data["forecast"]["forecastday"][1]
    day = tomorrow["day"]
    date_str = tomorrow["date"]
    date_display = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %d %b %Y")

    condition = day["condition"]["text"]
    max_temp = day["maxtemp_c"]
    min_temp = day["mintemp_c"]
    avg_temp = day["avgtemp_c"]
    rain_chance = day["daily_chance_of_rain"]
    uv_index = day["uv"]
    max_wind = day["maxwind_kph"]
    total_precip = day["totalprecip_mm"]

    weather_emoji = pick_emoji(condition, rain_chance)

    
    tips = []
    color = 0x57F287  

    if rain_chance >= HEAVY_RAIN_THRESHOLD:
        tips.append("☂️ **Bring an umbrella** — high chance of rain tomorrow")
        color = 0x5865F2  # blue
    elif rain_chance >= RAIN_CHANCE_THRESHOLD:
        tips.append("🌂 Might want an umbrella — some rain possible")
        color = 0xFEE75C  # yellow

    if max_temp >= HOT_TEMP_THRESHOLD:
        tips.append("😎 **Bring sunglasses** — it'll be hot and sunny")

    if uv_index >= UV_HIGH_THRESHOLD:
        tips.append(f"🧴 UV index is **{uv_index}** — wear sunscreen")

    if max_wind >= 40:
        tips.append(f"💨 Strong winds up to {max_wind:.0f} km/h — hold onto your stuff")

    # ── Heavy rain timing analysis ────────────────────────────────────────────
    hourly = tomorrow["hour"]
    rain_windows = analyze_hourly(hourly)

    timing_lines = []
    suggested_departure = False  

    for window in rain_windows:
        start_time = format_time(window["start"])
        end_time = format_time(window["end"])
        avg_c = window["avg_chance"]

        # Create the timing line showing the average
        if window["start"] == window["end"]:
            timing_lines.append(f"• At **{start_time}**, expect heavy rain ({avg_c}% avg)")
        else:
            timing_lines.append(f"• Between **{start_time}** and **{end_time}**, expect heavy rain ({avg_c}% avg)")

        # Suggest going home ONLY for afternoon/evening commute windows (3 PM to 8 PM)
        if 15 <= window["start"] <= 20 and not suggested_departure:
            safe_hour = max(window["start"] - 1, 0)
            tips.append(f"🚗 **Head home by {format_time(safe_hour)}** to avoid becoming 落汤鸡！")
            suggested_departure = True

    # ── AQI and CO analysis ───────────────────────────────────────────────────
    aqi_data = tomorrow["hour"][12].get("air_quality", {})
    aqi_index = aqi_data.get("us-epa-index", None)
    pm25 = aqi_data.get("pm2_5", None)
    co = aqi_data.get("co", None)

    if aqi_index == 0:
        aqi_index = None  # treat 0 as no data

    aqi_labels = {
        1: ("Good", "🟢"),
        2: ("Moderate", "🟡"),
        3: ("Unhealthy for sensitive groups", "🟠"),
        4: ("Unhealthy", "🔴"),
        5: ("Very Unhealthy", "🟣"),
        6: ("Hazardous", "⚫"),
    }

    if aqi_index and aqi_index >= AQI_WARNING_THRESHOLD:
        label, emoji = aqi_labels[aqi_index]
        tips.append(f"{emoji} Air quality is **{label}** — consider wearing a mask outside")

    if co and co >= CO_HIGH_THRESHOLD:
        tips.append("🚨 **High carbon monoxide levels** — avoid heavy traffic areas and stay indoors if possible")

    if not tips:
        tips.append("✅ Looks like a nice day! No special prep needed.")

    # ── Hourly rain breakdown (afternoon only, 10am–10pm) ────────────────────
    hourly_summary = []
    for hour in hourly:
        dt = datetime.strptime(hour["time"], "%Y-%m-%d %H:%M")
        if 10 <= dt.hour <= 22:
            chance = hour["chance_of_rain"]
            if chance >= 30:
                bar_len = round(chance / 10)
                bar = "█" * bar_len + "░" * (10 - bar_len)
                hourly_summary.append(
                    f"`{dt.strftime('%I %p').lstrip('0'):>5}` {bar} {chance}%"
                )

    # ── Build embed Discord ───────────────────────────────────────────────────────────
    description = "\n".join(tips)

    fields = [
        {
            "name": "🌡️ Temperature",
            "value": f"{min_temp:.0f}°C – {max_temp:.0f}°C (avg {avg_temp:.0f}°C)",
            "inline": True,
        },
        {
            "name": "🌧️ Rain chance",
            "value": f"{rain_chance}% ({total_precip:.1f}mm total)",
            "inline": True,
        },
        {
            "name": "☀️ UV Index",
            "value": str(uv_index),
            "inline": True,
        },
        {
            "name": "💨 Air Quality",
            "value": (f"{aqi_labels[aqi_index][1]} {aqi_labels[aqi_index][0]}\n"
                f"PM2.5: {pm25:.1f} µg/m³ | CO: {co:.1f} µg/m³"
            ) if (aqi_index and pm25 is not None and co is not None) else "No data",
            "inline": True,
        },
    ]

    if timing_lines:
        fields.append({
            "name": "⏰ Heavy rain expected",
            "value": "\n".join(timing_lines),
            "inline": False,
        })

    if hourly_summary:
        fields.append({
            "name": "📊 Rain forecast (10am–10pm)",
            "value": "\n".join(hourly_summary),
            "inline": False,
        })

    # Check for any weather alerts
    alerts = data.get("alerts", {}).get("alert", [])
    if alerts:
        alert_text = "\n".join([f"⚠️ {a['headline']}" for a in alerts[:2]])
        fields.append({
            "name": "🚨 Weather alerts",
            "value": alert_text,
            "inline": False,
        })

    payload = {
        "username": "Weather-Chan 🌤️",
        "embeds": [
            {
                "title": f"{weather_emoji} Tomorrow's Weather — {LOCATION}",
                "description": description,
                "color": color,
                "fields": fields,
                "footer": {
                    "text": f"{date_display}  •  Powered by WeatherAPI"
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        ],
    }
    return payload


def send_to_discord(payload):
    """POST the payload to your Discord webhook."""
    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    print(f"✅ Sent to Discord! ({datetime.now().strftime('%Y-%m-%d %H:%M')})")


def main():
    if not WEATHER_API_KEY:
        raise ValueError("WEATHER_API_KEY not set in .env")
    if not DISCORD_WEBHOOK_URL:
        raise ValueError("DISCORD_WEBHOOK_URL not set in .env")

    print(f"Fetching weather for {LOCATION}...")
    data = get_weather()
    payload = build_discord_payload(data)
    send_to_discord(payload)


if __name__ == "__main__":
    main()
