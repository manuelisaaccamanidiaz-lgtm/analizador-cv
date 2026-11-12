"""Evaluación del CV con el modelo de IA.

crear_evaluador_cv() arma la cadena prompt | modelo con salida estructurada.
evaluar_candidato() valida las entradas, invoca la cadena y controla los errores.

La cadena se recibe como parámetro (inyección de dependencias): así la interfaz
puede guardarla en caché y las pruebas pueden usar una cadena falsa sin gastar API.
"""

from models.cv_model import AnalisisCV
from prompts.cv_prompts import crear_sistema_prompts
from services.errores import ErrorEntrada, ErrorEvaluacion
from services.proveedores import ConfigModelo, crear_chat

MIN_CARACTERES_PUESTO = 20


def crear_evaluador_cv(config: ConfigModelo):
    """Crea la cadena prompt | modelo_estructurado para el proveedor elegido."""
    try:
        modelo = crear_chat(config)
        modelo_estructurado = modelo.with_structured_output(AnalisisCV, method="json_schema")
    except ErrorEvaluacion:
        raise
    except Exception as error:  # paquete no instalado, parámetros inválidos...
        raise ErrorEvaluacion(f"No se pudo configurar el modelo {config.etiqueta}: {error}") from error
    return crear_sistema_prompts() | modelo_estructurado


def validar_entradas(texto_cv: str, descripcion_puesto: str) -> tuple[str, str]:
    """Limpia y valida las entradas ANTES de gastar una llamada al modelo."""
    texto_cv = (texto_cv or "").strip()
    descripcion_puesto = (descripcion_puesto or "").strip()
    if not texto_cv:
        raise ErrorEntrada("El CV no tiene texto para analizar.")
    if len(descripcion_puesto) < MIN_CARACTERES_PUESTO:
        raise ErrorEntrada(
            f"Describe el puesto con al menos {MIN_CARACTERES_PUESTO} caracteres "
            "(requisitos, habilidades y responsabilidades)."
        )
    return texto_cv, descripcion_puesto


def evaluar_candidato(texto_cv: str, descripcion_puesto: str, evaluador) -> AnalisisCV:
    """Compara el CV con el puesto y devuelve el análisis validado.

    Nunca devuelve un resultado inventado: ante cualquier fallo lanza una excepción.
    """
    texto_cv, descripcion_puesto = validar_entradas(texto_cv, descripcion_puesto)

    try:
        analisis = evaluador.invoke({"texto_cv": texto_cv, "descripcion_puesto": descripcion_puesto})
    except Exception as error:  # red, cuota, clave inválida, respuesta que no cumple el esquema...
        raise ErrorEvaluacion(f"No se pudo evaluar el CV con el modelo: {error}") from error

    if not isinstance(analisis, AnalisisCV):
        raise ErrorEvaluacion("El modelo devolvió una respuesta con un formato inesperado.")
    return analisis
