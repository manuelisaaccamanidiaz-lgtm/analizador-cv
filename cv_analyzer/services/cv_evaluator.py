"""Configuración e invocación del modelo de IA.

Usa Gemini mediante LangChain. La clave y el nombre del modelo se leen de las
variables de entorno GOOGLE_API_KEY y GEMINI_MODEL (archivo .env).
"""

import os
from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from models.cv_model import AnalisisCV
from prompts.cv_prompts import crear_sistema_prompts

TEMPERATURA = 0.2
MIN_CARACTERES_PUESTO = 20


class ErrorEntrada(Exception):
    """Faltan datos o no son válidos: no se llama al modelo."""


class ErrorEvaluacion(Exception):
    """Falló la configuración, la llamada al modelo o la validación de su respuesta."""


def nombre_modelo() -> str:
    """Nombre del modelo configurado en GEMINI_MODEL."""
    modelo = os.getenv("GEMINI_MODEL", "").strip()
    if not modelo:
        raise ErrorEvaluacion("Falta la variable GEMINI_MODEL en el archivo .env.")
    return modelo


@lru_cache(maxsize=1)
def crear_evaluador_cv():
    """Crea UNA vez la cadena prompt | modelo con salida estructurada y la reutiliza."""
    if not os.getenv("GOOGLE_API_KEY", "").strip():
        raise ErrorEvaluacion("Falta la variable GOOGLE_API_KEY en el archivo .env.")

    modelo = ChatGoogleGenerativeAI(model=nombre_modelo(), temperature=TEMPERATURA)
    modelo_estructurado = modelo.with_structured_output(AnalisisCV, method="json_schema")
    return crear_sistema_prompts() | modelo_estructurado


def evaluar_candidato(texto_cv: str, descripcion_puesto: str) -> AnalisisCV:
    """Compara el CV con el puesto y devuelve el análisis validado.

    Nunca devuelve un resultado inventado: ante cualquier fallo lanza una excepción
    para que la interfaz muestre el error.
    """
    texto_cv = (texto_cv or "").strip()
    descripcion_puesto = (descripcion_puesto or "").strip()

    # 1. Validar ANTES de gastar una llamada al modelo
    if not texto_cv:
        raise ErrorEntrada("El CV no tiene texto para analizar.")
    if len(descripcion_puesto) < MIN_CARACTERES_PUESTO:
        raise ErrorEntrada(
            f"Describe el puesto con al menos {MIN_CARACTERES_PUESTO} caracteres "
            "(requisitos, habilidades y responsabilidades)."
        )

    # 2. Llamar al modelo (todo fallo se convierte en ErrorEvaluacion)
    try:
        evaluador = crear_evaluador_cv()
        analisis = evaluador.invoke({"texto_cv": texto_cv, "descripcion_puesto": descripcion_puesto})
    except ErrorEvaluacion:
        raise  # ya trae un mensaje claro (falta una variable del .env)
    except Exception as error:  # red, cuota, clave inválida, respuesta que no cumple el esquema...
        raise ErrorEvaluacion(f"No se pudo evaluar el CV con el modelo: {error}") from error

    # 3. Comprobar que llegó el formulario esperado
    if not isinstance(analisis, AnalisisCV):
        raise ErrorEvaluacion("El modelo devolvió una respuesta con un formato inesperado.")
    return analisis
