# EIMS Benchmark Results (Sprint 11)

**Date:** 2026-09-10 07:40 UTC  
**Iterations:** 30 per endpoint (+3 warmup)  
**Seed:** 10,000 assets / 50,000 audit_logs / 20,000 telemetry_metrics / 20,000 windows_event_logs  
**Seed time:** 14.9s / **Bench time:** 21.6s  

## Results

| Endpoint | p50 (ms) | p95 (ms) | p99 (ms) | min (ms) | max (ms) | mean (ms) |
|---|---:|---:|---:|---:|---:|---:|
| Global Search (trigram) | 37.92 | 61.87 | 69.34 | 34.41 | 70.57 | 42.09 |
| Search Audit-only | 153.08 | 308.04 | 320.42 | 121.26 | 321.82 | 176.43 |
| Timeline (UNION ALL, no filter) | 216.71 | 270.06 | 290.38 | 157.21 | 294.65 | 211.78 |
| Timeline Critical only | 54.5 | 66.7 | 68.4 | 43.39 | 68.82 | 55.33 |
| Timeline Audit-only | 108.34 | 162.28 | 169.32 | 83.78 | 170.38 | 116.37 |
| Telemetry Metrics | 26.22 | 32.5 | 34.69 | 20.61 | 35.39 | 26.81 |
| Telemetry Winlogs | 21.91 | 24.46 | 24.73 | 19.55 | 24.74 | 21.89 |

## Methodology

- All queries run via FastAPI TestClient (full request lifecycle including Pydantic validation).
- Data seeded within a single DB transaction.
- 3 warmup iterations discarded before measurement.
- p50/p95/p99 calculated via linear interpolation.
- PostgreSQL connection pool at default warm state.
