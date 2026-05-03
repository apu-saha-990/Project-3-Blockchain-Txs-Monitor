# Real-Time Blockchain Transaction Monitor

A system that watches live money movements on the Ethereum network, spots anything unusual, and sends an alert before anyone has to go looking.

---

## What Problem Does This Solve

Money moves on the Ethereum network every second. Most of it is invisible unless you build something to watch it. If someone moves a huge amount, if fees suddenly shoot up, or if the same money keeps going in circles between accounts — you want to know right now, not the next morning.

This project watches the network live. The moment something unusual happens, it catches it and sends an alert. No manual checking. No surprises.

---

## How It Works

1. The system connects to the Ethereum network and starts receiving every transaction the moment it appears — before it's even confirmed
2. Every transaction goes through four questions in order: how big is it, how expensive are the fees, is it going to a known service, and is it being sent through a hidden channel to avoid being seen publicly
3. Based on those answers, every transaction gets a label: ignore it, note it, flag it, fee alert, or critical — always in that order, most serious wins
4. Two separate watchers run on every transaction at the same time — one watches whether the number of transactions suddenly jumps, the other watches whether fees have been running high for a while
5. A third watcher maps where money is going between accounts — if it spots money coming back to where it started, it flags the whole loop
6. Everything that gets flagged is saved to a database so it can be looked at later
7. When something hits the threshold, an alert fires to Discord or Slack
8. When you start the tool it asks you which view you want — a live scrolling feed of everything, or a dashboard with panels and running totals

---

## What's Built

**Live transaction feed** — connects to the Ethereum network and picks up every transaction the moment it appears, before it's confirmed. Everything else in the system flows from this.

**Four questions, five labels** — every transaction gets put through four questions one after another. The answers decide how serious it is. The labels go from "ignore" up to "critical." The most serious label always wins — a huge transfer will always be critical, even if the fees are normal.

**Two separate unusual-activity watchers** — there are two watchers running side by side, each looking for a different problem.

The first one watches how many transactions are coming in. It compares the last 60 seconds against the last 10 minutes. If the last 60 seconds is running five times faster than normal, it fires an alert. Then it waits a full minute before it can fire again — so you get one clear alert, not a flood of them.

The second one watches fees. It doesn't care about one expensive transaction — it watches the average fee across the last several minutes. Only if fees have been high for a sustained period does it fire. One outlier won't trigger it.

**A money loop detector** — keeps a live map of where money is moving between accounts. Every time a new transaction comes in, it checks whether that money has now returned to where it started — like A pays B, B pays C, C pays A back. It looks back up to five steps and up to one hour. Once it spots a loop, it marks it so the same loop doesn't get reported over and over.

**Hidden transaction detection** — some transactions are sent through private channels to avoid being seen publicly. The system spots these by looking for a specific combination: real money moving but zero fees paid. That only happens on a private channel. Those get flagged automatically.

**A database built for time-based questions** — everything the system finds gets saved in a database that's designed to answer time-based questions quickly. "What happened between 2am and 4am?" is fast to answer even when there's a lot of data.

**Two display modes — you pick when you start** — when you launch the tool it asks which view you want. Mode A is a raw scrolling feed — every flagged transaction appears in colour as it arrives, unusual events in a different colour. Mode B is a dashboard — panels showing totals, fee averages, recent alerts, and money loops, all updating live. Same information, two different ways to see it.

**A live numbers feed** — a running count of every transaction, alert, and unusual event is kept up to date at all times. Other tools can check these numbers automatically without needing to get into the system directly.

**Alerts** — when something crosses a threshold, an alert goes straight to Discord or Slack.

**Demo mode — no account needed** — 70 real transactions from the Ethereum network, replayed through the full system. You don't need an account or any credentials. Unusual events and money loops are built into the dataset so the demo always produces real output, not a blank screen.

---

## A Bug I Found

**Bug 1 — The database refused to start**

When I added the money loop detector, I needed the database to reject duplicate loop records — the same loop should only be saved once. The obvious way to do that was to tell the database to reject any record that matched one already saved. I added that rule, ran the setup, and the database crashed on startup.

The error message didn't mean much to me at first. I went and read how this particular database works under the hood. It turns out it automatically splits data into chunks based on time — and that splitting comes with a rule: any reject-duplicates check must include the time column, or the database can't make it work across all the chunks. My check was on the loop identifier alone. So it refused to start.

The fix was to remove the rule from the database entirely and handle it in the code instead. Before saving a loop, the code now checks whether that loop has already been saved — and only saves it if it hasn't.

```
-- broken — reject-duplicates rule on loop ID alone, database refuses it
path_hash TEXT NOT NULL UNIQUE,

-- fixed — rule removed, the check now happens in the code
path_hash TEXT NOT NULL,
```

```python
# check first, only save if it hasn't been seen before
existing = await conn.fetchval(
    "SELECT id FROM recirculation_paths WHERE path_hash = $1", path_hash
)
if not existing:
    await conn.execute(insert_query, ...)
```

The lesson: some databases have rules that only apply to how they store data. I learned to check those rules before designing a table around them.

---

**Bug 2 — The dashboard was running but showing nothing**

After I got the dashboard working, I moved one config file from a subfolder to the main project folder to tidy up the structure. Everything started without errors. But when I opened the dashboard, all the charts were flat lines. Nothing.

I checked whether data was being collected. It was. I checked whether the database was running. It was. Everything looked fine. The problem turned out to be a single dot in a file path.

When the config file was in a subfolder, the path that pointed to it used `../` to go one level up. When I moved the file to the main folder, that path now pointed somewhere that didn't exist. The system started anyway — it doesn't tell you when a path is wrong, it just loads nothing. So the dashboard had no config, collected no data, and showed nothing. Silently.

```
# broken — path still pointing to old subfolder location
- ../monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

# fixed — path updated to match new location
- ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
```

The lesson: a system that starts without errors doesn't mean everything loaded. When something looks healthy but produces nothing, check the file paths first.

---

## How I Built This

I came from a factory and manufacturing background.

I use AI (Claude) throughout development — as a learning tool, code reviewer, and debugging partner. Every error message went back to Claude. The decisions are mine — what to build, how to put the pieces together, what broke, and how I fixed it.

I made every call: two display modes so the same tool works as a live feed or a dashboard without needing two separate tools, two separate unusual-activity watchers because a sudden burst of transactions and a long period of high fees are different problems that need different logic, a one-minute cooldown on alerts so the system fires once clearly rather than flooding a channel. Each of those decisions came from running the system and finding out what didn't work.

I built this in phases over several weeks. Each phase had to work before the next one started. The live feed came first, then the filters, then the database, then the dashboard, then the demo mode. Nothing was theoretical — every part was tested against real network traffic before moving on.

The systems run. The tests pass. I can demo everything live.

---

## What I Learned

- Transactions appear on the network before they're confirmed — that waiting period is where the useful signals are, not after they're locked in
- If any step in a fast-moving pipeline has to wait before it can continue, the whole thing falls behind — every step has to be able to run without holding up the next one
- Some databases that split data by time have rules that normal databases don't — duplicate checks that work fine usually can fail silently here (see Bug 1)
- A system starting without errors doesn't mean it loaded its config — wrong file paths fail without telling you (see Bug 2)
- The cooldown on an alert matters as much as the alert itself — without it, one spike produces hundreds of identical messages and the alert channel becomes useless
- How wide a time window you set for detecting money loops determines what you catch — too wide and you get false alarms, too narrow and slow patterns slip through
- A code checker flagged a duplicate entry in a data structure that ran fine when I tested it — the checker found it, the running system didn't
- The command that shuts down the system can also delete the database at the same time if you use the wrong flag — learned this the hard way

---

## Running It

**Local setup:**

```bash
docker compose up -d
docker exec -i txmonitor-db psql -U monitor -d txmonitor < src/storage/schema.sql
python3 -m src.main
```

**Demo mode — no account or API key needed:**

```bash
python3 demo/run_demo.py --mode B --speed 5
```

**For teams running this on a shared server rather than one machine, a full guide is in `kubernetes/COMMANDS.md`. Quick start:**

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
Dashboard:   http://localhost:3000  (admin / admin)
Metrics:     http://localhost:9090
Raw metrics: http://localhost:8000/metrics
```

---

## Environment Variables

```bash
ALCHEMY_WS_URL=wss://eth-mainnet.g.alchemy.com/v2/your_key   # Live Ethereum network connection
COINMARKETCAP_API_KEY=your_key                                 # ETH price in USD
DATABASE_URL=postgresql://monitor:monitor@localhost:5432/txmonitor  # Where data is stored
PROMETHEUS_PORT=8000                                           # Port that exposes live numbers
```

---

## What's Next

- **Alert when the live feed goes silent** — if no transactions arrive for 60 seconds, something has broken. Right now there is no alert for that. Without one, a dropped connection could go unnoticed for hours.

- **Automatic daily backups** — the database grows every day. A scheduled backup means nothing is lost if the machine has a problem. Without it, all stored history could disappear in one failure.

- **Log file management** — log files grow without limit on a long-running system. Keeping only recent logs and clearing old ones stops the machine from quietly running out of storage over time.

- **Track the same wallet across more than one network** — right now the system only watches Ethereum. Money can move across multiple networks to break the trail. Following it across networks is the biggest gap in what this system can currently detect.

- **Audit logging** — every time the system starts, stops, or has its settings changed, that should be recorded with a timestamp. In any environment where you need to account for what happened and when, this is not optional.

- **Automated checks on the detection logic** — the filters and unusual-activity watchers have clear inputs and outputs. Writing automated checks that verify they behave correctly under edge cases — a sudden burst of activity, a fee that sits just below the trigger point — would make it safe to change the logic without accidentally breaking something.

---

## Tech Stack

| What it does | Technology |
|---|---|
| Connects to the Ethereum network and streams transactions | Alchemy WebSocket API |
| Runs the pipeline, filters, and detectors | Python 3 |
| Stores transactions, blocks, and alerts by time | TimescaleDB |
| Keeps a live count of activity for external tools to read | Prometheus |
| Live dashboard and charts | Grafana |
| Routes alerts to Discord and Slack | Alertmanager |
| Packages the system so it runs the same everywhere | Docker + Docker Compose |
| Runs the system across a shared server cluster | Kubernetes (minikube) |
| Fetches live ETH price in USD | CoinMarketCap API |
| Runs automated checks on every code push | GitHub Actions |

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
