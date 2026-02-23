# check_labels.py
import os
import glob

# point this at the *root* that contains your image folders
DATA_ROOT = r"C:\Users\alpha\OneDrive\Desktop\IngeniousIrrigation\datasets"

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def is_image(p):
    return os.path.splitext(p)[1].lower() in IMG_EXTS


def main():
    images = []
    for root, _, files in os.walk(DATA_ROOT):
        for f in files:
            if is_image(f):
                images.append(os.path.join(root, f))

    if not images:
        print("No images found under", DATA_ROOT)
        return

    missing = []
    for img in images:
        base, _ = os.path.splitext(img)
        # YOLO expects a same-named .txt in a parallel 'labels' folder OR same folder
        # Weâ€™ll check both patterns:
        txt_same_folder = base + ".txt"
        # also check if you already use images/xxx.jpg -> labels/xxx.txt layout
        parts = base.split(os.sep)
        if "images" in parts:
            i = parts.index("images")
            lbl_base = os.sep.join(parts[:i] + ["labels"] + parts[i+1:])
            txt_labels_folder = lbl_base + ".txt"
        else:
            txt_labels_folder = None

        exists = os.path.exists(txt_same_folder) or (
            txt_labels_folder and os.path.exists(txt_labels_folder))
        if not exists:
            missing.append(img)

    print(f"Total images: {len(images)}")
    print(f"Images missing labels: {len(missing)}")

    # Show a few examples so you can see where they are
    for p in missing[:20]:
        print("MISSING:", p)


if __name__ == "__main__":
    main()