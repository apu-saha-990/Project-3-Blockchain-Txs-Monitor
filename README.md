# Project 3 — Real-Time Blockchain Transaction Monitor

A real-time Ethereum transaction monitoring system that streams live mempool data, filters by value and gas, detects anomalies, and stores everything in a time-series database.

---

## What It Does

- Streams live pending transactions from Ethereum mainnet via Alchemy WebSocket
- Filters transactions by value (0.5 / 10 / 100 ETH thresholds), gas price, contract type, and private MEV
- Detects volume spikes and gas anomalies across rolling time windows
- Identifies recirculation patterns using DFS cycle detection across a 1-hour transaction graph
- Stores all transactions, blocks, and anomalies in PostgreSQL with TimescaleDB hypertables
- Exports Prometheus metrics on port 8000 — transaction counts, gas averages, anomaly totals
- Sends alerts via Discord and Slack webhooks on threshold breaches
- Runs in two display modes — raw scrolling feed (Mode A) or structured terminal dashboard (Mode B)
- Includes an offline demo mode (Mode C) that replays 70 real mainnet transactions with no API key needed

---

## Why This Project Matters

Blockchain infrastructure teams need to know what is happening on-chain in real time. Large transfers, gas spikes, and circular fund flows are signals — for compliance, security, and operations. This system captures those signals, stores them, and surfaces them through a live terminal dashboard and Grafana. It runs 24/7 on a headless server without a GUI.

---

## How I Built This

I am a career changer from a factory and manufacturing background. No CS degree. No bootcamp.

I use AI (Claude) throughout development — as a learning tool, code reviewer, and debugging partner. Every terminal error went back to Claude. The decisions are mine — what to build, how to structure the pipeline, what broke, what I fixed, and how to put the layers together.

I built this in phases over several weeks. Each phase had to work before the next one started. The WebSocket stream came first, then the filter chain, then storage, then the dashboard, then metrics, then Kubernetes. Nothing was theoretical — every layer was tested live against Ethereum mainnet before moving on.

The systems run. The tests pass. I can demo everything live.

---

## What I Learned

- How the Ethereum mempool actually works — pending transactions vs confirmed, and why gas price matters for inclusion order
- Why asyncio matters for a high-throughput stream — blocking calls kill the pipeline
- How TimescaleDB hypertables partition time-series data and why that matters for query performance
- What a Prometheus pull model looks like in practice — scrape intervals, metric types, and label cardinality
- How DFS cycle detection works on a live transaction graph — and why window size matters for false positives
- That ruff lint failures in CI are fixable but not always auto-fixable — duplicate dictionary keys and `StrEnum` imports both required manual edits (see Post-Mortem)
- How to build a Kubernetes deployment from scratch — namespaces, ConfigMaps, Secrets, imagePullPolicy
- That `docker compose down -v` wipes your volumes — learned this the hard way

---

## Post-Mortem

**Bug:** GitHub Actions CI failing on lint step with 24 errors — `ruff check src/` returned exit code 1.

**Root cause 1:** Duplicate dictionary key in `src/filters/contract_filter.py`. The selector `0x23b872dd` appeared twice in the contract signatures dict. Python silently accepts this — ruff correctly flags it.

```python
# broken
"0x23b872dd": "ERC721_TRANSFER_FROM",
...
"0x23b872dd": "ERC721_TRANSFER_FROM",  # duplicate — ruff F601
```

```python
# fixed — removed the duplicate entry
"0x23b872dd": "ERC721_TRANSFER_FROM",
```

**Root cause 2:** `EventType` in `src/ingestion/stream_manager.py` inherited from both `str` and `enum.Enum`. Ruff UP042 flags this — the modern form is `enum.StrEnum`.

```python
# broken
from enum import Enum
class EventType(str, Enum):
```

```python
# fixed
import enum
class EventType(enum.StrEnum):
```

**Lesson:** `ruff --fix` handles most issues automatically but not all. Some require reading the error and fixing manually. Running ruff locally before pushing saves CI time.

---

## Running It

**Docker (local dev):**
```bash
docker compose up -d
docker exec -i txmonitor-db psql -U monitor -d txmonitor < src/storage/schema.sql
python3 -m src.main
```

**Demo mode (no API key needed):**
```bash
python3 demo/run_demo.py --mode B --speed 5
```

**Kubernetes (minikube):**
```bash
minikube start --driver=docker
eval $(minikube docker-env)
docker build -t txmonitor:latest .
eval $(minikube docker-env --unset)
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl create secret generic txmonitor-secrets \
  --from-literal=ALCHEMY_WS_URL="your_key" \
  --from-literal=COINMARKETCAP_API_KEY="your_key" \
  -n txmonitor
kubectl apply -f k8s/
kubectl exec -n txmonitor -i $(kubectl get pod -n txmonitor -l app=timescaledb \
  -o jsonpath='{.items[0].metadata.name}') -- \
  psql -U monitor -d txmonitor < src/storage/schema.sql
kubectl port-forward svc/grafana 3001:3000 -n txmonitor
```

**Access:**
```
Grafana:    http://localhost:3000  (admin / admin)
Prometheus: http://localhost:9090
Metrics:    http://localhost:8000/metrics
```

---

## Environment Variables

```bash
ALCHEMY_WS_URL=wss://eth-mainnet.g.alchemy.com/v2/your_key   # Alchemy WebSocket endpoint
COINMARKETCAP_API_KEY=your_key                                 # ETH/USD price feed
DATABASE_URL=postgresql://monitor:monitor@localhost:5432/txmonitor  # TimescaleDB connection
PROMETHEUS_PORT=8000                                           # Metrics export port
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Data ingestion | Python + WebSocket (Alchemy) |
| Stream management | asyncio |
| Filtering | Custom Python filter chain |
| Anomaly detection | Custom Python — rolling window |
| Recirculation detection | DFS cycle detection |
| Database | PostgreSQL + TimescaleDB |
| Metrics | Prometheus (`prometheus_client`) |
| Visualisation | Grafana |
| Terminal UI | Python Rich |
| Alerting | Alertmanager + Discord / Slack webhooks |
| Containerisation | Docker + Docker Compose |
| Orchestration | Kubernetes (minikube) |
| CI/CD | GitHub Actions — lint + docker build |
| Language | Python 3.12 |

---

## Project Structure

```
src/
├── main.py                    # Entrypoint — Mode A / B selector
├── ingestion/
│   ├── alchemy_ws.py          # WebSocket stream client
│   ├── stream_manager.py      # Event routing
│   └── price_feed.py          # ETH/USD price via CoinMarketCap
├── filters/
│   ├── value_filter.py        # ETH value thresholds
│   ├── gas_filter.py          # Gas spike detection
│   ├── contract_filter.py     # DEX / NFT / ERC20 classification
│   └── filter_chain.py        # Pipeline combinator
├── analysis/
│   ├── anomaly.py             # Volume + gas anomaly detectors
│   └── recirculation.py       # DFS cycle detection
├── storage/
│   ├── db.py                  # asyncpg database client
│   └── schema.sql             # TimescaleDB hypertables
├── dashboard/
│   └── dashboard.py           # Rich terminal dashboard
└── metrics/
    └── metrics.py             # Prometheus counters and gauges
demo/
├── demo_data.py               # 70 real mainnet transactions
├── demo_runner.py             # Replay engine
└── run_demo.py                # Demo entrypoint
k8s/                           # Kubernetes manifests
monitoring/
└── prometheus.yml             # Prometheus scrape config
.github/workflows/ci.yml       # GitHub Actions pipeline
docker-compose.yml
Dockerfile
```

---

## Roadmap

- Auto-restart on WebSocket disconnect
- Alert when stream goes silent for more than 60 seconds
- Nightly TimescaleDB backups via cron
- Log rotation for long-running deployments
- Cross-chain correlation — track the same wallet across Ethereum and a second chain

---

## Architecture

![Architecture Diagram](docs/architecture.png)

---

*Career changer from manufacturing. Learning in public. Building real things.*
