# Traffic Analytics — Complete Production Project
## Video Input → Annotated Output + Live Dashboard

---

## What Changed From The Original (And Why)

| Original | Updated | Why Better |
|---|---|---|
| Real-time stream | Video file upload | Portable, demonstrable, no camera needed |
| Raw JSON dashboard only | Annotated output video + dashboard | Visual proof the model works |
| No bounding boxes shown | Boxes + speed + track ID + trails | Recruiter can *see* the AI working |
| 3 prompts | 5 focused prompts | Each prompt generates one clean file |
| No persistence | PostgreSQL + job history | Multiple videos, full history |
| No user interaction | Drag-and-drop UI + download | Feels like a real product |

---

## Final File Structure

```
traffic-analytics/
├── notebooks/
│   └── 01_train_export.ipynb        ← Prompt 1 (Kaggle GPU)
├── inference/
│   ├── engine.py                    ← Prompt 2 (core loop)
│   ├── annotator.py                 ← Prompt 2 (draws boxes/speed/trails)
│   ├── analytics.py                 ← Prompt 2 (speed, incidents, counting line)
│   ├── sender.py                    ← Prompt 2 (async HTTP with retry)
│   └── config.py                    ← Prompt 2 (all constants)
├── backend/
│   ├── main.py                      ← Prompt 3
│   ├── routers/
│   │   ├── jobs.py                  ← upload, status, list
│   │   ├── traffic.py               ← receive analytics from inference
│   │   └── media.py                 ← serve annotated video + frames
│   ├── ws/
│   │   └── manager.py               ← WebSocket broadcaster
│   ├── db/
│   │   ├── models.py                ← SQLAlchemy models
│   │   ├── schemas.py               ← Pydantic v2 schemas
│   │   └── session.py               ← async DB session
│   ├── services/
│   │   └── job_runner.py            ← spawns inference subprocess
│   ├── alembic/                     ← migrations
│   ├── tests/
│   │   └── test_api.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── Upload.jsx           ← drag-and-drop video upload
│   │   │   ├── Processing.jsx       ← live progress + real-time analytics
│   │   │   └── Results.jsx          ← annotated video player + charts
│   │   ├── components/
│   │   │   ├── VideoPlayer.jsx      ← custom HTML5 player
│   │   │   ├── DensityChart.jsx     ← ApexCharts time series
│   │   │   ├── SpeedHistogram.jsx   ← speed distribution
│   │   │   ├── CategoryDonut.jsx    ← car/truck/bus/van breakdown
│   │   │   ├── IncidentTable.jsx    ← stopped vehicles log
│   │   │   ├── MetricsGrid.jsx      ← 4 KPI cards
│   │   │   ├── ProgressBar.jsx      ← processing progress
│   │   │   └── JobHistory.jsx       ← sidebar list of past jobs
│   │   └── hooks/
│   │       ├── useJobWebSocket.js
│   │       └── useJobHistory.js
│   ├── index.html
│   └── package.json
├── docker-compose.yml
├── Makefile
├── .github/workflows/ci.yml
└── README.md
```

---

## PROMPT 1 — Kaggle Training Notebook

> Paste this as the first cell of a new Kaggle notebook. Enable GPU accelerator (P100 or T4).

```
Write a complete Kaggle notebook as Python code cells with markdown header cells
between sections. The notebook fine-tunes YOLO11 Nano on VisDrone2019-DET and
exports the model in two formats. Follow every instruction exactly.

=== CELL 1: SETUP ===
Install: ultralytics==8.3.0, wandb, openvino>=2024.0, onnxruntime, rich
Authenticate W&B using: import os; os.environ["WANDB_API_KEY"] = userdata.get("WANDB_API_KEY")
Print versions of all installed packages.

=== CELL 2: DOWNLOAD DATASET ===
The VisDrone2019-DET dataset is available on Kaggle at dataset
"ultralytics/visdrone". Use kaggle.api.dataset_download_files() to download it
to /kaggle/input/visdrone. If the dataset is already present, skip the download.
Print the directory tree of the downloaded dataset.

=== CELL 3: DATASET CONVERSION ===
Write a function convert_visdrone_to_yolo(src_dir, dst_dir) that:
1. Reads VisDrone annotation .txt files (space-separated, 12 columns:
   left,top,width,height,score,category,truncation,occlusion and 4 extras).
   category IDs: 1=pedestrian,2=people,3=bicycle,4=car,5=van,
   6=truck,7=tricycle,8=awning-tricycle,9=bus,10=motor
   (subtract 1 to make 0-indexed for YOLO)
2. Skips annotations where score==0 (ignored regions)
3. Converts (left,top,width,height) to YOLO normalized (cx,cy,w,h)
4. Writes one YOLO .txt per image to dst_dir/labels/
5. Copies images to dst_dir/images/
6. Returns count of converted images and total annotations

Run the converter on train and val splits.
Apply a 90/10 split on the val set to create a test set (copy 10% of val images
and labels to a separate test/ folder).

Write a dataset YAML file at /kaggle/working/visdrone.yaml:
  path: /kaggle/working/visdrone_yolo
  train: images/train
  val: images/val
  test: images/test
  nc: 10
  names: [pedestrian, people, bicycle, car, van, truck, tricycle,
          awning-tricycle, bus, motor]

=== CELL 4: TRAINING ===
Initialize wandb run:
  wandb.init(project="traffic-analytics", name="yolo11n-visdrone-v1",
             config={model:"yolo11n",epochs:80,imgsz:640,batch:16,
                     optimizer:"AdamW",lr0:0.001,warmup_epochs:5,
                     mosaic:1.0,mixup:0.15,copy_paste:0.1,degrees:10.0,
                     hsv_h:0.015,hsv_s:0.7,hsv_v:0.4})

Load model: model = YOLO("yolo11n.pt")

Train with all the config parameters above. Set:
  project="/kaggle/working/runs", name="train", exist_ok=True, plots=True

After training finishes, log to W&B:
  - training results CSV as a table
  - confusion_matrix.png as an image
  - PR_curve.png as an image
  - F1_curve.png as an image
  - The best weights file best.pt as an artifact named "yolo11n-best"

=== CELL 5: VALIDATION ===
Run model.val() on the test split using the best weights.
Print a clean table showing per-class AP50, overall mAP50, and mAP50-95.
Assert mAP50 > 0.20 (VisDrone is hard — 0.20 is realistic for Nano).
If assertion fails, print "WARNING: mAP below threshold, check training" and continue.
Log all val metrics to the active W&B run.

=== CELL 6: EXPORT — OpenVINO INT8 ===
Export the best model to OpenVINO INT8 format:
  model.export(format="openvino", int8=True, imgsz=640, nms=True,
               data="/kaggle/working/visdrone.yaml")
The export uses the val split as the INT8 calibration dataset automatically
via the data= parameter. After export, verify these files exist:
  best_openvino_model/best.xml
  best_openvino_model/best.bin
  best_openvino_model/metadata.yaml

Run one test inference on a sample image using the OpenVINO model:
  ov_model = YOLO("best_openvino_model/")
  results = ov_model("/kaggle/input/visdrone/images/val/sample.jpg")
Print detected class names, confidence scores, and bounding box coordinates.
Log the annotated result image to W&B.

=== CELL 7: EXPORT — ONNX ===
Export to ONNX: model.export(format="onnx", simplify=True, opset=17, imgsz=640)
Verify best.onnx exists and is readable by onnxruntime.
Run the same sample image through onnxruntime and print output tensor shapes.

=== CELL 8: SAVE ARTIFACTS ===
Create /kaggle/working/artifacts/ and copy into it:
  - The full best_openvino_model/ folder
  - best.onnx
  - visdrone.yaml
  - A file class_map.json containing:
    {"0":"pedestrian","1":"people","2":"bicycle","3":"car","4":"van",
     "5":"truck","6":"tricycle","7":"awning-tricycle","8":"bus","9":"motor"}
  - A file model_info.json containing the mAP50, mAP50-95, training epochs,
    export formats, and W&B run URL

Print the full directory tree of /kaggle/working/artifacts/.
Log the entire artifacts folder as a W&B artifact named "traffic-model-v1" with
metadata {"mAP50": <value>, "format": "openvino-int8+onnx"}.
Print "DONE. Download /kaggle/working/artifacts/ to your local machine."

Include a markdown cell at the top of each section explaining what is happening
and the reasoning behind each decision. This is a portfolio notebook.
```

---

## PROMPT 2 — Video Inference Engine

> Paste this into Claude/ChatGPT to generate: inference/engine.py, inference/annotator.py, inference/analytics.py, inference/sender.py, inference/config.py

```
Generate five Python files for a video-based traffic analytics inference engine.
The engine processes an .mp4 video file, annotates every frame with bounding boxes
and analytics overlays, writes an annotated output video, and streams analytics
to a FastAPI backend in real time. Follow every specification exactly.

============================================================
FILE 1: inference/config.py
============================================================
Define all constants as module-level variables (not a class):

VISDRONE_CLASSES = {
    0:"pedestrian", 1:"people", 2:"bicycle", 3:"car", 4:"van",
    5:"truck", 6:"tricycle", 7:"awning-tricycle", 8:"bus", 9:"motor"
}

# Classes we count as "vehicles" for traffic analytics
VEHICLE_CLASS_IDS = {3, 4, 5, 6, 7, 8}  # car,van,truck,tricycle,awning-tricycle,bus

# Bounding box colors per class (BGR for OpenCV)
CLASS_COLORS = {
    3: (255,180,50),    # car — amber
    4: (100,200,255),   # van — light blue
    5: (50,50,255),     # truck — red
    6: (200,100,255),   # tricycle — purple
    7: (150,255,150),   # awning-tricycle — light green
    8: (0,165,255),     # bus — orange
    0: (200,200,200),   # pedestrian — gray
    1: (180,180,180),   # people — light gray
    2: (255,255,100),   # bicycle — yellow
    9: (255,100,200),   # motor — pink
}

CONF_THRESHOLD = 0.40
IOU_THRESHOLD = 0.50
SKIP_FRAMES = 2              # process every Nth frame
TRAIL_LENGTH = 40            # frames of position history to draw as trail
PIXELS_PER_METER = 8.5       # calibration: pixels per real-world meter
FPS_ASSUMED = 25.0           # assumed video FPS for speed calculation
STOPPED_PIXELS_THRESHOLD = 5.0   # pixel movement threshold for "stopped"
STOPPED_FRAMES_THRESHOLD = 75    # frames stationary before incident flag
CONGESTION_THRESHOLDS = {"LOW":5, "MODERATE":10, "HIGH":18, "CRITICAL":25}
API_BASE_URL = "http://localhost:8000"
ANALYTICS_SEND_EVERY_N_FRAMES = 25    # send analytics every N processed frames
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = [0.5, 1.0, 2.0]

============================================================
FILE 2: inference/analytics.py
============================================================
Write a class TrafficAnalytics with these methods:

__init__(self, video_fps: float, pixels_per_meter: float):
  Initialize internal state:
  - self.track_positions: dict[int, deque] mapping track_id to deque of (cx,cy)
    tuples, maxlen=TRAIL_LENGTH
  - self.track_speeds: dict[int, float] — most recent speed per track
  - self.track_classes: dict[int, int] — class ID per track
  - self.stationary_counters: dict[int, int] — consecutive stationary frames
  - self.active_incidents: dict[int, dict] — currently active incidents
  - self.resolved_incidents: list — all resolved incidents
  - self.crossing_line_counts: dict[str, int] — {"up":0, "down":0, "total":0}
  - self.crossing_line_y: int — set during update() from frame height
  - self.frame_count: int = 0
  - self.video_fps: float
  - self.pixels_per_meter: float

update(self, detections: list[dict], frame_height: int, frame_width: int) -> dict:
  detections is a list of dicts: {track_id, class_id, conf, x1,y1,x2,y2, cx,cy}
  
  Set self.crossing_line_y = int(frame_height * 0.55)  (55% down the frame)
  
  For each detection:
    1. Update self.track_positions[track_id].append((cx, cy))
       Update self.track_classes[track_id] = class_id
    
    2. Speed estimation:
       If track has >= 2 positions, compute Euclidean distance between last two
       positions in pixels. Convert: speed_ms = (pixel_dist * pixels_per_meter) / 
       (1.0 / video_fps). speed_kmh = speed_ms * 3.6. Clamp to [0, 200].
       Store in self.track_speeds[track_id].
    
    3. Stationary detection:
       If track has >= 2 positions and pixel_dist < STOPPED_PIXELS_THRESHOLD:
         increment self.stationary_counters[track_id]
       Else: self.stationary_counters[track_id] = 0
       
       If stationary_counters[track_id] >= STOPPED_FRAMES_THRESHOLD and
       track_id not in self.active_incidents:
         Add to active_incidents: {track_id, type:"stopped_vehicle",
           cx, cy, started_frame: self.frame_count}
    
    4. Counting line crossing:
       If track has >= 2 positions:
         prev_cy = positions[-2][1], curr_cy = positions[-1][1]
         If prev_cy < crossing_line_y and curr_cy >= crossing_line_y:
           crossing_line_counts["down"] += 1; crossing_line_counts["total"] += 1
         If prev_cy > crossing_line_y and curr_cy <= crossing_line_y:
           crossing_line_counts["up"] += 1; crossing_line_counts["total"] += 1
  
  After processing all detections:
    Resolve incidents for tracks no longer in detections:
      For track_id in active_incidents not in current detection track_ids:
        append to resolved_incidents, remove from active_incidents
    
    Compute and return analytics dict:
      visible_vehicle_ids = {d["track_id"] for d in detections 
                             if d["class_id"] in VEHICLE_CLASS_IDS}
      total_vehicles = len(visible_vehicle_ids)
      
      category_counts = {"cars":0,"vans":0,"trucks":0,"buses":0,"others":0}
      for track_id in visible_vehicle_ids:
        class_id = self.track_classes.get(track_id)
        map: 3->cars, 4->vans, 5->trucks, 8->buses, else->others
      
      vehicle_speeds = [self.track_speeds[tid] for tid in visible_vehicle_ids
                        if tid in self.track_speeds]
      avg_speed = sum(vehicle_speeds)/len(vehicle_speeds) if vehicle_speeds else 0.0
      max_speed = max(vehicle_speeds) if vehicle_speeds else 0.0
      
      congestion = next((k for k,v in reversed(CONGESTION_THRESHOLDS.items())
                         if total_vehicles >= v), "LOW")
      
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

  Increment self.frame_count at end.

get_summary(self) -> dict:
  Return a full summary with: total_frames_processed, total_unique_vehicles
  (len of all track_ids seen), peak_vehicle_count (track across all updates),
  total_incidents (len resolved + active), total_crossings, avg_speed_overall,
  crossing_counts.

============================================================
FILE 3: inference/annotator.py
============================================================
Write a class FrameAnnotator with this method:

__init__(self): no-op

draw(self, frame: np.ndarray, detections: list[dict],
     track_positions: dict, track_speeds: dict, track_classes: dict,
     analytics: dict) -> np.ndarray:
  
  Draw all annotations onto the frame (modifies and returns it):
  
  1. TRAILS: For each track_id in track_positions:
     Get the deque of (cx,cy) positions. Convert to a list.
     For i in range(1, len(positions)):
       alpha = i / len(positions)  (trail fades from transparent to solid)
       color = CLASS_COLORS.get(track_classes.get(track_id, 0), (255,255,255))
       thickness = max(1, int(alpha * 2))
       Draw cv2.line from positions[i-1] to positions[i] with color and thickness
       Note: Use overlay blending by creating a copy for the trail and addWeighted
  
  2. BOUNDING BOXES: For each detection in detections:
     color = CLASS_COLORS.get(class_id, (255,255,255))
     cv2.rectangle(frame, (x1,y1), (x2,y2), color, thickness=2)
     
     Label text: "{CLASS_NAME} #{track_id}"
     Draw a filled rectangle behind the label for readability:
       label_bg_rect from (x1, y1-24) to (x1 + text_width + 8, y1)
       cv2.rectangle filled with color at 80% opacity (use addWeighted trick)
     cv2.putText the label in white, font=FONT_HERSHEY_DUPLEX, scale=0.5
  
  3. SPEED BADGE: For each detection where track_id is in track_speeds:
     speed = track_speeds[track_id]
     speed_text = f"{speed:.0f} km/h"
     Draw speed text inside the bounding box at bottom:
       Position: (x1+4, y2-6), color=white, scale=0.45, thickness=1
     If speed > 80: draw speed text in red instead (speeding alert color)
  
  4. CONFIDENCE: Draw conf as small gray text at top-right corner of box:
     f"{conf:.2f}" at (x2-30, y1+12), color=(180,180,180), scale=0.35
  
  5. COUNTING LINE: 
     line_y = analytics["crossing_line_y"]
     Draw a dashed horizontal line across the full frame width at line_y.
     Dashed: loop in steps of 20px, draw 10px segments, skip 10px.
     Color: (0,255,200) cyan-green. Thickness=2.
     Label at right side: "COUNTING LINE" and show total crossings count.
  
  6. HUD OVERLAY (top-left info panel):
     Draw a semi-transparent dark rectangle: x=10,y=10,w=280,h=150, alpha=0.65
     Inside, draw 5 lines of text (white, scale=0.55, thickness=1):
       Line 1: f"VEHICLES: {analytics['total_vehicles']}"
       Line 2: f"CONGESTION: {analytics['congestion_level']}"  
         (color-code: LOW=green, MODERATE=amber, HIGH=orange, CRITICAL=red)
       Line 3: f"AVG SPEED: {analytics['avg_speed_kmh']} km/h"
       Line 4: f"MAX SPEED: {analytics['max_speed_kmh']} km/h"
       Line 5: f"CROSSINGS: {analytics['crossing_counts']['total']}"
     
  7. INCIDENTS BADGE: If analytics["active_incidents"]:
     Draw a red pulsing-style rectangle in top-right corner (x=frame_w-200, y=10)
     Width=190, height=30. Label: f"⚠ {len(incidents)} INCIDENT(S)"
     Text color=white on red background.
  
  8. FRAME NUMBER watermark: bottom-right corner in gray:
     f"FRAME {analytics['frame_number']}" at (frame_w-120, frame_h-10)
  
  Return the annotated frame.

============================================================
FILE 4: inference/sender.py
============================================================
Write a class AnalyticsSender using httpx.AsyncClient:

__init__(self, job_id: str, api_base_url: str):
  self.job_id = job_id
  self.api_base_url = api_base_url
  self.client = httpx.AsyncClient(timeout=5.0)
  self.failed_count = 0
  self.success_count = 0

async def send_analytics(self, analytics: dict, progress_pct: float):
  payload = {**analytics, "job_id": self.job_id, "progress_pct": round(progress_pct,1)}
  url = f"{self.api_base_url}/api/traffic-data"
  for attempt, backoff in enumerate(RETRY_BACKOFF_SECONDS):
    try:
      resp = await self.client.post(url, json=payload)
      if resp.status_code == 200:
        self.success_count += 1
        return True
      await asyncio.sleep(backoff)
    except Exception as e:
      if attempt == len(RETRY_BACKOFF_SECONDS)-1:
        self.failed_count += 1
        # log error with rich but never crash
  return False

async def send_complete(self, summary: dict):
  url = f"{self.api_base_url}/api/jobs/{self.job_id}/complete"
  try:
    await self.client.post(url, json=summary)
  except Exception:
    pass

async def close(self):
  await self.client.aclose()

============================================================
FILE 5: inference/engine.py
============================================================
Write the main entry point. Accept CLI args using argparse:
  --model   path to OpenVINO model directory (required)
  --video   path to input .mp4 file (required)  
  --output  path to save annotated output .mp4 (default: output_annotated.mp4)
  --job-id  job ID string from FastAPI (required, used in API calls)
  --api-url base URL of FastAPI backend (default: http://localhost:8000)
  --skip    frame skip interval (default: 2)

Main function (async):

1. Load model: model = YOLO(args.model)
   Print model info. Warm up with one dummy inference on a blank frame.

2. Open video: cap = cv2.VideoCapture(args.video)
   Read: total_frames, fps, width, height from cap.
   Create output writer: cv2.VideoWriter(args.output,
     cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

3. Initialize:
   analytics_engine = TrafficAnalytics(fps, PIXELS_PER_METER)
   annotator = FrameAnnotator()
   sender = AnalyticsSender(args.job_id, args.api_url)
   
   Use rich.progress Progress bar showing: frame N/total, FPS, ETA

4. Frame processing loop:
   frame_idx = 0
   While cap.isOpened():
     ret, frame = cap.read()
     If not ret: break
     frame_idx += 1
     
     If frame_idx % args.skip != 0:
       writer.write(frame)  # write unannotated frame to keep video length correct
       continue
     
     # Inference with tracking
     results = model.track(frame, persist=True, conf=CONF_THRESHOLD,
                           iou=IOU_THRESHOLD, tracker="bytetrack.yaml",
                           verbose=False)
     
     # Parse detections
     detections = []
     if results[0].boxes is not None and results[0].boxes.id is not None:
       boxes = results[0].boxes
       for i in range(len(boxes)):
         x1,y1,x2,y2 = map(int, boxes.xyxy[i].tolist())
         cx, cy = (x1+x2)//2, (y1+y2)//2
         detections.append({
           "track_id": int(boxes.id[i]),
           "class_id": int(boxes.cls[i]),
           "conf": float(boxes.conf[i]),
           "x1":x1,"y1":y1,"x2":x2,"y2":y2,"cx":cx,"cy":cy
         })
     
     # Update analytics
     analytics = analytics_engine.update(detections, height, width)
     
     # Annotate frame
     annotated = annotator.draw(frame.copy(),
                                detections,
                                analytics_engine.track_positions,
                                analytics_engine.track_speeds,
                                analytics_engine.track_classes,
                                analytics)
     
     # Write annotated frame
     writer.write(annotated)
     
     # Send analytics every ANALYTICS_SEND_EVERY_N_FRAMES
     if frame_idx % ANALYTICS_SEND_EVERY_N_FRAMES == 0:
       progress_pct = (frame_idx / total_frames) * 100
       await sender.send_analytics(analytics, progress_pct)
     
     # Update rich progress bar
   
   # Cleanup
   cap.release()
   writer.release()
   
   # Send completion with summary
   summary = analytics_engine.get_summary()
   summary["output_video_path"] = args.output
   await sender.send_complete(summary)
   await sender.close()
   
   Print final summary using rich.table:
     Total frames, unique vehicles tracked, peak count,
     total incidents, total crossings, avg speed.
   Print f"Annotated video saved to: {args.output}"

Run: asyncio.run(main())

Import everything needed. Use TYPE_CHECKING for type hints.
Add a __main__ guard. Never use global variables.
```

---

## PROMPT 3 — FastAPI Backend

> Paste this to generate the entire backend/ directory

```
Generate a complete FastAPI backend for a video-based traffic analytics system.
The backend receives an uploaded video, manages processing jobs, receives real-time
analytics from an inference engine subprocess, and serves results to a frontend.

============================================================
DATABASE MODELS (db/models.py) — SQLAlchemy async
============================================================

Table: jobs
  id: UUID primary key, default uuid4
  status: String(20) — "queued"|"processing"|"completed"|"failed"
  original_filename: String
  input_path: String       (absolute path to saved upload)
  output_path: String nullable (path to annotated video)
  created_at: DateTime default utcnow
  started_at: DateTime nullable
  completed_at: DateTime nullable
  total_frames: Integer nullable
  processed_frames: Integer nullable (updated during processing)
  progress_pct: Float default 0.0
  error_message: String nullable

Table: traffic_snapshots
  id: UUID primary key
  job_id: UUID foreign key -> jobs.id
  frame_number: Integer
  timestamp: DateTime default utcnow
  total_vehicles: Integer
  cars: Integer
  vans: Integer
  trucks: Integer
  buses: Integer
  others: Integer
  avg_speed_kmh: Float
  max_speed_kmh: Float
  congestion_level: String(20)
  crossing_total: Integer
  active_incidents_count: Integer

Table: incidents
  id: UUID primary key
  job_id: UUID foreign key -> jobs.id
  track_id: Integer
  incident_type: String(50) default "stopped_vehicle"
  frame_number: Integer
  x: Float
  y: Float
  detected_at: DateTime default utcnow
  resolved: Boolean default False

Use alembic for migrations. Write the initial migration file.
After creating traffic_snapshots in the migration, run:
  op.execute("SELECT create_hypertable('traffic_snapshots', 'timestamp', if_not_exists => TRUE);")
  (wrap in try/except in case TimescaleDB is not available — degrade gracefully)

============================================================
PYDANTIC SCHEMAS (db/schemas.py) — Pydantic v2
============================================================

TrafficDataPayload (received from inference engine):
  job_id: str
  frame_number: int
  progress_pct: float
  total_vehicles: int
  categories: dict[str, int]  (keys: cars,vans,trucks,buses,others)
  avg_speed_kmh: float
  max_speed_kmh: float
  congestion_level: str
  active_incidents: list[dict]
  crossing_counts: dict[str, int]

JobSummaryPayload (received on completion):
  job_id: str
  total_frames_processed: int
  total_unique_vehicles: int
  peak_vehicle_count: int
  total_incidents: int
  total_crossings: int
  avg_speed_overall: float
  output_video_path: str

JobResponse:
  All job table fields. Add computed field:
  congestion_color: str — derived from latest snapshot's congestion_level
    (LOW="#22c55e", MODERATE="#f59e0b", HIGH="#f97316", CRITICAL="#ef4444")

HistoryPoint:
  frame_number, total_vehicles, avg_speed_kmh, congestion_level, timestamp

============================================================
WEBSOCKET MANAGER (ws/manager.py)
============================================================

Class ConnectionManager:
  self.active: dict[str, set[WebSocket]] — job_id -> set of websockets
  self._lock: asyncio.Lock

  async connect(ws: WebSocket, job_id: str):
    await ws.accept()
    async with self._lock:
      self.active.setdefault(job_id, set()).add(ws)

  async disconnect(ws: WebSocket, job_id: str):
    async with self._lock:
      self.active.get(job_id, set()).discard(ws)

  async broadcast_to_job(job_id: str, data: dict):
    if job_id not in self.active: return
    dead = set()
    for ws in self.active[job_id]:
      try: await ws.send_json(data)
      except: dead.add(ws)
    async with self._lock:
      self.active[job_id] -= dead

Instantiate as module-level singleton: manager = ConnectionManager()

============================================================
ROUTERS
============================================================

--- routers/jobs.py ---

POST /api/jobs/upload
  Accept: UploadFile (video file, max 500MB)
  Validate content_type starts with "video/"
  Save file to ./uploads/{uuid4}_{filename}
  Create job record in DB with status="queued"
  Trigger background task: run_inference_job(job_id, input_path)
  Return: {"job_id": str, "status": "queued", "filename": original_filename}

Background task run_inference_job(job_id, input_path):
  Update job status="processing", started_at=utcnow in DB
  Broadcast {"event":"status","status":"processing"} to job's WebSocket channel
  Build subprocess command:
    ["python", "-m", "inference.engine",
     "--model", MODEL_PATH,
     "--video", input_path,
     "--output", f"./outputs/{job_id}_annotated.mp4",
     "--job-id", job_id,
     "--api-url", "http://localhost:8000"]
  Run subprocess using asyncio.create_subprocess_exec with stdout/stderr PIPE
  Stream stdout line by line: for each line, parse as JSON if possible and log
  Wait for process to complete. If returncode != 0:
    Update job status="failed", error_message=stderr
  (Completion is handled by the /api/jobs/{id}/complete endpoint)

GET /api/jobs
  Return list of all jobs ordered by created_at DESC.
  Include latest snapshot stats for each job (subquery or joined).
  
GET /api/jobs/{job_id}
  Return full job record + latest 1 traffic snapshot.
  404 if not found.

GET /api/jobs/{job_id}/history
  Query param: limit (default 300)
  Return list of traffic_snapshots for this job, ordered by frame_number,
  only columns: frame_number, total_vehicles, avg_speed_kmh, congestion_level
  This is used to populate the charts.

GET /api/jobs/{job_id}/incidents
  Return all incidents for this job ordered by detected_at.

GET /api/jobs/{job_id}/summary
  Return the final summary stats from the job + aggregate queries:
    - peak vehicle count (max total_vehicles from snapshots)
    - average speed (avg avg_speed_kmh from snapshots)
    - total duration seconds (completed_at - started_at)
    - congestion breakdown (count of each congestion_level)

--- routers/traffic.py ---

POST /api/traffic-data
  Receive TrafficDataPayload from inference engine.
  1. Write to traffic_snapshots table.
  2. Write any new incidents in active_incidents to incidents table.
  3. Update jobs.progress_pct and jobs.processed_frames.
  4. Broadcast to WebSocket: {"event":"analytics", "data": payload_dict}
  5. Return {"status":"ok"}

POST /api/jobs/{job_id}/complete
  Receive JobSummaryPayload from inference engine.
  Update job: status="completed", completed_at=utcnow, output_path=...
  Broadcast: {"event":"complete","summary": payload_dict}
  Return {"status":"ok"}

--- routers/media.py ---

GET /api/jobs/{job_id}/video
  Check job.output_path exists. If not: 404.
  Use FileResponse to stream the annotated .mp4 file.
  Set headers: Content-Disposition: inline, filename=annotated_{job_id}.mp4
  Accept-Ranges: bytes (for video seeking in browser)

GET /api/jobs/{job_id}/thumbnail
  Extract frame 1 from the annotated video using cv2.
  Return as JPEG image (StreamingResponse with media_type="image/jpeg").
  Cache-Control: max-age=3600

--- WebSocket ---

WebSocket /ws/jobs/{job_id}
  Connect, register with manager.
  Send initial job status: {"event":"connected","job_id":job_id,"status":job.status}
  Keep alive loop: every 20s send {"event":"ping"}
  On disconnect: manager.disconnect()

============================================================
MAIN APP (main.py)
============================================================

Create FastAPI app with title="Traffic Analytics API", version="1.0.0"

Add:
  CORSMiddleware: allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
  
Include all routers with prefix="/api" (except WebSocket which has no prefix).

On startup:
  Create uploads/ and outputs/ directories if they do not exist.
  Run alembic upgrade head programmatically.
  Initialize Redis connection (redis.asyncio).
  Log "Server ready" with the model path.

GET /health:
  Check DB connection (SELECT 1) and Redis ping.
  Return {"status":"ok","db":"connected","redis":"connected",
          "model_loaded": bool}

Add prometheus_fastapi_instrumentator instrumentation.
Add two Prometheus Gauge metrics: current_vehicle_count, current_fps.
Update them in the POST /api/traffic-data handler.

Environment variables to read (use python-dotenv):
  DATABASE_URL, REDIS_URL, MODEL_PATH, UPLOAD_DIR, OUTPUT_DIR

Include full inline comments explaining every design decision.
```

---

## PROMPT 4 — Frontend Dashboard

> Paste this to generate the entire frontend/src/ directory

```
Build a complete React + Vite frontend for a video-based traffic analytics system.
The UI has three views: Upload, Processing, and Results.

============================================================
TECH STACK
============================================================
React 18, Vite, Tailwind CSS (dark mode, bg-gray-950 base),
react-apexcharts + apexcharts, lucide-react, react-router-dom v6,
react-dropzone for file upload.

Install command (put in README):
  npm create vite@latest frontend -- --template react
  cd frontend && npm install tailwindcss @tailwindcss/vite \
    react-apexcharts apexcharts lucide-react react-router-dom react-dropzone

Colors to use throughout (as Tailwind classes or inline):
  bg-gray-950 (base background)
  bg-gray-900 (card background)
  bg-gray-800 (border / hover)
  text-white (primary text)
  text-gray-400 (secondary text)
  
Accent colors for congestion states:
  LOW: text-emerald-400, border-emerald-400
  MODERATE: text-amber-400, border-amber-400
  HIGH: text-orange-400, border-orange-400
  CRITICAL: text-red-400, border-red-400, animate-pulse on badge

Design details to apply everywhere:
  - Cards: bg-gray-900 border border-gray-800 rounded-xl p-4 md:p-6
  - Hover: hover:border-gray-600 hover:bg-gray-800/50 transition-all duration-200
  - Numbers: font-mono text (use monospace for all numeric values)
  - All number changes: animate with a count-up effect using requestAnimationFrame
    (write a useCountUp(target, duration=600) hook that animates from prev to target)
  - Skeleton loading: bg-gray-800 animate-pulse rounded for placeholder shapes

============================================================
CUSTOM HOOKS
============================================================

hooks/useJobWebSocket.js:
  useJobWebSocket(jobId)
  Connects to ws://localhost:8000/ws/jobs/{jobId}
  Auto-reconnects with exponential backoff: 1s, 2s, 4s, 8s, max 30s
  Returns:
    { wsStatus, latestAnalytics, progress, isComplete, summary, error }
  
  Internal state:
    wsStatus: "connecting"|"connected"|"disconnected"|"error"
    latestAnalytics: last received analytics payload
    progress: 0-100 float
    isComplete: boolean
    summary: completion summary object
  
  On message, parse JSON. Switch on event type:
    "analytics": update latestAnalytics, progress
    "complete": set isComplete=true, set summary
    "status": update job status
    "ping": ignore
  
  Clean up WebSocket on unmount.

hooks/useJobHistory.js:
  useJobHistory(jobId)
  On mount, fetch GET /api/jobs/{jobId}/history
  Returns { history: HistoryPoint[], loading, error }
  history is an array of { frame_number, total_vehicles, avg_speed_kmh }

============================================================
PAGE: Upload (src/pages/Upload.jsx)
============================================================

Layout: Centered card on screen, max-w-2xl, with:

Header: "Traffic Analytics" in large font + "Upload a video to analyze"

Dropzone area (react-dropzone):
  Accepts .mp4, .mov, .avi only. Max size 500MB.
  Idle state: dashed border, upload icon (lucide Upload), "Drop your video here"
  Hover state: border turns emerald-400, background lightens
  File selected: show filename, size, and a video thumbnail preview
    (use URL.createObjectURL + <video> element to show first frame)
  Rejected: show error message in red

Below dropzone: three feature badges in a row:
  "ByteTrack Tracking" | "Speed Estimation" | "Incident Detection"
  Each as a small chip with icon and gray text.

Upload button:
  Disabled if no file selected.
  Loading state shows spinner icon and "Uploading..."
  On click: POST to /api/jobs/upload as FormData.
  On success: navigate to /processing/{job_id}
  On error: show red alert with error message.

Show upload progress (0-100%) using a thin progress bar during the upload
using XMLHttpRequest (not fetch) so you can track progress events.

============================================================
PAGE: Processing (src/pages/Processing.jsx)
============================================================

Get jobId from URL params. Connect to useJobWebSocket(jobId).
Fetch job details from GET /api/jobs/{jobId} on mount.

Layout: Two-column on desktop, one column on mobile.

LEFT COLUMN:
  Job info card: filename, status badge, started_at time.
  
  Progress section:
    Label: "Processing: {progress_pct}%"
    Animated progress bar (smooth CSS transition on width change):
      bg-gradient-to-r from-emerald-500 to-teal-400
      Height 8px, rounded-full, transition-all duration-300
    Label below: "Frame {frame_number} of {total_frames} (estimated)"
  
  Live metrics (4 cards in 2x2 grid, update from WebSocket):
    - Vehicles in frame (with count-up animation)
    - Congestion level (color-coded)
    - Avg speed km/h
    - Processing FPS

RIGHT COLUMN:
  Live density chart (DensityChart component, see below)
    Title: "Live Vehicle Count"
    Data: rolling last 60 analytics points from WebSocket

  Status log:
    Scrollable list of timestamped events (ws connected, processing started,
    each congestion level change, incidents detected)
    Auto-scroll to bottom on new entries.

When isComplete = true:
  Show a success banner: "Analysis complete!"
  Show a "View Results" button that navigates to /results/{jobId}
  Auto-navigate after 3 seconds.

When wsStatus = "disconnected":
  Show amber banner: "Connection lost — attempting to reconnect..."

============================================================
PAGE: Results (src/pages/Results.jsx)
============================================================

Get jobId from URL params.
Fetch on mount:
  GET /api/jobs/{jobId}/summary → summary stats
  GET /api/jobs/{jobId}/history → history data for charts
  GET /api/jobs/{jobId}/incidents → incidents list

Layout: Three-row layout.

ROW 1 — SUMMARY KPI CARDS (4 cards, full width):
  - Total unique vehicles tracked
  - Peak simultaneous vehicles
  - Average speed km/h
  - Total incidents detected
  Each with an icon (lucide-react) and count-up animation.

ROW 2 — VIDEO PLAYER (left, 60%) + INCIDENT TABLE (right, 40%):

  VIDEO PLAYER (VideoPlayer.jsx):
    HTML5 <video> element pointing to /api/jobs/{jobId}/video
    Custom controls overlay (not browser defaults):
      Play/Pause button (lucide Play/Pause)
      Seek bar (custom input[type=range] styled)
      Time display: "1:23 / 4:56"
      Speed selector: 0.5x, 1x, 1.5x, 2x
      Fullscreen button
    Label above: "Annotated Output Video"
    Download link below: "Download annotated video" (anchor with download attr)

  INCIDENT TABLE (IncidentTable.jsx):
    Title: "Detected Incidents"
    Table columns: Track ID | Type | Frame | Location | Duration
    If no incidents: show empty state with checkmark
    Highlight rows in red on hover.
    Show count badge next to title.

ROW 3 — CHARTS (three charts side by side):

  DensityChart.jsx (left, 50%):
    ApexCharts area chart, series: total_vehicles over frame_number.
    Smooth curve, gradient fill, no markers.
    Add annotation line at y=18 labeled "HIGH threshold" in orange.
    X-axis: frame numbers (thin labels). Y-axis: count.
    Append new data without re-rendering full chart.

  SpeedHistogram.jsx (center, 25%):
    ApexCharts bar chart showing distribution of avg_speed_kmh values
    grouped into bins: 0-20, 20-40, 40-60, 60-80, 80+ km/h.
    Color each bar by speed range (green→yellow→orange→red).
    Title: "Speed Distribution"

  CategoryDonut.jsx (right, 25%):
    ApexCharts donut chart with series: [cars, vans, trucks, buses, others].
    Colors matching CLASS_COLORS theme.
    Show total in center using dataLabels formatter.
    Title: "Vehicle Types"

Below the charts:
  Download section: two buttons:
    "Download Annotated Video" (mp4)
    "Export Analytics CSV" (fetch /api/jobs/{jobId}/history, convert to CSV,
      trigger download using Blob URL)

Back button in top-left: navigate to / (upload page).
Job history sidebar (collapsible on mobile):
  List of all past jobs from GET /api/jobs.
  Each shows filename, status badge, created_at.
  Click navigates to /results/{job_id}.

============================================================
APP SHELL (App.jsx)
============================================================

React Router routes:
  / → Upload
  /processing/:jobId → Processing
  /results/:jobId → Results

Persistent header (all pages):
  Left: Logo icon (lucide Eye) + "TrafficVision" text
  Right: GitHub link icon + "View Source"

Global CSS: Apply dark scrollbar (scrollbar-color: #374151 #111827)
Use Tailwind's dark mode class strategy.
```

---

## PROMPT 5 — DevOps Layer

> Paste this to generate all infrastructure files

```
Generate the complete DevOps infrastructure for the traffic analytics project.
Create every file listed below exactly.

============================================================
docker-compose.yml
============================================================
version: "3.9"
services:
  postgres:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_DB: traffic
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: secret
    ports: ["5432:5432"]
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin -d traffic"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 15s

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports: ["8000:8000"]
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://admin:secret@postgres:5432/traffic
      REDIS_URL: redis://redis:6379
      MODEL_PATH: /app/artifacts/best_openvino_model/
      UPLOAD_DIR: /app/uploads
      OUTPUT_DIR: /app/outputs
    volumes:
      - ./artifacts:/app/artifacts:ro
      - uploads_data:/app/uploads
      - outputs_data:/app/outputs

volumes:
  postgres_data:
  uploads_data:
  outputs_data:

networks:
  default:
    name: traffic-net

============================================================
backend/Dockerfile
============================================================
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

============================================================
backend/requirements.txt
============================================================
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.35
asyncpg==0.30.0
alembic==1.13.0
pydantic[email]==2.8.0
python-multipart==0.0.12
httpx==0.27.0
redis[asyncio]==5.0.0
prometheus-fastapi-instrumentator==7.0.0
prometheus-client==0.21.0
python-dotenv==1.0.0
opencv-python-headless==4.10.0.84
ultralytics==8.3.0
openvino>=2024.0
psutil==6.0.0
rich==13.9.0

============================================================
Makefile
============================================================
.PHONY: setup db-up migrate backend inference frontend up down test lint clean

MODEL ?= artifacts/best_openvino_model/
VIDEO ?= sample.mp4

setup:
	cp -n .env.example .env || true
	pip install -r backend/requirements.txt
	cd frontend && npm install

db-up:
	docker compose up -d postgres redis
	@echo "Waiting for postgres..." && sleep 5

migrate:
	cd backend && alembic upgrade head

backend:
	cd backend && uvicorn main:app --reload --port 8000

inference:
	python -m inference.engine --model $(MODEL) --video $(VIDEO) \
	  --output outputs/annotated.mp4 --job-id local-test --api-url http://localhost:8000

frontend:
	cd frontend && npm run dev

up:
	docker compose up --build

down:
	docker compose down -v

test:
	cd backend && pytest tests/ -v --cov=. --cov-report=term-missing

lint:
	ruff check . && ruff format --check .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.pytest_cache frontend/dist

============================================================
.env.example
============================================================
DATABASE_URL=postgresql+asyncpg://admin:secret@localhost:5432/traffic
REDIS_URL=redis://localhost:6379
MODEL_PATH=./artifacts/best_openvino_model/
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs

============================================================
.github/workflows/ci.yml
============================================================
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install ruff
      - run: ruff check . && ruff format --check .

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: timescale/timescaledb:latest-pg16
        env:
          POSTGRES_DB: traffic
          POSTGRES_USER: admin
          POSTGRES_PASSWORD: secret
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-retries 10
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-retries 5
    env:
      DATABASE_URL: postgresql+asyncpg://admin:secret@localhost:5432/traffic
      REDIS_URL: redis://localhost:6379
      MODEL_PATH: ./artifacts/
      UPLOAD_DIR: ./uploads
      OUTPUT_DIR: ./outputs
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -r backend/requirements.txt pytest pytest-asyncio pytest-cov httpx
      - run: mkdir -p uploads outputs artifacts
      - run: cd backend && alembic upgrade head
      - run: cd backend && pytest tests/ -v --cov=. --cov-report=xml
      - uses: codecov/codecov-action@v4

  docker-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build ./backend -t traffic-backend:ci

============================================================
backend/tests/test_api.py
============================================================
Write pytest tests using httpx.AsyncClient and pytest-asyncio.
Use a test SQLite database (override DATABASE_URL in conftest.py).

Tests to write:
1. test_health_endpoint: GET /health returns 200 and {"status":"ok"}
2. test_upload_video_no_file: POST /api/jobs/upload with no file returns 422
3. test_upload_video_wrong_type: POST with a .txt file returns 400
4. test_post_traffic_data_valid: POST /api/traffic-data with valid TrafficDataPayload
   returns 200 and {"status":"ok"}
5. test_post_traffic_data_missing_fields: POST with missing job_id returns 422
6. test_get_jobs_empty: GET /api/jobs returns 200 and empty list
7. test_get_job_not_found: GET /api/jobs/nonexistent returns 404
8. test_get_history_empty: GET /api/jobs/fake-id/history returns 200 and []

Use fixtures:
  @pytest.fixture async def client() — AsyncClient with app, base_url=http://test
  @pytest.fixture autouse async def reset_db() — drop and recreate tables between tests

============================================================
README.md sections to write:
============================================================
1. Title + animated GIF placeholder (note: "replace with demo.gif")
2. Three badges: CI status, Python 3.11, License MIT
3. Architecture section: embed the system diagram (as ASCII or link to image)
4. Feature list (bullet points with emojis)
5. Tech stack table (4 columns: Layer, Technology, Purpose, Why I chose it)
6. Quick start (3 commands: make up, then make inference VIDEO=your.mp4)
7. API reference table (method, endpoint, description)
8. Model performance table (mAP50, mAP50-95, inference ms/frame, format)
9. Screenshots section with 3 captioned placeholders
10. What I learned (3 paragraphs: ML pipeline, systems design, what I'd change)
11. License: MIT
```

---

## Execution Order (Run In This Sequence)

```bash
# 1. Train the model (Kaggle)
#    Run notebooks/01_train_export.ipynb on Kaggle GPU
#    Download artifacts/ folder to your local machine

# 2. Start the databases
make db-up
make migrate

# 3. Start the backend (new terminal)
make backend

# 4. Start the frontend (new terminal)  
make frontend
# Open http://localhost:5173

# 5. Upload a video through the web UI
#    OR run inference directly for testing:
make inference VIDEO=your_traffic_video.mp4

# 6. Full Docker stack (optional, for final demo)
make up
```

---

## Integration Contract (How The Components Talk)

```
User uploads video
  → POST /api/jobs/upload (multipart)
  ← {job_id: "abc123", status: "queued"}

Frontend connects
  → WS /ws/jobs/abc123
  ← {"event":"status","status":"processing"}  (when job starts)

Inference engine runs (subprocess)
  → POST /api/traffic-data every 25 frames
     {job_id, frame_number, progress_pct, total_vehicles, categories,
      avg_speed_kmh, max_speed_kmh, congestion_level, active_incidents,
      crossing_counts}
  ← {"status":"ok"}

Backend receives analytics
  → Writes to traffic_snapshots table
  → Broadcasts to WS: {"event":"analytics", "data": {...}}

Frontend receives WS message
  → Updates progress bar to progress_pct
  → Updates all metric cards with count-up animation
  → Appends point to DensityChart

Inference engine finishes
  → POST /api/jobs/{id}/complete
     {total_frames_processed, total_unique_vehicles, peak_vehicle_count,
      total_incidents, avg_speed_overall, output_video_path}

Backend receives completion
  → Updates job status="completed"
  → Broadcasts: {"event":"complete","summary":{...}}

Frontend receives complete event
  → Shows "Analysis complete!" banner
  → Navigates to /results/abc123

Results page loads
  → GET /api/jobs/abc123/summary
  → GET /api/jobs/abc123/history
  → GET /api/jobs/abc123/incidents
  → Video player loads /api/jobs/abc123/video (streams mp4)
```

---

*Each prompt generates one self-contained module. Run them in order 1→5.
Paste each into Claude or ChatGPT separately — do not combine them.*
