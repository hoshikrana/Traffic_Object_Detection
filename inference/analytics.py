"""Traffic analytics engine — computes speed, congestion, incidents, and counting line crossings."""

from __future__ import annotations

import math
from collections import deque
from typing import Any

from .config import (
    CONGESTION_THRESHOLDS,
    STOPPED_FRAMES_THRESHOLD,
    STOPPED_PIXELS_THRESHOLD,
    TRAIL_LENGTH,
    VEHICLE_CLASS_IDS,
)


class TrafficAnalytics:
    """Stateful analytics engine that processes detections frame-by-frame."""

    def __init__(self, video_fps: float, pixels_per_meter: float, vehicle_class_ids: set[int] = None, class_names: dict[int, str] = None) -> None:
        # Per-track state
        self.track_positions: dict[int, deque] = {}  # track_id -> deque of (cx, cy, frame_number)
        self.track_speeds: dict[int, float] = {}     # track_id -> latest speed km/h
        self.track_classes: dict[int, int] = {}      # track_id -> class_id

        # Stationary detection
        self.stationary_counters: dict[int, int] = {}
        self.active_incidents: dict[int, dict] = {}
        self.resolved_incidents: list[dict] = []

        # Counting line
        self.crossing_line_counts: dict[str, int] = {"up": 0, "down": 0, "total": 0}
        self.crossing_line_y: int = 0

        # Counters
        self.frame_count: int = 0
        self.video_fps: float = video_fps
        self.pixels_per_meter: float = pixels_per_meter
        self.vehicle_class_ids = vehicle_class_ids if vehicle_class_ids is not None else VEHICLE_CLASS_IDS
        self.class_names = class_names

        # For summary stats
        self._all_track_ids: set[int] = set()
        self._peak_vehicle_count: int = 0
        self._all_speeds: list[float] = []

    def update(
        self,
        detections: list[dict[str, Any]],
        frame_height: int,
        frame_width: int,
    ) -> dict[str, Any]:
        """Process one frame of detections. Returns analytics dict."""
        # Set counting line at 55% of frame height
        self.crossing_line_y = int(frame_height * 0.55)

        current_track_ids = set()

        for det in detections:
            track_id = det["track_id"]
            class_id = det["class_id"]
            cx, cy = det["cx"], det["cy"]

            current_track_ids.add(track_id)
            self._all_track_ids.add(track_id)

            # 1. Update position history
            if track_id not in self.track_positions:
                self.track_positions[track_id] = deque(maxlen=TRAIL_LENGTH)
            self.track_positions[track_id].append((cx, cy, self.frame_count))
            self.track_classes[track_id] = class_id

            positions = self.track_positions[track_id]

            if len(positions) >= 2:
                # 2. Speed estimation using a temporal window to suppress bounding-box coordinate jitter
                # We calculate the speed between the oldest position in the queue (positions[0])
                # and the newest position (positions[-1]) to create a rolling smoothed velocity vector.
                prev_x, prev_y, prev_fn = positions[0]
                curr_x, curr_y, curr_fn = positions[-1]
                pixel_dist = math.sqrt((curr_x - prev_x) ** 2 + (curr_y - prev_y) ** 2)

                frame_diff = curr_fn - prev_fn
                if frame_diff > 0:
                    time_seconds = frame_diff / self.video_fps
                    speed_ms = (pixel_dist / self.pixels_per_meter) / time_seconds
                    speed_kmh = speed_ms * 3.6
                    speed_kmh = max(0.0, min(140.0, speed_kmh))  # clamp at realistic maximum highway speed
                    
                    # Apply an exponential moving average (EMA) for temporal smoothing once we have a stable history window
                    if len(positions) >= 5 and track_id in self.track_speeds:
                        alpha = 0.15  # smooth transition factor
                        self.track_speeds[track_id] = alpha * speed_kmh + (1 - alpha) * self.track_speeds[track_id]
                    else:
                        self.track_speeds[track_id] = speed_kmh
                else:
                    speed_kmh = self.track_speeds.get(track_id, 0.0)

                # 3. Stationary detection (independent of frame skips)
                if pixel_dist < STOPPED_PIXELS_THRESHOLD:
                    self.stationary_counters[track_id] = (
                        self.stationary_counters.get(track_id, 0) + (curr_fn - prev_fn)
                    )
                else:
                    self.stationary_counters[track_id] = 0

                if (
                    self.stationary_counters[track_id] >= STOPPED_FRAMES_THRESHOLD
                    and track_id not in self.active_incidents
                ):
                    self.active_incidents[track_id] = {
                        "track_id": track_id,
                        "type": "stopped_vehicle",
                        "cx": cx,
                        "cy": cy,
                        "started_frame": self.frame_count,
                    }

                # 4. Counting line crossing
                prev_cy = positions[-2][1]
                curr_cy = positions[-1][1]

                if prev_cy < self.crossing_line_y and curr_cy >= self.crossing_line_y:
                    self.crossing_line_counts["down"] += 1
                    self.crossing_line_counts["total"] += 1
                elif prev_cy > self.crossing_line_y and curr_cy <= self.crossing_line_y:
                    self.crossing_line_counts["up"] += 1
                    self.crossing_line_counts["total"] += 1

        # Resolve incidents for tracks no longer visible
        stale_incidents = [
            tid for tid in self.active_incidents if tid not in current_track_ids
        ]
        for tid in stale_incidents:
            incident = self.active_incidents.pop(tid)
            incident["resolved_frame"] = self.frame_count
            self.resolved_incidents.append(incident)

        # Compute analytics
        visible_vehicle_ids = {
            d["track_id"] for d in detections if d["class_id"] in self.vehicle_class_ids
        }
        total_vehicles = len(visible_vehicle_ids)
        self._peak_vehicle_count = max(self._peak_vehicle_count, total_vehicles)

        # Category counts
        category_counts = {"cars": 0, "vans": 0, "trucks": 0, "buses": 0, "others": 0}
        
        # Build category map dynamically based on class names
        for tid in visible_vehicle_ids:
            cid = self.track_classes.get(tid)
            cname = (self.class_names.get(cid) if self.class_names else "").lower()
            
            if "car" in cname or "bicycle" in cname or "motor" in cname:
                category_counts["cars"] += 1
            elif "van" in cname:
                category_counts["vans"] += 1
            elif "truck" in cname:
                category_counts["trucks"] += 1
            elif "bus" in cname:
                category_counts["buses"] += 1
            else:
                # Fallback based on ID if class_names is not set or custom
                class_to_category = {3: "cars", 4: "vans", 5: "trucks", 8: "buses"}
                cat = class_to_category.get(cid, "others")
                category_counts[cat] += 1

        # Speed stats
        vehicle_speeds = [
            self.track_speeds[tid]
            for tid in visible_vehicle_ids
            if tid in self.track_speeds
        ]
        avg_speed = sum(vehicle_speeds) / len(vehicle_speeds) if vehicle_speeds else 0.0
        max_speed = max(vehicle_speeds) if vehicle_speeds else 0.0
        self._all_speeds.extend(vehicle_speeds)

        # Congestion level
        congestion = "LOW"
        for level, threshold in reversed(list(CONGESTION_THRESHOLDS.items())):
            if total_vehicles >= threshold:
                congestion = level
                break

        self.frame_count += 1

        return {
            "frame_number": self.frame_count,
            "total_vehicles": total_vehicles,
            "categories": category_counts,
            "avg_speed_kmh": round(avg_speed, 1),
            "max_speed_kmh": round(max_speed, 1),
            "congestion_level": congestion,
            "active_incidents": list(self.active_incidents.values()),
            "crossing_counts": self.crossing_line_counts.copy(),
            "crossing_line_y": self.crossing_line_y,
        }

    def get_summary(self) -> dict[str, Any]:
        """Return a full summary of the analytics session."""
        overall_avg = (
            sum(self._all_speeds) / len(self._all_speeds) if self._all_speeds else 0.0
        )
        return {
            "total_frames_processed": self.frame_count,
            "total_unique_vehicles": len(self._all_track_ids),
            "peak_vehicle_count": self._peak_vehicle_count,
            "total_incidents": len(self.resolved_incidents) + len(self.active_incidents),
            "total_crossings": self.crossing_line_counts["total"],
            "avg_speed_overall": round(overall_avg, 1),
            "crossing_counts": self.crossing_line_counts.copy(),
        }
