# teach_api.py â€” persist typed facts into your KB (JSONL + Chroma)
from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
import time
import json
import chromadb
from sentence_transformers import SentenceTransformer

DATA_DIR = Path("data/knowledge")
DATA_DIR.mkdir(parents=True, exist_ok=True)
KB_PATH = DATA_DIR / "knowledge.jsonl"

# Embeddings + Chroma (persistent)
embedder = SentenceTransformer("all-MiniLM-L6-v2")
chroma = chromadb.PersistentClient(path=str(DATA_DIR / "chroma"))
collection = chroma.get_or_create_collection(
    name="ii_kb", metadata={"hnsw:space": "cosine"})

app = Flask(__name__)
CORS(app)  # allow requests from http://127.0.0.1:8080, 5050, etc.


def store(text: str, typ: str = "fact"):
    entry = {"timestamp": time.time(), "type": typ, "text": text}
    KB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with KB_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    doc_id = f"{entry['timestamp']}_{typ}"
    collection.upsert(ids=[doc_id], documents=[text],
                      metadatas=[{"type": typ}])


@app.post("/teach")
def teach():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    typ = (payload.get("type") or "fact").strip().lower()
    if not text:
        return jsonify({"ok": False, "error": "empty"}), 400
    store(text, typ)
    return jsonify({"ok": True})


@app.post("/teach_batch")
def teach_batch():
    payload = request.get_json(silent=True) or {}
    items = payload.get("items") or []
    if not items:
        return jsonify({"ok": False, "error": "no items"}), 400
    for it in items:
        text = (it.get("text") or "").strip()
        typ = (it.get("type") or "fact").strip().lower()
        if text:
            store(text, typ)
    return jsonify({"ok": True, "count": len(items)})


@app.get("/")
def home():
    return "teach_api up"


if __name__ == "__main__":
    app.run(port=5054, debug=True)