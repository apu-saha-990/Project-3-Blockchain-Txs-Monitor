# Project 4 — Real-Time Blockchain Transaction Monitor

A system that watches live Ethereum network traffic, filters it by size and behaviour, spots unusual patterns, and stores everything so it can be reviewed later.

---

## What Problem Does This Solve

Financial networks move money constantly — and most of it is invisible unless you build something to watch it. If a large transfer happens, if gas prices spike suddenly, or if money starts moving in circles between accounts, you want to know about it in real time — not the next morning. This project watches the Ethereum network live, catches those signals the moment they happen, and sends an alert before anyone has to go looking.

---

## How It Works

1. The system connects to the Ethereum network and starts receiving every pending transaction before it's confirmed
2. Each transaction passes through a filter — is it large enough to care about? Is the gas price unusually high? Is it interacting with a known exchange or marketplace?
3. The anomaly detector compares what's happening right now against the last few minutes of history — if the rate suddenly jumps, it flags it
4. The recirculation detector maps where money is going — if the same funds keep moving between the same accounts in a loop, it catches it
5. Every flagged transaction is saved to a time-series database so it can be reviewed and charted later
6. Alerts fire to Discord or Slack when thresholds are hit
7. A live terminal dashboard shows everything scrolling in real time

---

## What's Built

**Live transaction stream** — Connects to the Ethereum network and receives every pending transaction the moment it enters the queue, before it's confirmed into a block.

**Filter pipeline** — Four filters run in sequence. One checks transaction size. One checks gas price against a rolling average. One identifies what kind of transaction it is — exchange swap, token transfer, NFT sale. One flags private transactions that bypass the public queue entirely.

**Anomaly detector** — Watches the rate of transactions over a short window and compares it to a longer baseline. If the short window suddenly runs far above the baseline, it fires an alert.

**Recirculation detector** — Builds a live map of where money is going between accounts. If it detects a loop — money going A → B → C → A — it flags it and saves the pattern.

**Time-series database** — Every transaction, block, and anomaly is written to a database that partitions data by time. This makes queries over time ranges fast even at high volume.

**Metrics and dashboards** — A metrics endpoint exposes transaction counts, gas averages, and anomaly totals. A dashboarding tool connects to it and renders live charts.

**Alerting** — Alertmanager routes threshold alerts to Discord and Slack via webhooks.

**Terminal dashboard** — A live scrolling feed with colour-coded output. Large transactions highlight differently from normal ones. Anomalies are highlighted in a separate colour. Runs headless — no GUI needed.

**Offline demo mode** — 70 real mainnet transactions from March 2026 replayed through the full pipeline. No API key needed. Anomalies and recirculation events are scripted into the dataset so the demo is predictable.

---

## A Bug I Found

**Bug 1 — The database refused to start**

When I added the recirculation detector, I needed to store every circular pattern it found — but only once per unique pattern, not duplicates. The obvious way to do that was to put a unique constraint on the pattern's fingerprint column in the database. I wrote it in, ran the setup, and the database crashed on startup with an error I hadn't seen before.

The error said something about a unique constraint not being compatible with that type of table. I didn't understand it at first. I went back and read how my time-series database works under the hood — it automatically splits data across partitions by time. And it has a hard rule: a unique constraint must include the time column, or the database can't enforce it across all partitions. My constraint was on the fingerprint column alone. So it rejected the whole table.

The fix was to remove the unique constraint from the database entirely and move the duplicate check into the application code instead. Before saving a pattern, the code now checks whether that fingerprint already exists — and only writes it if it doesn't.

```sql
-- broken — unique constraint on fingerprint alone, database rejects it
path_hash TEXT NOT NULL UNIQUE,

-- fixed — constraint removed, duplicate check handled in code
path_hash TEXT NOT NULL,
```

```python
# before inserting, check if this pattern was already seen
existing = await conn.fetchval(
    "SELECT id FROM recirculation_paths WHERE path_hash = $1", path_hash
)
if not existing:
    await conn.execute(insert_query, ...)
```

The lesson: a time-series database that partitions data automatically has different rules from a regular database. Constraints that work fine in a standard setup can silently break here. I learned to check those rules before designing the table around them.

---

**Bug 2 — Prometheus running but showing nothing**

After I got the metrics and dashboards working, I moved the docker-compose file from a subfolder to the project root to clean up the folder structure. Everything started fine. No errors anywhere. But when I opened the dashboard, all the charts were empty. No data at all — just flat lines.

I spent time checking whether the metrics endpoint was working. It was. I checked whether the database was running. It was. Everything looked healthy. The problem turned out to be a single dot in a file path.

When docker-compose was inside a subfolder, the path to the Prometheus config file used `../` to go one level up and find it. When I moved docker-compose to the root, that path was now wrong — pointing to a location that didn't exist. The container started anyway because it doesn't error when a volume path is missing. It just mounted nothing. So Prometheus had no config and scraped nothing — silently.

```yaml
# broken — path relative to old subfolder location
- ../monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

# fixed — path from project root
- ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
```

The lesson: when a container starts without errors but produces no output, the config file might not have loaded at all. Docker won't tell you. I now always check volume mounts first when something looks healthy but produces nothing.

---

## How I Built This

I'm a career changer from a factory and manufacturing background. No CS degree. No bootcamp.

I use AI (Claude) throughout development — as a learning tool, code reviewer, and debugging partner. Every terminal error went back to Claude. The decisions are mine — what to build, how to structure the pipeline, what broke, what I fixed, and how to put the layers together.

I built this in phases over several weeks. Each phase had to work before the next one started. The live stream came first, then the filters, then the database writes, then the dashboard, then the metrics, then the Kubernetes deployment. Nothing was theoretical — every layer was tested against real Ethereum mainnet traffic before moving on.

The systems run. The tests pass. I can demo everything live.

---

## What I Learned

- How pending transactions actually work — they enter a queue before confirmation, and that queue is where the real signal is
- Why blocking calls kill a high-throughput stream — everything has to be non-blocking or the pipeline falls behind
- How time-series databases partition data by time — and why that breaks normal database rules around unique constraints (see Bug 1)
- That containers starting without errors doesn't mean they loaded their config — volume path issues are silent (see Bug 2)
- How a metrics scrape model works in practice — an external tool polls your app on a schedule and pulls the numbers
- How cycle detection works on a live graph — and why the time window matters for avoiding false positives
- That lint tools catch bugs your runtime won't — a duplicate dictionary key ran fine locally but was correctly flagged as broken
- That `docker compose down -v` wipes your database volumes — learned this the hard way

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
Dashboard:  http://localhost:3000  (admin / admin)
Metrics:    http://localhost:9090
Raw metrics: http://localhost:8000/metrics
```

---

## Environment Variables

```bash
ALCHEMY_WS_URL=wss://eth-mainnet.g.alchemy.com/v2/your_key   # Live Ethereum network connection
COINMARKETCAP_API_KEY=your_key                                 # ETH price in USD
DATABASE_URL=postgresql://monitor:monitor@localhost:5432/txmonitor  # Where transactions are stored
PROMETHEUS_PORT=8000                                           # Port that exposes live metrics
```

---

## What's Next

- Alert when the live stream goes silent for more than 60 seconds
- Nightly database backups on a schedule
- Log rotation for long-running deployments
- Track the same wallet across more than one network

---


## Project Structure

```
src/
├── main.py
├── ingestion/
│   ├── alchemy_ws.py
│   ├── stream_manager.py
│   └── price_feed.py
├── filters/
│   ├── value_filter.py
│   ├── gas_filter.py
│   ├── contract_filter.py
│   └── filter_chain.py
├── analysis/
│   ├── anomaly.py
│   └── recirculation.py
├── storage/
│   ├── db.py
│   └── schema.sql
├── dashboard/
│   └── dashboard.py
└── metrics/
    └── metrics.py
demo/
├── demo_data.py
├── demo_runner.py
└── run_demo.py
k8s/
monitoring/
└── prometheus.yml
.github/workflows/ci.yml
docker-compose.yml
Dockerfile
```

---

*Career changer from manufacturing. Learning in public. Building real things.*
