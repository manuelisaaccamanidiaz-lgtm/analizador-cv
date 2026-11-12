"""Flujo compartido por Evaluar y Comparar: de un PDF a un ResultadoEvaluacion."""

import hashlib
import uuid

import streamlit as st

from services.pdf_processor import huella_archivo
from services.proveedores import ConfigModelo
from ui.cache import analizar_cacheado, extraer_texto_cacheado
from ui.estado import ResultadoEvaluacion


def clave_analisis(huella: str, puesto: str, config: ConfigModelo) -> str:
    """Identifica una combinación CV + puesto + modelo (para saber si se reutilizó la caché)."""
    huella_puesto = hashlib.sha256(puesto.strip().encode("utf-8")).hexdigest()[:16]
    return f"{huella}:{huella_puesto}:{config.proveedor}:{config.modelo}"


def evaluar_archivo(nombre: str, contenido: bytes, puesto: str, config: ConfigModelo) -> ResultadoEvaluacion:
    """Extrae el texto y evalúa el CV. Lanza ErrorPDF / ErrorEntrada / ErrorEvaluacion si algo falla."""
    huella = huella_archivo(contenido)
    clave = clave_analisis(huella, puesto, config)
    reutilizado = clave in st.session_state["claves_analizadas"]

    texto_cv = extraer_texto_cacheado(contenido)
    analisis = analizar_cacheado(texto_cv, puesto.strip(), config.proveedor, config.modelo)

    st.session_state["claves_analizadas"].add(clave)
    return ResultadoEvaluacion(
        id=str(uuid.uuid4()), analisis=analisis, texto_cv=texto_cv, pdf_bytes=contenido,
        archivo=nombre, huella=huella, puesto=puesto.strip(), config=config, reutilizado=reutilizado,
    )


def aplicar_plantilla(clave_selector: str, clave_puesto: str) -> None:
    """Callback del selector de plantillas: copia la descripción en el cuadro de texto."""
    from ui.cache import obtener_plantillas

    nombre = st.session_state.get(clave_selector)
    plantillas = obtener_plantillas()
    if nombre in plantillas:
        st.session_state[clave_puesto] = plantillas[nombre]
