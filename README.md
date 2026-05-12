# 🌦️ Weather-Chan: Smart Discord Weather Bot

A lightweight, highly accurate Python automation script that sends localized weather forecasts and air quality alerts to Discord. Powered by **Open-Meteo**, this bot is specifically tuned to handle the unpredictable tropical weather patterns of Southeast Asia (like Kuala Lumpur).

---

## 📸 Preview | 预览
<p align="center">
  <img width="477" height="493" alt="WeatherChan1" src="https://github.com/user-attachments/assets/5a14f17c-5acf-4e2e-aa02-cd4f14d5e5e8" />
</p>

---

## 🚀 Features | 功能特点

* **High-Accuracy Forecasts:** Uses high-resolution models (**ECMWF/ICON**) to fix the "100% rain" inaccuracies common in tropical climates.
* **Commute Intelligence:** Automatically calculates if you should leave work early (around 3 PM - 6 PM) based on predicted heavy rain windows.
* **Air Quality Monitoring:** Tracks US-EPA AQI and Carbon Monoxide (CO) levels with health-based thresholds.
* **Zero Key Setup:** Uses Open-Meteo's open-data API, no more managing API keys for weather data.
* **Visual Reports:** Includes a rain probability bar chart (10 AM - 10 PM) for quick visual scanning.

---

## 🛠️ Configuration | 配置指南

This bot is designed to run via **GitHub Actions**. Follow these steps to set it up:

1. **Clone/Fork the repository** to your GitHub account.
2. Navigate to your repo **Settings** > **Secrets and variables** > **Actions**.
3. Create two **Repository secrets**:
   * `LOCATION`: Your city (e.g., `Kuala Lumpur`).
   * `DISCORD_WEBHOOK_URL`: Your Discord channel's webhook URL.
4. Go to the **Actions** tab and manually run the workflow file to verify the connection.
5. 🥳 **Congratulations!** Your bot will now run automatically on your scheduled time.

---

## 📊 Thresholds & Standards | 阈值与标准

| Parameter | Threshold | Action | Note |
| :--- | :--- | :--- | :--- |
| **Rain Chance** | 40% | Umbrella Tip | Standard preparation |
| **Heavy Rain** | 70% | Commute Alert | Triggers "Head home early" logic |
| **AQI (US-EPA)** | 101 | Mask Warning | Unhealthy for sensitive groups |
| **CO (WHO)** | 4400 µg/m³ | Health Alert | Based on WHO 24h Guidelines |

---

## 📚 References | 参考资料

This project utilizes standards and data from the following authoritative sources:

* **[Open-Meteo API](https://open-meteo.com/):** Primary weather and air quality engine.
* **[Data.gov.my](https://developer.data.gov.my/realtime-api/weather#source-of-weather-data):** Reference for Malaysia-specific weather data sources.
* **[R-PUR Health Guide](https://www.r-pur.com/en/blogs/air/%C2%B5g-m-3-aqi):** Guidance on translating µg/m³ to AQI.
* **[WHO Guidelines](https://www.who.int/news-room/fact-sheets/detail/ambient-(outdoor)-air-quality-and-health):** CO thresholds aligned with 2021 Global Air Quality Guidelines.
* **[WeatherAPI](https://www.weatherapi.com/):** Historical logic reference.

---

## 📝 中文说明 (Chinese Version)

这是一个轻量级的 Python 自动化脚本，通过 Discord Webhook 发送精准的本地天气预报和空气质量提醒。针对吉隆坡等热带地区，本项目切换至 Open-Meteo 引擎，大幅提升了降雨预测的准确性。

### 核心功能：
* **通勤优化：** 针对 18:00 下班的用户，自动分析 15:00-18:00 的强降雨窗口，提前发出“早点回家”建议，避免成为“落汤鸡”。
* **精细空气质量：** 监测 US-EPA AQI 及一氧化碳 (CO) 浓度，并根据 WHO 最新标准提供防护建议。
* **免密钥设计：** 无需注册 WeatherAPI 密钥，开箱即用。

### 配置步骤 (GitHub Actions)：
1. **Fork 或克隆** 本仓库到你的 GitHub 账号。
2. 进入仓库的 **Settings** > **Secrets and variables** > **Actions**。
3. 创建两个 **Repository secrets**:
   * `LOCATION`: 你所在的城市 (例如：`Kuala Lumpur`)。
   * `DISCORD_WEBHOOK_URL`: 你的 Discord 频道 Webhook URL。
4. 前往 **Actions** 标签页，手动运行一次 Workflow 文件以测试连接。
5. **设置完成！** 机器人将根据预设时间自动运行。

---

## 📄 License | 许可证
This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
本项目采用 **MIT 许可证** - 详情请参阅 [LICENSE](LICENSE) 文件。
