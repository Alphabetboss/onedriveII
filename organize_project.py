import os
import shutil
import requests

ROOT = os.path.abspath(os.path.dirname(__file__))

FOLDERS = {
    '.glb': 'static/models/',
    '.css': 'static/css/',
    '.js': 'static/js/',
    '.html': 'templates/',
    '.png': 'static/assets/',
    '.jpg': 'static/assets/',
    '.jpeg': 'static/assets/',
}

# Create folders
for folder in set(FOLDERS.values()):
    os.makedirs(os.path.join(ROOT, folder), exist_ok=True)

# ðŸ”½ List of files to download
DOWNLOADS = [
    "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/AnimatedCube/glTF/AnimatedCube.glb",
    "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/Fox/glTF/Fox.glb"
]
    # Add more URLs here

def download_file(url):
    filename = url.split("/")[-1]
    ext = os.path.splitext(filename)[1].lower()
    if ext not in FOLDERS:
        print(f"Skipping unsupported file: {filename}")
        return

    dest_folder = os.path.join(ROOT, FOLDERS[ext])
    dest_path = os.path.join(dest_folder, filename)

    if os.path.exists(dest_path):
        print(f"Already exists: {filename}")
        return

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded: {filename} â†’ {FOLDERS[ext]}")
    except Exception as e:
        print(f"Failed to download {filename}: {e}")

# ðŸ” Download assets
for url in DOWNLOADS:
    download_file(url)

# ðŸ”„ Organize local files
for dirpath, _, filenames in os.walk(ROOT):
    for file in filenames:
        ext = os.path.splitext(file)[1].lower()
        if ext in FOLDERS:
            src = os.path.join(dirpath, file)
            dst = os.path.join(ROOT, FOLDERS[ext], file)
            if os.path.abspath(src) != os.path.abspath(dst):
                try:
                    shutil.move(src, dst)
                    print(f"Moved: {file} â†’ {FOLDERS[ext]}")
                except Exception as e:
                    print(f"Failed to move {file}: {e}")