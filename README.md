# ATLAS

ATLAS is a zero-dependency paper-trading prototype based on the CSI ORIGIN 2026 Problem Statement 3 build document.

## Run

```powershell
npm start
```

Open http://localhost:3000.

The demo uses a deterministic market simulator so it runs without exchange, database, Redis, or Claude credentials. The API mirrors the planned operator contract and keeps the propose/dispose boundary explicit:

- `GET /agent/status`
- `POST /agent/kill`
- `POST /agent/resume`
- `GET /agent/decisions`
- `GET /agent/decisions/:id/receipt`
- `GET /portfolio`
- `GET /market`
- `GET /metrics`
- `GET /config/risk`
- `PUT /config/risk`
- `POST /stress-test`

The simulator advances through perceive, interpret, classify regime, allocate/risk-check, execute, observe outcome, and adapt on a 4-second cadence. It is paper trading only.
