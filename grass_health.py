import cv2
import numpy as np
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 0))
CAMERA_RESOLUTION = os.getenv("CAMERA_RESOLUTION", "640x480")
width, height = map(int, CAMERA_RESOLUTION.split("x"))

# Initialize camera
cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)


def analyze_grass_health(frame):
    """Returns a hydration score based on green pixel density."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    green_mask = cv2.inRange(hsv, (35, 40, 40), (85, 255, 255))
    green_ratio = np.sum(green_mask > 0) / (frame.shape[0] * frame.shape[1])
    score = round(green_ratio * 10, 2)  # Scale to 0â€“10
    return score


while True:
    ret, frame = cap.read()
    if not ret:
        print("Camera feed failed.")
        break

    score = analyze_grass_health(frame)
    cv2.putText(frame, f"Hydration Score: {score}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("Live Grass Feed", frame)

    key = cv2.waitKey(1)
    if key == ord("q"):
        break
    elif key == ord("s"):
        # Save snapshot
        filename = f"snapshot_{score}.jpg"
        cv2.imwrite(filename, frame)
        print(f"Snapshot saved: {filename}")

cap.release()
cv2.destroyAllWindows()