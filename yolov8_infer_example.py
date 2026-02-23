# yolov8_infer_example.py
from ultralytics import YOLO
import cv2
import numpy as np

# Load your trained YOLOv8 model
model = YOLO("best.pt")  # <-- change this to your actual .pt path

# Read a test image (or capture from camera)
frame = cv2.imread("test_image.jpg")  # change path to your test image

# Run inference
results = model(frame)[0]

# Initialize counters
h, w = frame.shape[:2]
areas = {"grass": 0.0, "water": 0.0, "dead_grass": 0.0}

# Count detected object areas
for box, cls in zip(results.boxes.xyxy.cpu().numpy(), results.boxes.cls.cpu().numpy()):
    x1, y1, x2, y2 = box[:4]
    area = max(0, (x2 - x1) * (y2 - y1))
    label = model.names[int(cls)]
    if label in areas:
        areas[label] += area

total_area = w * h
grass_frac = areas["grass"] / total_area

print(f"Grass coverage fraction: {grass_frac:.4f}")
