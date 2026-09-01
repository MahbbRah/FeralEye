# 📱 FeralEye: Complete Android & Termux 24/7 Deployment Guide

This guide documents the exact, field-tested installation procedure, performance tuning, and troubleshooting solutions for running **FeralEye** 24/7 on an old or budget Android phone as a dedicated edge AI camera appliance.

---

## 🎯 Why Use an Old Android Phone?

- **Zero Added Cost**: Repurposes old or cracked-screen smartphones (4GB+ RAM recommended).
- **Ultra-Low Power**: Consumes $< 1.5\text{W}$ (under \$2/year electricity).
- **Built-in UPS Battery**: Remains online during power outages and blackouts.
- **Dedicated Hardware**: Runs completely standalone without requiring a PC, Mac, or Raspberry Pi.

---

## 🚀 Quick Step-by-Step Installation Recipe

### Step 1: Install Termux (F-Droid Only)

> [!WARNING]
> Do **NOT** install Termux from the Google Play Store (it is deprecated and will fail to install packages).

1. Download and install **Termux** from [F-Droid](https://f-droid.org/packages/com.termux/).
2. Open Termux on your phone.

---

### Step 2: Set Up SSH Access (Control from Mac / PC)

Typing long commands on a phone touch keyboard is tedious. Setting up SSH allows you to paste commands directly from your computer terminal.

In **Termux**, run:
```bash
# 1. Update Termux package mirrors
pkg update && pkg upgrade -y

# 2. Install OpenSSH & generate host keys
pkg install openssh -y
ssh-keygen -A

# 3. Set a password for your Termux user
passwd

# 4. Check your Termux username (e.g. u0_a123)
whoami

# 5. Start the SSH server
sshd
```

**Find Phone's IP Address**:
- On phone: `Settings → Wi-Fi → Tap connected Wi-Fi name → Note the IP address` (e.g. `192.168.1.150`).

**Connect from your Computer Terminal**:
```bash
# Note: Termux SSH runs on port 8022 (not default port 22)
ssh <your_username>@<phone_ip> -p 8022
```
*Example:* `ssh u0_a123@192.168.1.150 -p 8022`

---

### Step 3: Install Pre-compiled ARM64 Native Packages

> [!IMPORTANT]
> Do **not** compile heavy C/C++ vision libraries (OpenCV / PyTorch) from source via `pip`. Using Termux's pre-compiled binaries installs in **5 seconds** instead of taking 1+ hours.

In your SSH window, run:

```bash
# 1. Enable Termux X11 and TUR (User Repository) mirrors
pkg install x11-repo tur-repo -y

# 2. Install native pre-compiled OpenCV, PyTorch, NumPy, and system libraries
pkg install opencv-python python-torch python-torchvision python-numpy python-pillow dbus libglvnd python-cryptography git make cmake -y
```

---

### Step 4: Clone FeralEye & Install Python Dependencies

```bash
# 1. Clone the repository
git clone https://github.com/MahbbRah/FeralEye.git
cd FeralEye

# 2. Install lightweight Python dependencies
# (We use --no-deps on ultralytics to avoid compiling heavy training plotting libraries)
pip install ultralytics --no-deps
pip install python-dotenv requests pyyaml tqdm
```

---

### Step 5: Configure `.env` for Mobile Hardware

Copy the example configuration:
```bash
cp .env.example .env
nano .env
```

Set these mobile-optimized settings:
```ini
# Use camera's lightweight 640x720 sub-stream (saves 80% CPU decoding load)
CAMERA_RTSP_URL=rtsp://192.168.1.233/live/ch00_1
STREAM_BACKEND=opencv

# Use the lightweight Nano model
MODEL_NAME=yolo11n.pt
INFERENCE_IMAGE_SIZE=416
DETECTION_FPS=0.5

# Monitored Targets
TARGET_CLASSES=["cat", "dog"]
CONFIDENCE_THRESHOLD=0.25
ALERT_COOLDOWN_SEC=180.0

# 20-Second Event Video Recording
RECORD_EVENT_VIDEO=true
VIDEO_PRE_BUFFER_SEC=10.0
VIDEO_POST_BUFFER_SEC=10.0

# Smartphone Push Notifications
NTFY_ENABLED=true
NTFY_TOPIC=my_feraleye_alerts_123
NTFY_PRIORITY=urgent

# Google Drive Cloud Backup (Optional)
GDRIVE_SYNC_ENABLED=false
```
*(Press `Ctrl + O` then `Enter` to save, and `Ctrl + X` to exit nano)*

---

### Step 6: Verify Installation

Run the built-in diagnostic test:
```bash
# 1. Test AI Vision Stack
python -c "import cv2, torch, ultralytics; from config import config; print('✅ FeralEye AI stack verified successfully on Android!')"

# 2. Test Smartphone Push Notification
python tools/test_alerts.py --channel ntfy
```

---

### Step 7: Run 24/7 Headless (Screen Off)

To ensure Android does not kill the app when you turn off the screen:

1. **Acquire Termux Wake Lock**:
   ```bash
   termux-wake-lock
   ```
   *(A lock icon will appear in your notification bar saying "Termux wake lock held").*

2. **Disable Android Battery Optimization**:
   On your phone: `Settings → Apps → Termux → Battery → Select "Unrestricted" (or "Don't Optimize")`.

3. **Start Background Service**:
   ```bash
   nohup python main.py > logs/camera_guard.log 2>&1 &
   ```

4. **Monitor Live Logs**:
   ```bash
   tail -f logs/camera_guard.log
   ```
   *(To stop the background service later: `pkill -f main.py`)*

---

## 🛠️ Field Troubleshooting & Common Gotchas

During initial testing, several edge-case Android issues were encountered and resolved. Here are the solutions:

### 1. `ERROR: Installing pip is forbidden, this will break the python-pip package (termux)`
- **Cause**: Termux manages `pip` through its APT package manager.
- **Solution**: Do not run `pip install --upgrade pip`. Run `pip install <package>` directly.

---

### 2. `ImportError: dlopen failed: library "libdbus-1.so" not found`
- **Cause**: Pre-compiled `opencv-python` links dynamically against Qt6, which requires DBus.
- **Solution**:
  ```bash
  pkg install dbus libglvnd -y
  ```

---

### 3. `ValueError: Unsupported operating system: Android` (Ultralytics)
- **Cause**: Ultralytics' internal config directory lookup previously only accepted `"Linux"`, `"Darwin"`, or `"Windows"`.
- **Solution**: FeralEye includes an automatic patch ([`utils/android_patch.py`](file:///Volumes/Works/persona-projects/predatorDetectorCamera/utils/android_patch.py)) that transparently maps Android to Linux and sets `YOLO_CONFIG_DIR=~/.config/Ultralytics`.

---

### 4. `Failed to build 'pydantic-core' (Rust/Maturin missing)`
- **Cause**: Standard Pydantic v2 requires compiling Rust binaries.
- **Solution**: FeralEye's [`config.py`](file:///Volumes/Works/persona-projects/predatorDetectorCamera/config.py) is built with 100% pure Python standard library `dataclasses` + `python-dotenv`, eliminating the Rust compiler requirement completely.

---

### 5. `psutil: platform android is not supported`
- **Cause**: Android's SELinux permission sandbox blocks `psutil` system metrics.
- **Solution**: FeralEye treats `psutil` as an optional dependency with an automatic fallback.

---

### 6. `Google Drive Error 403: Service Accounts do not have storage quota`
- **Cause**: Google Service Accounts have 0 MB storage for personal `@gmail.com` accounts.
- **Solution**: Use **User OAuth2** credentials:
  ```bash
  python tools/get_gdrive_token.py
  ```
  Paste the generated `GDRIVE_OAUTH_REFRESH_TOKEN` into `.env` to upload directly into your personal 15GB/5TB storage.

---

### 7. Rooster / Chicken False Positive as Human
- **Cause**: Restricting YOLO class predictions forced probability into `person` because `bird` was suppressed.
- **Solution**: FeralEye enables full-class competition (poultry is recognized as `bird` and discarded), adds a physical height sanity filter, and uses class-specific thresholds (`person: 0.65`, `cat/dog: 0.25`).

---

## ⚡ Performance Optimization Reference

| Setting | Full Resolution (`ch00_0`) | Mobile Optimized (`ch00_1`) |
| :--- | :--- | :--- |
| **Stream Resolution** | $1920 \times 2160$ | $640 \times 720$ |
| **Model** | `yolo11s.pt` (Small) | `yolo11n.pt` (Nano) |
| **Inference Image Size** | `640` | `416` |
| **Inference Latency** | $\approx 6,200\text{ ms}$ | $\mathbf{\approx 250 - 350\text{ ms}}$ |
| **CPU Utilization** | High (Thermal Throttling) | **Low ($< 15\%$, Lukewarm)** |
| **RAM Consumption** | $\approx 450\text{ MB}$ | **$\approx 280\text{ MB}$** |

---

## 📄 License
MIT License
