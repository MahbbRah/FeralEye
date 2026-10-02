# 📺 FeralEye: 2GB RAM TV Box 24/7 Deployment & Optimization Guide

This guide details how to turn a spare **2GB RAM Android TV Box** (Amlogic, Rockchip, Allwinner, Tanix, X96, Mi Box, etc.) into a dedicated, low-power, 24/7 AI edge guard.

---

## 💡 Can a 2GB RAM TV Box Handle FeralEye?

**Yes, easily!** When configured with FeralEye's low-overhead settings:

| Component | RAM Usage |
| :--- | :--- |
| **Base OS (Android TV / Armbian Linux)** | ~350 – 500 MB |
| **FeralEye Runtime (`yolo11n` + Sub-stream + 416px)** | **~250 – 300 MB** |
| **Free / Buffer RAM Margin** | **~1.2 GB+ available** |

Total footprint is **under 800 MB**, leaving over 1.2 GB of RAM headroom.

---

## 🛠️ Choose Your TV Box Setup Path

- [**Path A: Stock Android / Android TV OS**](#-path-a-stock-android--android-tv-no-flashing-required) *(Recommended if you want to keep the existing Android OS)*
- [**Path B: Armbian / Linux Server**](#-path-b-armbian--debian-linux-flashed-box) *(Recommended if your box is already running Armbian or you want a pure Linux headless server)*

---

## 🚀 Path A: Stock Android / Android TV (No Flashing Required)

### Step 1: Install Termux on the TV Box

> [!WARNING]
> Do **NOT** install Termux from Google Play Store (it is outdated). Use the F-Droid build.

1. Download the latest **Termux APK** (`arm64-v8a` or `universal`) from [F-Droid Termux Releases](https://f-droid.org/packages/com.termux/).
2. Copy the APK to a **USB flash drive** and insert it into the TV box, OR install it via **ADB**:
   ```bash
   # From your Mac / PC on the same Wi-Fi network:
   adb connect <tv_box_ip>:5555
   adb install Termux.apk
   ```
3. Open Termux on the TV Box (use a USB mouse / TV remote / ADB shell).

---

### Step 2: Set Up Remote SSH Access (Control from Mac / PC)

Open Termux on the TV box and run:

```bash
# 1. Update Termux package lists
pkg update && pkg upgrade -y

# 2. Install OpenSSH
pkg install openssh -y
ssh-keygen -A

# 3. Set a password for Termux
passwd

# 4. Check your username and IP
whoami
ifconfig | grep "inet "

# 5. Start SSH daemon
sshd
```

**Connect from your Mac/PC terminal**:
```bash
# Termux uses port 8022 by default
ssh <username>@<tv_box_ip> -p 8022
```
*(Example: `ssh u0_a45@192.168.1.180 -p 8022`)*

---

### Step 3: Install Pre-Compiled ARM64 Vision Libraries

To avoid compiling heavy C/C++ packages:

```bash
# 1. Enable TUR and X11 repositories
pkg install x11-repo tur-repo -y

# 2. Install pre-built OpenCV, PyTorch, NumPy, Pillow, and system dependencies
pkg install opencv-python python-torch python-torchvision python-numpy python-pillow dbus libglvnd python-cryptography git make cmake -y
```

---

### Step 4: Clone FeralEye & Install Python Dependencies

```bash
# 1. Clone repository
git clone https://github.com/MahbbRah/FeralEye.git
cd FeralEye

# 2. Install lightweight dependencies without heavy training extras
pip install ultralytics --no-deps
pip install python-dotenv requests pyyaml tqdm
```

---

### Step 5: Configure `.env` for 2GB RAM TV Box

```bash
cp .env.example .env
nano .env
```

Apply the **2GB RAM TV Box Optimized Preset**:
```ini
# Use Camera Sub-stream (640x720 / 640x360) - critical for low memory
CAMERA_RTSP_URL=rtsp://192.168.1.233/live/ch00_1
STREAM_BACKEND=opencv

# Ultra-lightweight YOLO11 Nano model
MODEL_NAME=yolo11n.pt
INFERENCE_IMAGE_SIZE=416
DETECTION_FPS=0.5

# Detection targets & thresholds
TARGET_CLASSES=["cat", "dog"]
CONFIDENCE_THRESHOLD=0.25
ALERT_COOLDOWN_SEC=180.0

# Memory-optimized video clip buffer (5s pre + 10s post)
RECORD_EVENT_VIDEO=true
VIDEO_PRE_BUFFER_SEC=5.0
VIDEO_POST_BUFFER_SEC=10.0

# Notifications (ntfy.sh instant push)
NTFY_ENABLED=true
NTFY_TOPIC=my_feraleye_alerts_123
NTFY_PRIORITY=urgent

# Google Drive Sync (Optional)
GDRIVE_SYNC_ENABLED=false
```

---

### Step 6: Test & Run 24/7 in Background

1. **Verify Stack**:
   ```bash
   python -c "import cv2, torch, ultralytics; from config import config; print('✅ FeralEye AI stack loaded successfully on TV Box!')"
   ```
2. **Prevent Sleep (Wake Lock)**:
   ```bash
   termux-wake-lock
   ```
3. **Start 24/7 Background Service**:
   ```bash
   nohup python main.py > logs/camera_guard.log 2>&1 &
   ```
4. **View Live Logs**:
   ```bash
   tail -f logs/camera_guard.log
   ```

---

## 🐧 Path B: Armbian / Debian Linux (Flashed Box)

If your TV box runs Armbian or Debian:

### Step 1: Install System Packages
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv python3-opencv ffmpeg git
```

### Step 2: Set Up Python Virtual Environment
```bash
git clone https://github.com/MahbbRah/FeralEye.git
cd FeralEye

python3 -m venv venv
source venv/bin/activate

# Install dependencies (CPU PyTorch + Ultralytics)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### Step 3: Configure `.env`
Apply the same 2GB RAM optimized preset as shown in Step 5 above.

### Step 4: Create a Systemd Service (Auto-Start on Boot)

```bash
sudo nano /etc/systemd/system/feraleye.service
```

Paste:
```ini
[Unit]
Description=FeralEye Edge AI Camera Guard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/FeralEye
ExecStart=/root/FeralEye/venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=append:/root/FeralEye/logs/camera_guard.log
StandardError=append:/root/FeralEye/logs/camera_guard.log

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable feraleye
sudo systemctl start feraleye
```

---

## ⚙️ 2GB RAM Tuning Cheat Sheet

| Setting | Recommendation for 2GB RAM | Why |
| :--- | :--- | :--- |
| **Stream** | `ch00_1` (Sub-stream) | Saves ~200MB video frame buffer & reduces CPU load by 75%. |
| **Model** | `yolo11n.pt` | Model size is only 5.6MB; inference takes ~250ms on ARM CPU. |
| **`INFERENCE_IMAGE_SIZE`** | `416` | Cuts compute operations in half compared to 640px while maintaining accuracy. |
| **`DETECTION_FPS`** | `0.5` (1 frame every 2s) | Keeps CPU cool (< 15% load) without thermal throttling. |
| **`VIDEO_PRE_BUFFER_SEC`** | `5.0` | Keeps rolling frame memory queue under 30MB RAM. |
| **Swap / ZRAM** | Enable 1GB ZRAM/Swap | Guarantees Android/Linux OOM killer never terminates the process. |

---

## 🆘 Quick Troubleshooting

- **Out of Memory / Process Killed**: Verify `CAMERA_RTSP_URL` uses the sub-stream (`ch00_1`) and `VIDEO_PRE_BUFFER_SEC=5.0`.
- **High CPU / Heat**: Set `DETECTION_FPS=0.5` and `INFERENCE_IMAGE_SIZE=416`.
- **Auto-Sleep / Disconnections**: Run `termux-wake-lock` or set Android TV developer settings -> "Stay awake while plugged in".
