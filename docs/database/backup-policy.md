# Política de backups

> **Estado:** versión académica simplificada. v1 corre en SQLite local; backup = copia del archivo.

## Qué se respalda

- `data/sentinel.db` — base operacional (estado de flota, incidentes, despachos, log).
- `data/graphs/coquimbo.graphml` — grafo OSM cacheado (regenerable, opcional).

## Frecuencia

- **Diaria** durante el desarrollo (`cron` local que copia a `~/backups/sentinel-dispatch/`).
- **Por entrega** un snapshot etiquetado con la versión académica.

## Retención

- Diarios: 7 días.
- Por entrega: indefinido (se mantienen los `vX.Y-fase`).

## Restauración

```bash
cp ~/backups/sentinel-dispatch/sentinel-YYYYMMDD.db data/sentinel.db
```

Probar restauración mensualmente. Backup no probado es fe.
