import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# ðŸ”§ Load environment variables
load_dotenv()
RAG_PORT = int(os.getenv("RAG_PORT", 5052))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ðŸ“œ Logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("RAGServer")

# ðŸ§  Load model and build index
documents = [
    "Sprinkler zones should be adjusted based on sunlight exposure.",
    "Grass health can be monitored using NDVI analysis.",
    "Leaks often appear as dark patches in infrared snapshots.",
    "Voice commands can trigger zone overrides or analysis.",
    "Watering schedules should adapt to seasonal changes."
]

model = SentenceTransformer("all-MiniLM-L6-v2")
doc_embeddings = model.encode(documents)
index = faiss.IndexFlatL2(doc_embeddings.shape[1])
index.add(np.array(doc_embeddings))

# ðŸ” RAG query logic


def query_rag_system(query: str) -> dict:
    if query.lower() == "ping":
        return {"ok": True, "response": "pong"}
    try:
        query_vec = model.encode([query])
        D, I = index.search(np.array(query_vec), k=1)
        best_match = documents[I[0][0]]
        return {"ok": True, "response": best_match}
    except Exception as e:
        logger.error(f"RAG search error: {e}")
        return {"ok": False, "error": str(e)}


# ðŸ—ï¸ Initialize Flask app
app = Flask(__name__)
CORS(app)

# ðŸ©º Health check


@app.get("/ask")
def health_check():
    return jsonify({"ok": True, "message": "RAG server is alive"})

# ðŸ’¬ Query endpoint


@app.post("/ask")
def ask():
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({"ok": False, "error": "Missing 'query'"}), 400

    result = query_rag_system(query)
    return jsonify(result)


@app.get("/")
def index():
    return jsonify({
        "ok": True,
        "message": "Welcome to the RAG server",
        "endpoints": {
            "health": "/ask (GET)",
            "query": "/ask (POST)"
        }
    })
# ðŸš€ Startup banner


def print_banner():
    print(f"\nðŸ“¡ RAG Server running at http://127.0.0.1:{RAG_PORT}")
    print("ðŸ©º Health: GET /ask")
    print("ðŸ’¬ Query: POST /ask\n")


# ðŸ Run server
if __name__ == "__main__":
    print_banner()
    app.run(host="127.0.0.1", port=RAG_PORT, debug=False)