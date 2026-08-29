"""SMTP Email Alert Notification Provider."""

import smtplib
import logging
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from typing import List, Optional

from alerts.base import BaseAlertHandler
from events.models import ConfirmedAlertEvent

logger = logging.getLogger("camera_guard.alerts.email")


class EmailAlertHandler(BaseAlertHandler):
    """
    Sends structured HTML email notifications with attached evidence images
    via SMTP (Gmail, Outlook, or custom SMTP server).
    """

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        sender_email: str,
        sender_password: str,
        recipient_emails: List[str],
        use_tls: bool = True,
        camera_name: str = "Poultry Pen"
    ):
        self.smtp_server = smtp_server.strip()
        self.smtp_port = smtp_port
        self.sender_email = sender_email.strip()
        self.sender_password = sender_password.strip()
        self.recipient_emails = [e.strip() for e in recipient_emails if e.strip()]
        self.use_tls = use_tls
        self.camera_name = camera_name

    def send_alert(self, event: ConfirmedAlertEvent) -> bool:
        if not self.smtp_server or not self.sender_email or not self.recipient_emails:
            logger.warning("Email alert skipped: incomplete SMTP configuration.")
            return False

        best_det = event.best_result.best_detection
        class_name = best_det.class_name.upper() if best_det else "PREDATOR"
        conf_pct = best_det.confidence * 100 if best_det else 0.0
        time_str = event.triggered_at.strftime("%Y-%m-%d %H:%M:%S")

        subject = f"🚨 [PREDATOR ALERT] {class_name} Detected at {self.camera_name} ({time_str})"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f8f9fa; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="background-color: #d9534f; color: #ffffff; padding: 15px 20px;">
                    <h2 style="margin: 0;">🚨 Predator Alert Detected</h2>
                </div>
                <div style="padding: 20px;">
                    <p style="font-size: 16px; color: #333333;">A <strong>{class_name}</strong> was detected and confirmed by the camera guard system.</p>
                    <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eeeeee;"><strong>📍 Location:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eeeeee;">{self.camera_name}</td></tr>
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eeeeee;"><strong>🐾 Target:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eeeeee; color: #d9534f; font-weight: bold;">{class_name}</td></tr>
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eeeeee;"><strong>🎯 Confidence:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eeeeee;">{conf_pct:.1f}%</td></tr>
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eeeeee;"><strong>⏱️ Timestamp:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eeeeee;">{time_str}</td></tr>
                        <tr><td style="padding: 8px; border-bottom: 1px solid #eeeeee;"><strong>🆔 Event ID:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eeeeee;">{event.event_id}</td></tr>
                    </table>
                    <p style="margin-top: 20px; font-size: 13px; color: #777777;">See attached evidence photo for verified bounding box coordinates.</p>
                </div>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart("related")
        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = ", ".join(self.recipient_emails)

        msg.attach(MIMEText(html_content, "html"))

        # Attach photo
        photo_path = event.evidence_image_path
        if photo_path and Path(photo_path).exists():
            try:
                with open(photo_path, "rb") as f:
                    img = MIMEImage(f.read())
                    img.add_header("Content-Disposition", "attachment", filename=Path(photo_path).name)
                    msg.attach(img)
            except Exception as e:
                logger.error(f"Failed to attach image to email: {e}")

        try:
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10.0)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=10.0)

            if self.sender_password:
                server.login(self.sender_email, self.sender_password)

            server.sendmail(self.sender_email, self.recipient_emails, msg.as_string())
            server.quit()
            logger.info(f"✅ Alert email sent successfully to: {self.recipient_emails}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
