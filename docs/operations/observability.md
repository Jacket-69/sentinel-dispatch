# Observabilidad

## Logs estructurados

`structlog` con output JSON. Eventos namespaced (`triaje.*`, `dispatch.*`, `astar.*`, `auth.*`, `api.*`).

```json
{
  "ts": "2026-05-06T17:32:11Z",
  "level": "info",
  "service": "dispatch",
  "event": "dispatch.created",
  "request_id": "abc123",
  "incident_id": "I-0042",
  "unit_id": "U03",
  "category_mpds": "Echo",
  "eta_seconds": 312
}
```

Reglas: un evento por línea, `request_id` propagado, sin datos sensibles.

## Métricas

`prometheus-client` expuesto en `/metrics`:

- `sentinel_dispatch_dispatches_total{category}` — counter por categoría MPDS.
- `sentinel_astar_duration_seconds` — histogram de tiempo de ruteo.
- `sentinel_dispatch_latency_seconds` — histogram extremo a extremo.
- `sentinel_unit_state{unit_id, state}` — gauge.

## Health checks

- `/healthz` — liveness (proceso responde).
- `/readyz` — readiness (BD conectada, grafo OSM cargado).

## Métricas DORA — referencia, no medidas

Las cuatro métricas DORA (Deployment Frequency, Lead Time, Change Failure Rate, Time to Restore) están documentadas como referencia en la metodología general. **No se miden formalmente en este proyecto** porque n=2 personas y ≤5 deploys reales producen ruido estadístico (ver `Metodología aplicada.md` del vault).

## Sin Sentry en v1

Excepciones se loggean estructuradas y se revisan en archivo. Sentry es opcional si después se quiere centralizar.
