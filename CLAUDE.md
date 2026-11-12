# RallycutPa

Herramienta local (Mac + Docker) que convierte grabaciones de pádel con cámara fija en highlights: reel top N, clips por rally y partido limpio.

## Fuentes de verdad

- `README.md`: uso, flujo, detección, métricas y config.
- `docs/brainstorm.md`: decisiones, hallazgos y próximos pasos. Léelo antes de proponer cambios.

## Estructura

- `scripts/highlights VIDEO`: de punta a punta (quick start). `scripts/rc <cmd>`: cada etapa por separado, dentro del contenedor `tools`.
- `scripts/*.py`: scripts uv con dependencias inline (`chapters`, `calibrate`, `signals`, `segment`, `export`, `sweep`, `labels`).
- `config/camera-*.json`: plantilla y configs fijas; por defecto la config se deriva del encuadre (`calibrate` → `work/camera.json`).
- Una grabación por carpeta en `media/<date>/`; las partes de una grabación se unen en `work/source.mp4`.
- `tests/`: pytest; se corre con `scripts/rc test`.

## Idioma

- Inglés: código, flags y commits (Conventional Commits).
- Español: `README.md`, `docs/` y comunicación con el usuario.

## Reglas técnicas

- El original no se modifica. El análisis corre sobre el proxy; los exports se reencodean.
- El movimiento en el ROI es la señal principal; el audio solo confirma (se oyen otras canchas).
- Los cambios de detección se validan con las métricas contra `labels.csv` (`segment`, `sweep`), no a ojo.
- La heurística ya quedó medida y no alcanza para los bordes del rally: el siguiente paso es ML (YOLO/TrackNet).
- Toda función nueva lleva su prueba; `scripts/rc test` tiene que pasar antes de commitear.

## Ahorro de tokens

- Lo que se repite va a un script en `scripts/`, no a comandos sueltos.
- Limita salidas (`| tail`, `-v error` en ffmpeg).
- Prueba con fragmentos cortos, no con videos completos.
