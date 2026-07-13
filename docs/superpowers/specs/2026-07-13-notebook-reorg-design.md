# Reorganización de notebooks SAMI — 4 → 3 notebooks narrativos

**Fecha:** 2026-07-13
**Rama:** `feature/analysis-notebooks`
**Objetivo:** Reordenar y re-encuadrar el análisis existente (4 notebooks) en 3 notebooks
narrativos. NB1 y NB2 son *reorganización pura* (sin análisis nuevo). NB3 se
**re-diseña** hacia un stack de NLP más simple.

Fuentes (ahora en `notebooks/arxiv/`): `eda_responses.ipynb`, `eda_meal.ipynb`,
`analysis_responses.ipynb`, `analysis_meal.ipynb`.

## Decisiones tomadas

| Tema | Decisión |
|---|---|
| Mapa de ciudades (4.2 de `eda_responses`) | **Va a NB2**, no a NB1. NB1 no tiene mapas. |
| Sección 9 (drop-off / reformulación) | Drop-off por categoría → NB2. **Reformulación (basada en similitud de embeddings) se elimina** (método "fancy"). |
| Outputs | **Se limpian todos.** Los notebooks se ensamblan sin outputs; el usuario los corre de arriba a abajo. |
| Paleta de color | **Se elimina por completo** (`from palette import *` y refs `AGUA/BLUES/bar_colors()`…). Charts caen a defaults de matplotlib. La paleta unificada se añade después. |
| Tradiciones de documentación | Se conservan: headers markdown por sección, comentario-pregunta-guía al inicio de cada celda de código, celdas de setup colapsadas, sin análisis en el setup. |

## Arco narrativo

NB1 frío y factual (solo "qué datos tenemos") → NB2 operativo, empieza la fricción
(abandono, categorías con peor satisfacción, primeras voces cualitativas) → NB3
humano/emocional, cierra con el mapa síntesis de necesidad + malestar.

## Dependencias de cómputo (clave del split)

- **NB1** — CPU. Solo `load_responses()` + `load_meal()`. Univariado.
- **NB2** — CPU. `+ load_messages()` (spine) + `mmc_entities`. Cruces, temporal,
  cualitativo, necesidades por diccionario. **Sin GPU, sin embeddings.**
- **NB3** — GPU. Embeddings (e5-large) + KMeans a nivel usuario + sentimiento.
  Toda la carga pesada vive aquí.

Cada notebook es **autocontenido y re-ejecutable**: su propio preámbulo de imports +
carga de datos + defs auxiliares necesarias (`MMC_LABELS`, `NON_TOPIC_CATS`, etc.),
porque ya no comparten un mismo kernel.

---

## NB1 — `01_eda_perfil_y_satisfaccion.ipynb`

**EDA puro: solo distribuciones univariadas. Sin cruces, sin eje temporal, sin lectura temática, sin mapas, sin word clouds.**

Setup: imports mínimos (numpy/pandas/matplotlib/seaborn), **sin palette**.
`df = load_responses()`, `meal = load_meal()`.

| # | Sección | Fuente (celda) |
|---|---|---|
| 1 | Data Load (respuestas) | eda_responses c6–7 |
| 2 | Data Quality (respuestas) | eda_responses c10–11 |
| 3.1 | Nacionalidad | eda_responses c15 |
| 3.2 | Género | eda_responses c17 |
| 3.3 | Edad (hist + cohortes) | eda_responses c19–20 |
| 3.4 | Responsabilidades de cuidado | eda_responses c22 |
| 4.1 | Ciudades — **solo conteo de usuarios por ciudad top** | eda_responses c26 |
| 5.1 | Tiempo fuera del país de origen | eda_responses c34 |
| 6.1 | Temas discutidos (frecuencia simple) | eda_responses c41 |
| 6.2 | Preguntas por usuario (tabla resumen) | eda_responses c43 |
| 6.3 | Encuesta enviada (share) | eda_responses c45 |
| — | Data Load + Quality (MEAL) | eda_meal c5, c7 |
| — | Utilidad percibida (univariado) | eda_meal c9 |
| — | Recomendaría (univariado) | eda_meal c11 |
| — | Canal de descubrimiento | eda_meal c13 |
| — | Longitud de recomendaciones (solo el dato) | eda_meal c16 |

**Excluido explícitamente** (va a NB2): antigüedad-por-ciudad (c27), mapa de ciudades
(c29–30), mapa origen→destino (c36–37), uso en el tiempo (c47), cross-cuts (c51/53/55),
word cloud (eda_meal c18), MEAL en el tiempo (eda_meal c20). También se retira
`analysis_meal` secciones 1–3 (duplican `eda_meal`).

**Objetivos:** (1) qué datos existen y su completitud; (2) quiénes son (demografía,
campo por campo); (3) dónde están (ciudad, tiempo fuera), sin combinar; (4) línea base
de satisfacción como conteos simples.

---

## NB2 — `02_analisis_general_comportamiento_necesidades.ipynb`

**Todo lo complejo que no es NLP: cruces, tendencias, cualitativo, necesidades, abandono.**

Setup: imports (sin palette) + `mmc_entities`. `df`, `meal`, `msgs = load_messages(df)`.
Defs auxiliares: `MMC_LABELS`, `NON_TOPIC_CATS`, helpers de cross-tab/heatmap.

Orden narrativo:

| Bloque | Contenido | Fuente (celda) |
|---|---|---|
| 1. Cruces demográficos/geográficos | Antigüedad por ciudad | eda_responses c27 |
| | Mapa de ciudades | eda_responses c29–30 |
| | Mapa origen → destino | eda_responses c36–37 |
| | Cross-cuts 7.1 género×nacionalidad, 7.2 engagement×ciudad, 7.3 edad×destino | eda_responses c51, c53, c55 |
| 2. Tendencias temporales | Uso del chatbot en el tiempo | eda_responses c47 |
| | Respuestas MEAL en el tiempo (acumulado + tendencia) | eda_meal c20 |
| 3. Voces cualitativas | Word cloud | eda_meal c18 |
| | Lectura temática de recomendaciones libres | analysis_meal c11 |
| 4. Necesidades | Más solicitadas (entidades/diccionario) | analysis_responses c17 |
| | Geografía por ciudad (nivel mensaje) | analysis_responses c19–20 |
| 5. Temporal de categorías | Categorías de necesidad en el tiempo (vs eventos) | analysis_responses c22–23 |
| 6. Perfil × categoría | Categoría × género / edad | analysis_responses c25–27 |
| 7. Profundidad y abandono | Engagement depth | analysis_responses c29 |
| | Drop-off **por categoría** (sin reformulación) | analysis_responses c31 |
| 8. Cierre | Satisfacción (MEAL) × categoría | analysis_responses c36–37 |

**Eliminado:** reformulación por similitud de embeddings (analysis_responses c32).

**Objetivos:** (1) cruces que el EDA univariado no muestra; (2) lectura cualitativa;
(3) qué necesitan y dónde/cuándo; (4) si el perfil predice la categoría; (5) profundidad,
abandono y su relación con satisfacción — puente al NLP.

---

## NB3 — `03_nlp_clustering_usuario_y_sentimiento.ipynb`

**NLP simplificado a nivel usuario.** Cambia respecto al plan original: se abandona el
pipeline UMAP+HDBSCAN + zero-shot tinting + temas emergentes + reformulación + emoción de
7 clases. Se conserva un stack más simple y auditable.

Setup: imports + `sentence_transformers`, spaCy (lemmatización es), modelo de sentimiento.
`msgs = load_messages(df)`, luego **agregación a nivel usuario** (concatenar mensajes por
`phone` en un documento por usuario).

| Sección | Contenido |
|---|---|
| 0. Setup + documento por usuario | Concatenar mensajes por usuario; lemmatización (spaCy es). |
| 1. Features | **Primario:** sentence embeddings (e5-large) del documento de usuario. **Comparación:** TF-IDF del texto lematizado. |
| 2. KMeans (nivel usuario) | KMeans sobre embeddings (k a elegir; k=7 para comparar con las categorías MMC). Repetir KMeans sobre TF-IDF como contraste. |
| 3. Clusters vs. clasificación original | Asignar a cada usuario su categoría MMC dominante / `Chat_summary`; medir concordancia (ARI, NMI, pureza, matriz de confusión) para embeddings-KMeans y TF-IDF-KMeans. ¿Confirman los clusters las 7 categorías oficiales? |
| 4. Sentimiento | Análisis de sentimiento de 3 clases (mensaje → agregado por usuario/cluster/categoría) como señal de malestar. |
| 5. Mapa síntesis geográfica | Necesidad dominante + tono de sentimiento por ciudad. **Cierre de todo el análisis.** |

**Eliminado de NB3:** UMAP/HDBSCAN, zero-shot NLI tinting, temas emergentes,
reformulación por embeddings, emoción de 7 clases.

**Objetivos:** (1) descubrir agrupamiento de usuarios y contrastarlo con las 7 categorías
oficiales; (2) medir qué tan bien se separan; (3) tono emocional como señal de malestar;
(4) síntesis geográfica: dónde coinciden mayor necesidad y peor tono.

---

## Entregables

1. `notebooks/01_eda_perfil_y_satisfaccion.ipynb` (reconstruido desde el stub actual `1_eda_...`, que se elimina).
2. `notebooks/02_analisis_general_comportamiento_necesidades.ipynb`.
3. `notebooks/03_nlp_clustering_usuario_y_sentimiento.ipynb`.
4. Los 4 notebooks fuente permanecen en `notebooks/arxiv/` como referencia.

## No-objetivos

- No se ejecuta ningún notebook aquí (requieren GPU, datos, modelos); el usuario los corre.
- No se elige ni aplica paleta de color (se añade después).
- No se crea análisis nuevo en NB1/NB2. NB3 sí cambia de método (simplificación acordada).
