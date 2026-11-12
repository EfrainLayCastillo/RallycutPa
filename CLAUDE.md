# RallycutPa

CLI local (Mac) que convierte grabaciones largas de pádel con cámara fija wide en highlights: partido limpio sin tiempos muertos, clips por rally y reel top N (horizontal y 9:16).

## Fuente de verdad

- `docs/brainstorm.md`: problema, restricciones confirmadas, pipeline y decisiones. Léelo antes de proponer cambios.

## Idioma

- Inglés: código, nombres de módulos, flags del CLI, commits (Conventional Commits).
- Español: `README.md`, `docs/` y comunicación con el usuario.

## Reglas técnicas

- El original nunca se reencoda: los cortes del master van con `ffmpeg -c copy`. Solo los exports "share" se reencodan.
- El análisis corre sobre proxies de baja resolución, nunca sobre el original.
- Movimiento dentro del ROI de la cancha es la señal principal; el audio solo confirma (se oyen otras canchas).
- Encode con VideoToolbox nativo; Docker solo para aislar dependencias de análisis.
- Sin ML hasta que la heurística esté medida contra ground truth y se quede corta.

## Ahorro de tokens

- Cambia archivos con `Edit`; `Write` solo para archivos nuevos.
- Limita salidas largas (`| tail -n 20`, `-loglevel error` en ffmpeg).
- No proceses videos completos para probar: usa fragmentos cortos de muestra.
