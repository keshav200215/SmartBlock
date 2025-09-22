AWL: AML Wallet Risk Scoring via Oracle (wfchain + BTC/ETH data)

Real-time AML risk checks for non-custodial wallets.
A CosmWasm smart contract on wfchain calls an off-chain Oracle, which queries an AWL (AML Wallet Logic) service to compute a risk score (1–10) and flag based on the wallet’s last 10–20 transactions (BTC/ETH). The Oracle then signs and updates the contract on-chain.

1) Why this project?

Non-custodial wallets lack centralized oversight; contracts can’t evaluate AML risk by themselves.

We enable smart contracts to query an Oracle for a risk rating in real time, using public datasets (BTC/ETH), unsupervised ML, and simple rules.

2) System Architecture
User / dApp
   │
   ▼
CosmWasm Contract (wfchain)
   │   (executes -> requests risk)
   ▼
Oracle-Service (Node/TS)
   │   (fetches last-20, calls AWL, signs result)
   ▼
AWL-Service (Python/FastAPI/ML)
   │   (features → IsolationForest + rules)
   ▼
Postgres (BTC/ETH samples) / CSV features


Risk fusion: score = 0.6 * ML + 0.4 * rules → risk (1–10); flag = risk ≥ 7.

3) Features & Modeling
BTC features (from last 20 movements)

moves, in_count, out_count

btc_in, btc_out, net_btc, net_ratio = |net|/(in+out)

median_dt_sec (burstiness)

ETH features (from last 20 movements + logs)

native_in_sum, native_out_sum, native_net, net_ratio

token_moves, tokens_touched

median_dt_sec

approvals (ERC-20 approvals parsed from logs)

Model

Unsupervised: IsolationForest over wallet features (no labels required).

Rules (examples): High net outflow (net_ratio > 0.9), bursty timing (median_dt_sec < 30s), many approvals (≥5), token churn.

4) Repo Layout
.
├─ code/
│  ├─ src/
│  │  ├─ awl_service/           # FastAPI service (ML scoring)
│  │  │  ├─ app.py              # API (/train, /score)
│  │  │  ├─ model.py            # train/load IsolationForest
│  │  │  ├─ features.py         # compute features from last-20
│  │  │  ├─ schemas.py          # pydantic IO models
│  │  │  └─ __init__.py
│  │  └─ oracle_service/        # (optional) Node/TS oracle code
│  ├─ models/                   # saved joblib model
│  └─ tests/                    # unit/integration tests
├─ data/                        # btc_wallet_features.csv, eth_wallet_features.csv (exported)
├─ docker/                      # Postgres scripts (optional)
├─ artifacts/
│  ├─ demo/                     # demo video
│  └─ arch/                     # slides/presentation
├─ .env                         # runtime configuration (paths, keys)
├─ requirements.txt             # FastAPI/ML deps
└─ README.md


If you keep Oracle in a separate repo, mirror the structure there. The artifacts/ folder follows hackathon guidelines.

5) Prerequisites

wfchain (CosmWasm/wasmd dev chain via Docker)

Node.js (for oracle-service, CosmJS)

Python 3.9+ (for AWL service; FastAPI + scikit-learn)

Postgres (optional at runtime if you already exported CSV wallet features)

6) Data Pipeline (one-time prep)

You can run the solution without live Postgres by training from CSV feature exports:

Load BTC/ETH samples to Postgres (dockerized), create views for last-20 & features.

Export:

\copy (SELECT * FROM btc_wallet_features) TO 'btc_wallet_features.csv' CSV HEADER
\copy (SELECT * FROM eth_wallet_features) TO 'eth_wallet_features.csv' CSV HEADER


Place both CSVs under ./data/.

(If you need the SQL/view scripts, see /docker or request the snippets.)

7) AWL-Service (FastAPI)
7.1 Configure env

Create .env in repo root:

BTC_FEATURES_CSV=./data/btc_wallet_features.csv
ETH_FEATURES_CSV=./data/eth_wallet_features.csv
MODEL_PATH=./code/models/awl_model.joblib
FLAG_THRESHOLD=7

7.2 Install & run
cd code
python3 -m venv .venv && source .venv/bin/activate
pip install -r ../requirements.txt
export PYTHONPATH=src
uvicorn awl_service.app:app --host 0.0.0.0 --port 8080 --reload

7.3 Train & Score (HTTP)
# train from CSVs (saves model to MODEL_PATH)
curl -X POST http://localhost:8080/train

# score (BTC example)
curl -s -X POST http://localhost:8080/score \
 -H 'Content-Type: application/json' \
 -d '{
  "chain":"btc",
  "last20":[
    {"block_timestamp":"2024-01-01 00:00:00 UTC","is_input":false,"amount_btc":0.5},
    {"block_timestamp":"2024-01-01 00:00:20 UTC","is_input":true,"amount_btc":0.49}
  ]
}'


Response

{ "chain":"btc", "risk":2, "flag":false, "reasons":["bursty timing"], "features":{...} }


API

POST /train → trains IsolationForest on CSVs.

POST /score → body { chain, last20[], approvals? } → { risk, flag, reasons, features }.

8) Oracle-Service (Node/TS) on wfchain

The Oracle:

Receives a risk request (from UI/contract event/Postman).

Finds last-20 for the wallet (from your DB or an indexer), computes ETH approvals if needed.

Calls AWL /score.

Signs the result with oracle mnemonic.

Executes contract OracleDataUpdate on wfchain.

8.1 Env (example)
RPC=http://localhost:26657
CHAIN_ID=testing
DENOM=ustake
PREFIX=wasm
CONTRACT_ADDR=wasm1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ORACLE_MNEMONIC="your words here"
AWL_URL=http://localhost:8080/score

8.2 Minimal request endpoint (sketch)
// POST /request-risk { chain, address, last20[], approvals? }
// 1) call AWL /score 2) sign payload 3) execute contract


Use @cosmjs/cosmwasm-stargate and a TS client generated by cosmwasm-ts-codegen from your contract schema.

9) Smart Contract (CosmWasm on wfchain)

Instantiate with { oracle_pubkey, oracle_key_type: "secp256k1" }.

Execute OracleDataUpdate with oracle-signed payload {chain, address, risk, flag, reasons, ttl}.

Verify signature against stored pubkey; update on-chain state.

Query exposes the latest oracle data for use in other contracts.

(Contract template derived from the hackathon sample; see sample-contract/.)

10) Demo Flow

Start services

wfchain Docker (wasmd)

AWL on http://localhost:8080

Oracle on http://localhost:8088

Upload + instantiate contract with oracle pubkey.

Trigger a tx / risk request (from dApp or Postman) supplying {chain, address}.

Observe

Oracle logs a call to AWL, signs, broadcasts OracleDataUpdate.

Show tx hash, then query contract to see {risk, flag, reasons} stored.

11) Testing

Unit tests: feature functions and rule scoring (code/tests/).

Integration: start AWL, run POST /train, then POST /score with sample payloads.

Contract: happy-path (valid signature), reject-path (wrong signer).

12) Troubleshooting

500 on /score: ensure .env points to correct CSV paths and run from repo root (export PYTHONPATH=src).

Model not found: call POST /train once (creates MODEL_PATH).

Oracle fails to broadcast: check RPC, CHAIN_ID, PREFIX, funded oracle address, and CONTRACT_ADDR.

Empty ETH approvals: ensure you loaded some eth-logs*.csv with non-empty topics.