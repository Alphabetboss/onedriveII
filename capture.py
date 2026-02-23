import cv2
import os

def capture_image(save_path='static/captured.jpg'):
    # ðŸ“ Ensure static folder exists
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # ðŸŽ¥ Open default camera
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("âŒ Failed to open camera")
        return False

    ret, frame = cap.read()
    cap.release()

    if ret:
        cv2.imwrite(save_path, frame)
        print(f"âœ… Image saved to {save_path}")
        return True
    else:
        print("âŒ Failed to capture frame")
        return False