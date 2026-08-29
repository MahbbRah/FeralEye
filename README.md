# 🐾 FeralEye: Local AI Predator & Cat Detection Camera Guard

**FeralEye** is a lightweight, edge-optimized, always-running predator detection system designed for IP cameras (V380/ONVIF/RTSP). It continuously monitors sensitive areas (e.g., poultry pens, gardens, livestock) using state-of-the-art YOLO vision models without requiring cloud services, proprietary apps, or recurring subscriptions.

---

## ✨ Features

- **⚡ Lightweight & Fast**: Samples frames at 1 FPS, utilizing `< 2%` CPU on Apple Silicon / edge devices with `yolo11s` / `yolo11n`.
- **🛡️ Sliding-Window Confirmation**: Requires multiple positive detections across a configurable time window (e.g., $\ge 2$ detections in 4 seconds) to eliminate transient false positives.
- **📸 Automated Evidence Capture**: Automatically annotates and archives high-resolution evidence photos with bounding boxes, confidence scores, and timestamps.
- **🚨 Instant Multi-Channel Alerts**:
  - **Ntfy.sh**: Free, instant smartphone push alarms with urgent sirens and attached photos.
  - **Telegram Bot**: Instant photo and metadata push notifications.
  - **Discord Webhooks**: Embedded alert cards in private channels.
  - **SMTP Email**: Full HTML alert emails with photo attachments.
  - **Local Audio Siren**: Physical audio deterrent alarm played through device speakers.
  - **Home Assistant Webhooks**: Smart-home triggers for floodlights, sirens, and sprinklers.
- **🔄 Auto-Healing Stream Ingestion**: Threaded OpenCV & native FFmpeg readers with exponential backoff auto-reconnect.
- **⏱️ Smart Cooldown**: Configurable cooldown (e.g., 3 minutes) prevents notification storms.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    Camera["V380 / ONVIF IP Camera\n(RTSP H.265 Stream)"] --> Reader["Threaded Frame Reader\n(OpenCV / FFmpeg Buffer-1)"]
    Reader --> Sampler["1 FPS Rate Limiter"]
    Sampler --> Motion["Optional Motion Pre-Filter"]
    Motion --> YOLO["YOLO11 Object Detector\n(Cat / Predator Class Filter)"]
    YOLO --> StateEngine["Confirmation State Engine\n(Sliding Window & Cooldown)"]
    StateEngine -- "Confirmed Event" --> Evidence["Evidence Storage\n(Annotated Photo)"]
    StateEngine -- "Confirmed Event" --> Dispatcher["Async Alert Dispatcher"]
    Dispatcher --> Ntfy["Ntfy Push Alarm"]
    Dispatcher --> Telegram["Telegram Bot"]
    Dispatcher --> Discord["Discord Webhook"]
    Dispatcher --> Email["SMTP Email"]
    Dispatcher --> Audio["Local Speaker Siren"]
```

---

## 🚀 Quick Start

### 1. Clone & Setup Virtual Environment

```bash
git clone https://github.com/MahbbRah/FeralEye.git
cd FeralEye

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example configuration:
```bash
cp .env.example .env
```

Edit `.env` with your camera stream and notification settings:
```ini
# Camera Stream
CAMERA_RTSP_URL=rtsp://192.168.1.233/live/ch00_0
STREAM_BACKEND=opencv

# Detection
MODEL_NAME=yolo11s.pt
TARGET_CLASSES=["cat", "dog"]
CONFIDENCE_THRESHOLD=0.25

# Alerts (Ntfy Push Notification)
NTFY_ENABLED=true
NTFY_TOPIC=my_feraleye_alerts_123
NTFY_PRIORITY=urgent
```

### 3. Run the Service

```bash
python main.py
```

---

## 🧪 Testing & Verification Tools

### Test Camera Stream
```bash
python tests/test_stream.py
```

### Test Smartphone Push Alerts
```bash
python tools/test_alerts.py --channel ntfy
```

### Offline Media Evaluator (Historical Photos / Videos)
```bash
# Evaluate a folder of images/videos
python tools/evaluate.py --source ./test_inputs --classes "cat,dog" --conf 0.25

# Simulate a recorded video clip in real-time
python tools/simulate_stream.py /path/to/recorded_clip.mp4
```

---

## 📂 Project Structure

```
FeralEye/
├── .env.example               # Configuration template
├── config.py                  # Pydantic settings & validation
├── main.py                    # Main service orchestrator
├── requirements.txt           # Minimal dependencies
│
├── camera/                    # RTSP stream readers (OpenCV & FFmpeg)
├── detection/                 # YOLO11 detector & optional motion filter
├── events/                    # Sliding-window state machine & data models
├── evidence/                  # Evidence image annotator & storage
├── alerts/                    # Dispatcher & multi-channel notification providers
├── tools/                     # Evaluation, simulation & alert test utilities
└── utils/                     # Multi-channel structured logger
```

---

## 📄 License
MIT License
