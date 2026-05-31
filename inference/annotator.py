"""Frame annotator — draws bounding boxes, trails, speed badges, HUD overlay, and counting line."""

from __future__ import annotations

from collections import deque
from typing import Any

import cv2
import numpy as np

from .config import CLASS_COLORS, VISDRONE_CLASSES

# Font settings
_FONT = cv2.FONT_HERSHEY_DUPLEX
_FONT_SMALL = cv2.FONT_HERSHEY_SIMPLEX

# Congestion level color mapping (BGR)
_CONGESTION_COLORS = {
    "LOW": (80, 200, 80),       # green
    "MODERATE": (50, 180, 240), # amber
    "HIGH": (50, 140, 250),     # orange
    "CRITICAL": (60, 60, 240),  # red
}


def get_simulated_plate(track_id: int) -> str:
    """Generate a realistic, deterministic simulated license plate string from track ID."""
    letters = "".join(chr(65 + (track_id * 7 + i * 3) % 26) for i in range(3))
    digits = "".join(str((track_id * 13 + i * 7) % 10) for i in range(4))
    return f"{letters}-{digits}"


class FrameAnnotator:
    """Draws all visual annotations onto video frames."""

    def __init__(self) -> None:
        pass

    def draw(
        self,
        frame: np.ndarray,
        detections: list[dict[str, Any]],
        track_positions: dict[int, deque],
        track_speeds: dict[int, float],
        track_classes: dict[int, int],
        analytics: dict[str, Any],
        class_names: dict[int, str] = None,
    ) -> np.ndarray:
        """Draw all annotations onto the frame and return it."""
        frame_h, frame_w = frame.shape[:2]
        overlay = frame.copy()

        class_map = class_names if class_names is not None else VISDRONE_CLASSES

        # 1. TRAILS (Only draw for vehicles to prevent clutter)
        for track_id, positions in track_positions.items():
            pos_list = list(positions)
            if len(pos_list) < 2:
                continue
            
            class_id = track_classes.get(track_id, 0)
            class_name = class_map.get(class_id, "unknown").lower()
            is_vehicle_trail = any(kw in class_name for kw in ["car", "van", "truck", "bus", "motorcycle", "bicycle", "tricycle", "motor", "vehicle"])
            
            if not is_vehicle_trail:
                continue # Skip trails for pedestrians/persons to keep frame clean

            if class_id in CLASS_COLORS:
                color = CLASS_COLORS[class_id]
            else:
                h = hash(class_id)
                color = (((h & 0xFF) % 200 + 55), (((h >> 8) & 0xFF) % 200 + 55), (((h >> 16) & 0xFF) % 200 + 55))

            for i in range(1, len(pos_list)):
                alpha = i / len(pos_list)
                thickness = max(1, int(alpha * 2))
                pos1 = pos_list[i - 1]
                pos2 = pos_list[i]
                pt1 = (int(pos1[0]), int(pos1[1]))
                pt2 = (int(pos2[0]), int(pos2[1]))
                # Fade trail by blending
                fade_color = tuple(int(c * alpha) for c in color)
                cv2.line(overlay, pt1, pt2, fade_color, thickness, cv2.LINE_AA)

        # Blend trails onto frame
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Collision avoidance tracker for side-badges
        occupied_rects = []

        # 2. BOUNDING BOXES & OVERLAYS
        for det in detections:
            x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
            class_id = det["class_id"]
            track_id = det["track_id"]
            conf = det["conf"]
            
            class_name = class_map.get(class_id, "unknown")
            is_vehicle = any(kw in class_name.lower() for kw in ["car", "van", "truck", "bus", "motorcycle", "bicycle", "tricycle", "motor", "vehicle"])
            is_pedestrian = any(kw in class_name.lower() for kw in ["person", "people", "pedestrian"])

            # Setup colors
            if class_id in CLASS_COLORS:
                color = CLASS_COLORS[class_id]
            elif is_pedestrian:
                color = (180, 180, 180) # Quiet gray for pedestrians
            else:
                h = hash(class_id)
                color = (((h & 0xFF) % 200 + 55), (((h >> 8) & 0xFF) % 200 + 55), (((h >> 16) & 0xFF) % 200 + 55))

            # Bounding box sizing properties
            box_w = x2 - x1
            box_h = y2 - y1
            is_distant = box_w < 35 or box_h < 35

            if not is_vehicle or is_distant:
                # ==========================================
                # Style A: Clean, Minimalist Draw (Non-Vehicles or Distant Small Vehicles)
                # ==========================================
                # Draw simple 1px bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1, cv2.LINE_AA)
                
                # Draw dynamic clean top-text (no massive side-badge)
                speed_text = ""
                if is_vehicle and track_id in track_speeds:
                    speed_text = f" | {track_speeds[track_id]:.0f} km/h"
                
                simple_label = f"{class_name} #{track_id}{speed_text}"
                (lw, lh), _ = cv2.getTextSize(simple_label, cv2.FONT_HERSHEY_SIMPLEX, 0.32, 1)
                
                label_y = max(lh + 4, y1 - 4)
                
                # Tiny quiet background for the label text
                cv2.rectangle(frame, (x1, label_y - lh - 2), (x1 + lw + 4, label_y + 2), (15, 15, 15), -1)
                cv2.putText(
                    frame,
                    simple_label,
                    (x1 + 2, label_y - 1),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.32,
                    (230, 230, 230),
                    1,
                    cv2.LINE_AA,
                )
            else:
                # ==========================================
                # Style B: High-End Dynamic Vehicle Layout (Side Badges & ALPR)
                # ==========================================
                # 2.1 Draw primary sleek rectangle (2px thin line)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
                
                # High-tech corner highlights (3px thick)
                corner_len = min(15, max(5, box_w // 5, box_h // 5))
                cv2.line(frame, (x1, y1), (x1 + corner_len, y1), color, 3, cv2.LINE_AA)
                cv2.line(frame, (x1, y1), (x1, y1 + corner_len), color, 3, cv2.LINE_AA)
                cv2.line(frame, (x2, y1), (x2 - corner_len, y1), color, 3, cv2.LINE_AA)
                cv2.line(frame, (x2, y1), (x2, y1 + corner_len), color, 3, cv2.LINE_AA)
                cv2.line(frame, (x1, y2), (x1 + corner_len, y2), color, 3, cv2.LINE_AA)
                cv2.line(frame, (x1, y2), (x1, y2 - corner_len), color, 3, cv2.LINE_AA)
                cv2.line(frame, (x2, y2), (x2 - corner_len, y2), color, 3, cv2.LINE_AA)
                cv2.line(frame, (x2, y2), (x2, y2 - corner_len), color, 3, cv2.LINE_AA)

                # Elegant small confidence tag at bottom-right of bounding box
                conf_label = f"{conf:.0%}"
                (ctw, cth), _ = cv2.getTextSize(conf_label, cv2.FONT_HERSHEY_SIMPLEX, 0.3, 1)
                cv2.rectangle(frame, (x2 - ctw - 6, y2 - cth - 4), (x2, y2), (20, 20, 20), -1)
                cv2.putText(frame, conf_label, (x2 - ctw - 3, y2 - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (180, 180, 180), 1, cv2.LINE_AA)

                # 2.2 Dynamic Collision-Avoidance Side Badge Layout
                plate = get_simulated_plate(track_id)
                badge_w = 135
                badge_h = 58
                
                # Check overlaps to shift badges vertically
                def collides(bx, by):
                    for (ox, oy, ow, oh) in occupied_rects:
                        if not (bx + badge_w + 3 <= ox or ox + ow + 3 <= bx or by + badge_h + 3 <= oy or oy + oh + 3 <= by):
                            return True
                    return False

                placed = False
                badge_x, badge_y = 0, 0
                
                preferred_sides = ["right", "left", "inside"]
                if x2 + badge_w + 6 > frame_w:
                    preferred_sides = ["left", "right", "inside"]

                for side in preferred_sides:
                    if placed:
                        break
                    if side == "right":
                        bx = x2 + 6
                        # Test y shifts (original centered y, then shift down/up in steps of 15px)
                        for shift in [0, 15, -15, 30, -30, 45, -45]:
                            by = y1 + (y2 - y1 - badge_h) // 2 + shift
                            by = max(4, min(frame_h - badge_h - 4, by))
                            if not collides(bx, by) and bx + badge_w <= frame_w:
                                badge_x, badge_y = bx, by
                                placed = True
                                break
                    elif side == "left":
                        bx = x1 - badge_w - 6
                        for shift in [0, 15, -15, 30, -30, 45, -45]:
                            by = y1 + (y2 - y1 - badge_h) // 2 + shift
                            by = max(4, min(frame_h - badge_h - 4, by))
                            if not collides(bx, by) and bx >= 0:
                                badge_x, badge_y = bx, by
                                placed = True
                                break
                    elif side == "inside":
                        bx = max(4, min(frame_w - badge_w - 4, x1 + 6))
                        for shift in [0, 15, -15, 30, -30]:
                            by = y1 + 4 + shift
                            by = max(4, min(frame_h - badge_h - 4, by))
                            if not collides(bx, by):
                                badge_x, badge_y = bx, by
                                placed = True
                                break

                if not placed:
                    # Fallback to default right side or left side
                    badge_x = x2 + 6 if x2 + badge_w + 6 <= frame_w else max(0, x1 - badge_w - 6)
                    badge_y = max(4, min(frame_h - badge_h - 4, y1 + (y2 - y1 - badge_h) // 2))

                occupied_rects.append((badge_x, badge_y, badge_w, badge_h))

                # Draw Badge background
                badge_overlay = frame.copy()
                cv2.rectangle(badge_overlay, (badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h), (12, 12, 12), -1)
                cv2.addWeighted(badge_overlay, 0.70, frame, 0.30, 0, frame)
                
                # Draw Badge 1px border matching box color
                cv2.rectangle(frame, (badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h), color, 1, cv2.LINE_AA)
                
                # Text inside the badge
                text_x = badge_x + 8
                line1_y = badge_y + 16
                line2_y = badge_y + 33
                line3_y = badge_y + 50
                
                # Line 1: CAR #ID
                cv2.putText(
                    frame,
                    f"{class_name.upper()} #{track_id}",
                    (text_x, line1_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.36,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
                
                # Line 2: Speed
                if track_id in track_speeds:
                    speed = track_speeds[track_id]
                    speed_text = f"Speed: {speed:.1f} km/h"
                    speed_color = (100, 255, 100) if speed <= 80 else (100, 100, 255) # Green/Red BGR
                else:
                    speed_text = "Speed: calculating"
                    speed_color = (180, 180, 180)
                    
                cv2.putText(
                    frame,
                    speed_text,
                    (text_x, line2_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.36,
                    speed_color,
                    1,
                    cv2.LINE_AA,
                )
                
                # Line 3: Plate
                cv2.putText(
                    frame,
                    f"Plate: {plate}",
                    (text_x, line3_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.36,
                    (100, 255, 255), # Amber/Yellow BGR
                    1,
                    cv2.LINE_AA,
                )

        # 5. COUNTING LINE (dashed)
        line_y = analytics.get("crossing_line_y", int(frame_h * 0.55))
        dash_color = (0, 255, 200)  # cyan-green
        for x_start in range(0, frame_w, 20):
            x_end = min(x_start + 10, frame_w)
            cv2.line(frame, (x_start, line_y), (x_end, line_y), dash_color, 2, cv2.LINE_AA)

        # Counting line label
        crossing_total = analytics.get("crossing_counts", {}).get("total", 0)
        count_label = f"COUNTING LINE | Total: {crossing_total}"
        cv2.putText(
            frame,
            count_label,
            (frame_w - 280, line_y - 8),
            _FONT_SMALL,
            0.5,
            dash_color,
            1,
            cv2.LINE_AA,
        )

        # 6. HUD OVERLAY (top-left info panel)
        hud_overlay = frame.copy()
        cv2.rectangle(hud_overlay, (10, 10), (290, 160), (20, 20, 20), -1)
        cv2.addWeighted(hud_overlay, 0.65, frame, 0.35, 0, frame)

        # HUD border
        cv2.rectangle(frame, (10, 10), (290, 160), (60, 60, 60), 1, cv2.LINE_AA)

        # HUD text
        hud_lines = [
            (f"VEHICLES: {analytics.get('total_vehicles', 0)}", (255, 255, 255)),
            (
                f"CONGESTION: {analytics.get('congestion_level', 'LOW')}",
                _CONGESTION_COLORS.get(analytics.get("congestion_level", "LOW"), (255, 255, 255)),
            ),
            (f"AVG SPEED: {analytics.get('avg_speed_kmh', 0)} km/h", (255, 255, 255)),
            (f"MAX SPEED: {analytics.get('max_speed_kmh', 0)} km/h", (255, 255, 255)),
            (
                f"CROSSINGS: {analytics.get('crossing_counts', {}).get('total', 0)}",
                (255, 255, 255),
            ),
        ]
        for i, (text, color) in enumerate(hud_lines):
            cv2.putText(
                frame,
                text,
                (20, 38 + i * 26),
                _FONT_SMALL,
                0.55,
                color,
                1,
                cv2.LINE_AA,
            )

        # 7. INCIDENTS BADGE
        incidents = analytics.get("active_incidents", [])
        if incidents:
            badge_x = frame_w - 200
            badge_overlay = frame.copy()
            cv2.rectangle(
                badge_overlay, (badge_x, 10), (badge_x + 190, 40), (0, 0, 200), -1
            )
            cv2.addWeighted(badge_overlay, 0.85, frame, 0.15, 0, frame)
            incident_text = f"! {len(incidents)} INCIDENT(S)"
            cv2.putText(
                frame,
                incident_text,
                (badge_x + 10, 32),
                _FONT_SMALL,
                0.55,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        # 8. FRAME NUMBER watermark
        frame_text = f"FRAME {analytics.get('frame_number', 0)}"
        cv2.putText(
            frame,
            frame_text,
            (frame_w - 140, frame_h - 10),
            _FONT_SMALL,
            0.45,
            (120, 120, 120),
            1,
            cv2.LINE_AA,
        )

        return frame
