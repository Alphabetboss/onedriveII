# capture_and_detect.py
import cv2
import argparse
import time
from green_detector import pct_green_from_bgr_image, hydration_need_from_green_frac, visualize_mask_on_image

def capture_frame(device_index=0, width=None, height=None, timeout=5.0):
    cap = cv2.VideoCapture(device_index, cv2.CAP_ANY)
    start = time.time()
    if width: cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height: cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    while True:
        ok, frame = cap.read()
        if ok:
            cap.release()
            return frame
        if time.time() - start > timeout:
            cap.release()
            raise RuntimeError("Camera capture timeout - no frame obtained")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=int, default=0, help="OpenCV device index")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--debug-out", type=str, default=None, help="If set, write debug image overlay")
    args = parser.parse_args()

    frame = capture_frame(args.device, args.width, args.height)
    green_frac, mask = pct_green_from_bgr_image(frame)
    score = hydration_need_from_green_frac(green_frac)

    print(f"green_fraction={green_frac:.4f}, hydration_need={score:.2f} (0=dry -> 10=oversat)")

    if args.debug_out:
        vis = visualize_mask_on_image(frame, mask)
        cv2.imwrite(args.debug_out, vis)
        print(f"debug image written to {args.debug_out}")

if __name__ == "__main__":
    main()
