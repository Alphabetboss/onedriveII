# astra_offline.py (resampling via integer decimation -> fixed for 96k device)
# Offline assistant "Astra": captures at device rate, downsamples to MODEL_SAMPLE_RATE (16000)
# and feeds Vosk. Requires numpy (you already have it).

import os
import queue
import time
import json
import sounddevice as sd
import numpy as np
from pathlib import Path

# ASR (Vosk)
from vosk import Model, KaldiRecognizer

# TTS
import pyttsx3

# Local LLM hook (optional)
try:
    from llama_cpp import Llama
    LLM_AVAILABLE = True
except Exception:
    LLM_AVAILABLE = False

# ---------------- CONFIG ----------------
DEVICE_INDEX = 15  # your mic
MODEL_SAMPLE_RATE = 16000   # Vosk/Kaldi model sample rate (do NOT change for the model)
DEFAULT_CHANNELS = 1
VOSK_MODEL_PATH = r"C:\models\vosk-model"
LLM_MODEL_PATH = r"C:\models\ggml-model.bin"
# ----------------------------------------

print("sounddevice version:", sd.__version__)
# list devices quickly
try:
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        print(f"  {i:3d}: {dev['name']!r}  (max_in: {dev.get('max_input_channels',0)})")
except Exception as e:
    print("Could not list audio devices:", e)

# get device info
try:
    if DEVICE_INDEX is None:
        dev_info = sd.query_devices(kind='input')
    else:
        dev_info = sd.query_devices(DEVICE_INDEX)
    device_samplerate = int(dev_info.get('default_samplerate', MODEL_SAMPLE_RATE))
    device_max_in = int(dev_info.get('max_input_channels', DEFAULT_CHANNELS))
    print(f"\nUsing device index {DEVICE_INDEX if DEVICE_INDEX is not None else '(default)'}: {dev_info['name']}")
    print(f"Device default samplerate: {device_samplerate}, max_input_channels: {device_max_in}\n")
except Exception as e:
    print("Could not query device info, falling back to defaults:", e)
    device_samplerate = MODEL_SAMPLE_RATE
    device_max_in = DEFAULT_CHANNELS

# compute decimation factor (integer) if possible
if device_samplerate % MODEL_SAMPLE_RATE == 0:
    decimation = device_samplerate // MODEL_SAMPLE_RATE
    print(f"Decimation factor: {decimation} (device {device_samplerate} -> model {MODEL_SAMPLE_RATE})")
else:
    decimation = None
    print(f"WARNING: device samplerate {device_samplerate} is NOT an integer multiple of model rate {MODEL_SAMPLE_RATE}.")
    print("The script will attempt a crude fallback; results may be poor. Consider using a device with sample rate multiple of 16000.")

SAMPLE_RATE = device_samplerate
CHANNELS = 1  # keep mono for ASR

# Initialize Vosk
vosk_model = None
recognizer = None
if not os.path.exists(VOSK_MODEL_PATH):
    print("Warning: VOSK model path not found:", VOSK_MODEL_PATH)
else:
    try:
        vosk_model = Model(VOSK_MODEL_PATH)
        # always create recognizer for MODEL_SAMPLE_RATE (we will feed it downsampled audio)
        recognizer = KaldiRecognizer(vosk_model, MODEL_SAMPLE_RATE)
        print("Vosk recognizer initialized for model sample rate:", MODEL_SAMPLE_RATE)
    except Exception as e:
        print("Failed to initialize Vosk model/recognizer:", e)
        recognizer = None

# TTS
tts = pyttsx3.init()
tts.setProperty("rate", 160)

# LLM (optional)
llm = None
if LLM_AVAILABLE:
    if not os.path.exists(LLM_MODEL_PATH):
        print("LLM model path not found; disabling LLM.")
        LLM_AVAILABLE = False
    else:
        try:
            llm = Llama(model_path=LLM_MODEL_PATH)
        except Exception as e:
            print("LLM init error:", e)
            LLM_AVAILABLE = False

q = queue.Queue()

def audio_callback(indata, frames, time_info, status):
    if status:
        print("Audio status:", status)
    # indata is memoryview-like; convert to bytes
    q.put(bytes(indata))

def downsample_int16_bytes(b: bytes, factor: int) -> bytes:
    """
    Convert raw int16 bytes -> int16 numpy -> take every factor'th sample -> return bytes.
    Assumes little-endian int16 PCM.
    """
    if factor is None or factor == 1:
        return b
    arr = np.frombuffer(b, dtype=np.int16)
    if arr.size == 0:
        return b
    # if multiple channels (interleaved), take first channel
    if CHANNELS > 1:
        # reshape to (n_frames, channels) then select channel 0
        try:
            arr = arr.reshape(-1, CHANNELS)[:, 0]
        except Exception:
            # fallback: just decimate raw array
            pass
    dec = arr[::factor]
    return dec.tobytes()

def record_and_transcribe(timeout=6):
    """Capture audio at device SAMPLE_RATE, downsample to MODEL_SAMPLE_RATE, feed Vosk."""
    if recognizer is None:
        print("ASR recognizer not available (Vosk missing or failed to init).")
        return ""

    print("Listening... (speak now)")
    recognizer.Reset()
    start = time.time()
    try:
        with sd.RawInputStream(samplerate=SAMPLE_RATE,
                               blocksize=1024,
                               dtype='int16',
                               channels=CHANNELS,
                               callback=audio_callback,
                               device=DEVICE_INDEX):
            while True:
                try:
                    data = q.get(timeout=timeout+1)
                except queue.Empty:
                    # timeout, finalize
                    res = json.loads(recognizer.FinalResult())
                    text = res.get("text", "")
                    print("Transcribed (final, timeout):", text)
                    return text
                # downsample if needed
                if decimation:
                    send_bytes = downsample_int16_bytes(data, decimation)
                else:
                    # crude fallback: if device rate > model rate but not integer multiple,
                    # attempt simple linear interpolation by reshaping and taking every Nth approx.
                    ratio = device_samplerate / MODEL_SAMPLE_RATE
                    if ratio > 1.0:
                        # compute approximate integer factor
                        approx = int(round(ratio))
                        send_bytes = downsample_int16_bytes(data, approx)
                    else:
                        send_bytes = data
                # give to recognizer
                if recognizer.AcceptWaveform(send_bytes):
                    res = json.loads(recognizer.Result())
                    text = res.get("text", "")
                    print("Transcribed:", text)
                    return text
                # stop on timeout too
                if time.time() - start > timeout:
                    res = json.loads(recognizer.FinalResult())
                    text = res.get("text", "")
                    print("Transcribed (final, timeout):", text)
                    return text
    except sd.PortAudioError as e:
        print("PortAudio error while recording:", e)
        print("Check device index, sample rates, and device not in use.")
        return ""
    except Exception as e:
        print("Unexpected audio error:", e)
        return ""

def ask_local_llm(prompt: str) -> str:
    if LLM_AVAILABLE and llm is not None:
        try:
            out = llm(prompt=prompt, max_tokens=256, temperature=0.2)
            resp = out.get("choices", [{}])[0].get("text", "").strip()
            return resp or "Sorry, I couldn't produce an answer."
        except Exception as e:
            print("LLM inference error:", e)

    if "water" in prompt.lower() or "sprinkler" in prompt.lower():
        return "Astra: I recommend checking the schedule and the soil moisture sensor. Do you want me to run a diagnostic?"
    return "Astra: I heard you. I am running offline and will respond when connected to a model."

def speak_text(text: str):
    if not text:
        return
    out = text.replace("Astra:", "").strip()
    print("Astra:", out)
    try:
        tts.say(out)
        tts.runAndWait()
    except Exception as e:
        print("TTS error:", e)

def main_loop():
    print("=== Astra (offline) assistant ===")
    print("Press Enter to start recording. Ctrl+C to quit.")
    try:
        while True:
            input("Press Enter to speak...")
            user_text = record_and_transcribe(timeout=8)
            if not user_text.strip():
                print("No speech detected.")
                continue
            system_prompt = ("You are Astra, an offline assistant for the Ingenious Irrigation system. "
                             "Answer concisely and helpfully about irrigation, schedules, and diagnostics.")
            prompt = f"{system_prompt}\n\nUser: {user_text}\nAstra:"
            reply = ask_local_llm(prompt)
            speak_text(reply)
    except KeyboardInterrupt:
        print("\nExiting Astra.")
    except Exception as e:
        print("Runtime error:", e)

if __name__ == "__main__":
    main_loop()
