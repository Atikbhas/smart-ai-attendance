"""Recognition Module - Real-time face recognition with attendance tracking.

Loads encodings, recognizes faces in real-time webcam feed,
displays names with confidence, supports multiple faces.
"""

import cv2
import face_recognition
import numpy as np
import time
import threading
from queue import Queue, Empty
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import sys

from utils import (
    load_encodings, init_camera, release_camera, resize_frame,
    draw_face_box, draw_info_panel, draw_progress_bar,
    PROCESSING_SCALE, CONFIDENCE_THRESHOLD, logger
)


@dataclass
class RecognitionResult:
    """Result of face recognition for a single face."""
    name: str
    confidence: float
    location: Tuple[int, int, int, int]
    timestamp: datetime


class FaceRecognizer:
    """Optimized face recognizer with frame skipping and threading."""
    
    def __init__(self, encodings_data: dict, 
                 confidence_threshold: float = CONFIDENCE_THRESHOLD,
                 process_every_n_frames: int = 2,
                 scale: float = PROCESSING_SCALE):
        self.known_encodings = encodings_data.get("encodings", [])
        self.known_names = encodings_data.get("names", [])
        self.confidence_threshold = confidence_threshold
        self.process_every_n_frames = process_every_n_frames
        self.scale = scale
        
        self.frame_count = 0
        self.last_results: List[RecognitionResult] = []
        
        self.frame_queue: Queue = Queue(maxsize=2)
        self.result_queue: Queue = Queue(maxsize=2)
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        
        self.stats = {
            "frames_processed": 0,
            "faces_detected": 0,
            "faces_recognized": 0,
            "avg_fps": 0.0
        }
        self.fps_start = time.time()
        self.fps_frames = 0
    
    def start_worker(self):
        """Start background worker thread for face processing."""
        self.running = True
        self.worker_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.worker_thread.start()
    
    def stop_worker(self):
        """Stop background worker thread."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
    
    def _process_loop(self):
        """Background processing loop."""
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=0.1)
            except Empty:
                continue
            
            results = self._recognize_faces(frame)
            try:
                self.result_queue.put_nowait(results)
            except:
                pass  # Queue full, skip
    
    def _recognize_faces(self, frame: np.ndarray) -> List[RecognitionResult]:
        """Recognize faces in a frame."""
        small_frame = resize_frame(frame, self.scale)
        rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        face_locations = face_recognition.face_locations(rgb_small)
        face_encodings = face_recognition.face_encodings(rgb_small, face_locations)
        
        results = []
        for encoding, location in zip(face_encodings, face_locations):
            name = "Unknown"
            confidence = 0.0
            
            if self.known_encodings:
                distances = face_recognition.face_distance(self.known_encodings, encoding)
                best_match_idx = np.argmin(distances)
                min_distance = distances[best_match_idx]
                
                confidence = 1.0 - min_distance
                
                if confidence >= self.confidence_threshold:
                    name = self.known_names[best_match_idx]
            
            results.append(RecognitionResult(
                name=name,
                confidence=confidence,
                location=location,
                timestamp=datetime.now()
            ))
        
        return results
    
    def process_frame(self, frame: np.ndarray) -> List[RecognitionResult]:
        """Process a frame (uses worker thread if available)."""
        self.frame_count += 1
        self.fps_frames += 1
        
        if self.frame_count % self.process_every_n_frames == 0:
            try:
                self.frame_queue.put_nowait(frame.copy())
            except:
                pass  # Queue full
        
        try:
            self.last_results = self.result_queue.get_nowait()
        except Empty:
            pass  # Use last results
        
        elapsed = time.time() - self.fps_start
        if elapsed >= 1.0:
            self.stats["avg_fps"] = self.fps_frames / elapsed
            self.fps_frames = 0
            self.fps_start = time.time()
        
        self.stats["frames_processed"] += 1
        self.stats["faces_detected"] += len(self.last_results)
        self.stats["faces_recognized"] += sum(1 for r in self.last_results if r.name != "Unknown")
        
        return self.last_results
    
    def draw_results(self, frame: np.ndarray, results: List[RecognitionResult]) -> np.ndarray:
        """Draw recognition results on frame."""
        for result in results:
            draw_face_box(frame, result.location, result.name, result.confidence, self.scale)
        return frame
    
    def get_stats(self) -> Dict:
        """Get current statistics."""
        return self.stats.copy()


def run_recognition(camera_index: int = 0, 
                    encodings_file: str = "models/encodings.pkl",
                    confidence_threshold: float = CONFIDENCE_THRESHOLD,
                    process_every_n: int = 2,
                    scale: float = PROCESSING_SCALE) -> None:
    """Run real-time face recognition.
    
    Args:
        camera_index: Camera device index
        encodings_file: Path to encodings pickle file
        confidence_threshold: Minimum confidence for recognition
        process_every_n: Process every N frames for speed
        scale: Frame resize scale for processing
    """
    encodings_data = load_encodings(Path(encodings_file))
    if encodings_data is None:
        print("Failed to load encodings. Run train_model.py first.")
        return
    
    recognizer = FaceRecognizer(
        encodings_data, 
        confidence_threshold=confidence_threshold,
        process_every_n_frames=process_every_n,
        scale=scale
    )
    recognizer.start_worker()
    
    cap = init_camera(camera_index)
    if cap is None:
        recognizer.stop_worker()
        return
    
    print("\n" + "="*60)
    print("Real-time Face Recognition")
    print("Press 'q' to quit, 's' to save snapshot")
    print("="*60 + "\n")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame")
                break
            
            frame = cv2.flip(frame, 1)
            
            results = recognizer.process_frame(frame)
            frame = recognizer.draw_results(frame, results)
            
            stats = recognizer.get_stats()
            info_lines = [
                f"FPS: {stats['avg_fps']:.1f}",
                f"Faces: {len(results)}",
                f"Threshold: {confidence_threshold:.2f}",
                f"Known people: {len(set(encodings_data.get('names', [])))}",
                "",
                "Controls: 'q'=Quit | 's'=Snapshot"
            ]
            draw_info_panel(frame, info_lines)
            
            cv2.imshow("Face Recognition Attendance", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"recognition_{timestamp}.jpg"
                cv2.imwrite(filename, frame)
                print(f"Snapshot saved: {filename}")
                
    finally:
        recognizer.stop_worker()
        release_camera(cap)
        print("\nRecognition stopped.")


def recognize_from_image(image_path: str,
                         encodings_file: str = "models/encodings.pkl",
                         confidence_threshold: float = CONFIDENCE_THRESHOLD) -> List[RecognitionResult]:
    """Recognize faces in a static image.
    
    Args:
        image_path: Path to image file
        encodings_file: Path to encodings pickle file
        confidence_threshold: Minimum confidence for recognition
        
    Returns:
        List of recognition results
    """
    encodings_data = load_encodings(Path(encodings_file))
    if encodings_data is None:
        return []
    
    image = face_recognition.load_image_file(image_path)
    rgb_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    recognizer = FaceRecognizer(encodings_data, confidence_threshold=confidence_threshold)
    results = recognizer._recognize_faces(rgb_image)
    
    for result in results:
        print(f"Found: {result.name} (confidence: {result.confidence:.2%})")
    
    return results


def main():
    """Main entry point for recognition."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Real-time face recognition")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--encodings", type=str, default="models/encodings.pkl",
                        help="Encodings file (default: models/encodings.pkl)")
    parser.add_argument("--threshold", type=float, default=CONFIDENCE_THRESHOLD,
                        help=f"Confidence threshold (default: {CONFIDENCE_THRESHOLD})")
    parser.add_argument("--skip-frames", type=int, default=2,
                        help="Process every N frames (default: 2)")
    parser.add_argument("--scale", type=float, default=PROCESSING_SCALE,
                        help=f"Processing scale (default: {PROCESSING_SCALE})")
    parser.add_argument("--image", type=str, help="Recognize from image file instead of webcam")
    args = parser.parse_args()
    
    if args.image:
        recognize_from_image(args.image, args.encodings, args.threshold)
    else:
        run_recognition(
            camera_index=args.camera,
            encodings_file=args.encodings,
            confidence_threshold=args.threshold,
            process_every_n=args.skip_frames,
            scale=args.scale
        )


if __name__ == "__main__":
    main()