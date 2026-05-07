---
adr: 0005
title: Deploy demo vía Cloudflare Tunnel desde PC local con mitigaciones de resiliencia
status: accepted
date: 2026-05-06
deciders: Benjamin López
tags: [adr, deploy, devops, demo]
---

# ADR 0005 — Deploy demo vía Cloudflare Tunnel desde PC local

## Contexto

Sentinel-Dispatch se defiende oralmente al final del semestre 2026-S1 con **demo en vivo**. Benjamin **no tiene laptop**, así que la demo debe correr en su PC de escritorio (`GLaDOS`) en casa, expuesta públicamente para que el profesor pueda interactuar desde la sala de defensa.

Restricciones reales:

- Equipo de 1–2 personas; tiempo de desarrollo escaso.
- Presupuesto: prefiere $0 si no compromete la defensa.
- Sin laptop → si el PC se cuelga durante la defensa, no hay backup local.
- La defensa es un **evento puntual** de ~30 min; no se necesita 24/7 sostenido todo el semestre.

Opciones evaluadas: Fly.io paid (~$5–10 USD), Cloudflare Tunnel desde PC ($0), Oracle Cloud Always Free ARM ($0 con setup pesado).

## Decisión

Usamos **Cloudflare Tunnel** (`cloudflared`) desde el PC de Benjamin, exponiendo `http://localhost:8000` como `*.trycloudflare.com` (efímero) o un subdominio fijo si Benjamin tiene dominio propio.

Acompañado de **mitigaciones de resiliencia** explícitas:

1. **Tunnel probado al menos 1 semana antes de la defensa**, no el día de.
2. **UPS** si está disponible (cualquier UPS de gama baja sostiene 5–10 min, suficiente para sobrevivir cortes breves).
3. **Screencast pre-grabado** de la demo funcionando (2–3 min mostrando triaje → A* → despacho), almacenado en el celular y en Google Drive. **Fallback del fallback**: si todo falla en vivo, se proyecta el video y se narra encima.
4. **Acceso remoto al PC desde celular** vía **Tailscale** (app móvil + nodo Tailscale en `GLaDOS`); permite reiniciar la app/tunnel desde la sala de defensa si algo se cuelga.
5. **Cron healthcheck** local: cada 5 min `curl /healthz`; si falla, reinicia el contenedor con `docker compose up -d`.
6. **`docker-compose.yml`** con servicio `app` + servicio `cloudflared` lado a lado, ambos con `restart: unless-stopped`.

### Setup operativo

Pasos detallados en [`scripts/cloudflared-setup.md`](../../../scripts/cloudflared-setup.md). Resumen:

```bash
# 1. Levantar app + cloudflared
docker compose up -d

# 2. Obtener URL pública
docker logs sentinel-cloudflared | grep trycloudflare.com

# 3. Verificar
curl https://<random>.trycloudflare.com/healthz
```

Para la defensa se usa una URL **estable** mediante Cloudflare Tunnel con cuenta Cloudflare gratis + dominio propio (alternativa a la URL efímera). Documentado en el playbook.

## Alternativas consideradas

### A. Fly.io paid (~$5–10 USD totales por 2 meses)
- **Pros:**
  - 24/7 sin depender del PC, luz o internet de casa.
  - IP estática + SSL automático.
  - Setup en ~30 min con `flyctl deploy`.
- **Contras:**
  - Cuesta dinero (poco pero >0).
  - Requiere tarjeta internacional (Stripe).
  - Imagen Docker tiene que caber en RAM de la VM elegida (256 MB free; el grafo OSM probablemente exige paid de 1 GB).
- **Por qué se descarta:** Benjamin prefiere $0 y la combinación PC + mitigaciones cubre el riesgo razonable.

### C. Oracle Cloud Always Free ARM
- **Pros:**
  - 24 GB RAM gratis para siempre; sobra para el grafo y todo.
  - 24/7 garantizado por Oracle.
  - $0 sostenido.
- **Contras:**
  - **Capacity ARM Ampere saturada** desde 2022; conseguir instancia puede tomar días o semanas de retry.
  - Setup honesto: 2–6 horas (VCN, security groups, SSL Let's Encrypt manual, Ubuntu ARM update, Docker ARM).
  - Política de "idle reclamation": Oracle puede reclaim instancias inactivas; mitigable con tráfico cron pero hay que recordarlo.
  - ARM compatibility: Python puro está OK, pero rompe si en F3 aparece una lib con binding nativo no-ARM.
  - Tarjeta de crédito para verificación.
  - **ROI académico nulo**: el profesor no evalúa la infra; las 6 h de setup se restan al A*.
- **Por qué se descarta:** complejidad y tiempo de setup superan el beneficio para un proyecto de 2 meses con defensa puntual. Vale para proyectos long-term (Proyecto de Título) o aprendizaje cloud para CV.

### D. Tailscale Funnel (en lugar de Cloudflare Tunnel)
- **Pros:**
  - También $0, también desde PC casa.
  - Misma cuenta Tailscale ya usada para acceso remoto al PC.
- **Contras:**
  - Tailscale Funnel exige plan personal (gratis pero con límites de bandwidth).
  - Cloudflare tiene mejor performance global y URL más "presentable" (`*.trycloudflare.com` o dominio).
- **Por qué se descarta:** Cloudflare está más maduro para exposición pública; Tailscale lo usamos solo para acceso remoto al PC (mitigación 4 arriba).

### E. ngrok free
- **Pros:** familiar, simple.
- **Contras:**
  - Free tier: URL random cada arranque, throttling de 40 conn/min, y a veces interstitial de "ngrok presents".
  - Cloudflare Tunnel free no tiene esos límites para uso casual.
- **Por qué se descarta:** Cloudflare es estrictamente mejor en free tier.

## Consecuencias

### Positivas
- **Costo $0**.
- **Setup rápido**: el playbook deja todo levantado en ~15 min de tiempo real.
- Mismo `docker-compose.yml` sirve para desarrollo local y para demo (solo el servicio `cloudflared` cambia entre OFF en dev y ON en demo).
- Aprendizaje útil de Cloudflare Tunnel (transferible a otros proyectos).

### Negativas / costo
- **Disponibilidad acoplada al PC + internet de casa + luz** durante la defensa. Las 5 mitigaciones documentadas reducen el riesgo a aceptable, no a cero.
- **PC debe quedar encendido** las horas previas a la defensa (consumo eléctrico marginal, no operacional).
- Si el PC físico falla irrecuperablemente justo antes de la defensa, el screencast (mitigación 3) es el último recurso.

### Neutras
- La URL pública es `*.trycloudflare.com` (efímera) por defecto; estable solo si se vincula dominio propio.
- El servicio `cloudflared` corre como contenedor Docker, no como servicio systemd, para mantener el setup portable.

## Cumplimiento / verificación

- `docker-compose.yml` levanta app + cloudflared con `restart: unless-stopped`.
- `scripts/cloudflared-setup.md` documenta el playbook reproducible.
- `scripts/healthcheck.sh` + cron entry verifica vida cada 5 min.
- `docs/operations/runbook.md` incluye sección "Demo en vivo" con: pre-flight check (T-24h, T-2h, T-30min), comandos para reiniciar desde el celular, y procedimiento de fallback al screencast.
- **Drill de defensa**: ensayar la demo completa desde la sala de defensa (o equivalente con WiFi distinto) al menos 1 semana antes; documentar tiempos y problemas.

## Referencias

- [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [Tailscale Funnel](https://tailscale.com/kb/1223/funnel/)
- [Fly.io pricing](https://fly.io/docs/about/pricing/)
- [Oracle Cloud Always Free](https://www.oracle.com/cloud/free/) — referencia para conocer el tier
- [ADR-0001 — Stack](0001-stack.md) (deploy es el último eslabón)
- `scripts/cloudflared-setup.md` (playbook operativo)
