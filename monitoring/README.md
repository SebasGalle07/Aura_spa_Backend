# Observabilidad

Este directorio deja listo un stack local de Prometheus y Grafana para consumir las metricas del backend.

## Endpoints expuestos por el backend

- `/metrics`
- `/healthz`

## Levantar Prometheus y Grafana

Desde `Aura_spa_Backend/monitoring`:

```powershell
docker compose up -d
```

Servicios:

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Credenciales iniciales de Grafana:

- usuario: `admin`
- clave: valor de `GRAFANA_ADMIN_PASSWORD`; si no lo defines localmente, usa `AuraSpa2026!`

Prometheus consulta `/metrics` con token Bearer. El backend debe tener configurado el mismo valor en `METRICS_TOKEN`.

## Targets configurados

- `host.docker.internal:8080` para backend local
- `https://aura-spa-backend-yujwbtz45a-uc.a.run.app/metrics` para la instancia desplegada

Si cambias la URL de Cloud Run, actualiza `prometheus/prometheus.yml`.
