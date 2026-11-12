"""Exportación del análisis a JSON y Markdown (para el botón de descarga)."""

import json
from datetime import datetime, timezone

from models.cv_model import NOMBRES_CRITERIOS, PESOS_CRITERIOS, AnalisisCV
from services.umbrales import evaluacion_principal, recomendacion_final

ICONOS_ESTADO = {"cumple": "✅ Cumple", "parcial": "🟡 Parcial", "no_cumple": "❌ No cumple"}


def analisis_a_diccionario(analisis: AnalisisCV, *, puesto: str, archivo: str, modelo: str) -> dict:
    """Todo lo necesario para reconstruir el análisis, más los datos calculados por Python."""
    return {
        "generado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "archivo": archivo,
        "modelo": modelo,
        "puesto": puesto,
        "porcentaje_ajuste": analisis.porcentaje_ajuste,
        "evaluacion_principal": evaluacion_principal(analisis.porcentaje_ajuste).texto,
        "recomendacion_final": recomendacion_final(analisis.porcentaje_ajuste).texto,
        "analisis": analisis.model_dump(),
    }


def informe_json(analisis: AnalisisCV, **datos) -> str:
    return json.dumps(analisis_a_diccionario(analisis, **datos), ensure_ascii=False, indent=2)


def informe_markdown(analisis: AnalisisCV, *, puesto: str, archivo: str, modelo: str) -> str:
    """Informe legible para compartir con el equipo de selección."""
    principal = evaluacion_principal(analisis.porcentaje_ajuste)
    recomendacion = recomendacion_final(analisis.porcentaje_ajuste)

    filas_criterios = "\n".join(
        f"| {NOMBRES_CRITERIOS[c]} | {int(p * 100)} % | {getattr(analisis.puntajes, c)} |"
        for c, p in PESOS_CRITERIOS.items()
    )
    filas_requisitos = "\n".join(
        f"| {r.requisito} | {'Obligatorio' if r.obligatorio else 'Deseable'} | {ICONOS_ESTADO[r.estado]} | "
        f"{(r.evidencia or '—').replace('|', '/')} |"
        for r in analisis.requisitos
    ) or "| — | — | — | — |"

    def lista(elementos: list[str]) -> str:
        return "\n".join(f"{i}. {e}" for i, e in enumerate(elementos, start=1)) or "—"

    return f"""# Informe de evaluación de CV

- **Candidato:** {analisis.nombre_candidato}
- **Archivo:** {archivo}
- **Modelo:** {modelo}
- **Fecha (UTC):** {datetime.now(timezone.utc):%Y-%m-%d %H:%M}

## Resultado

- **Ajuste al puesto:** {analisis.porcentaje_ajuste} %
- **Evaluación principal:** {principal.emoji} {principal.texto}
- **Recomendación final:** {recomendacion.emoji} {recomendacion.texto}

| Criterio | Peso | Nota (0-100) |
| --- | --- | --- |
{filas_criterios}

## Perfil

- **Educación:** {analisis.education}
- **Experiencia relevante:** {analisis.experiencia_anios} años

{analisis.experiencia_relevante}

## Requisitos del puesto

| Requisito | Tipo | Estado | Evidencia en el CV |
| --- | --- | --- | --- |
{filas_requisitos}

## Habilidades clave

{", ".join(analisis.habilidades_clave) or "—"}

## Fortalezas

{lista(analisis.fortalezas)}

## Áreas de desarrollo

{lista(analisis.areas_mejora)}

## Puesto evaluado

```text
{puesto}
```

> Análisis generado por un modelo de IA como apoyo. No reemplaza la decisión de una persona.
"""
