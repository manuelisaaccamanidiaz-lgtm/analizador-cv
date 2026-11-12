"""Esquemas Pydantic: los "formularios" que llena el modelo de IA.

- AnalisisCV: el análisis completo de un CV frente a un puesto.
- PreguntasEntrevista: preguntas sugeridas para la entrevista.

El porcentaje de ajuste NO lo escribe el modelo: el modelo da una nota de 0 a 100
por criterio y Python calcula el total ponderado (propiedad porcentaje_ajuste).
"""

from typing import Literal

from pydantic import BaseModel, Field

# Pesos del taller. Se usan en el prompt (para explicarle al modelo) y en el cálculo.
PESOS_CRITERIOS: dict[str, float] = {
    "experiencia": 0.40,
    "habilidades": 0.35,
    "formacion": 0.15,
    "coherencia": 0.10,
}

NOMBRES_CRITERIOS: dict[str, str] = {
    "experiencia": "Experiencia relevante",
    "habilidades": "Habilidades técnicas",
    "formacion": "Formación y certificaciones",
    "coherencia": "Coherencia profesional",
}

EstadoRequisito = Literal["cumple", "parcial", "no_cumple"]


class PuntajesCriterios(BaseModel):
    """Nota de 0 a 100 en cada criterio del taller."""

    experiencia: int = Field(ge=0, le=100, description="Nota 0-100 de la experiencia relevante para el puesto.")
    habilidades: int = Field(ge=0, le=100, description="Nota 0-100 de las habilidades técnicas pedidas.")
    formacion: int = Field(ge=0, le=100, description="Nota 0-100 de la formación y certificaciones.")
    coherencia: int = Field(ge=0, le=100, description="Nota 0-100 de la coherencia de la trayectoria con el puesto.")


class RequisitoEvaluado(BaseModel):
    """Un requisito del puesto y si el CV lo demuestra."""

    requisito: str = Field(min_length=1, description="Requisito tomado de la descripción del puesto.")
    obligatorio: bool = Field(description="true si el puesto lo marca como obligatorio; false si es deseable.")
    estado: EstadoRequisito = Field(
        description="'cumple' si el CV lo demuestra, 'parcial' si lo demuestra en parte, 'no_cumple' si no aparece."
    )
    evidencia: str = Field(
        description="Frase breve copiada o resumida del CV que lo demuestra. Vacío si el estado es 'no_cumple'."
    )


class AnalisisCV(BaseModel):
    """Resultado estructurado de comparar un CV con un puesto de trabajo."""

    nombre_candidato: str = Field(
        min_length=1,
        description="Nombre completo del candidato tal como aparece en el CV. Si no aparece, 'No especificado'.",
    )
    experiencia_anios: int = Field(
        ge=0, le=60, description="Años de experiencia RELEVANTE para el puesto. 0 si no hay experiencia relacionada."
    )
    habilidades_clave: list[str] = Field(
        description="Entre 5 y 10 habilidades del CV relevantes para el puesto, de la más a la menos importante."
    )
    education: str = Field(
        min_length=1, description="Nivel educativo más alto y especialización. Si no aparece, 'No especificado'."
    )
    experiencia_relevante: str = Field(
        min_length=1, description="Resumen breve (2 a 4 oraciones) de la experiencia relacionada con el puesto."
    )
    fortalezas: list[str] = Field(description="Entre 3 y 5 fortalezas del candidato para este puesto.")
    areas_mejora: list[str] = Field(
        description="Entre 2 y 4 áreas de desarrollo o requisitos del puesto que el CV no demuestra."
    )
    requisitos: list[RequisitoEvaluado] = Field(
        description="Cada requisito importante de la descripción del puesto, evaluado con evidencia del CV."
    )
    puntajes: PuntajesCriterios = Field(description="Nota de 0 a 100 en cada uno de los cuatro criterios.")

    @property
    def porcentaje_ajuste(self) -> int:
        """Total ponderado 40/35/15/10, calculado en Python (no lo inventa el modelo)."""
        total = sum(getattr(self.puntajes, criterio) * peso for criterio, peso in PESOS_CRITERIOS.items())
        return int(total + 0.5)  # redondeo "de colegio": 64.5 -> 65

    def conteo_requisitos(self) -> dict[str, int]:
        """Cuántos requisitos cumple, cumple en parte o no cumple."""
        conteo = {"cumple": 0, "parcial": 0, "no_cumple": 0}
        for requisito in self.requisitos:
            conteo[requisito.estado] += 1
        return conteo


class PreguntaEntrevista(BaseModel):
    pregunta: str = Field(min_length=1, description="Pregunta concreta para hacerle al candidato.")
    objetivo: str = Field(min_length=1, description="Qué se quiere comprobar con la pregunta, en una frase.")


class PreguntasEntrevista(BaseModel):
    preguntas: list[PreguntaEntrevista] = Field(
        description="Entre 3 y 5 preguntas de entrevista enfocadas en las dudas del análisis."
    )
