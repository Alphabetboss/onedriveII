# train_api.py â€” pair a spoken/typed fact with a labeled snapshot
from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
import time
import json
import requests
import csv

import chromadb
from sentence_transformers import SentenceTransformer

DATA_DIR = Path("data/knowledge")
DATA_DIR.mkdir(parents=True, exist_ok=True)
KB_PATH = DATA_DIR / "knowledge.jsonl"
PAIR_DIR = Path("data/training")
PAIR_DIR.mkdir(parents=True, exist_ok=True)
PAIR_FILE = PAIR_DIR / "pairs.csv"

CAMERA_BASE = "http://127.0.0.1:5051"

embedder = SentenceTransformer("all-MiniLM-L6-v2")
chroma = chromadb.PersistentClient(path=str(DATA_DIR / "chroma"))
collection = chroma.get_or_create_collection(
    name="ii_kb", metadata={"hnsw:space": "cosine"})

app = Flask(__name__)
CORS(app)


def store_text(text: str, typ: str = "fact"):
    entry = {"timestamp": time.time(), "type": typ, "text": text}
    with KB_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    doc_id = f"{entry['timestamp']}_{typ}"
    collection.upsert(ids=[doc_id], documents=[text],
                      metadatas=[{"type": typ}])
    return entry


def take_snapshot(label: str):
    r = requests.get(f"{CAMERA_BASE}/snapshot",
                     params={"label": label}, timeout=8)
    r.raise_for_status()
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(j.get("error", "snapshot failed"))
    return j["path"]


@app.post("/pair")
def pair():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    label = (payload.get("label") or "unlabeled").strip()
    if not text:
        return jsonify({"ok": False, "error": "empty text"}), 400

    # 1) store the text in KB + vector DB
    entry = store_text(text, "fact")

    # 2) snapshot from camera server
    try:
        path = take_snapshot(label)
    except Exception as e:
        return jsonify({"ok": False, "error": f"snapshot: {e}"}), 500

    # 3) append a CSV row safely (handles quotes/commas/newlines)
    new_file = not PAIR_FILE.exists()
    with PAIR_FILE.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "type", "text", "label", "snapshot_path"])
        w.writerow([entry["timestamp"], "fact", text, label, path])

    return jsonify({"ok": True, "snapshot_path": path})


@app.get("/")
def home():
    return "train_api up â€” POST /pair {text, label}"


if __name__ == "__main__":
    app.run(port=5055, debug=True)