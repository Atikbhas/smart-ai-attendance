"""Face Capture Module - Capture face images for training.

Captures 50-100 clear face images per person with live preview,
blur detection, and single-face validation.
"""

import cv2
import face_recognition
import sys
from pathlib import Path

from utils import (
    ensure_directories, get_person_dir, count_images, init_camera,
    release_camera, is_blurry, calculate_blur_score, draw_progress_bar,
    draw_info_panel, CAPTURE_COUNT, MIN_FACE_SIZE, BLUR_THRESHOLD
)


def capture_faces(person_name: str, target_count: int = CAPTURE_COUNT, 
                  camera_index: int = 0) -> int:
    """Capture face images for a person.
    
    Args:
        person_name: Name of the person to capture faces for
        target_count: Number of images to capture (default 50)
        camera_index: Camera device index
        
    Returns:
        Number of images successfully captured
    """
    ensure_directories()
    person_dir = get_person_dir(person_name)
    person_dir.mkdir(parents=True, exist_ok=True)
    
    existing_count = count_images(person_name)
    print(f"\n{'='*60}")
    print(f"Face Capture for: {person_name}")
    print(f"Existing images: {existing_count}")
    print(f"Target: {target_count} new images")
    print(f"{'='*60}\n")
    
    if existing_count >= target_count:
        print(f"Already have {existing_count} images. Skipping capture.")
        return existing_count
    
    cap = init_camera(camera_index)
    if cap is None:
        return existing_count
    
    captured = 0
    needed = target_count - existing_count
    
    print("Controls:")
    print("  SPACE - Capture image (auto-captures when face detected)")
    print("  'q' - Quit early")
    print("  's' - Skip current frame")
    print()
    
    try:
        while captured < needed:
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame")
                break
            
            frame = cv2.flip(frame, 1)
            display_frame = frame.copy()
            
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            
            face_detected = len(face_locations) == 1
            face_too_many = len(face_locations) > 1
            
            if face_detected:
                top, right, bottom, left = face_locations[0]
                face_width = right - left
                face_height = bottom - top
                
                face_img = frame[top:bottom, left:right]
                blur_score = calculate_blur_score(face_img)
                is_clear = not is_blurry(face_img) and face_width >= MIN_FACE_SIZE and face_height >= MIN_FACE_SIZE
                
                color = (0, 255, 0) if is_clear else (0, 165, 255)
                cv2.rectangle(display_frame, (left, top), (right, bottom), color, 2)
                
                status = "CLEAR - Press SPACE" if is_clear else "BLURRY/SMALL - Adjust"
                cv2.putText(display_frame, status, (left, top - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                cv2.putText(display_frame, f"Blur: {blur_score:.1f}", (left, bottom + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                
                if is_clear:
                    cv2.putText(display_frame, "READY", (left, top - 35),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            elif face_too_many:
                cv2.putText(display_frame, "MULTIPLE FACES - Show only one face",
                           (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            else:
                cv2.putText(display_frame, "NO FACE DETECTED - Position face in frame",
                           (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
            
            progress = (existing_count + captured) / target_count
            draw_progress_bar(display_frame, progress)
            
            info_lines = [
                f"Person: {person_name}",
                f"Captured: {captured}/{needed}",
                f"Total: {existing_count + captured}/{target_count}",
                f"Blur threshold: {BLUR_THRESHOLD}",
                "",
                "SPACE: Capture | 'q': Quit | 's': Skip"
            ]
            draw_info_panel(display_frame, info_lines)
            
            cv2.imshow(f"Face Capture - {person_name}", display_frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("\nCapture cancelled by user.")
                break
            elif key == ord(' '):
                if face_detected and is_clear:
                    img_name = f"{person_name.replace(' ', '_')}_{existing_count + captured + 1:03d}.jpg"
                    img_path = person_dir / img_name
                    cv2.imwrite(str(img_path), frame)
                    captured += 1
                    print(f"Captured {captured}/{needed}: {img_name}")
                elif face_too_many:
                    print("Multiple faces detected. Please show only one face.")
                elif not face_detected:
                    print("No face detected. Please position your face in the frame.")
                else:
                    print("Image rejected: blurry or too small. Try again.")
            elif key == ord('s'):
                continue
                
    finally:
        release_camera(cap)
    
    print(f"\nCapture complete. Total images for {person_name}: {existing_count + captured}")
    return existing_count + captured


def capture_multiple_people(names: list, target_count: int = CAPTURE_COUNT, 
                            camera_index: int = 0) -> dict:
    """Capture faces for multiple people sequentially.
    
    Args:
        names: List of person names
        target_count: Images per person
        camera_index: Camera device index
        
    Returns:
        Dictionary mapping names to captured counts
    """
    results = {}
    for name in names:
        print(f"\n{'#'*60}")
        print(f"# Capturing for: {name}")
        print(f"{'#'*60}")
        count = capture_faces(name, target_count, camera_index)
        results[name] = count
        if count < target_count:
            print(f"Warning: Only captured {count}/{target_count} images for {name}")
    return results


def main():
    """Main entry point for face capture."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Capture face images for training")
    parser.add_argument("names", nargs="+", help="Person name(s) to capture")
    parser.add_argument("-c", "--count", type=int, default=CAPTURE_COUNT,
                        help=f"Number of images per person (default: {CAPTURE_COUNT})")
    parser.add_argument("--camera", type=int, default=0,
                        help="Camera index (default: 0)")
    args = parser.parse_args()
    
    if len(args.names) == 1:
        capture_faces(args.names[0], args.count, args.camera)
    else:
        capture_multiple_people(args.names, args.count, args.camera)


if __name__ == "__main__":
    main()