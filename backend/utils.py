import numpy as np
import soundfile as sf
import base64
import random
from io import BytesIO

# Real Amman / Zarqa coordinates + street names (100 real locations, repeated for 1000 meters)
REAL_LOCATIONS = [
    {"lat": 31.9539, "lon": 35.9106, "street": "شارع الملكة رانيا - مقابل الجامعة الأردنية"},
    {"lat": 31.9632, "lon": 35.9190, "street": "دوار المدينة الرياضية"},
    {"lat": 31.9456, "lon": 35.8845, "street": "شارع الرشيد - الزرقاء"},
    {"lat": 31.9719, "lon": 35.8355, "street": "ماركا الشمالية - قرب المطار"},
    {"lat": 31.9491, "lon": 35.9289, "street": "جاردنز - شارع وصفي التل"},
    # ... 95 more real ones — just repeat for 1000 meters
]

def generate_normal_sound(duration=10, sr=16000):
    """Normal household sounds: tap, shower, toilet flush, background noise"""
    t = np.linspace(0, duration, int(sr * duration), False)
    signal = np.zeros(int(sr * duration))
    # Random tap drips
    for _ in range(random.randint(3, 12)):
        start = random.randint(0, len(t)-2000)
        drip = np.sin(2 * np.pi * 800 * t[:2000]) * np.exp(-t[:2000]*5)
        signal[start:start+2000] += drip * 0.4
    # Low background hum + occasional car
    signal += np.random.normal(0, 0.05, len(signal))
    signal = np.clip(signal, -1, 1)
    return (signal * 32767).astype(np.int16)

def generate_leak_sound(duration=10, sr=16000):
    """High-pressure leak hiss + water flow rumble"""
    t = np.linspace(0, duration, int(sr * duration), False)
    hiss = 0.6 * np.sin(2 * np.pi * 1000 * t) * np.random.normal(0.9, 0.1, len(t))
    flow = 0.3 * np.sin(2 * np.pi * 50 * t) * np.exp(-t/3)
    noise = np.random.normal(0, 0.1, len(t))
    signal = hiss + flow + noise
    signal = np.clip(signal, -1, 1)
    return (signal * 32767).astype(np.int16)

def audio_to_base64(audio_int16, sr=16000):
    buffer = BytesIO()
    sf.write(buffer, audio_int16, samplerate=sr, format='WAV')
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_audio(b64_str):
    audio_bytes = base64.b64decode(b64_str)
    buffer = BytesIO(audio_bytes)
    audio, sr = sf.read(buffer)
    return audio.astype(np.float32), sr

def resample_audio(audio, source_sr, target_sr=16000):
    if source_sr == target_sr:
        return audio.astype(np.float32)
    duration = audio.shape[0] / source_sr
    target_len = int(duration * target_sr)
    old_times = np.linspace(0, duration, audio.shape[0], endpoint=False)
    new_times = np.linspace(0, duration, target_len, endpoint=False)
    resampled = np.interp(new_times, old_times, audio)
    return resampled.astype(np.float32)