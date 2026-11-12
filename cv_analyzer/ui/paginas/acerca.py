"""Página informativa: cómo funciona la aplicación y sus límites."""

import streamlit as st

from models.cv_model import NOMBRES_CRITERIOS, PESOS_CRITERIOS
from prompts.cv_prompts import VERSION_PROMPT

st.title("ℹ️ Acerca de")
st.markdown(
    "El **Analizador de CV** compara un currículum en PDF con la descripción de un puesto usando un modelo de IA "
    "(Gemini, OpenAI u Ollama) mediante LangChain. Es una herramienta de **apoyo**: no reemplaza la decisión de una persona."
)

col_a, col_b = st.columns(2, gap="large")
with col_a, st.container(border=True):
    st.markdown("#### ⚙️ Cómo funciona")
    st.markdown(
        "1. `pypdf` extrae el texto del PDF.\n"
        "2. Un prompt de reclutador y **salida estructurada** (Pydantic) obligan al modelo a llenar un formulario.\n"
        "3. El modelo da una nota por criterio; **Python** calcula el total ponderado y las etiquetas.\n"
        "4. El chat usa **RAG**: embeddings + Chroma para responder solo con lo que dice el CV."
    )
with col_b, st.container(border=True):
    st.markdown("#### ⚖️ Criterios")
    st.markdown(
        "| Criterio | Peso |\n| --- | --- |\n"
        + "\n".join(f"| {NOMBRES_CRITERIOS[c]} | {int(p * 100)} % |" for c, p in PESOS_CRITERIOS.items())
    )

with st.container(border=True):
    st.markdown("#### 🔐 Privacidad y límites")
    st.markdown(
        "- El texto del CV se envía al proveedor de IA elegido (con **Ollama** se procesa en tu computador).\n"
        "- El historial guarda el **análisis**, no el PDF ni su texto.\n"
        "- No hay OCR: los CV escaneados no se pueden leer.\n"
        "- El resultado puede variar entre ejecuciones; revisa siempre la evidencia de cada requisito.\n"
        "- El prompt ignora instrucciones escondidas dentro del CV (inyección de prompt)."
    )

st.caption(f"Versión del prompt: {VERSION_PROMPT}")
