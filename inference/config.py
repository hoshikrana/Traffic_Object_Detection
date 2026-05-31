"""Configuration constants for the traffic analytics inference engine."""

# VisDrone class mapping (0-indexed)
VISDRONE_CLASSES = {
    0: "pedestrian",
    1: "people",
    2: "bicycle",
    3: "car",
    4: "van",
    5: "truck",
    6: "tricycle",
    7: "awning-tricycle",
    8: "bus",
    9: "motor",
}

# Classes we count as "vehicles" for traffic analytics
VEHICLE_CLASS_IDS = {3, 4, 5, 6, 7, 8}  # car, van, truck, tricycle, awning-tricycle, bus

# Bounding box colors per class (BGR for OpenCV)
CLASS_COLORS = {
    3: (255, 180, 50),    # car — amber
    4: (100, 200, 255),   # van — light blue
    5: (50, 50, 255),     # truck — red
    6: (200, 100, 255),   # tricycle — purple
    7: (150, 255, 150),   # awning-tricycle — light green
    8: (0, 165, 255),     # bus — orange
    0: (200, 200, 200),   # pedestrian — gray
    1: (180, 180, 180),   # people — light gray
    2: (255, 255, 100),   # bicycle — yellow
    9: (255, 100, 200),   # motor — pink
}

# Detection thresholds
CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.50

# Class-specific confidence thresholds to prevent false positives in background vegetation/landscape
# Larger objects like cars, trucks, and buses require higher confidence, while smaller targets
# like pedestrians or manhole covers remain highly sensitive.
CLASS_CONF_THRESHOLDS = {
    "car": 0.40,
    "truck": 0.45,
    "bus": 0.45,
    "van": 0.38,
    "person": 0.25,
    "pedestrian": 0.25,
    "people": 0.25,
    "manhole": 0.25,
}

# Frame processing
SKIP_FRAMES = 2              # process every Nth frame
TRAIL_LENGTH = 40            # frames of position history to draw as trail

# Speed estimation calibration
PIXELS_PER_METER = 8.5       # calibration: pixels per real-world meter
FPS_ASSUMED = 25.0           # assumed video FPS for speed calculation

# Stationary / incident detection
STOPPED_PIXELS_THRESHOLD = 5.0   # pixel movement threshold for "stopped"
STOPPED_FRAMES_THRESHOLD = 75    # frames stationary before incident flag

# Congestion thresholds (must be checked in reverse order)
CONGESTION_THRESHOLDS = {
    "LOW": 5,
    "MODERATE": 10,
    "HIGH": 18,
    "CRITICAL": 25,
}

# API communication
API_BASE_URL = "http://localhost:8000"
ANALYTICS_SEND_EVERY_N_FRAMES = 25    # send analytics every N processed frames
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = [0.5, 1.0, 2.0]
