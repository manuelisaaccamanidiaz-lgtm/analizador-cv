# 📄 Analizador de CV con IA

Aplicación de Streamlit que compara currículums en PDF con la descripción de un puesto. Usa **LangChain** con **Gemini, OpenAI u Ollama**, salida estructurada con **Pydantic**, **RAG** con **Chroma** para chatear con el CV y **PostgreSQL** (en Docker) para el historial.

> El análisis es un apoyo generado por IA y puede variar entre ejecuciones. No reemplaza la decisión de una persona.

## ✨ Funcionalidades

| Área | Qué hace |
| --- | --- |
| 🔍 **Evaluar** | Ajuste al puesto, nota por criterio con **gráfico radar**, requisitos ✅/🟡/❌ con **evidencia del CV**, habilidades, fortalezas y áreas de mejora |
| 📋 **Plantillas** | 6 descripciones de puesto listas para usar |
| 🎤 **Entrevista** | Preguntas sugeridas para aclarar lo que el CV no demuestra |
| 📄 **Documento** | Vista del PDF y del texto que realmente leyó la IA |
| ⬇️ **Exportar** | Informe en JSON o Markdown |
| 📊 **Comparar** | Ranking de hasta 10 candidatos para el mismo puesto, con descarga en CSV |
| 💬 **Chat con el CV** | Preguntas en lenguaje natural respondidas con **RAG** (embeddings + Chroma), citando la página |
| 🗂️ **Historial** | Análisis guardados en **PostgreSQL**, con búsqueda, filtros, estadísticas, feedback 👍/👎 y eliminación |
| 🤖 **Modelos** | Selector Gemini / OpenAI / Ollama en la barra lateral |
| ♻️ **Caché** | El mismo CV con el mismo puesto y el mismo modelo no se vuelve a enviar a la IA |

## ⚙️ Cómo funciona

```text
CV.pdf ─► pypdf (texto) ─┐
                          ├─► prompt de reclutador ─► modelo con salida estructurada ─► AnalisisCV
Puesto ──────────────────┘                                                               │
                                                     notas por criterio ─► Python calcula el % ponderado
                                                                                         │
                                                     umbrales ─► etiquetas ─► interfaz / historial / informe

Chat:  CV ─► fragmentos ─► embeddings ─► Chroma ─► (pregunta) ─► fragmentos parecidos ─► modelo ─► respuesta
```

### Criterios y umbrales

El modelo da una nota de 0 a 100 por criterio; **Python** calcula el total ponderado:

| Criterio | Peso |
| --- | --- |
| Experiencia relevante | 40 % |
| Habilidades técnicas | 35 % |
| Formación y certificaciones | 15 % |
| Coherencia profesional | 10 % |

| Porcentaje | Evaluación principal | | Porcentaje | Recomendación final |
| --- | --- | --- | --- | --- |
| 80–100 | 🟢 Excelente | | 70–100 | ✅ Candidato recomendado |
| 60–79 | 🟡 Bueno | | 50–69 | 🤔 Candidato con potencial |
| 40–59 | 🟠 Regular | | 0–49 | ❌ Candidato no recomendado |
| 0–39 | 🔴 Bajo | | | |

## 🗂️ Estructura

```text
.
├── .devcontainer/devcontainer.json   # Dev Container de VS Code
├── .vscode/tasks.json                # Tareas: Streamlit y pytest
├── Dockerfile                        # Python 3.12 + dependencias
├── docker-compose.yml                # app + PostgreSQL (servicio db)
├── .env.example                      # (opcional) credenciales de PostgreSQL
├── README.md
├── GUIA_DE_ESTUDIO.md                # Explicación de cada archivo (incluye RAG)
├── DESPLIEGUE.md                     # Cómo publicar la app
└── cv_analyzer/
    ├── app.py                        # Configuración, navegación y barra lateral
    ├── .streamlit/config.toml        # Tema de colores y límite de subida
    ├── .env.example                  # Claves y modelos de los proveedores
    ├── datos/plantillas_puesto.json  # Plantillas de puesto
    ├── models/cv_model.py            # AnalisisCV, PuntajesCriterios, RequisitoEvaluado, PreguntasEntrevista
    ├── prompts/                      # cv_prompts, entrevista_prompts, rag_prompts
    ├── services/
    │   ├── proveedores.py            # Gemini / OpenAI / Ollama (chat y embeddings)
    │   ├── cv_evaluator.py           # Evaluación con salida estructurada
    │   ├── pdf_processor.py          # Texto y huella del PDF
    │   ├── umbrales.py               # Porcentaje → etiquetas
    │   ├── entrevista.py             # Preguntas sugeridas
    │   ├── rag.py                    # Chat con el CV (RAG + Chroma)
    │   ├── historial.py              # SQLAlchemy: PostgreSQL o SQLite
    │   ├── informe.py                # Exportación JSON y Markdown
    │   ├── plantillas.py             # Lectura de plantillas
    │   └── errores.py                # Errores propios
    ├── ui/
    │   ├── estado.py                 # session_state y barra lateral
    │   ├── cache.py                  # st.cache_resource y st.cache_data
    │   ├── flujo.py                  # PDF → ResultadoEvaluacion
    │   ├── componentes.py            # Tarjetas, radar, pestañas, feedback
    │   └── paginas/                  # evaluar, comparar, chat, historial, acerca
    ├── tests/                        # 60 pruebas sin llamar a ninguna API
    └── requirements.txt
```

## 🚀 Instalación (Dev Container)

Requisitos: Docker Desktop y VS Code con la extensión **Dev Containers**.

1. Si otro contenedor usa el puerto 8501, detenlo (`docker stop <nombre>`).
2. Abre esta carpeta en VS Code → `Ctrl + Shift + P` → **Dev Containers: Reopen in Container**. Se levantan **dos** contenedores: `cv-analyzer-dev` (la app) y `cv-analyzer-db` (PostgreSQL).
3. En la terminal del contenedor:

```bash
cd /app/cv_analyzer
cp .env.example .env
```

4. Edita `cv_analyzer/.env` y configura **al menos un** proveedor:

| Proveedor | Variables | Notas |
| --- | --- | --- |
| Gemini | `GOOGLE_API_KEY`, `GEMINI_MODEL`, `GEMINI_EMBEDDING_MODEL` | El modelo de embeddings solo es necesario para el chat |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL` | Opcional |
| Ollama | `OLLAMA_MODEL`, `OLLAMA_EMBEDDING_MODEL` | Gratis y local: Ollama debe estar corriendo en tu PC (`ollama pull <modelo>`) |

La base de datos **no** se configura aquí: `docker-compose.yml` ya le pasa `DATABASE_URL` a la app.

## ▶️ Ejecución

Desde `cv_analyzer/` (o `Ctrl + Shift + B`):

```bash
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Abre <http://localhost:8501>.

### Sin Docker

Con un entorno virtual también funciona: si no existe `DATABASE_URL`, el historial se guarda en `cv_analyzer/datos/historial.db` (SQLite). Cambia `OLLAMA_BASE_URL` a `http://localhost:11434` si usas Ollama.

## 🧪 Pruebas

```bash
python -m pytest -v
```

60 pruebas que **no** usan ninguna API: puntaje ponderado, umbrales, Pydantic, PDF, prompts, evaluador (entrada inválida, fallo de API, formato inesperado), proveedores, historial (con SQLite en memoria), RAG (con embeddings y modelo falsos), entrevista, informes y plantillas.

## 🗄️ Base de datos

- PostgreSQL 17 en el servicio `db`, con un volumen (`datos_postgres`): los datos sobreviven a `docker compose down`.
- `docker compose down -v` **borra** el volumen y, con él, el historial.
- El puerto de PostgreSQL no se publica fuera de Docker. Para verlo con DBeaver o pgAdmin, descomenta `ports` en el servicio `db`.
- Para cambiar usuario y contraseña, crea un `.env` en la raíz a partir de `.env.example` (antes de crear la base).
- Se guarda el **análisis**, no el PDF ni su texto (datos personales).

## 🔐 Privacidad y límites

- El texto del CV se envía al proveedor elegido; con **Ollama** se procesa en tu computador.
- El `.gitignore` excluye los `.env`, los `.pdf` y la base SQLite local.
- Sin OCR: los PDF escaneados no se pueden leer.
- El prompt trata el CV como datos: ignora instrucciones escondidas (inyección de prompt).
- El chat responde solo con fragmentos del CV y debe decir cuándo el CV no menciona algo.

## 🛠️ Resolución de problemas

| Síntoma | Qué revisar |
| --- | --- |
| La barra lateral dice «No hay proveedores configurados» | Crea `cv_analyzer/.env` y llena las variables de al menos un proveedor |
| «Para chatear con el CV falta …_EMBEDDING_MODEL» | Agrega el modelo de embeddings del proveedor elegido |
| Error de base de datos en Historial | `docker compose ps`: el servicio `db` debe estar `healthy` |
| Ollama no responde | Ollama debe estar abierto en tu PC; revisa `OLLAMA_BASE_URL` |
| «No se encontró texto en el PDF» | Es un PDF escaneado: usa uno con texto seleccionable |
| `port is already allocated` | Otro contenedor usa el 8501 |

Para publicar la app, consulta [DESPLIEGUE.md](DESPLIEGUE.md).
