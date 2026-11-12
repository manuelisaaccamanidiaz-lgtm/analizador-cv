"""Plantillas de descripción de puesto (datos/plantillas_puesto.json)."""

import json
from pathlib import Path

from services.errores import ErrorAplicacion

RUTA_PLANTILLAS = Path(__file__).resolve().parent.parent / "datos" / "plantillas_puesto.json"


def cargar_plantillas(ruta: Path = RUTA_PLANTILLAS) -> dict[str, str]:
    """Devuelve {nombre de la plantilla: descripción del puesto}, validando el archivo."""
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except FileNotFoundError as error:
        raise ErrorAplicacion(f"No se encontró el archivo de plantillas: {ruta}") from error
    except json.JSONDecodeError as error:
        raise ErrorAplicacion(f"El archivo de plantillas no contiene JSON válido: {error}") from error

    plantillas = datos.get("plantillas") if isinstance(datos, dict) else None
    if not isinstance(plantillas, list):
        raise ErrorAplicacion("El archivo de plantillas debe tener una lista 'plantillas'.")

    resultado: dict[str, str] = {}
    for plantilla in plantillas:
        nombre, descripcion = plantilla.get("nombre"), plantilla.get("descripcion")
        if not (isinstance(nombre, str) and nombre.strip() and isinstance(descripcion, str) and descripcion.strip()):
            raise ErrorAplicacion(f"Plantilla incompleta: {plantilla}")
        if nombre in resultado:
            raise ErrorAplicacion(f"Plantilla repetida: {nombre}")
        resultado[nombre] = descripcion.strip()
    return resultado
