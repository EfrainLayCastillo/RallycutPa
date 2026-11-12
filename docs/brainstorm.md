# Brainstorm: RallycutPa

Highlights automáticos de partidos de pádel grabados con una cámara fija y wide. Uso y comandos: [`README.md`](../README.md).

## Objetivo

A partir de un partido de ~1:30–2 h, generar:

1. **Reel de highlights**: top N rallies (por defecto 6), en horizontal y en vertical 9:16. Es la prioridad.
2. **Clips por rally** y **partido limpio** (sin tiempos muertos). Secundarios: necesitan una detección mucho más precisa que la del reel.

El reel tolera perder rallies (recall bajo), pero no tolera tiempo muerto (necesita precisión alta). El partido limpio es lo contrario. Por eso se miden por separado.

## Restricciones

| Tema | Decisión |
|---|---|
| Fuentes | GoPro y celulares en horizontal, H.264 (también AV1 en descargas). Ingest decide con `ffprobe`, no por marca. Los celulares pueden grabar con frame rate variable: los tiempos se toman del PTS, no del índice de frame. |
| Cámara | Fija, pegada al vidrio de fondo, a baja altura, detrás de una pareja. La pareja cercana sale grande y de espaldas, y desaparece cuando se acerca al fondo. La lejana sale chica y de frente. |
| Canchas vecinas | Se ven por los costados y se oyen. El ROI las excluye; el audio no sirve para separarlas. |
| Calidad | El master no se reencoda (`-c copy`), salvo que la fuente ya venga comprimida y con GOP largo (por ejemplo, exports a 720p con keyframes cada ~6 s): ahí se reencoda, porque la pérdida no se nota. Los exports "share" siempre se reencodan. |
| Entorno | Mac local. El análisis corre en Docker (`rallycutpa-tools`). El encode final conviene hacerlo nativo con VideoToolbox, que Docker no puede usar. |
| Grabación recomendada | ≥1080p (ideal 4K para el crop 9:16), sin overlays, encuadre que deje fuera las canchas vecinas. |

## Pipeline

```
prepare → signals → segment (calibrar → detectar → puntuar) → export
```

| Etapa | Estado | Cómo |
|---|---|---|
| prepare | ✅ | Proxy 640 px @ 5 fps + audio 16 kHz mono. Falta: concatenar capítulos GoPro (`GH01…`, `GH02…`). |
| signals | ✅ | Diferencia de frames en el ROI, separada en mitad cercana y lejana; vibración (phase correlation); cambios del marcador si hay overlay; envolvente de audio y golpes. |
| segment | ✅ | Actividad normalizada + histéresis. El umbral se **calibra solo** según la cantidad esperada de puntos (ver abajo). |
| score | ✅ | Ranking promedio de duración, pico de movimiento, golpes y pico de audio al cierre (festejo). |
| export | ✅ parcial | Reel top N y clips en horizontal. Faltan el crop 9:16 y VideoToolbox nativo. |

### Calibración por puntos esperados

Si no se sabe cuántos rallies hay, se usa un prior basado en el partido típico. Un partido amateur de 1:30 h tiene ~2.5 sets × ~9.5 games × ~6.5 puntos ≈ 155 puntos, o sea **~1.7 puntos/min**.

Para un video de D minutos se esperan `D × points_per_min` rallies. El umbral `on` (con `off = on × off_ratio`) se elige para que la cantidad detectada quede lo más cerca posible de ese número. Esto evita fijar umbrales a mano por video o por iluminación. `points_per_min` es configurable por si se juega a otro ritmo (pro ~2, recreativo ~1.2).

### Crop vertical 9:16 (pendiente)

- Ventana a altura completa, desplazada solo en X y siguiendo el centroide del movimiento en el ROI, con suavizado fuerte.
- El centroide se pondera hacia la pareja lejana (caras y festejos), para que la cercana, grande y de espaldas, no lo domine.
- Si la señal es pobre, crop centrado fijo.
- A 720p la ventana mide 405×720 y se ve blanda; se necesita ≥1080p.

## Medición

Etiquetas manuales en `labels.csv` (`rally` / `dead`) junto a cada video. Métricas:

- **reel_precision**: de los segundos etiquetados que caen dentro del reel, qué parte es rally. Es la métrica principal.
- **rally_cov**: qué parte del tiempo `rally` queda dentro de algún clip.
- **dead_leak**: qué parte del tiempo `dead` se cuela en algún clip.

`scripts/rc sweep` busca los mejores parámetros contra esas etiquetas.

## Hallazgos (2026-11-12, video de prueba pegado al vidrio, 720p, 18:36 min, 11 tramos etiquetados)

| Config | rally_cov | dead_leak | reel_precision (top 6) |
|---|---|---|---|
| Umbral fijo sensible | 100% | 99% | — |
| Umbral fijo estricto | 41% | 10% | — |
| **Auto 1.7 puntos/min (actual)** | 69% | 66% | **89%** |

- **El reel funciona razonablemente; el partido limpio no.** El ranking pone arriba los rallies reales. Pero, con movimiento por diferencia de frames, caminar al saque o ir a buscar la pelota se ve igual que jugar, así que los bordes de cada rally arrastran tiempo muerto.
- **El audio no separa.** Los golpes de esta cancha no se destacan sobre las vecinas: 0.2–0.9 "golpes"/s tanto en rally como en tiempo muerto. Se desactivó `min_hits`.
- **Sin vibración.** Con este montaje, los pelotazos contra el vidrio no se notan en la imagen.
- **Pelota por color + movimiento: descartado.** A 720p la pelota mide 2–3 px; la camiseta amarilla, la piel y la compresión generan tantos falsos positivos como verdaderos.
- **Pocas etiquetas.** Hay 31 s etiquetados dentro del reel; los números orientan, pero todavía no son concluyentes.
- Descartados: `auto-editor` (no tiene ROI, usa audio global y su binario de Linux no corre en arm64), y quitar metadatos para reducir peso (el ahorro es de KB).

## Próximos pasos

1. **Más etiquetas**: ≥20 tramos por clase, repartidos en todo el partido, idealmente de una grabación propia a ≥1080p.
2. **Recortar los bordes del rally** para el partido limpio. La heurística quedó medida y no alcanza, así que corresponde ML:
   - YOLO para personas: velocidad y pose de los jugadores (split-step y swing ≠ caminar). Ojo con la licencia AGPL de ultralytics.
   - Tracking de pelota (TrackNet o YOLO con un modelo de pelota): la señal más directa de "pelota en juego", pero exige ≥1080p.
3. Crop 9:16 y encode nativo con VideoToolbox.
4. Concatenar capítulos GoPro en `prepare`.

## Preguntas abiertas

- ¿Una cámara por partido o varias con sync multi-ángulo? Asumido: una.
- ¿Integración con MatchPa (subir highlights al partido)? Fuera del MVP.
