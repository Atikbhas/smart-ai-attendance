"""Training Module - Generate face encodings from dataset images.

Reads all images from dataset/, generates face encodings using
face_recognition library, and saves to encodings.pkl.
"""

import face_recognition
import cv2
from pathlib import Path
from typing import List, Tuple, Optional
import sys

from utils import (
    DATASET_DIR, list_people, get_image_paths, save_encodings,
    is_blurry, calculate_blur_score, logger
)


def process_person_images(person_name: str, min_face_size: int = 80,
                          blur_threshold: float = 100.0) -> Tuple[List, List, int, int]:
    """Process all images for a single person.
    
    Returns:
        Tuple of (encodings, names, valid_count, skipped_count)
    """
    image_paths = get_image_paths(person_name)
    encodings = []
    names = []
    valid = 0
    skipped = 0
    
    for img_path in image_paths:
        try:
            image = face_recognition.load_image_file(str(img_path))
            
            if is_blurry(image, blur_threshold):
                logger.warning(f"Skipping blurry image: {img_path.name} (blur={calculate_blur_score(image):.1f})")
                skipped += 1
                continue
            
            face_locations = face_recognition.face_locations(image)
            
            if len(face_locations) != 1:
                logger.warning(f"Skipping {img_path.name}: found {len(face_locations)} faces (expected 1)")
                skipped += 1
                continue
            
            top, right, bottom, left = face_locations[0]
            face_width = right - left
            face_height = bottom - top
            
            if face_width < min_face_size or face_height < min_face_size:
                logger.warning(f"Skipping {img_path.name}: face too small ({face_width}x{face_height})")
                skipped += 1
                continue
            
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if face_encodings:
                encodings.append(face_encodings[0])
                names.append(person_name)
                valid += 1
            else:
                logger.warning(f"Skipping {img_path.name}: could not generate encoding")
                skipped += 1
                
        except Exception as e:
            logger.error(f"Error processing {img_path.name}: {e}")
            skipped += 1
    
    return encodings, names, valid, skipped


def train_model(dataset_dir: Path = DATASET_DIR, 
                output_file: Optional[Path] = None,
                min_face_size: int = 80,
                blur_threshold: float = 100.0) -> bool:
    """Train face recognition model from dataset.
    
    Args:
        dataset_dir: Path to dataset directory
        output_file: Path to save encodings (default: models/encodings.pkl)
        min_face_size: Minimum face size in pixels
        blur_threshold: Blur threshold for Laplacian variance
        
    Returns:
        True if training successful, False otherwise
    """
    people = list_people()
    
    if not people:
        logger.error("No people found in dataset. Run capture_faces.py first.")
        return False
    
    print(f"\n{'='*60}")
    print(f"Training Face Recognition Model")
    print(f"Dataset: {dataset_dir}")
    print(f"People found: {len(people)}")
    print(f"{'='*60}\n")
    
    all_encodings = []
    all_names = []
    total_valid = 0
    total_skipped = 0
    
    for i, person in enumerate(people, 1):
        print(f"[{i}/{len(people)}] Processing {person}...")
        encodings, names, valid, skipped = process_person_images(
            person, min_face_size, blur_threshold
        )
        all_encodings.extend(encodings)
        all_names.extend(names)
        total_valid += valid
        total_skipped += skipped
        print(f"  Valid: {valid}, Skipped: {skipped}")
    
    if not all_encodings:
        logger.error("No valid encodings generated. Check your dataset.")
        return False
    
    encodings_data = {
        "encodings": all_encodings,
        "names": all_names,
        "num_people": len(set(all_names)),
        "total_encodings": len(all_encodings)
    }
    
    save_encodings(encodings_data, output_file)
    
    print(f"\n{'='*60}")
    print(f"Training Complete!")
    print(f"Total people: {encodings_data['num_people']}")
    print(f"Total encodings: {encodings_data['total_encodings']}")
    print(f"Skipped images: {total_skipped}")
    print(f"Encodings saved to: {output_file or 'models/encodings.pkl'}")
    print(f"{'='*60}\n")
    
    return True


def main():
    """Main entry point for training."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Train face recognition model")
    parser.add_argument("--dataset", type=str, default="dataset",
                        help="Dataset directory (default: dataset)")
    parser.add_argument("--output", type=str, default="models/encodings.pkl",
                        help="Output encodings file (default: models/encodings.pkl)")
    parser.add_argument("--min-face-size", type=int, default=80,
                        help="Minimum face size in pixels (default: 80)")
    parser.add_argument("--blur-threshold", type=float, default=100.0,
                        help="Blur threshold (default: 100.0)")
    args = parser.parse_args()
    
    success = train_model(
        dataset_dir=Path(args.dataset),
        output_file=Path(args.output),
        min_face_size=args.min_face_size,
        blur_threshold=args.blur_threshold
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()