# MeshStats Dashboard

Live Meshtastic network dashboard for AZMSH, powered by your MeshMonitor database.

## Stack
- **Backend:** FastAPI (Python) — reads meshmonitor.db read-only via REST API on port 8000
- **Frontend:** Single-page HTML/JS dashboard served via nginx on port 8082
- **Auto-refresh:** Every 60 seconds

## Setup on Synology NAS

### 1. Copy files to your NAS
Copy the entire `meshstats` folder to your Synology, e.g.:
```
/volume1/docker/meshstats/
```

### 2. Build and start
SSH into your Synology and run:
```bash
cd /volume1/docker/meshstats
docker-compose up -d --build
```

### 3. Access the dashboard
Open your browser and go to:
```
http://YOUR_NAS_IP:8082
```

## API Endpoints
The backend exposes these endpoints (port 8000):
- `GET /api/stats/summary` — overall stats
- `GET /api/stats/nodes?limit=100` — node list with packet counts
- `GET /api/stats/packets` — packet type breakdown
- `GET /api/stats/hourly` — hourly activity (last 24h)
- `GET /api/stats/messages?limit=50` — recent messages
- `GET /api/stats/neighbors` — neighbor relationships
- `GET /api/stats/telemetry/{node_id}` — telemetry for a specific node
- `GET /health` — health check

## Notes
- The database is mounted **read-only** — this will never interfere with MeshMonitor
- The DB path is hardcoded to the default MeshMonitor volume location
- If your MeshMonitor data is elsewhere, update the volume path in docker-compose.yml
