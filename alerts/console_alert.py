"""Console & Structured Log Alert Dispatcher."""

import logging
from alerts.base import BaseAlertHandler
from events.models import ConfirmedAlertEvent

logger = logging.getLogger("camera_guard.alerts")


class ConsoleAlertHandler(BaseAlertHandler):
    """Prints a prominent visual alert block to the console/log."""

    def send_alert(self, event: ConfirmedAlertEvent) -> bool:
        best_det = event.best_result.best_detection
        class_name = best_det.class_name.upper() if best_det else "PREDATOR"
        conf = best_det.confidence if best_det else 0.0

        alert_msg = (
            "\n" + "=" * 60 + "\n"
            f"🚨 [PREDATOR ALERT TRIGGERED] 🚨\n"
            f"  Target:          {class_name}\n"
            f"  Confidence:      {conf:.1%}\n"
            f"  Event ID:        {event.event_id}\n"
            f"  Triggered At:    {event.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"  Evidence File:   {event.evidence_image_path or 'N/A'}\n"
            + "=" * 60
        )
        print(alert_msg)
        return True
