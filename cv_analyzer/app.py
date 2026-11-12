"""Punto de entrada de Streamlit: configuración, navegación y barra lateral.

Ejecutar desde la carpeta cv_analyzer:
    streamlit run app.py --server.address=0.0.0.0 --server.port=8501
"""

from pathlib import Path

from dotenv import load_dotenv

# Carga las claves y modelos desde cv_analyzer/.env antes de importar el resto.
load_dotenv(Path(__file__).resolve().parent / ".env")

import streamlit as st  # noqa: E402

from ui.estado import inicializar_estado, mostrar_barra_lateral  # noqa: E402

st.set_page_config(page_title="Analizador de CV", page_icon="📄", layout="wide")
inicializar_estado()

paginas = {
    "Análisis": [
        st.Page("ui/paginas/evaluar.py", title="Evaluar candidato", icon="🔍", default=True),
        st.Page("ui/paginas/comparar.py", title="Comparar candidatos", icon="📊"),
        st.Page("ui/paginas/chat.py", title="Chat con el CV", icon="💬"),
    ],
    "Registro": [
        st.Page("ui/paginas/historial.py", title="Historial", icon="🗂️"),
        st.Page("ui/paginas/acerca.py", title="Acerca de", icon="ℹ️"),
    ],
}

pagina = st.navigation(paginas)
mostrar_barra_lateral()
pagina.run()
