"""Punto de entrada de Streamlit.

Ejecutar desde la carpeta cv_analyzer:
    streamlit run app.py --server.address=0.0.0.0 --server.port=8501
"""

from pathlib import Path

from dotenv import load_dotenv

# Carga GOOGLE_API_KEY y GEMINI_MODEL desde cv_analyzer/.env antes de usar el modelo.
load_dotenv(Path(__file__).resolve().parent / ".env")

from ui.streamlit_ui import main  # noqa: E402  (se importa después de cargar el .env)

main()
