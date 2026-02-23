# voice_trainer.py  â€”  Push-to-talk (Spacebar) + local knowledge capture + camera labels
# Hold SPACE to record; release to transcribe & save (question/answer/fact/command).
# Commands you can say: "snapshot leak", "label oversaturated", etc.

import os
import re
import json
import time
import threading
import queue
import sys
import requests
from pathlib import Path
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import pyttsx3
from pynput import keyboard

# ================== Config ==================
DATA_DIR = Path("data/knowledge")
DATA_DIR.mkdir(parents=True, exist_ok=True)
KB_PATH = DATA_DIR / "knowledge.jsonl"

# camera_server.py base URL
CAMERA_BASE = os.getenv("II_CAMERA_BASE", "http://127.0.0.1:5051")
# "base" | "small" | "medium" | etc.
WHISPER_MODEL = os.getenv("II_WHISPER", "base")
SAMPLE_RATE = 16000
CHANNELS = 1
MAX_TALK_SECONDS = 30         # hard cap per utterance
SILENCE_TAIL_SECONDS = 0.6    # trim trailing silence when releasing Space
# ============================================

# ---------- Audio setup (device picker) ----------


def pick_input_device():
    pref = os.getenv("II_INPUT_DEVICE", "").strip().lower()
    try:
        devices = sd.query_devices()
    except Exception as e:
        print("âŒ Could not query audio devices:", e)
        print("â€¢ Check Windows microphone privacy settings (Microphone access for Desktop apps).")
        sys.exit(1)

    # Default input if set and valid
    default_in = None
    try:
        default_in = sd.default.device[0] if isinstance(
            sd.default.device, (list, tuple)) else sd.default.device
    except Exception:
        pass

    if not pref and isinstance(default_in, int) and default_in >= 0:
        return default_in

    # Match by exact index or substring of device name
    for i, d in enumerate(devices):
        name = f"{d.get('name','')}".lower()
        if pref and (pref == str(i) or pref in name):
            return i

    # First device with input channels
    for i, d in enumerate(devices):
        max_in = d.get("max_input_channels", d.get("maxInputChannels", 0))
        if max_in and max_in > 0:
            return i

    print("âŒ No input (microphone) device found.")
    sys.exit(1)


INPUT_DEVICE = pick_input_device()
print("ðŸŽ¤ Using input device:", INPUT_DEVICE,
      sd.query_devices()[INPUT_DEVICE]["name"])

# ---------- STT, embeddings, DB, TTS ----------
print("ðŸ”¡ Loading Whisper model:", WHISPER_MODEL)
# uses CPU by default; set env for GPU if you want
asr = WhisperModel(WHISPER_MODEL)

embedder = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path=str(DATA_DIR / "chroma"))
collection = chroma_client.get_or_create_collection(
    name="ii_kb", metadata={"hnsw:space": "cosine"})

tts = pyttsx3.init()


def speak(text: str):
    try:
        tts.say(text)
        tts.runAndWait()
    except Exception:
        pass

# ---------- Knowledge helpers ----------


def intent_of(text: str):
    lower = text.lower().strip()

    # Camera commands (dataset labeling while you talk)
    m = re.match(r"(snapshot|label)\s+([a-zA-Z0-9_\-]+)", lower)
    if m:
        return ("command", {"action": m.group(1), "label": m.group(2)})

    if lower.endswith("?") or lower.startswith(("what", "why", "how", "when", "where", "who")):
        return ("question", {})
    if lower.startswith(("answer:", "ans:", "the answer is")):
        return ("answer", {})
    if lower.startswith(("fact:", "note:", "remember that", "stat:", "statement:")) or "remember that" in lower:
        return ("fact", {})
    if re.search(r"\d", lower):  # numbers often indicate stats
        return ("fact", {})
    return ("fact", {})  # default to storing declarative knowledge


def store_knowledge(entry):
    KB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with KB_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    doc_id = f"{entry['timestamp']}_{entry['type']}_{hash(entry['text'])%10**8}"
    collection.upsert(ids=[doc_id], documents=[
                      entry["text"]], metadatas=[{"type": entry["type"]}])


def do_camera_command(cmd):
    try:
        label = cmd["label"]
        r = requests.get(f"{CAMERA_BASE}/snapshot",
                         params={"label": label}, timeout=5)
        if r.ok:
            print("ðŸ“¸ Snapshot saved:", r.json().get("path"))
            speak(f"Saved {label} snapshot.")
        else:
            print("Snapshot error:", r.text)
            speak("Snapshot failed.")
    except Exception as e:
        print("Camera command error:", e)
        speak("Could not reach camera.")


# ---------- Recording: push-to-talk with Space ----------
recording = threading.Event()
audio_buf = []
stream = None
buf_lock = threading.Lock()


def audio_callback(indata, frames, time_info, status):
    if status:
        print("Audio status:", status)
    with buf_lock:
        audio_buf.append(indata.copy())


def start_recording():
    global stream, audio_buf
    with buf_lock:
        audio_buf = []
    # Use ~200ms blocks
    blocksize = int(0.2 * SAMPLE_RATE)  # 3200 at 16kHz
    stream = sd.InputStream(samplerate=SAMPLE_RATE,
                            channels=CHANNELS,
                            dtype='float32',
                            callback=audio_callback,
                            blocksize=blocksize,
                            device=INPUT_DEVICE)
    stream.start()
    recording.set()
    print("ðŸŽ™ï¸ Recordingâ€¦ (hold Space)")


def stop_recording_and_process():
    global stream
    if stream:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
    recording.clear()

    # Gather audio
    with buf_lock:
        if not audio_buf:
            print("â€¦no audio captured.")
            return
        data = np.concatenate(audio_buf, axis=0)[:, 0]  # mono float32

    # Trim tail silence (simple fixed tail)
    tail = int(SILENCE_TAIL_SECONDS * SAMPLE_RATE)
    if len(data) > tail:
        data = data[:-tail]

    # Cap length
    max_len = int(MAX_TALK_SECONDS * SAMPLE_RATE)
    data = data[:max_len]

    # Transcribe
    print("ðŸ§  Transcribingâ€¦")
    segments, _ = asr.transcribe(data, language="en")
    text = " ".join(s.text.strip() for s in segments if s.text).strip()
    if not text:
        print("â€¦nothing recognized.")
        speak("I didn't catch that.")
        return

    print(f"ðŸ‘‚ Heard: {text}")
    typ, extra = intent_of(text)
    ts = time.time()
    entry = {"timestamp": ts, "type": typ, "text": text}

    if typ == "command":
        do_camera_command(extra)
        return

    store_knowledge(entry)
    speak(f"Captured {typ}.")


def on_press(key):
    try:
        if key == keyboard.Key.space and not recording.is_set():
            start_recording()
    except Exception:
        pass


def on_release(key):
    try:
        if key == keyboard.Key.space and recording.is_set():
            print("ðŸ›‘ Released Space â€” processingâ€¦")
            stop_recording_and_process()
    except Exception:
        pass


def main():
    print("ðŸŸ¢ Push-to-talk ready. Hold SPACE to speak; release to save.")
    print("   Commands: say â€œsnapshot leakâ€ or â€œlabel oversaturatedâ€.")
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()