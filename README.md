# 🚦 TrafficVision — AI-Powered Traffic Analytics

![Demo](docs/demo.gif)
> *Replace `docs/demo.gif` with an actual recording of the system in action.*

[![CI Pipeline](https://img.shields.io/github/actions/workflow/status/yourusername/TrafficVision/ci.yml?branch=main&label=CI&logo=github)](https://github.com/yourusername/TrafficVision/actions)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3110/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**TrafficVision** is an end-to-end AI-powered traffic analytics system that detects, tracks, and analyzes vehicles and pedestrians from video feeds in real time. Built as a production-grade portfolio project demonstrating the full ML pipeline — from model training to deployment with a live dashboard.

---

## ✨ Features

| | Feature | Description |
|---|---|---|
| 🎯 | **Multi-Object Detection & Tracking** | YOLO11 + ByteTrack for robust, real-time multi-object tracking across frames |
| ⚡ | **Real-Time Speed Estimation** | Perspective-corrected speed calculation using configurable calibration zones |
| 📊 | **Live Analytics Dashboard** | React-based dashboard with real-time charts, counts, and heatmaps via WebSocket |
| 🔴 | **Automatic Incident Detection** | Rule-based alerts for stopped vehicles, wrong-way driving, and congestion |
| 📈 | **Vehicle Counting Line** | Configurable virtual counting lines with directional tracking |
| 🎬 | **Annotated Video Output** | Generate publication-ready annotated videos with bounding boxes, trails, and overlays |

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────────────┐     ┌──────────────────┐
│             │     │              Inference Engine                    │     │                  │
│  Video      │     │  ┌─────────┐  ┌──────────┐  ┌───────────────┐  │     │   Frontend       │
│  Source     ├────►│  │ YOLO11  ├─►│ ByteTrack├─►│ Speed / Count │  │     │   (React +       │
│  (file /    │     │  │ (ONNX)  │  │ Tracker  │  │ Analytics     │  ├────►│    ApexCharts)   │
│   stream)   │     │  └─────────┘  └──────────┘  └───────────────┘  │     │                  │
└─────────────┘     └──────────────────┬───────────────────────────────┘     └────────┬─────────┘
                                       │                                             │
                                       ▼                                             │
                              ┌─────────────────┐                                    │
                              │  FastAPI Backend │◄───────────────────────────────────┘
                              │  + WebSocket     │         (REST + WS)
                              └────────┬────────┘
                                       │
                            ┌──────────┼──────────┐
                            ▼          ▼          ▼
                      ┌──────────┐ ┌───────┐ ┌────────┐
                      │PostgreSQL│ │ Redis │ │ S3 /   │
                      │(events)  │ │(cache)│ │ local  │
                      └──────────┘ └───────┘ └────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **ML / Vision** | YOLO11 (Ultralytics) | Object detection |
| | ByteTrack | Multi-object tracking |
| | OpenCV | Video I/O and frame processing |
| | ONNX Runtime | Optimized CPU inference |
| **Backend** | FastAPI | REST API & WebSocket server |
| | PostgreSQL | Persistent event and analytics storage |
| | Redis | Real-time state caching & pub/sub |
| | Alembic | Database migrations |
| **Frontend** | React 18 | UI framework |
| | Vite | Build tool & dev server |
| | Tailwind CSS | Utility-first styling |
| | ApexCharts | Real-time interactive charts |
| **DevOps** | Docker & Compose | Containerized deployment |
| | GitHub Actions | CI/CD pipeline |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** with pip
- **Node.js 18+** with npm
- **Docker Desktop** (for PostgreSQL & Redis)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/TrafficVision.git
cd TrafficVision
```

### 2. Start Infrastructure Services

```bash
docker compose up -d  # PostgreSQL + Redis
```

### 3. Set Up the Backend

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the backend server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Set Up the Frontend

```bash
cd frontend
npm install
npm run dev
```

### 5. Open the Dashboard

Navigate to **http://localhost:5173** in your browser.

---

## 🏋️ Model Training

The model is trained on the [VisDrone2019-DET](https://github.com/VisDrone/VisDrone-Dataset) dataset using a Kaggle notebook.

### Kaggle Notebook Setup

1. **Create a new Kaggle notebook** with GPU accelerator (T4 or P100)
2. **Add the dataset**: Search for `ultralytics/visdrone` in "Add Data"
3. **Add your W&B API key** to Kaggle Secrets as `WANDB_API_KEY`
4. **Copy cells** from [`notebooks/01_train_export.py`](notebooks/01_train_export.py) into notebook cells
5. **Run all cells** — training takes ~2-3 hours on a T4 GPU

### What the Notebook Does

| Cell | Task | Description |
|------|------|-------------|
| 1 | Setup | Installs dependencies, authenticates W&B |
| 2 | Download | Fetches VisDrone2019-DET from Kaggle datasets |
| 3 | Convert | Converts VisDrone annotations → YOLO format, creates train/val/test splits |
| 4 | Train | Trains YOLO11-nano for 80 epochs with AdamW + augmentation |
| 5 | Validate | Evaluates on test split, prints per-class AP50, asserts mAP50 > 0.20 |
| 6 | Export | Exports to ONNX (opset 17), verifies with ONNX Runtime |
| 7 | Package | Bundles model + metadata into downloadable artifacts |

### After Training

Download the artifacts from `/kaggle/working/artifacts/` and place them:

```
models/
├── best.onnx          # Trained YOLO11-nano ONNX model
├── class_map.json     # Class ID → name mapping
└── model_info.json    # Model metadata & training config
```

### Detected Classes (VisDrone)

| ID | Class | ID | Class |
|----|-------|----|-------|
| 0 | Pedestrian | 5 | Truck |
| 1 | People | 6 | Tricycle |
| 2 | Bicycle | 7 | Awning-Tricycle |
| 3 | Car | 8 | Bus |
| 4 | Van | 9 | Motor |

---

## 📡 API Reference

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check and system status |
| `POST` | `/api/video/upload` | Upload a video file for processing |
| `GET` | `/api/video/{id}/status` | Get processing status for a video |
| `GET` | `/api/analytics/summary` | Aggregated analytics summary |
| `GET` | `/api/analytics/counts` | Vehicle counts over time |
| `GET` | `/api/analytics/speed` | Speed statistics per class |
| `GET` | `/api/incidents` | List of detected incidents |
| `GET` | `/api/incidents/{id}` | Incident details and snapshot |
| `POST` | `/api/config/zones` | Configure detection/counting zones |
| `GET` | `/api/config/zones` | Get current zone configuration |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `ws://localhost:8000/ws/live` | Real-time detection events and analytics stream |

---

## 📁 Project Structure

```
TrafficVision/
├── backend/                    # FastAPI backend application
│   ├── api/                    # API route handlers
│   │   ├── routes/             # Endpoint definitions
│   │   └── websocket.py        # WebSocket handler
│   ├── core/                   # Application configuration
│   │   ├── config.py           # Settings & environment variables
│   │   └── database.py         # Database connection
│   ├── inference/              # ML inference engine
│   │   ├── detector.py         # YOLO ONNX inference wrapper
│   │   ├── tracker.py          # ByteTrack integration
│   │   └── pipeline.py         # Detection → Tracking → Analytics
│   ├── analytics/              # Traffic analytics modules
│   │   ├── counter.py          # Line-crossing vehicle counter
│   │   ├── speed.py            # Speed estimation engine
│   │   └── incidents.py        # Incident detection rules
│   ├── models/                 # SQLAlchemy ORM models
│   ├── schemas/                # Pydantic request/response schemas
│   └── main.py                 # Application entry point
├── frontend/                   # React frontend application
│   ├── src/
│   │   ├── components/         # Reusable UI components
│   │   ├── pages/              # Page-level components
│   │   ├── hooks/              # Custom React hooks (useWebSocket, etc.)
│   │   ├── services/           # API client services
│   │   └── App.tsx             # Root application component
│   ├── package.json
│   └── vite.config.ts
├── notebooks/                  # Training & experimentation
│   └── 01_train_export.py      # Kaggle training notebook script
├── models/                     # Trained model artifacts
│   ├── best.onnx               # YOLO11-nano ONNX model
│   ├── class_map.json          # Class ID → name mapping
│   └── model_info.json         # Model metadata
├── migrations/                 # Alembic database migrations
│   └── versions/
├── tests/                      # Test suite
│   ├── test_api/
│   ├── test_inference/
│   └── test_analytics/
├── docs/                       # Documentation & media
│   └── demo.gif                # Demo animation
├── docker-compose.yml          # Infrastructure services
├── Dockerfile                  # Backend container definition
├── requirements.txt            # Python dependencies
├── alembic.ini                 # Alembic configuration
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI pipeline
├── .env.example                # Environment variable template
├── README.md                   # This file
└── LICENSE                     # MIT License
```

---

## 📸 Screenshots

| Dashboard | Detection View |
|-----------|---------------|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Detection](docs/screenshots/detection.png) |
| *Real-time analytics dashboard with vehicle counts, speed distribution, and incident alerts.* | *Annotated video frame showing bounding boxes, tracking IDs, and speed estimates.* |

> *Replace placeholder images with actual screenshots of your running application.*

---

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=backend --cov-report=html

# Run specific test modules
pytest tests/test_inference/ -v
pytest tests/test_analytics/ -v
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with ❤️ for the intersection of computer vision and urban mobility.
</p>
