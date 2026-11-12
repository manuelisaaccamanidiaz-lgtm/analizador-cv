# 📄 Analizador de CV con IA

Aplicación de Streamlit que compara un currículum en PDF con la descripción de un puesto. Extrae el texto del documento, lo envía a un modelo de **Gemini** mediante **LangChain** y muestra un análisis estructurado del candidato: perfil, habilidades, fortalezas, áreas de mejora, porcentaje de ajuste y recomendación de contratación.

> El porcentaje lo estima un modelo de IA y puede variar entre ejecuciones. Es una herramienta de apoyo, no una decisión de contratación.

## Funcionalidades

- Carga de un CV en PDF con texto seleccionable.
- Entrada de requisitos y responsabilidades del puesto.
- Extracción de nombre, experiencia, educación y habilidades relevantes.
- Fortalezas y áreas de mejora.
- Porcentaje de ajuste al puesto entre 0 y 100.
- Evaluación principal y recomendación final calculadas a partir del porcentaje.
- El resultado se conserva en `st.session_state` hasta pulsar **Limpiar**.
- **Guardar Análisis** muestra un aviso de funcionalidad en desarrollo (no hay persistencia).

## Funcionamiento

```text
CV.pdf ──► pdf_processor.extraer_texto_pdf() ──┐
                                               ├──► cv_prompts.crear_sistema_prompts()
Descripción del puesto ────────────────────────┘                │
                                                                ▼
                         cv_evaluator.evaluar_candidato()  (prompt | Gemini con salida estructurada)
                                                                │
                                                                ▼
                         AnalisisCV ──► umbrales ──► streamlit_ui muestra el resultado
```

1. `app.py` carga el `.env` y llama a `main()` de la interfaz.
2. El usuario sube un PDF y escribe la descripción del puesto.
3. Al pulsar **Analizar Candidato**, la interfaz comprueba que existan ambas entradas.
4. `extraer_texto_pdf()` lee el PDF con `pypdf`, recorre sus páginas y une el texto con separadores. Si no hay texto, el archivo está dañado o es demasiado largo, lanza `ErrorPDF`.
5. `evaluar_candidato()` valida la descripción y llama a la cadena `prompt | modelo_estructurado`. Cualquier fallo se convierte en `ErrorEvaluacion`: **nunca** se muestra un resultado inventado.
6. `umbrales.py` convierte el porcentaje en las etiquetas de la interfaz.

### Criterios de evaluación (en el prompt)

| Criterio | Peso |
| --- | --- |
| Experiencia relevante | 40 % |
| Habilidades técnicas | 35 % |
| Formación y certificaciones | 15 % |
| Coherencia profesional | 10 % |

El porcentaje lo genera el modelo siguiendo estos pesos; el código no calcula una fórmula ponderada.

### Umbrales (calculados en Python)

| Porcentaje | Evaluación principal | | Porcentaje | Recomendación final |
| --- | --- | --- | --- | --- |
| 80–100 | 🟢 Excelente | | 70–100 | ✅ Candidato recomendado |
| 60–79 | 🟡 Bueno | | 50–69 | 🤔 Candidato con potencial |
| 40–59 | 🟠 Regular | | 0–49 | ❌ Candidato no recomendado |
| 0–39 | 🔴 Bajo | | | |

Ejemplo: 65 % → **Bueno** y **Candidato con potencial**.

## Estructura

```text
.
├── .devcontainer/devcontainer.json   # Dev Container de VS Code
├── .vscode/tasks.json                # Tareas: Streamlit y pytest
├── Dockerfile                        # Python 3.12 + dependencias
├── docker-compose.yml                # Monta el proyecto en /app, puerto 8501
├── .dockerignore
├── .gitignore
├── README.md
├── GUIA_DE_ESTUDIO.md                # Explicación de cada archivo
└── cv_analyzer/
    ├── app.py                        # Punto de entrada de Streamlit
    ├── models/cv_model.py            # Esquema Pydantic AnalisisCV
    ├── prompts/cv_prompts.py         # Instrucciones, pesos y plantilla
    ├── services/
    │   ├── pdf_processor.py          # Extracción de texto del PDF
    │   ├── cv_evaluator.py           # Configuración e invocación del modelo
    │   └── umbrales.py               # Porcentaje → etiquetas
    ├── ui/streamlit_ui.py            # Entradas, validaciones y presentación
    ├── tests/test_cv_analyzer.py     # 37 pruebas sin llamar al modelo
    ├── requirements.txt
    └── .env.example
```

### Modelo de salida (`AnalisisCV`)

Todos los campos son obligatorios:

| Campo | Tipo | Contenido |
| --- | --- | --- |
| `nombre_candidato` | `str` | Nombre extraído del CV |
| `experiencia_anios` | `int` (0–60) | Años de experiencia relevante |
| `habilidades_clave` | `list[str]` | Habilidades relevantes para el puesto |
| `education` | `str` | Nivel educativo y especialización |
| `experiencia_relevante` | `str` | Resumen de experiencia relacionada |
| `fortalezas` | `list[str]` | Fortalezas del candidato |
| `areas_mejora` | `list[str]` | Áreas de desarrollo |
| `porcentaje_ajuste` | `int` (0–100) | Ajuste al puesto |

## Instalación (Dev Container)

Requisitos: Docker Desktop y VS Code con la extensión **Dev Containers**.

1. Abre esta carpeta en VS Code.
2. `Ctrl + Shift + P` → **Dev Containers: Reopen in Container**. Al crearse, el contenedor instala `cv_analyzer/requirements.txt`.
3. Si otro contenedor usa el puerto 8501, detenlo antes (`docker stop <nombre>`).

## Configuración

En la terminal del contenedor:

```bash
cd /app/cv_analyzer
cp .env.example .env
```

Edita `cv_analyzer/.env`:

| Variable | Valor |
| --- | --- |
| `GOOGLE_API_KEY` | Tu clave de Google AI Studio |
| `GEMINI_MODEL` | Un modelo Gemini compatible con salida estructurada (por ejemplo, `gemini-3.5-flash-lite`) |

`.env` está en `.gitignore` y **nunca** se sube al repositorio. `app.py` lo carga con `load_dotenv()`.

## Ejecución

Desde `cv_analyzer/` (o `Ctrl + Shift + B` en VS Code):

```bash
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Abre <http://localhost:8501>.

Ejemplo de descripción del puesto:

```text
Puesto: Desarrollador Python
Requisitos obligatorios: 3 años de experiencia, Python, APIs REST y PostgreSQL.
Deseables: Docker, pruebas automatizadas y experiencia con LangChain.
Responsabilidades: desarrollar servicios, integrar APIs y mantener pruebas.
```

## Pruebas automáticas

```bash
python -m pytest -v
```

37 pruebas que no usan la API: umbrales (incluidos los límites 39/40, 49/50, 59/60, 69/70, 79/80), validaciones de `AnalisisCV`, extracción de PDF (texto, PDF sin texto, archivo inválido, CV demasiado largo), prompt (pesos que suman 100, regla anti-inyección) y evaluador (entrada inválida que no llama al modelo, fallo de API sin resultado inventado, respuesta con formato inesperado).

## Mejoras respecto a la versión de referencia

| Problema de la versión de referencia | Solución |
| --- | --- |
| El `except` del evaluador creaba `AnalisisCV` con campos mal escritos (`fotalezas`, `porcetaje_ajuste`) y también fallaba | No se construye un resultado alternativo: se lanza `ErrorEvaluacion` y la interfaz muestra el error |
| El resultado desaparecía con cualquier interacción | Se guarda en `st.session_state` |
| **Limpiar** solo hacía `st.rerun()` | Un callback borra la descripción, el resultado y reinicia el selector de archivo |
| No se cargaba el `.env` | `app.py` llama a `load_dotenv()` |
| Sin control de longitud del CV | Límite de 30 000 caracteres |
| Texto del CV sin protección contra instrucciones ocultas | El prompt trata el CV como datos (regla anti-inyección) |
| Etiquetas dependientes del modelo | Se calculan en Python a partir del porcentaje |

## Decisiones técnicas

- **Modelo:** Gemini con `langchain-google-genai` en lugar de `gpt-4o-mini` (el profesor permite elegir el proveedor). Temperatura `0.2`; algunos modelos Gemini tienen valores de muestreo fijos y la ignoran (aparece un `UserWarning`).
- **Salida estructurada:** `with_structured_output(AnalisisCV, method="json_schema")`.
- **PDF:** `pypdf` en lugar de `PyPDF2`, que está obsoleto y fue sustituido por `pypdf` (misma clase `PdfReader`).
- **`experiencia_anios`:** se escribe sin «ñ» para evitar caracteres especiales en el esquema que se envía al modelo.

## Limitaciones

- **Sin OCR:** un PDF escaneado (solo imágenes) no se puede analizar.
- **Sin persistencia:** el análisis no se guarda en disco ni en base de datos.
- **Un CV por análisis:** no hay procesamiento por lotes.
- **Evaluación generativa:** el porcentaje y las observaciones pueden variar entre ejecuciones; no hay validación independiente del criterio de contratación.
- **Privacidad:** el texto del CV se envía a la API de Gemini. Usa CV propios o con permiso del dueño.

## Resolución de problemas

| Síntoma | Qué revisar |
| --- | --- |
| No aparece «Reopen in Container» | Abre la carpeta raíz (la que tiene `.devcontainer`) e instala la extensión Dev Containers |
| `ModuleNotFoundError` de `ui`, `services`... | Ejecuta Streamlit desde `cv_analyzer/` |
| «Falta la variable GOOGLE_API_KEY» | Crea `cv_analyzer/.env` a partir de `.env.example` |
| «No se encontró texto en el PDF» | El PDF es escaneado: usa uno con texto seleccionable |
| Error del modelo | Revisa la clave, la cuota, la conexión y el nombre de `GEMINI_MODEL` |
| `port is already allocated` | Otro contenedor usa el 8501: detenlo o cambia el puerto del host en `docker-compose.yml` |
