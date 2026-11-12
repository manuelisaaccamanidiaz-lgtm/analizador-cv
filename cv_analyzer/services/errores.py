"""Errores propios de la aplicación.

Cada tipo de fallo tiene su clase para que la interfaz pueda mostrar
un mensaje adecuado (y nunca un resultado inventado).
"""


class ErrorAplicacion(Exception):
    """Base de todos los errores controlados de la aplicación."""


class ErrorEntrada(ErrorAplicacion):
    """Faltan datos o no son válidos: no se llama al modelo."""


class ErrorPDF(ErrorAplicacion):
    """El PDF no se pudo leer o no contiene texto utilizable."""


class ErrorEvaluacion(ErrorAplicacion):
    """Falló la llamada al modelo o la validación de su respuesta."""


class ErrorConfiguracion(ErrorEvaluacion):
    """Falta una variable de entorno o el proveedor no está disponible."""


class ErrorChat(ErrorAplicacion):
    """Falló la creación del índice o la respuesta del chat con el CV."""


class ErrorBaseDatos(ErrorAplicacion):
    """Falló la lectura o escritura del historial."""
