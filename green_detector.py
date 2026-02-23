# green_detector.py
import cv2
import numpy as np
from typing import Tuple

def pct_green_from_bgr_image(bgr_image: np.ndarray, debug_mask: bool=False) -> Tuple[float, np.ndarray]:
    """
    Compute fraction of pixels classified as 'green' using HSV thresholds.
    Returns (green_fraction [0..1], mask)
    """
    # Convert to HSV
    hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)

    # Default HSV thresholds for green (tweak these for your lawn)
    # H: ~35-85, S: >40, V: >40
    lower = np.array([30, 40, 40])
    upper = np.array([85, 255, 255])

    mask = cv2.inRange(hsv, lower, upper)

    # Optional morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    green_pixels = np.count_nonzero(mask)
    total_pixels = mask.size
    green_frac = green_pixels / total_pixels if total_pixels > 0 else 0.0

    return float(green_frac), mask

def hydration_need_from_green_frac(green_frac: float,
                                   dry_frac: float = 0.05,
                                   optimal_frac: float = 0.30,
                                   saturated_frac: float = 0.70) -> float:
    """
    Map green_frac to the 0-10 inverted hydration need scale:
      - 0 => very dry (needs more water),
      - 5 => optimal,
      - 10 => oversaturated (no water).
    Default breakpoints:
      * dry_frac: below this -> very dry
      * optimal_frac: around this -> normal
      * saturated_frac: at/above this -> oversaturated
    You should tune these fractions for your lawn and camera view.
    Returns float in [0, 10].
    """
    # Clamp
    gf = max(0.0, min(1.0, green_frac))

    # Piecewise mapping:
    if gf <= dry_frac:
        return 0.0
    if gf >= saturated_frac:
        return 10.0

    # Between dry_frac and saturated_frac -> map to 0..10 nonlinearly with optimal around optimal_frac -> 5
    # We'll use a two-segment linear mapping: dry_frac->optimal_frac => 0..5, optimal_frac->saturated_frac => 5..10
    if gf <= optimal_frac:
        # map dry_frac..optimal_frac -> 0..5
        return 5.0 * (gf - dry_frac) / max(1e-6, (optimal_frac - dry_frac))
    else:
        # map optimal_frac..saturated_frac -> 5..10
        return 5.0 + 5.0 * (gf - optimal_frac) / max(1e-6, (saturated_frac - optimal_frac))

def visualize_mask_on_image(bgr_image: np.ndarray, mask: np.ndarray, alpha: float=0.5) -> np.ndarray:
    """Overlay mask (green) onto original image for debug/preview."""
    overlay = bgr_image.copy()
    overlay[mask > 0] = (0, 255, 0)  # green overlay on masked pixels
    return cv2.addWeighted(overlay, alpha, bgr_image, 1 - alpha, 0)
