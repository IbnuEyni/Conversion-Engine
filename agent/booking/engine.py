"""Cal.com booking engine for discovery calls."""

from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


class BookingEngine:
    def __init__(self):
        self._sink_dir = Path("data/outbound_sink/bookings")
        self._sink_dir.mkdir(parents=True, exist_ok=True)

    async def get_available_slots(self, days_ahead: int = 7) -> list[dict]:
        """Get available slots from Cal.com."""
        if not settings.calcom_api_key:
            return self._mock_slots()

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{settings.calcom_base_url}/api/v1/availability",
                    params={
                        "apiKey": settings.calcom_api_key,
                        "eventTypeId": settings.calcom_event_type_id,
                        "days": days_ahead,
                    },
                )
                resp.raise_for_status()
                return resp.json().get("slots", [])
        except Exception as e:
            logger.warning(f"Cal.com availability fetch failed: {e}, using mock slots")
            return self._mock_slots()

    async def book_slot(
        self,
        prospect_name: str,
        prospect_email: str,
        slot_time: str,
        notes: str = "",
        prospect_id: str = "",
    ) -> dict:
        """Book a discovery call slot."""
        booking = {
            "prospect_name": prospect_name,
            "prospect_email": prospect_email,
            "slot_time": slot_time,
            "notes": notes,
            "prospect_id": prospect_id,
            "timestamp": datetime.utcnow().isoformat(),
            "draft": True,
        }

        if settings.is_live and settings.calcom_api_key:
            return await self._book_calcom(booking)
        return self._book_to_sink(booking)

    async def _book_calcom(self, booking: dict) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{settings.calcom_base_url}/api/v1/bookings",
                    params={"apiKey": settings.calcom_api_key},
                    json={
                        "eventTypeId": settings.calcom_event_type_id,
                        "start": booking["slot_time"],
                        "name": booking["prospect_name"],
                        "email": booking["prospect_email"],
                        "notes": booking.get("notes", ""),
                        "metadata": {"prospect_id": booking.get("prospect_id", ""), "draft": True},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                booking["status"] = "booked"
                booking["calcom_booking_id"] = data.get("id", "")
                booking["booking_url"] = data.get("url", "")
                logger.info(f"Cal.com booking created: {data.get('id')}")
        except Exception as e:
            booking["status"] = "failed"
            booking["error"] = str(e)
            logger.error(f"Cal.com booking failed: {e}")
        self._log(booking)
        return booking

    def _book_to_sink(self, booking: dict) -> dict:
        booking["status"] = "sink"
        booking["calcom_booking_id"] = f"mock_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        self._log(booking)
        logger.info(f"Booking routed to sink: {booking['prospect_name']} at {booking['slot_time']}")
        return booking

    def _log(self, booking: dict):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        pid = booking.get("prospect_id", "unknown")
        (self._sink_dir / f"{ts}_{pid}.json").write_text(
            json.dumps(booking, indent=2, default=str)
        )

    def _mock_slots(self) -> list[dict]:
        from datetime import timedelta
        now = datetime.utcnow()
        slots = []
        for day_offset in range(1, 6):
            d = now + timedelta(days=day_offset)
            if d.weekday() < 5:  # weekdays only
                for hour in (10, 14, 16):  # 10am, 2pm, 4pm ET
                    slots.append({
                        "time": d.replace(hour=hour, minute=0, second=0).isoformat() + "Z",
                        "available": True,
                    })
        return slots
