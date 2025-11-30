# LeakWhisperer API Documentation

Complete API reference for frontend integration with the LeakWhisperer backend. Audio transcription is executed via the free HuggingFace Inference API (Whisper Tiny), so production deployments should set the `HF_API_TOKEN` environment variable to avoid rate limits.

## Base URL

```
http://localhost:8000
```

**Note:** The backend has CORS enabled for all origins (`*`), so frontend can connect from any domain/port.

---

## REST Endpoints

### 1. Get API Information

**GET** `/`

Returns basic API information and available endpoints.

**Response:**
```json
{
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
```

**Example:**
```javascript
const response = await fetch('http://localhost:8000/');
const apiInfo = await response.json();
console.log(apiInfo);
```

---

### 2. Get All Meters

**GET** `/meters`

Returns an array of all 1000 meters with their current status.

**Response:** `Array<Meter>`

**Meter Object Structure:**
```typescript
{
  meter_id: string;        // e.g., "meter_0001"
  lat: number;             // Latitude (e.g., 31.9637)
  lon: number;             // Longitude (e.g., 35.9189)
  street: string;          // Street name in Amman
  status: "normal" | "leak";
  last_update: number;     // Unix timestamp
  flow_rate_lph: number;   // Flow rate in liters per hour (0 if normal)
  confidence: number;      // Leak detection confidence (0.0 to 1.0)
  audio_base64: string | null;  // Base64-encoded audio (null if no recent upload)
  severity: "normal" | "low" | "medium" | "high" | "critical";
  transcript: string;      // Whisper AI transcript of the audio
}
```

**Example:**
```javascript
const response = await fetch('http://localhost:8000/meters');
const meters = await response.json();
console.log(`Total meters: ${meters.length}`);
console.log(`Active leaks: ${meters.filter(m => m.status === 'leak').length}`);
```

---

### 3. Get Single Meter

**GET** `/meter/{meter_id}`

Returns details for a specific meter.

**Parameters:**
- `meter_id` (path): The meter ID (e.g., `meter_0001`)

**Response:** `Meter | {}`

Returns the meter object if found, or an empty object `{}` if the meter doesn't exist.

**Example:**
```javascript
const meterId = 'meter_0011';
const response = await fetch(`http://localhost:8000/meter/${meterId}`);
const meter = await response.json();

if (Object.keys(meter).length === 0) {
  console.log('Meter not found');
} else {
  console.log(`Status: ${meter.status}, Severity: ${meter.severity}`);
}
```

---

### 4. Get Statistics

**GET** `/stats`

Returns aggregated statistics about the meter network.

**Response:**
```typescript
{
  total_meters: number;
  active_leaks: number;
  water_saved_today_m3: number;      // Cubic meters saved today
  projected_yearly_saving_jod: number; // Projected savings in JOD per year
}
```

**Example:**
```javascript
const response = await fetch('http://localhost:8000/stats');
const stats = await response.json();
console.log(`Active leaks: ${stats.active_leaks}/${stats.total_meters}`);
console.log(`Water saved today: ${stats.water_saved_today_m3} m³`);
console.log(`Projected yearly saving: ${stats.projected_yearly_saving_jod} JOD`);
```

---

### 5. Upload Audio (Internal Use)

**POST** `/upload-audio`

**Note:** This endpoint is typically called by the mock generator. Frontend doesn't need to use this unless building a test interface.

Uploads audio data for leak detection analysis.

**Request Body:**
```json
{
  "meter_id": "meter_0001",
  "audio_base64": "UklGRiQAAABXQVZFZm10...",  // Base64-encoded WAV audio
  "lat": 31.9637,          // Optional
  "lon": 35.9189,          // Optional
  "timestamp": 1704123456  // Optional
}
```

**Response:** `Meter` (same structure as above)

**Example:**
```javascript
const payload = {
  meter_id: 'meter_0001',
  audio_base64: '...' // base64 audio string
};

const response = await fetch('http://localhost:8000/upload-audio', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(payload)
});

const result = await response.json();
console.log(`Leak detected: ${result.is_leak}, Confidence: ${result.confidence}`);
```

---

## WebSocket Endpoint

### Real-time Leak Updates

**WebSocket** `ws://localhost:8000/ws/leaks`

Connects to receive real-time notifications whenever a leak is detected. The server automatically broadcasts leak events to all connected clients.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/leaks');
```

**Message Format:**

When a leak is detected, the server sends a JSON message with this structure:

```typescript
{
  meter_id: string;
  lat: number;
  lon: number;
  status: "leak";
  severity: "low" | "medium" | "high" | "critical";
  flow_rate_lph: number;
}
```

**Complete Example:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/leaks');

ws.onopen = () => {
  console.log('Connected to leak notifications');
  // Send a keep-alive message (server expects periodic messages)
  ws.send('ping');
};

ws.onmessage = (event) => {
  const leakData = JSON.parse(event.data);
  console.log('🚨 NEW LEAK DETECTED:', leakData);
  
  // Update your map/dashboard with the leak
  addLeakToMap(leakData);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket disconnected');
  // Reconnect after delay
  setTimeout(() => {
    // Reconnect logic here
  }, 3000);
};

// Keep connection alive by sending periodic pings
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send('ping');
  }
}, 30000); // Every 30 seconds
```

**Important Notes:**
- The server expects periodic messages to keep the connection alive. Send any text (e.g., `"ping"`) every 30 seconds.
- If the connection drops, implement reconnection logic.
- Multiple clients can connect simultaneously; all will receive the same leak notifications.

---

## Data Types & Enums

### Meter Status
- `"normal"` - No leak detected
- `"leak"` - Leak detected

### Severity Levels
- `"normal"` - No leak
- `"low"` - Flow rate > 0 and < 400 L/h
- `"medium"` - Flow rate 400-900 L/h
- `"high"` - Flow rate 900-1500 L/h
- `"critical"` - Flow rate ≥ 1500 L/h

---

## Error Handling

### HTTP Status Codes

- `200 OK` - Request successful
- `404 Not Found` - Endpoint or meter not found
- `500 Internal Server Error` - Server error (check server logs)
- `503 Service Unavailable` - Whisper AI pipeline not initialized

### Error Response Format

```json
{
  "detail": "Error message description"
}
```

**Example Error Handling:**
```javascript
try {
  const response = await fetch('http://localhost:8000/meter/invalid_id');
  
  if (!response.ok) {
    if (response.status === 404) {
      console.error('Meter not found');
    } else if (response.status === 503) {
      const error = await response.json();
      console.error('Service unavailable:', error.detail);
    } else {
      console.error(`HTTP error: ${response.status}`);
    }
    return;
  }
  
  const meter = await response.json();
  // Process meter data
} catch (error) {
  console.error('Network error:', error);
}
```

---

## Frontend Integration Examples

### React Hook for Meters

```javascript
import { useState, useEffect } from 'react';

function useMeters() {
  const [meters, setMeters] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8000/meters')
      .then(res => res.json())
      .then(data => {
        setMeters(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Error fetching meters:', err);
        setLoading(false);
      });
  }, []);

  return { meters, loading };
}
```

### React Hook for Real-time Leaks

```javascript
import { useState, useEffect, useRef } from 'react';

function useLeakNotifications(onLeakDetected) {
  const wsRef = useRef(null);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/leaks');
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('Connected to leak notifications');
      ws.send('ping');
    };

    ws.onmessage = (event) => {
      const leakData = JSON.parse(event.data);
      onLeakDetected(leakData);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('Reconnecting in 3 seconds...');
      setTimeout(() => {
        if (wsRef.current?.readyState === WebSocket.CLOSED) {
          // Trigger reconnection
          wsRef.current = new WebSocket('ws://localhost:8000/ws/leaks');
        }
      }, 3000);
    };

    // Keep-alive interval
    const keepAlive = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      }
    }, 30000);

    return () => {
      clearInterval(keepAlive);
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [onLeakDetected]);
}
```

### Complete Dashboard Integration Example

```javascript
import { useState, useEffect } from 'react';
import { useMeters, useLeakNotifications } from './hooks';

function Dashboard() {
  const { meters, loading } = useMeters();
  const [stats, setStats] = useState(null);
  const [leaks, setLeaks] = useState([]);

  // Fetch stats
  useEffect(() => {
    fetch('http://localhost:8000/stats')
      .then(res => res.json())
      .then(setStats);
  }, []);

  // Real-time leak notifications
  useLeakNotifications((leakData) => {
    console.log('New leak:', leakData);
    setLeaks(prev => [...prev, leakData]);
    // Update stats
    fetch('http://localhost:8000/stats')
      .then(res => res.json())
      .then(setStats);
  });

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <h1>LeakWhisperer Dashboard</h1>
      {stats && (
        <div>
          <p>Total Meters: {stats.total_meters}</p>
          <p>Active Leaks: {stats.active_leaks}</p>
          <p>Water Saved Today: {stats.water_saved_today_m3} m³</p>
        </div>
      )}
      <Map meters={meters} leaks={leaks} />
    </div>
  );
}
```

---

## Testing the API

### Using cURL

```bash
# Get all meters
curl http://localhost:8000/meters

# Get specific meter
curl http://localhost:8000/meter/meter_0011

# Get stats
curl http://localhost:8000/stats
```

### Using Browser Console

```javascript
// Test REST endpoints
fetch('http://localhost:8000/stats')
  .then(r => r.json())
  .then(console.log);

// Test WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/leaks');
ws.onmessage = (e) => console.log('Leak:', JSON.parse(e.data));
ws.onopen = () => ws.send('ping');
```

---

## Quick Start Checklist

- [ ] Backend server is running on `http://localhost:8000`
- [ ] Test root endpoint: `GET /` returns API info
- [ ] Fetch all meters: `GET /meters` returns 1000 meters
- [ ] Connect WebSocket: `ws://localhost:8000/ws/leaks`
- [ ] Listen for leak events and update UI in real-time
- [ ] Display stats: `GET /stats` for dashboard metrics
- [ ] Map meters by `lat`/`lon` and highlight leaks with `status: "leak"`

---

## Notes for Frontend Developers

1. **Mock Generator**: The backend includes a mock generator (`backend/mock_generator.py`) that continuously simulates 1000 meters. This is already running and generating leak events.

2. **Initial Load**: On first load, call `GET /meters` to get all 1000 meters and display them on the map.

3. **Real-time Updates**: Connect to the WebSocket immediately to receive new leak detections as they happen.

4. **Map Coordinates**: All meters are located in Amman, Jordan. Use these coordinates for map bounds:
   - Center: `[31.9539, 35.9106]` (Amman city center)
   - Suggested zoom: `12-13` for city view

5. **Audio Playback**: Meters include `audio_base64` field. You can decode and play the audio to hear the leak sounds (base64 → audio blob → audio element).

6. **Polling Alternative**: If WebSocket isn't feasible, poll `GET /meters` every 2-3 seconds to detect status changes.

---

## Support

For questions or issues, check:
- Backend logs in the terminal running `uvicorn`
- `backend/README-backend.md` for backend setup
- `idea.md` for overall project architecture

Happy coding! 🚀

