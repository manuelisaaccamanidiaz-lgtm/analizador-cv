"""Cachés de Streamlit.

- st.cache_resource guarda OBJETOS que se reutilizan (motor de la base de datos,
  cadenas del modelo, índices de Chroma). Se crean una vez y se comparten.
- st.cache_data guarda RESULTADOS (texto extraído, análisis). Si llegan los mismos
  datos de entrada, devuelve el resultado guardado SIN volver a llamar al modelo.

Las funciones reciben textos simples (proveedor, modelo...) porque Streamlit
usa los parámetros para construir la clave de la caché.
"""

import streamlit as st

from models.cv_model import AnalisisCV
from services.cv_evaluator import crear_evaluador_cv, evaluar_candidato
from services.entrevista import crear_generador_preguntas
from services.historial import crear_motor, inicializar_bd
from services.pdf_processor import extraer_texto_pdf
from services.plantillas import cargar_plantillas
from services.proveedores import ConfigModelo, crear_chat, crear_embeddings
from services.rag import crear_indice


# ---------------------------- Recursos ------------------------------------
@st.cache_resource(show_spinner=False)
def obtener_motor():
    motor = crear_motor()
    inicializar_bd(motor)
    return motor


@st.cache_resource(show_spinner=False)
def obtener_evaluador(proveedor: str, modelo: str):
    return crear_evaluador_cv(ConfigModelo(proveedor, modelo))


@st.cache_resource(show_spinner=False)
def obtener_generador_preguntas(proveedor: str, modelo: str):
    return crear_generador_preguntas(ConfigModelo(proveedor, modelo))


@st.cache_resource(show_spinner=False)
def obtener_modelo_chat(proveedor: str, modelo: str):
    return crear_chat(ConfigModelo(proveedor, modelo))


@st.cache_resource(show_spinner=False, max_entries=20)
def obtener_indice(huella: str, texto_cv: str, proveedor: str, modelo: str, modelo_embeddings: str | None):
    """Un índice de Chroma por CV y proveedor (los embeddings de cada proveedor son distintos)."""
    embeddings = crear_embeddings(ConfigModelo(proveedor, modelo, modelo_embeddings))
    return crear_indice(texto_cv, embeddings, nombre_coleccion=f"cv-{huella[:16]}-{proveedor}")


# ----------------------------- Datos --------------------------------------
@st.cache_data(show_spinner=False)
def obtener_plantillas() -> dict[str, str]:
    return cargar_plantillas()


@st.cache_data(show_spinner=False, max_entries=50)
def extraer_texto_cacheado(contenido: bytes) -> str:
    return extraer_texto_pdf(contenido)


@st.cache_data(show_spinner=False, max_entries=200)
def analizar_cacheado(texto_cv: str, descripcion_puesto: str, proveedor: str, modelo: str) -> AnalisisCV:
    """Mismo CV + mismo puesto + mismo modelo = mismo resultado, sin nueva llamada (ni costo).

    Si la función lanza una excepción, Streamlit NO guarda nada en caché.
    """
    return evaluar_candidato(texto_cv, descripcion_puesto, obtener_evaluador(proveedor, modelo))
