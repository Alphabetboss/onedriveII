# camera_analyzer.py

import cv2
import numpy as np

class CameraAnalyzer:
    def __init__(self):
        # Define HSV ranges for green, yellow, brown
        self.color_ranges = {
            "green": ((35, 40, 40), (85, 255, 255)),
            "yellow": ((20, 100, 100), (35, 255, 255)),
            "brown": ((10, 100, 20), (20, 255, 200))
        }

    def analyze_image(self, image_path):
        image = cv2.imread(image_path)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        total_pixels = image.shape[0] * image.shape[1]

        results = {}
        for color, (lower, upper) in self.color_ranges.items():
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            count = cv2.countNonZero(mask)
            results[color] = round((count / total_pixels) * 100, 2)

        return results["green"], results["yellow"], results["brown"]