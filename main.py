import time
import signal
import sys
from typing import List

import utils.android_patch  # noqa: F401

try:
    import psutil
    has_psutil = True
except ImportError:
    psutil = None
    has_psutil = False

from config import config
from utils.logger import setup_logger
from camera.cv_stream import OpenCVRTSPStream
from camera.ffmpeg_stream import FFmpegRTSPStream
from detection.yolo_detector import YOLODetector
from detection.motion_filter import MotionFilter
from events.state_engine import DetectionStateEngine, State
from evidence.storage import EvidenceStorage
from evidence.clip_recorder import EventVideoRecorder
from evidence.retention import EvidenceRetention
from cloud.gdrive_sync import GoogleDriveSync
from alerts.base import BaseAlertHandler
from alerts.console_alert import ConsoleAlertHandler
from alerts.telegram_alert import TelegramAlertHandler
from alerts.ntfy_alert import NtfyAlertHandler
from alerts.discord_alert import DiscordAlertHandler
from alerts.email_alert import EmailAlertHandler
from alerts.webhook_alert import WebhookAlertHandler
from alerts.audio_alert import AudioDeterrentAlertHandler
from alerts.dispatcher import AlertDispatcher


def build_alert_dispatcher() -> AlertDispatcher:
    """Builds the list of enabled alert handlers and wraps them in a threadpool dispatcher."""
    handlers: List[BaseAlertHandler] = [
        ConsoleAlertHandler()  # Always log to console/log file
    ]

    if config.TELEGRAM_ENABLED and config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        handlers.append(
            TelegramAlertHandler(
                bot_token=config.TELEGRAM_BOT_TOKEN,
                chat_id=config.TELEGRAM_CHAT_ID,
                camera_name=config.CAMERA_NAME,
                proxy_url=config.TELEGRAM_PROXY_URL
            )
        )

    if config.NTFY_ENABLED and config.NTFY_TOPIC:
        handlers.append(
            NtfyAlertHandler(
                topic=config.NTFY_TOPIC,
                server_url=config.NTFY_SERVER_URL,
                priority=config.NTFY_PRIORITY,
                camera_name=config.CAMERA_NAME
            )
        )

    if config.DISCORD_ENABLED and config.DISCORD_WEBHOOK_URL:
        handlers.append(
            DiscordAlertHandler(
                webhook_url=config.DISCORD_WEBHOOK_URL,
                camera_name=config.CAMERA_NAME
            )
        )

    if config.EMAIL_ENABLED and config.SMTP_SERVER and config.EMAIL_SENDER and config.EMAIL_RECIPIENTS:
        handlers.append(
            EmailAlertHandler(
                smtp_server=config.SMTP_SERVER,
                smtp_port=config.SMTP_PORT,
                sender_email=config.EMAIL_SENDER,
                sender_password=config.EMAIL_PASSWORD,
                recipient_emails=config.EMAIL_RECIPIENTS,
                use_tls=config.EMAIL_USE_TLS,
                camera_name=config.CAMERA_NAME
            )
        )

    if config.WEBHOOK_ENABLED and config.WEBHOOK_URL:
        handlers.append(
            WebhookAlertHandler(
                webhook_url=config.WEBHOOK_URL,
                camera_name=config.CAMERA_NAME
            )
        )

    if config.AUDIO_ALARM_ENABLED:
        handlers.append(
            AudioDeterrentAlertHandler(
                sound_file=config.AUDIO_ALARM_FILE
            )
        )

    return AlertDispatcher(handlers=handlers)


def main():
    # 1. Initialize logging
    logger = setup_logger(
        name="camera_guard",
        log_file=config.LOG_FILE,
        level=config.LOG_LEVEL
    )
    logger.info("=" * 60)
    logger.info(" Starting Predator & Cat Detection Camera Guard Service")
    logger.info(f" Location Name:       {config.CAMERA_NAME}")
    logger.info(f" Camera Stream:       {config.CAMERA_RTSP_URL}")
    logger.info(f" Stream Backend:      {config.STREAM_BACKEND.upper()}")
    logger.info(f" Model Name:          {config.MODEL_NAME}")
    logger.info(f" Detection Target(s): {config.TARGET_CLASSES}")
    logger.info(f" Target Sampling FPS: {config.DETECTION_FPS:.1f}")
    logger.info(f" Motion Filter:       {'Enabled' if config.ENABLE_MOTION_FILTER else 'Disabled'}")
    logger.info(f" Confirmation Rule:   {config.CONFIRMATION_COUNT} detections in {config.CONFIRMATION_WINDOW_SEC}s")
    logger.info(f" Alert Cooldown:      {config.ALERT_COOLDOWN_SEC}s")
    logger.info("=" * 60)

    # 2. Setup graceful shutdown signals
    running = True

    def handle_shutdown(signum, frame):
        nonlocal running
        sig_name = signal.Signals(signum).name
        logger.info(f"Received shutdown signal ({sig_name}). Stopping service gracefully...")
        running = False

    try:
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
    except ValueError:
        pass  # In case invoked in a subthread

    # 3. Instantiate sub-modules
    if config.STREAM_BACKEND.lower() == "ffmpeg":
        stream = FFmpegRTSPStream(
            rtsp_url=config.CAMERA_RTSP_URL,
            target_fps=config.DETECTION_FPS,
            output_width=1280,
            output_height=720,
            reconnect_initial_delay_sec=config.CAMERA_RECONNECT_INITIAL_DELAY_SEC,
            reconnect_max_delay_sec=config.CAMERA_RECONNECT_MAX_DELAY_SEC,
        )
    else:
        stream = OpenCVRTSPStream(
            rtsp_url=config.CAMERA_RTSP_URL,
            connect_timeout_sec=config.CAMERA_CONNECT_TIMEOUT_SEC,
            reconnect_initial_delay_sec=config.CAMERA_RECONNECT_INITIAL_DELAY_SEC,
            reconnect_max_delay_sec=config.CAMERA_RECONNECT_MAX_DELAY_SEC,
        )

    detector = YOLODetector(
        model_name=config.MODEL_NAME,
        target_classes=config.TARGET_CLASSES,
        confidence_threshold=config.CONFIDENCE_THRESHOLD,
        imgsz=config.INFERENCE_IMAGE_SIZE,
    )

    motion_filter = MotionFilter(
        min_contour_area=config.MOTION_MIN_AREA,
        threshold_delta=config.MOTION_THRESHOLD,
    ) if config.ENABLE_MOTION_FILTER else None

    state_engine = DetectionStateEngine(
        confirmation_count=config.CONFIRMATION_COUNT,
        confirmation_window_sec=config.CONFIRMATION_WINDOW_SEC,
        cooldown_sec=config.ALERT_COOLDOWN_SEC,
    )

    evidence_storage = EvidenceStorage(
        base_dir=config.EVIDENCE_DIRECTORY,
        save_annotated=config.SAVE_ANNOTATED_IMAGE,
        save_raw=config.SAVE_RAW_IMAGE,
    )

    clip_recorder = EventVideoRecorder(
        evidence_directory=config.EVIDENCE_DIRECTORY,
        pre_buffer_sec=config.VIDEO_PRE_BUFFER_SEC,
        post_buffer_sec=config.VIDEO_POST_BUFFER_SEC,
        target_fps=config.VIDEO_CLIP_FPS,
        enabled=config.RECORD_EVENT_VIDEO,
        clip_lengths=config.VIDEO_CLIP_LENGTHS,
    )

    evidence_retention = EvidenceRetention(
        base_dir=config.EVIDENCE_DIRECTORY,
        retention_days=config.RETENTION_LOCAL_DAYS,
        check_interval_sec=config.RETENTION_CHECK_INTERVAL_SEC,
        enabled=True,
    )

    gdrive_sync = GoogleDriveSync(
        service_account_json_path=config.GDRIVE_SERVICE_ACCOUNT_JSON,
        oauth_client_id=config.GDRIVE_OAUTH_CLIENT_ID,
        oauth_client_secret=config.GDRIVE_OAUTH_CLIENT_SECRET,
        oauth_refresh_token=config.GDRIVE_OAUTH_REFRESH_TOKEN,
        folder_id=config.GDRIVE_FOLDER_ID,
        enabled=config.GDRIVE_SYNC_ENABLED,
        upload_photos=config.GDRIVE_UPLOAD_PHOTOS,
        upload_videos=config.GDRIVE_UPLOAD_VIDEOS,
    )

    alert_dispatcher = build_alert_dispatcher()

    # 4. Start RTSP background reader
    stream.start()

    # Start local evidence retention (background thread; prunes old files on interval)
    evidence_retention.start()

    # 5. Timing and metrics state
    target_interval = 1.0 / max(0.1, config.DETECTION_FPS)
    last_metrics_log_time = time.time()
    last_cloud_retention_time = time.time()
    frames_processed_count = 0
    total_inference_time_ms = 0.0
    process_handle = psutil.Process() if has_psutil else None

    logger.info("Entering main detection loop...")

    try:
        while running:
            loop_start = time.perf_counter()

            if not stream.is_connected:
                time.sleep(0.5)
                continue

            has_frame, frame = stream.get_latest_frame()
            if not has_frame or frame is None:
                time.sleep(0.05)
                continue

            # Step 1: Optional Motion Pre-Filtering
            should_run_ai = True
            if motion_filter:
                has_motion, motion_area = motion_filter.check_motion(frame)
                if not has_motion:
                    should_run_ai = False
                    logger.debug("No motion detected. Skipping AI inference.")

            # Step 2: AI Detection
            if should_run_ai:
                result = detector.detect(frame)
                frames_processed_count += 1
                total_inference_time_ms += result.inference_time_ms

                # Step 3: State Machine & Confirmation
                state, alert_event = state_engine.process_result(result)

                # Step 4: Handle Confirmed Alert
                if alert_event:
                    # 1. Save evidence image to disk
                    saved_path = evidence_storage.save_event_evidence(alert_event)

                    # 2. Non-blocking concurrent alert dispatch (Push/Telegram/Email)
                    alert_dispatcher.dispatch(alert_event)

                    # 3. Google Drive Sync (Photo immediately upon detection)
                    if config.GDRIVE_SYNC_ENABLED:
                        gdrive_sync.sync_photo_async(alert_event)

                    # 4. 20-Second Event Video Recording (10s Pre-buffer + 10s Post-buffer)
                    if config.RECORD_EVENT_VIDEO:
                        clip_recorder.record_event_clip_async(
                            event=alert_event,
                            stream=stream,
                            on_complete_callback=lambda ev: gdrive_sync.sync_video_async(ev) if config.GDRIVE_SYNC_ENABLED else None
                        )

            # Periodic Telemetry & Performance Logging
            now_sec = time.time()
            if (now_sec - last_metrics_log_time) >= config.METRICS_LOG_INTERVAL_SEC:
                elapsed_sec = now_sec - last_metrics_log_time
                achieved_fps = frames_processed_count / elapsed_sec if elapsed_sec > 0 else 0.0
                avg_latency = total_inference_time_ms / frames_processed_count if frames_processed_count > 0 else 0.0
                mem_mb = (process_handle.memory_info().rss / (1024 * 1024)) if process_handle else 0.0
                cpu_pct = process_handle.cpu_percent() if process_handle else 0.0

                logger.info(
                    f"[Telemetry] Status: {state_engine.current_state.value} | "
                    f"FPS: {achieved_fps:.2f} | Avg Latency: {avg_latency:.1f}ms | "
                    f"CPU: {cpu_pct:.1f}% | RAM: {mem_mb:.1f}MB | Stream: Connected"
                )

                # Reset counters
                last_metrics_log_time = now_sec
                frames_processed_count = 0
                total_inference_time_ms = 0.0

            # Periodic Google Drive cloud retention (older events pruned by GDRIVE_RETENTION_DAYS)
            if config.GDRIVE_SYNC_ENABLED and (now_sec - last_cloud_retention_time) >= config.RETENTION_CHECK_INTERVAL_SEC:
                logger.info("☁️ [Google Drive] Running periodic cloud retention cleanup...")
                try:
                    gdrive_sync.cleanup_old_evidence(retention_days=config.GDRIVE_RETENTION_DAYS)
                except Exception as e:
                    logger.exception(f"Google Drive cloud retention failed: {e}")
                last_cloud_retention_time = now_sec

            # Frame rate throttle
            elapsed_loop = time.perf_counter() - loop_start
            sleep_time = target_interval - elapsed_loop
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received.")
    except Exception as e:
        logger.exception(f"Unhandled fatal error in detection loop: {e}")
    finally:
        logger.info("Cleaning up resources...")
        evidence_retention.stop()
        stream.stop()
        alert_dispatcher.shutdown(wait=False)
        logger.info("Predator Guard service shut down cleanly.")


if __name__ == "__main__":
    main()
