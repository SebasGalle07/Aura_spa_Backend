# Observabilidad

Este directorio deja listo un stack local de Prometheus y Grafana para consumir las metricas del backend.

## Endpoints expuestos por el backend

- `/metrics`
- `/healthz`

## Metricas del proceso 4: PQRS

El backend expone metricas especificas para seguimiento del proceso PQRS:

- `aura_spa_service_case_events_total`: creacion, revision, beneficios otorgados y validaciones rechazadas.
- `aura_spa_service_case_status_transitions_total`: cambios de estado de cada PQRS.
- `aura_spa_service_case_benefit_events_total`: beneficios otorgados, reservados, usados, liberados o expirados.

Los dashboards provisionados incluyen:

- `Aura Spa - Monitoreo General`: vista general de backend, autenticacion, reservas, facturacion y PQRS.
- `Aura Spa - Proceso 4 PQRS`: vista enfocada en PQRS creadas, revisadas, rechazadas por validacion, beneficios otorgados, eventos por tipo de solicitud y transiciones de estado.

Grafana se configura con idioma por defecto `es-ES` y zona horaria `America/Bogota`. Si un usuario ya tenia una preferencia guardada en su perfil, debe cambiarla desde sus preferencias de usuario para ver la interfaz en espanol.

## Levantar Prometheus y Grafana

Desde `Aura_spa_Backend/monitoring`:

```powershell
docker compose up -d
```

Servicios:

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Dashboard general: `Aura Spa - Monitoreo General`
- Dashboard del proceso 4: `Aura Spa - Proceso 4 PQRS`

Credenciales iniciales de Grafana:

- usuario: `admin`
- clave: valor de `GRAFANA_ADMIN_PASSWORD`; si no lo defines localmente, usa `AuraSpa2026!`

Prometheus consulta `/metrics` con token Bearer. El backend debe tener configurado el mismo valor en `METRICS_TOKEN`.

## Targets configurados

- `host.docker.internal:8080` para backend local
- `https://aura-spa-backend-yujwbtz45a-uc.a.run.app/metrics` para la instancia desplegada

Si cambias la URL de Cloud Run, actualiza `prometheus/prometheus.yml`.
