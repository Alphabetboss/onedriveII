# camera_util.py â€” returns a latest image path if present
from __future__ import annotations
from pathlib import Path
from typing import Optional

CAMERA_DIR = Path(__file__).parent / 'camera'

def latest_image() -> Optional[str]:
    if not CAMERA_DIR.exists(): return None
    imgs = sorted([p for p in CAMERA_DIR.iterdir() if p.suffix.lower() in {'.jpg','.jpeg','.png'}], reverse=True)
    return str(imgs[0]) if imgs else None