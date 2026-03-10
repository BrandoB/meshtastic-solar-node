from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
import time

app = FastAPI(title="MeshStats API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.environ.get("DB_PATH", "/data/meshmonitor.db")

def get_db():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/stats/summary")
def summary():
    db = get_db()
    now = int(time.time())
    data = {}
    data["total_nodes"] = db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    data["active_30m"] = db.execute("SELECT COUNT(*) FROM nodes WHERE lastHeard > ?", (now - 1800,)).fetchone()[0]
    data["active_24h"] = db.execute("SELECT COUNT(*) FROM nodes WHERE lastHeard > ?", (now - 86400,)).fetchone()[0]
    data["direct_nodes"] = db.execute("SELECT COUNT(*) FROM nodes WHERE hopsAway = 0").fetchone()[0]
    data["total_packets"] = db.execute("SELECT COUNT(*) FROM packet_log").fetchone()[0]
    data["total_messages"] = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    avg_snr = db.execute("SELECT AVG(snr) FROM nodes WHERE snr IS NOT NULL AND lastHeard > ?", (now - 86400,)).fetchone()[0]
    data["avg_snr"] = round(avg_snr, 2) if avg_snr else None
    db.close()
    return data

@app.get("/api/stats/nodes")
def nodes(limit: int = 100):
    db = get_db()
    rows = db.execute("""
        SELECT 
            n.longName, n.shortName, n.nodeId, n.hopsAway,
            n.snr, n.rssi, n.lastHeard, n.packetRatePerHour,
            n.channelUtilization, n.airUtilTx,
            n.latitude, n.longitude, n.batteryLevel, n.voltage,
            n.firmwareVersion, n.role, n.isFavorite,
            COUNT(p.id) as packet_count
        FROM nodes n
        LEFT JOIN packet_log p ON p.from_node = n.nodeNum
        WHERE n.lastHeard IS NOT NULL
        GROUP BY n.nodeNum
        ORDER BY packet_count DESC
        LIMIT ?
    """, (limit,)).fetchall()
    db.close()
    return [dict(r) for r in rows]

@app.get("/api/stats/packets")
def packets():
    db = get_db()
    rows = db.execute("""
        SELECT portnum_name, COUNT(*) as count,
               AVG(snr) as avg_snr, AVG(rssi) as avg_rssi,
               AVG(payload_size) as avg_size
        FROM packet_log
        GROUP BY portnum_name
        ORDER BY count DESC
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]

@app.get("/api/stats/hourly")
def hourly():
    db = get_db()
    rows = db.execute("""
        SELECT strftime('%H', datetime(timestamp, 'unixepoch', 'localtime')) as hour,
               COUNT(*) as packets
        FROM packet_log
        WHERE timestamp > strftime('%s', 'now') - 86400
        GROUP BY hour
        ORDER BY hour
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]

@app.get("/api/stats/messages")
def messages(limit: int = 50):
    db = get_db()
    rows = db.execute("""
        SELECT m.id, m.text, m.timestamp, m.channel,
               n.longName as from_name, n.shortName as from_short,
               m.fromNodeId
        FROM messages m
        LEFT JOIN nodes n ON n.nodeId = m.fromNodeId
        ORDER BY m.timestamp DESC
        LIMIT ?
    """, (limit,)).fetchall()
    db.close()
    return [dict(r) for r in rows]

@app.get("/api/stats/neighbors")
def neighbors():
    db = get_db()
    rows = db.execute("""
        SELECT ni.node_id, ni.neighbor_id, ni.snr,
               n1.longName as node_name, n2.longName as neighbor_name
        FROM neighbor_info ni
        LEFT JOIN nodes n1 ON n1.nodeId = ni.node_id
        LEFT JOIN nodes n2 ON n2.nodeId = ni.neighbor_id
        ORDER BY ni.snr DESC
        LIMIT 100
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]

@app.get("/api/stats/telemetry/{node_id}")
def telemetry(node_id: str, limit: int = 50):
    db = get_db()
    rows = db.execute("""
        SELECT * FROM telemetry
        WHERE node_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (node_id, limit)).fetchall()
    db.close()
    return [dict(r) for r in rows]

@app.get("/health")
def health():
    return {"status": "ok", "db": DB_PATH}
