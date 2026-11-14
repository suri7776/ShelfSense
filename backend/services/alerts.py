# backend/services/alerts.py
# Watches detection results and creates Alert rows when stock is
# low / empty, or a product is detected in the wrong planogram slot.
# Uses a simple in-memory counter so a single noisy frame doesn't fire
# a stock alert - needs 2 consecutive bad readings. Misplaced-product
# alerts fire immediately (a misplaced item is visually obvious in a
# single frame, unlike a borderline stock count).

from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from backend.models.database import Alert
from backend.models.schemas import DetectionResult

# Module-level so it persists across requests within the same process
_alert_streak: dict = {}


class AlertEngine:
    def __init__(self, db: Session):
        self.db = db

    def process_detections(self, detections: List[DetectionResult], camera_id: str) -> List[dict]:
        fired = []

        for det in detections:
            if det.product_class == "empty_slot":
                continue

            key = f"{camera_id}_{det.product_class}"

            if det.severity in ("low", "empty"):
                _alert_streak[key] = _alert_streak.get(key, 0) + 1
                if _alert_streak[key] >= 2:
                    fired.append(self._create_alert(det, camera_id))
                    _alert_streak[key] = 0  # reset after firing to avoid spam
            else:
                _alert_streak[key] = 0

        return fired

    def process_misplaced(self, misplaced_products: List[dict], camera_id: str) -> List[dict]:
        """Misplaced products fire an alert immediately (no debounce)."""
        fired = []
        for item in misplaced_products:
            alert = Alert(
                product_class=item["detected_product"],
                severity="misplaced",
                facings_detected=1,
                estimated_total=0,
                camera_id=camera_id,
                timestamp=datetime.utcnow(),
            )
            self.db.add(alert)
            self.db.commit()
            self.db.refresh(alert)

            fired.append({
                "id": alert.id,
                "product_class": alert.product_class,
                "severity": "misplaced",
                "facings_detected": 1,
                "estimated_total": 0,
                "timestamp": alert.timestamp.isoformat(),
                "message": item["message"],
                "expected_product": item["expected_product"],
                "slot_number": item["slot_number"],
            })

        return fired

    def process_stock_snapshot(self, current_stock: dict, planogram: dict, camera_id: str) -> List[dict]:
        """
        Fire low-stock / out-of-stock alerts based on a full current-stock
        snapshot (used after a batch upload). No debounce - a batch upload
        is a deliberate snapshot, not a noisy single frame, so each
        low/empty product fires immediately.
        """
        fired = []
        expected_facings = planogram.get("expected_facings", {})

        for product, count in current_stock.items():
            expected = expected_facings.get(product, 0)
            if expected == 0:
                continue

            if count == 0:
                severity = "empty"
            elif (count / expected) * 100 < 40:
                severity = "low"
            else:
                continue

            alert = Alert(
                product_class=product,
                severity=severity,
                facings_detected=count,
                estimated_total=0,
                camera_id=camera_id,
                timestamp=datetime.utcnow(),
            )
            self.db.add(alert)
            self.db.commit()
            self.db.refresh(alert)

            message = (
                f"OUT OF STOCK - {product}" if severity == "empty"
                else f"LOW STOCK - {product} - {count}/{expected} ({round(count/expected*100, 1)}%)"
            )

            fired.append({
                "id": alert.id,
                "product_class": product,
                "severity": severity,
                "facings_detected": count,
                "estimated_total": 0,
                "timestamp": alert.timestamp.isoformat(),
                "message": message,
            })

        return fired

    def _create_alert(self, det: DetectionResult, camera_id: str) -> dict:
        alert = Alert(
            product_class=det.product_class,
            severity=det.severity,
            facings_detected=det.facings_count,
            estimated_total=det.estimated_total,
            camera_id=camera_id,
            timestamp=datetime.utcnow(),
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)

        return {
            "id": alert.id,
            "product_class": alert.product_class,
            "severity": alert.severity,
            "facings_detected": alert.facings_detected,
            "estimated_total": alert.estimated_total,
            "timestamp": alert.timestamp.isoformat(),
            "message": self._message(det),
        }

    def _message(self, det: DetectionResult) -> str:
        if det.severity == "empty":
            return f"OUT OF STOCK - {det.product_class}"
        if det.severity == "low":
            return f"LOW STOCK - {det.product_class} - {det.facings_count} remaining"
        return f"{det.product_class}: {det.severity}"
