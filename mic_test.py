import sounddevice as sd, wave, numpy as np
DEVICE = 15
DURATION = 5
SR = 16000
print("Recording", DURATION, "s from device", DEVICE)
rec = sd.rec(int(DURATION * SR), samplerate=SR, channels=1, dtype='int16', device=DEVICE)
sd.wait()
data = rec.tobytes()
with wave.open("mic_test.wav", "wb") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(SR)
    f.writeframes(data)
print("Saved mic_test.wav — play it to confirm audio.")
