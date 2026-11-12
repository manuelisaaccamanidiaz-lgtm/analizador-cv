"""Conversión del porcentaje de ajuste en etiquetas para la interfaz.

Las etiquetas se calculan en Python (no las decide el modelo) para que siempre
sean coherentes con el porcentaje. Hay dos tablas, como pide el taller:

Evaluación principal          Recomendación final
80-100  Excelente             70-100  Candidato recomendado
60-79   Bueno                 50-69   Candidato con potencial
40-59   Regular               0-49    Candidato no recomendado
0-39    Bajo

Ejemplo: 65 % -> "Bueno" y "Candidato con potencial".
"""

from typing import NamedTuple


class Etiqueta(NamedTuple):
    texto: str
    emoji: str
    nivel: str  # "success", "warning" o "error": el tipo de aviso de Streamlit


def _validar(porcentaje: int) -> None:
    if not 0 <= porcentaje <= 100:
        raise ValueError(f"El porcentaje debe estar entre 0 y 100; se recibió {porcentaje}.")


def evaluacion_principal(porcentaje: int) -> Etiqueta:
    """Etiqueta de la evaluación principal (Excelente, Bueno, Regular, Bajo)."""
    _validar(porcentaje)
    if porcentaje >= 80:
        return Etiqueta("Excelente", "🟢", "success")
    if porcentaje >= 60:
        return Etiqueta("Bueno", "🟡", "success")
    if porcentaje >= 40:
        return Etiqueta("Regular", "🟠", "warning")
    return Etiqueta("Bajo", "🔴", "error")


def recomendacion_final(porcentaje: int) -> Etiqueta:
    """Recomendación de contratación según el porcentaje."""
    _validar(porcentaje)
    if porcentaje >= 70:
        return Etiqueta("Candidato recomendado", "✅", "success")
    if porcentaje >= 50:
        return Etiqueta("Candidato con potencial", "🤔", "warning")
    return Etiqueta("Candidato no recomendado", "❌", "error")
