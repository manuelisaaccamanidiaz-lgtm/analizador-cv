"""Preguntas de entrevista sugeridas: una SEGUNDA llamada al modelo, con otro objetivo.

Se genera solo cuando el usuario la pide (botón), para no gastar llamadas de más.
"""

from models.cv_model import AnalisisCV, PreguntasEntrevista
from prompts.entrevista_prompts import crear_prompt_entrevista
from services.errores import ErrorEvaluacion
from services.proveedores import ConfigModelo, crear_chat

ETIQUETAS_ESTADO = {"cumple": "cumple", "parcial": "cumple en parte", "no_cumple": "no cumple"}


def crear_generador_preguntas(config: ConfigModelo):
    """Cadena prompt | modelo con salida estructurada PreguntasEntrevista."""
    try:
        modelo = crear_chat(config).with_structured_output(PreguntasEntrevista, method="json_schema")
    except ErrorEvaluacion:
        raise
    except Exception as error:
        raise ErrorEvaluacion(f"No se pudo configurar el modelo {config.etiqueta}: {error}") from error
    return crear_prompt_entrevista() | modelo


def resumir_para_entrevista(analisis: AnalisisCV) -> str:
    """Resumen corto del análisis: solo lo que sirve para preparar la entrevista (menos tokens)."""
    lineas = [
        f"Candidato: {analisis.nombre_candidato}",
        f"Experiencia relevante: {analisis.experiencia_anios} años. {analisis.experiencia_relevante}",
        f"Ajuste al puesto: {analisis.porcentaje_ajuste} %",
        "Requisitos:",
        *[
            f"- {r.requisito} ({'obligatorio' if r.obligatorio else 'deseable'}): {ETIQUETAS_ESTADO[r.estado]}"
            for r in analisis.requisitos
        ],
        "Áreas de mejora: " + "; ".join(analisis.areas_mejora),
    ]
    return "\n".join(lineas)


def generar_preguntas(analisis: AnalisisCV, descripcion_puesto: str, generador) -> PreguntasEntrevista:
    """Devuelve las preguntas sugeridas o lanza ErrorEvaluacion (nunca preguntas inventadas por el código)."""
    try:
        resultado = generador.invoke(
            {"descripcion_puesto": descripcion_puesto, "resumen_analisis": resumir_para_entrevista(analisis)}
        )
    except Exception as error:
        raise ErrorEvaluacion(f"No se pudieron generar las preguntas: {error}") from error
    if not isinstance(resultado, PreguntasEntrevista):
        raise ErrorEvaluacion("El modelo devolvió las preguntas con un formato inesperado.")
    return resultado
