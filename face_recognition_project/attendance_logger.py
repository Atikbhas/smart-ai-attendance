"""Attendance Logger - Example integration for attendance tracking.

Logs recognized faces to CSV with timestamp, prevents duplicate entries
per person per day. Can be extended for database integration.
"""

import csv
import threading
from datetime import datetime, date
from pathlib import Path
from typing import Set, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class AttendanceRecord:
    """Single attendance record."""
    name: str
    date: str
    time: str
    confidence: float


class AttendanceLogger:
    """Thread-safe attendance logger with CSV storage."""
    
    def __init__(self, csv_path: str = "attendance.csv", 
                 min_confidence: float = 0.6,
                 cooldown_seconds: int = 30):
        self.csv_path = Path(csv_path)
        self.min_confidence = min_confidence
        self.cooldown_seconds = cooldown_seconds
        
        self._lock = threading.Lock()
        self._logged_today: Set[Tuple[str, str]] = set()
        self._last_log_time: dict = {}
        
        self._ensure_csv_exists()
        self._load_existing()
    
    def _ensure_csv_exists(self):
        """Create CSV with headers if it doesn't exist."""
        if not self.csv_path.exists():
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Name", "Date", "Time", "Confidence"])
    
    def _load_existing(self):
        """Load existing records to prevent duplicates."""
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                for row in reader:
                    if len(row) >= 2:
                        self._logged_today.add((row[0], row[1]))
        except FileNotFoundError:
            pass
    
    def log(self, name: str, confidence: float) -> bool:
        """Log attendance for a person.
        
        Args:
            name: Person's name
            confidence: Recognition confidence (0-1)
            
        Returns:
            True if logged, False if duplicate or below threshold
        """
        if name == "Unknown" or confidence < self.min_confidence:
            return False
        
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        key = (name, today)
        
        with self._lock:
            if key in self._logged_today:
                return False
            
            last_time = self._last_log_time.get(name)
            if last_time:
                elapsed = (now - last_time).total_seconds()
                if elapsed < self.cooldown_seconds:
                    return False
            
            try:
                with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([name, today, time_str, f"{confidence:.4f}"])
                
                self._logged_today.add(key)
                self._last_log_time[name] = now
                logger.info(f"Attendance logged: {name} at {time_str} (conf: {confidence:.2%})")
                return True
            except Exception as e:
                logger.error(f"Failed to log attendance: {e}")
                return False
    
    def get_today_attendance(self) -> list:
        """Get all attendance records for today."""
        today = date.today().strftime("%Y-%m-%d")
        records = []
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('Date') == today:
                        records.append(AttendanceRecord(
                            name=row['Name'],
                            date=row['Date'],
                            time=row['Time'],
                            confidence=float(row.get('Confidence', 0))
                        ))
        except FileNotFoundError:
            pass
        return records
    
    def get_all_attendance(self) -> list:
        """Get all attendance records."""
        records = []
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(AttendanceRecord(
                        name=row['Name'],
                        date=row['Date'],
                        time=row['Time'],
                        confidence=float(row.get('Confidence', 0))
                    ))
        except FileNotFoundError:
            pass
        return records
    
    def export_daily_report(self, report_date: str = None) -> str:
        """Export daily attendance report."""
        if report_date is None:
            report_date = date.today().strftime("%Y-%m-%d")
        
        report_path = Path(f"attendance_report_{report_date}.csv")
        records = [r for r in self.get_all_attendance() if r.date == report_date]
        
        with open(report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Date", "Time", "Confidence"])
            for r in records:
                writer.writerow([r.name, r.date, r.time, r.confidence])
        
        return str(report_path)


class AttendanceRecognizer:
    """Face recognizer with integrated attendance logging."""
    
    def __init__(self, encodings_data: dict, 
                 attendance_logger: AttendanceLogger,
                 confidence_threshold: float = 0.6,
                 process_every_n_frames: int = 2,
                 scale: float = 0.25):
        from recognize import FaceRecognizer
        self.recognizer = FaceRecognizer(
            encodings_data,
            confidence_threshold=confidence_threshold,
            process_every_n_frames=process_every_n_frames,
            scale=scale
        )
        self.attendance_logger = attendance_logger
        self.recognizer.start_worker()
    
    def process_frame(self, frame):
        """Process frame and log attendance."""
        results = self.recognizer.process_frame(frame)
        for result in results:
            self.attendance_logger.log(result.name, result.confidence)
        return results
    
    def draw_results(self, frame, results):
        """Draw results on frame."""
        return self.recognizer.draw_results(frame, results)
    
    def stop(self):
        """Stop the recognizer."""
        self.recognizer.stop_worker()


def main():
    """Demo: Run recognition with attendance logging."""
    from utils import load_encodings, init_camera, release_camera, draw_info_panel
    import cv2
    
    encodings_data = load_encodings()
    if not encodings_data:
        print("No encodings found. Run train_model.py first.")
        return
    
    attendance_logger = AttendanceLogger("attendance.csv", min_confidence=0.6)
    recognizer = AttendanceRecognizer(encodings_data, attendance_logger)
    
    cap = init_camera()
    if not cap:
        return
    
    print("\nAttendance Recognition System")
    print("Press 'q' to quit, 'r' to show today's report")
    print("="*50)
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame = cv2.flip(frame, 1)
            results = recognizer.process_frame(frame)
            frame = recognizer.draw_results(frame, results)
            
            today_records = attendance_logger.get_today_attendance()
            info_lines = [
                f"FPS: {recognizer.recognizer.get_stats()['avg_fps']:.1f}",
                f"Faces: {len(results)}",
                f"Today's attendance: {len(today_records)}",
                "",
                "Controls: 'q'=Quit | 'r'=Report"
            ]
            draw_info_panel(frame, info_lines)
            
            cv2.imshow("Attendance System", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                print("\n--- Today's Attendance ---")
                for record in today_records:
                    print(f"  {record.time} - {record.name} ({record.confidence:.2%})")
                print("--------------------------\n")
    finally:
        recognizer.stop()
        release_camera(cap)
    
    print("\nFinal attendance report:")
    for record in attendance_logger.get_today_attendance():
        print(f"  {record.time} - {record.name} ({record.confidence:.2%})")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()