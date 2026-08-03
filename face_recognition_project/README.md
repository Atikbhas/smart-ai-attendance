# Face Recognition Attendance System

A professional, production-ready face recognition attendance system built with Python, OpenCV, and the face_recognition library (dlib-based).

## Features

- **Face Capture**: Capture 50-100 clear face images per person with live preview, blur detection, and single-face validation
- **Model Training**: Generate face encodings from dataset images, skip invalid images, save to `encodings.pkl`
- **Real-time Recognition**: Recognize faces in real-time webcam feed with confidence percentages, bounding boxes, and multi-face support
- **Performance Optimized**: Frame resizing, frame skipping, and optional multithreading for high FPS
- **Clean Architecture**: Modular design with separation of concerns

## Requirements

- Python 3.12+
- Windows/macOS/Linux
- Webcam

## Installation

### 1. Clone/Navigate to Project

```bash
cd face_recognition_project
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note for Windows**: If `dlib` installation fails, install Visual Studio Build Tools first, or use:
```bash
pip install dlib==19.24.6 --no-cache-dir
```

Or install via conda:
```bash
conda install -c conda-forge dlib
```

### 4. Verify Installation

```bash
python -c "import face_recognition; print('OK')"
```

## Usage

### 1. Capture Faces

Capture face images for one or more people:

```bash
# Single person
python capture_faces.py "John Doe"

# Multiple people
python capture_faces.py "John Doe" "Jane Smith" "Bob Wilson"

# Custom image count (default: 50)
python capture_faces.py "John Doe" -c 100

# Different camera
python capture_faces.py "John Doe" --camera 1
```

**Controls during capture:**
- `SPACE` - Capture image (only when clear face detected)
- `q` - Quit early
- `s` - Skip current frame

The system will:
- Show live camera preview with face detection overlay
- Reject blurry images (Laplacian variance < 100)
- Reject images with multiple faces or no faces
- Require minimum face size (80x80 pixels)
- Display capture progress bar

### 2. Train Model

Generate face encodings from captured images:

```bash
# Default settings
python train_model.py

# Custom dataset/output paths
python train_model.py --dataset dataset --output models/encodings.pkl

# Adjust quality thresholds
python train_model.py --min-face-size 100 --blur-threshold 150
```

Output: `models/encodings.pkl` containing all face encodings and names.

### 3. Recognize Faces (Real-time)

Run real-time face recognition from webcam:

```bash
# Default settings
python recognize.py

# Custom settings
python recognize.py --camera 0 --threshold 0.6 --skip-frames 2 --scale 0.25
```

**Controls during recognition:**
- `q` - Quit
- `s` - Save snapshot

### 4. Recognize from Image File

```bash
python recognize.py --image path/to/photo.jpg
```

## Project Structure

```
face_recognition_project/
├── capture_faces.py      # Face capture module
├── train_model.py        # Training module
├── recognize.py          # Recognition module
├── utils.py              # Shared utilities
├── requirements.txt      # Dependencies
├── dataset/              # Training images (auto-created)
│   └── Person_Name/
│       ├── image1.jpg
│       └── image2.jpg
├── models/               # Model files (auto-created)
│   └── encodings.pkl     # Face encodings
└── README.md             # This file
```

## Configuration

Key settings in `utils.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CAPTURE_COUNT` | 50 | Images to capture per person |
| `BLUR_THRESHOLD` | 100.0 | Laplacian variance threshold |
| `MIN_FACE_SIZE` | 80 | Minimum face size in pixels |
| `PROCESSING_SCALE` | 0.25 | Frame resize factor for recognition |
| `CONFIDENCE_THRESHOLD` | 0.6 | Minimum confidence for recognition |
| `FRAME_WIDTH/HEIGHT` | 640x480 | Camera resolution |

## Performance Tips

1. **Reduce `PROCESSING_SCALE`** (0.15-0.25) for faster processing
2. **Increase `skip-frames`** (2-3) to process fewer frames
3. **Lower camera resolution** (320x240) for faster capture
4. **Use multithreading** (enabled by default in `recognize.py`)

## Attendance Integration Example

```python
from recognize import FaceRecognizer, run_recognition
from utils import load_encodings
from datetime import datetime
import csv

# Custom attendance logger
class AttendanceLogger:
    def __init__(self, csv_file="attendance.csv"):
        self.csv_file = csv_file
        self.logged_today = set()
        self._load_existing()
    
    def _load_existing(self):
        try:
            with open(self.csv_file, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        self.logged_today.add((row[0], row[1]))  # name, date
        except FileNotFoundError:
            pass
    
    def log(self, name: str):
        today = datetime.now().strftime("%Y-%m-%d")
        key = (name, today)
        if key not in self.logged_today and name != "Unknown":
            with open(self.csv_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([name, today, datetime.now().strftime("%H:%M:%S")])
            self.logged_today.add(key)
            print(f"Attendance logged: {name} at {datetime.now().strftime('%H:%M:%S')}")

# Usage in recognition loop
logger = AttendanceLogger()

# In your recognition callback:
def on_recognition(results):
    for r in results:
        logger.log(r.name)
```

## Troubleshooting

### Camera not found
```bash
# List available cameras (Linux)
v4l2-ctl --list-devices

# Try different camera index
python capture_faces.py "Name" --camera 1
```

### Low FPS
- Reduce `PROCESSING_SCALE` to 0.15
- Increase `--skip-frames` to 3
- Lower camera resolution in `utils.py`

### Poor recognition accuracy
- Capture more images per person (80-100)
- Ensure good lighting during capture
- Increase `CONFIDENCE_THRESHOLD` to 0.65-0.7
- Retrain with `train_model.py`

### dlib installation issues (Windows)
```bash
# Option 1: Install Visual Studio Build Tools
# Option 2: Use conda
conda install -c conda-forge dlib face_recognition
# Option 3: Pre-built wheel
pip install https://github.com/z-mahmud22/Dlib_Windows_Python3.x/raw/master/dlib-19.24.0-cp312-cp312-win_amd64.whl
```

## License

MIT License - Free for personal and commercial use.

## Extending the System

The modular design makes it easy to extend:

- **Add attendance logging**: Subclass `FaceRecognizer` and override `process_frame`
- **Add GUI**: Use `tkinter` or `PyQt` with the existing modules
- **Add database**: Replace CSV logging with SQLite/PostgreSQL
- **Add web interface**: Wrap with Flask/FastAPI
- **Add anti-spoofing**: Integrate blink detection or depth sensing