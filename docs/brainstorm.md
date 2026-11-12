# Brainstorm: RallycutPa

Uso, detección y métricas: [`README.md`](../README.md). Acá van el porqué, lo aprendido y lo que falta.

## Objetivo

De un partido de 1:30–2 h con cámara fija:

1. **Reel top 6** (horizontal y 9:16). Es la prioridad. Necesita precisión: nada de tiempo muerto.
2. **Clips por rally y partido limpio.** Son secundarios. Necesitan recall y bordes exactos.

## Decisiones

| Tema | Decisión | Por qué |
|---|---|---|
| Cámara | Fija, pegada al vidrio de fondo, baja | Es el montaje real del club. La pareja cercana sale grande y a veces fuera de cuadro; la lejana, chica y de frente. |
| ROI | Polígono por posición de cámara, movimiento separado cerca/lejos | Las canchas vecinas se ven por los costados; la pareja cercana domina los píxeles. |
| Audio | Solo confirma, desactivado por defecto | Se oyen las canchas vecinas: los golpes propios no se destacan. |
| Umbral | Calibrado por puntos esperados (1.7/min) | Evita ajustarlo a mano por video o por iluminación. |
| Color | LUT por fabricante (GoPro / DJI) en el proxy y los exports | El log tiene poco contraste y afecta la detección. El original no se toca. |
| Master | `-c copy`, salvo fuentes ya comprimidas con GOP largo | Con keyframes cada ~6 s el corte sería impreciso, y reencodear no se nota. |
| Entorno | Análisis en Docker; encode final con VideoToolbox nativo | Docker en Mac no accede a VideoToolbox. |
| Grabación | ≥1080p (ideal 4K), sin overlays ni canchas vecinas en cuadro | A 720p, el crop 9:16 queda en 405×720. |

## Hallazgos (2026-11-12)

- **El movimiento separa jugar de estar quieto, pero no de caminar.** Ir al saque o buscar la pelota mueve tanto como un rally. El ranking igual pone arriba los rallies reales: el reel tiene 89% de precisión, aunque medido sobre solo 31 s etiquetados.
- **Hay que sacrificar rallies para no colar tiempo muerto.** Con umbrales fijos, dejar el tiempo muerto en 0% obliga a perder el 64% del rally.
- **Descartado:**
  - detección de pelota por color (2–3 px a 720p, demasiados falsos positivos);
  - `auto-editor` (no tiene ROI y su binario no corre en arm64);
  - quitar metadatos para reducir peso (ahorra KB).
- **Sin vibración visible** con este montaje.

## Próximos pasos

1. Etiquetar ≥20 tramos por clase en una grabación propia a ≥1080p.
2. **Bordes del rally con ML**: la heurística ya quedó medida y no alcanza.
   - YOLO de personas con velocidad o pose (split-step y swing ≠ caminar). Ojo con la licencia AGPL de ultralytics.
   - Tracking de pelota (TrackNet): la señal más directa, pero exige ≥1080p.
3. Crop 9:16 que siga a la pareja lejana, con suavizado fuerte y fallback a crop centrado.
4. Encode nativo con VideoToolbox y concatenación de capítulos GoPro en `prepare`.
5. Validar el LUT de D-Log M con un clip real de la Osmo Action 5 Pro.

## Preguntas abiertas

- ¿Varias cámaras por partido (sync multi-ángulo)? Por ahora se asume una.
- ¿Integración con MatchPa? Fuera del MVP.
