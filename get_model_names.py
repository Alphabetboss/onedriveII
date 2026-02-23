import os
try:
    from ultralytics import YOLO
except Exception as e:
    print("ULTRALYTICS IMPORT FAILED:", e)
    raise SystemExit(1)

model_path = os.path.join("static","models","hydration_model.pt")
if not os.path.exists(model_path):
    print("MODEL NOT FOUND:", model_path)
    raise SystemExit(1)

try:
    m = YOLO(model_path)
    # common places for names
    names = getattr(m, "names", None) or getattr(getattr(m, "model", None), "names", None)
    if names is None:
        print("No class names found in model (names=None).")
    else:
        print("CLASS NAMES (type {}):".format(type(names).__name__))
        print(names)
except Exception as e:
    print("ERROR loading model or reading names:", e)