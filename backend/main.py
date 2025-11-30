import os
import random
import time
from typing import Any, Dict, List, Tuple

import httpx
import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.utils import REAL_LOCATIONS, base64_to_audio, resample_audio

app = FastAPI(title="LeakWhisperer Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
meters_db: Dict[str, Dict[str, Any]] = {}
active_websockets: List[WebSocket] = []

TARGET_SAMPLE_RATE = 16_000
HF_API_URL = os.getenv(
    "HF_API_URL",
    "https://api-inference.huggingface.co/models/openai/whisper-tiny",
)
HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_API_TIMEOUT = float(os.getenv("HF_API_TIMEOUT", "45"))

# Initialize 1000 meters with real Amman locations
for i in range(1000):
    loc = REAL_LOCATIONS[i % len(REAL_LOCATIONS)]
    meters_db[f"meter_{i:04d}"] = {
        "meter_id": f"meter_{i:04d}",
        "lat": loc["lat"] + random.uniform(-0.003, 0.003),
        "lon": loc["lon"] + random.uniform(-0.003, 0.003),
        "street": loc["street"],
        "status": "normal",
        "last_update": time.time(),
        "flow_rate_lph": 0,
        "confidence": 0.0,
        "audio_base64": None,
        "severity": "normal",
        "transcript": "",
    }

async def transcribe_audio(audio_bytes: bytes) -> str:
    if not HF_API_URL:
        raise HTTPException(500, detail="HF_API_URL not configured")

    headers = {
        "Accept": "application/json",
        "Content-Type": "audio/wav",
    }
    if HF_API_TOKEN:
        headers["Authorization"] = f"Bearer {HF_API_TOKEN}"

    async with httpx.AsyncClient(timeout=HF_API_TIMEOUT) as client:
        response = await client.post(HF_API_URL, headers=headers, content=audio_bytes)

    if response.status_code == 503:
        raise HTTPException(503, detail="ASR model warming up on HuggingFace; retry shortly.")
    if response.status_code == 401:
        raise HTTPException(
            502,
            detail="Unauthorized by HuggingFace Inference API. Set HF_API_TOKEN env var.",
        )
    if response.status_code >= 400:
        raise HTTPException(502, detail=f"HuggingFace ASR error: {response.text}")

    payload = response.json()
    if isinstance(payload, dict) and payload.get("error"):
        raise HTTPException(503, detail=f"ASR unavailable: {payload['error']}")

    if isinstance(payload, list):
        transcript = payload[0].get("text", "") if payload else ""
    else:
        transcript = payload.get("text", "")
    return transcript.strip()


async def analyze_leak(audio_b64: str) -> Tuple[bool, float, str]:
    audio, sr, audio_bytes = base64_to_audio(audio_b64)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = resample_audio(audio, sr, TARGET_SAMPLE_RATE)
    transcript = await transcribe_audio(audio_bytes)
    transcript_lower = transcript.lower()
    keywords = ("hiss", "leak", "water", "flow", "pipe", "pressure")
    keyword_hit = any(word in transcript_lower for word in keywords)
    keyword_score = 0.8 if keyword_hit else min(0.4, len(transcript_lower) / 80)
    
    # Compute high-frequency energy ratio (800-4000 Hz) as described in idea.md
    # This is more accurate for detecting leak hissing sounds
    # Use FFT to analyze frequency spectrum
    fft = np.fft.rfft(audio)
    power_spectrum = np.abs(fft) ** 2
    frequencies = np.fft.rfftfreq(len(audio), 1.0 / TARGET_SAMPLE_RATE)
    
    # High-frequency range for leak detection (800-4000 Hz)
    high_freq_mask = (frequencies >= 800) & (frequencies <= 4000)
    
    high_freq_energy = np.sum(power_spectrum[high_freq_mask])
    total_energy = np.sum(power_spectrum)
    
    # High-frequency energy ratio - leaks have more energy in high frequencies
    if total_energy > 0:
        high_freq_ratio = high_freq_energy / total_energy
    else:
        high_freq_ratio = 0.0
    
    # Normalize the ratio (typical leaks: 0.3-0.6, normal: <0.2)
    normalized_hf_ratio = min(1.0, high_freq_ratio * 2.0)
    
    leak_score = min(1.0, 0.6 * normalized_hf_ratio + 0.4 * keyword_score)
    is_leak = leak_score >= 0.55
    return is_leak, round(leak_score, 3), transcript

def estimate_flow(confidence: float) -> int:
    base = 350
    max_flow = 2200
    return int(base + (max_flow - base) * min(confidence, 1.0))

def compute_severity(flow_rate: int) -> str:
    if flow_rate >= 1500:
        return "critical"
    if flow_rate >= 900:
        return "high"
    if flow_rate >= 400:
        return "medium"
    if flow_rate > 0:
        return "low"
    return "normal"

async def broadcast_leak(meter_data: dict):
    message = {
        "meter_id": meter_data["meter_id"],
        "lat": meter_data["lat"],
        "lon": meter_data["lon"],
        "status": meter_data["status"],
        "severity": meter_data.get("severity", "high"),
        "flow_rate_lph": meter_data["flow_rate_lph"]
    }
    for ws in active_websockets[:]:
        try:
            await ws.send_json(message)
        except:
            active_websockets.remove(ws)

@app.get("/")
async def root():
    return {
        "message": "LeakWhisperer Backend API",
        "version": "1.0.0",
        "endpoints": {
            "GET /": "API information (this endpoint)",
            "POST /upload-audio": "Upload audio for leak detection",
            "GET /meters": "Get all meters",
            "GET /meter/{meter_id}": "Get specific meter",
            "GET /stats": "Get statistics",
            "WebSocket /ws/leaks": "Real-time leak updates"
        }
    }

@app.post("/upload-audio")
async def upload_audio(data: dict):
    meter_id = data["meter_id"]
    audio_b64 = data["audio_base64"]
    is_leak, confidence, transcript = await analyze_leak(audio_b64)
    flow_rate = estimate_flow(confidence) if is_leak else 0
    severity = compute_severity(flow_rate)

    meters_db[meter_id].update({
        "status": "leak" if is_leak else "normal",
        "last_update": time.time(),
        "flow_rate_lph": flow_rate,
        "confidence": confidence,
        "audio_base64": audio_b64,
        "severity": severity,
        "transcript": transcript,
    })

    if is_leak:
        await broadcast_leak(meters_db[meter_id])

    return {
        **meters_db[meter_id],
        "is_leak": is_leak,
        "severity": severity
    }

@app.get("/meters")
async def get_meters():
    return list(meters_db.values())

@app.get("/meter/{meter_id}")
async def get_meter(meter_id: str):
    return meters_db.get(meter_id, {})

@app.get("/stats")
async def get_stats():
    active_leaks = sum(1 for m in meters_db.values() if m["status"] == "leak")
    saved_m3 = active_leaks * 1200 * 2  # fake but realistic
    return {
        "total_meters": len(meters_db),
        "active_leaks": active_leaks,
        "water_saved_today_m3": round(saved_m3, 1),
        "projected_yearly_saving_jod": round(active_leaks * 1200 * 24 * 365 * 2 / 1000, 1)
    }

@app.websocket("/ws/leaks")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        active_websockets.remove(websocket)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
