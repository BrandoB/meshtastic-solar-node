# Meshtastic Solar Node + MeshStats Dashboard

A fully solar-powered outdoor Meshtastic node build using a Raspberry Pi 5 and MeshAdv Pi Hat, with a live network statistics dashboard backed by MeshMonitor running on a Synology NAS.

---

## Hardware

| Component | Part |
|---|---|
| SBC | Raspberry Pi 5 |
| Meshtastic Radio Hat | MeshAdv Pi Hat (1W LoRa) |
| PoE Hat | Waveshare PoE Hat (F) |
| Solar Charge Controller | Tycon Systems TP-SCPOE1248 |
| Solar Panel | 18V 25W |
| Battery | 12V 10Ah LiFePO4 with integrated BMS |
| PoE Injector (power) | Linovision Gigabit 90W Passive PoE Injector |
| PoE Injector (inline) | PoE Texas DC-Powered PoE+ 30W Gigabit Inline Injector (12-60V in → 802.3at out) |
| Antenna | Slinkdsco Waterproof 5.8dBi Fiberglass 915MHz N-Male |
| Router | Netgear RS700 |

---

## Network Architecture

```
Netgear RS700 (gigabit)
    └── Linovision 90W Passive PoE Injector
            └── Tycon TP-SCPOE1248 (solar charge controller / 100Mb switch)
                    ├── 18V 25W Solar Panel
                    ├── 12V 10Ah LiFePO4 Battery
                    └── PoE Texas Inline Injector (12V DC in → 802.3at PoE+ out)
                            └── Raspberry Pi 5 + Waveshare PoE Hat + MeshAdv Pi Hat
```

The Tycon unit handles solar charge management and battery maintenance. The PoE Texas injector converts the Tycon's 12V DC output into IEEE 802.3at PoE+ to power the Pi.

---

## Known Issue: Ethernet Autonegotiation

### Problem

The Tycon TP-SCPOE1248 is a **100Mb switch**. The Raspberry Pi 5's BCM54213PE gigabit NIC will not autonegotiate down to 100Mb through the PoE chain, resulting in:

- `Link detected: no` in `ethtool`
- Speed: Unknown / Duplex: Unknown
- No IP address assigned

### Fix

Force `eth0` to 100Mb/s Full duplex with autonegotiation disabled. On the Pi:

```bash
sudo ip link set eth0 down
sudo ethtool -s eth0 speed 100 duplex full autoneg off
sudo ip link set eth0 up
```

Verify the fix:
```bash
ethtool eth0 | grep -E "Speed|Duplex|Link"
```

Expected output:
```
Speed: 100Mb/s
Duplex: Full
Link detected: yes
```

### Making It Persistent

The setting is managed by NetworkManager via netplan on Raspberry Pi OS. Set it through the desktop Network Manager GUI (right-click the network icon → Edit Connections → Ethernet → Speed/Duplex). The setting is written to `/etc/netplan/*.yaml` as:

```yaml
networkmanager:
  passthrough:
    ethernet.duplex: "full"
    ethernet.speed: "100"
```

Alternatively, create a systemd service to apply it on every boot:

```bash
sudo nano /etc/systemd/system/eth0-force-100mb.service
```

```ini
[Unit]
Description=Force eth0 to 100Mb full duplex
After=network.target

[Service]
Type=oneshot
ExecStart=/sbin/ethtool -s eth0 speed 100 duplex full autoneg off
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable eth0-force-100mb.service
sudo systemctl start eth0-force-100mb.service
```

---

## Software Stack

| Software | Host | Purpose |
|---|---|---|
| Meshtastic | Pi 5 (MeshAdv Hat) | LoRa mesh radio |
| MeshMonitor | Synology NAS (Docker) | Node monitoring, packet logging, messaging |
| MeshStats API | Synology NAS (Docker) | FastAPI backend querying MeshMonitor SQLite DB |
| MeshStats UI | Synology NAS (Docker) | Live dashboard served via nginx |

---

## MeshStats Dashboard

A live statistics dashboard that reads directly from the MeshMonitor SQLite database and presents it in a browser UI with auto-refresh every 60 seconds.

### Features

- Summary stats: total nodes, active nodes (30m / 24h), direct links, avg SNR, packet count, message count
- Node table: sortable by packets, SNR, RSSI, last heard, hops — with battery indicators, channel utilization, and hop distance badges
- Packet tab: packet type breakdown with signal quality per type
- Activity tab: hourly traffic chart (last 24h, local time), top nodes leaderboard, SNR health distribution
- Messages tab: recent channel messages with timestamps and sender names
- Live/offline status indicator with countdown timer

### Architecture

```
MeshMonitor container
    └── meshmonitor.db (SQLite, ~230MB after a few days)
            └── MeshStats API (FastAPI, port 8000) — read-only mount
                    └── MeshStats UI (nginx, port 8082) — fetches from API
```

The database is mounted **read-only** into the API container so MeshStats can never interfere with MeshMonitor.

### Prerequisites

- Docker and Docker Compose on your Synology NAS
- MeshMonitor already running with its data volume at:
  `/volume1/@docker/volumes/meshmonitor_meshmonitor-data/_data/meshmonitor.db`

### File Structure

```
meshstats/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   └── main.py          # FastAPI app
└── frontend/
    ├── Dockerfile
    └── index.html       # Single-file dashboard (vanilla JS + Chart.js)
```

### Setup

**1. Copy files to your Synology:**

Place the `meshstats` folder at `/volume1/docker/meshstats/`

**2. Build and start containers:**

```bash
cd /volume1/docker/meshstats
docker-compose up -d --build
```

**3. Access the dashboard:**

```
http://YOUR_NAS_IP:8082
```

### docker-compose.yml

```yaml
version: "3.8"

services:
  meshstats-api:
    build: ./backend
    container_name: meshstats-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - /volume1/@docker/volumes/meshmonitor_meshmonitor-data/_data/meshmonitor.db:/data/meshmonitor.db:ro
    environment:
      - DB_PATH=/data/meshmonitor.db

  meshstats-ui:
    build: ./frontend
    container_name: meshstats-ui
    restart: unless-stopped
    ports:
      - "8082:80"
    depends_on:
      - meshstats-api
```

### API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/stats/summary` | Overall network summary stats |
| `GET /api/stats/nodes?limit=150` | Node list with packet counts |
| `GET /api/stats/packets` | Packet type breakdown with signal quality |
| `GET /api/stats/hourly` | Hourly activity for last 24h (local time) |
| `GET /api/stats/messages?limit=50` | Recent channel messages |
| `GET /api/stats/neighbors` | Neighbor relationships |
| `GET /api/stats/telemetry/{node_id}` | Telemetry history for a specific node |
| `GET /health` | Health check |

### Updating the Dashboard

To update the frontend after making changes to `index.html`:

```bash
cd /volume1/docker/meshstats
docker-compose up -d --build meshstats-ui
```

To update the API after making changes to `main.py`:

```bash
cd /volume1/docker/meshstats
docker-compose up -d --build meshstats-api
```

---

## AZMSH Network

This node participates in the [Arizona Meshtastic Community (AZMSH)](https://azmsh.net) network on the primary AZMSH channel.

### Recommended Settings (per AZMSH guidelines)

| Setting | Value |
|---|---|
| Role | Client |
| Hop Count | 3 |
| Node Info Broadcast | Every 4–6 hours |
| Position Broadcast | Every 12–24 hours (stationary node) |
| Telemetry | Every 4–6 hours |
| MQTT Downlink | Disabled on primary channel |

---

## Pi Configuration Notes

### Static DHCP Reservation

The Pi is assigned a static IP via DHCP reservation on the Netgear RS700 router using MAC address `D8:3A:DD:D2:40:9E`.

### SSH

SSH is enabled on the Pi. To connect from any machine on the local network:

```bash
ssh mesh@192.168.1.35
```

For convenience, add to your `~/.ssh/config`:

```
Host meshpi
    HostName 192.168.1.35
    User mesh
```

Then simply use `ssh meshpi`.

### Backing Up the Pi

To create a full image backup (from another Linux machine with the SD card inserted):

```bash
sudo dd if=/dev/sdX of=meshpi-backup.img bs=4M status=progress
```

Flash back to a new SD card using [Balena Etcher](https://etcher.balena.io/).

---

## Photos

*(Add photos of your build here)*

---

## License

MIT
