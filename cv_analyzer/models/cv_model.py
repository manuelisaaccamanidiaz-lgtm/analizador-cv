"""Esquema de la respuesta que debe devolver el modelo de IA.

AnalisisCV es el "formulario" que el modelo llena gracias a
with_structured_output: si falta un campo o un valor no cumple las reglas
(por ejemplo, un porcentaje de 150), Pydantic lo rechaza.
"""

from pydantic import BaseModel, Field


class AnalisisCV(BaseModel):
    """Resultado estructurado de comparar un CV con un puesto de trabajo."""

    nombre_candidato: str = Field(
        min_length=1,
        description="Nombre completo del candidato tal como aparece en el CV. "
        "Si el CV no lo indica, escribir 'No especificado'.",
    )
    experiencia_anios: int = Field(
        ge=0,
        le=60,
        description="Años de experiencia RELEVANTE para el puesto. "
        "0 si no hay experiencia laboral relacionada.",
    )
    habilidades_clave: list[str] = Field(
        description="Entre 5 y 10 habilidades del CV relevantes para el puesto, "
        "de la más a la menos importante. Solo habilidades que aparezcan en el CV.",
    )
    education: str = Field(
        min_length=1,
        description="Nivel educativo más alto y especialización. "
        "Si el CV no lo indica, escribir 'No especificado'.",
    )
    experiencia_relevante: str = Field(
        min_length=1,
        description="Resumen breve (2 a 4 oraciones) de la experiencia relacionada con el puesto.",
    )
    fortalezas: list[str] = Field(
        description="Entre 3 y 5 fortalezas del candidato para este puesto.",
    )
    areas_mejora: list[str] = Field(
        description="Entre 2 y 4 áreas de desarrollo o requisitos del puesto que el CV no demuestra.",
    )
    porcentaje_ajuste: int = Field(
        ge=0,
        le=100,
        description="Porcentaje de ajuste al puesto entre 0 y 100, según los criterios ponderados.",
    )
