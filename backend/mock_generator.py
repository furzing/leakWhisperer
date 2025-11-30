import time
import random

import requests

from utils import generate_normal_sound, generate_leak_sound, audio_to_base64, REAL_LOCATIONS

url = "http://localhost:8000/upload-audio"
meters = [f"meter_{i:04d}" for i in range(1000)]
locations = [REAL_LOCATIONS[i % len(REAL_LOCATIONS)] for i in range(1000)]

print("LeakWhisperer Mock Generator STARTED | 1000 meters active")
print("Press Ctrl+C to stop\n")

while True:
    for i in range(1000):
        meter_id = meters[i]
        lat = locations[i]["lat"] + random.uniform(-0.001, 0.001)
        lon = locations[i]["lon"] + random.uniform(-0.001, 0.001)

        # 0.9% chance of leak at any given moment -> 7-12 active leaks
        if random.random() < 0.009:
            audio_int16 = generate_leak_sound()
            print(f"LEAK DETECTED -> {meter_id} | {lat:.4f},{lon:.4f}")
        else:
            audio_int16 = generate_normal_sound()

        payload = {
            "meter_id": meter_id,
            "lat": lat,
            "lon": lon,
            "timestamp": time.time(),
            "audio_base64": audio_to_base64(audio_int16)
        }

        try:
            requests.post(url, json=payload, timeout=2)
        except Exception:
            pass  # Silent if backend not ready

        time.sleep(0.003)  # ~1000 meters every 3 seconds -> feels real-time
