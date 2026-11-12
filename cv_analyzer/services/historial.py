"""Historial de análisis guardado en una base de datos con SQLAlchemy.

- En Docker se usa PostgreSQL (variable DATABASE_URL del docker-compose).
- Sin DATABASE_URL se usa un archivo SQLite local (datos/historial.db): útil para
  pruebas o para ejecutar sin Docker. El código es el MISMO para ambas bases.
"""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, DateTime, Integer, String, Text, create_engine, delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from models.cv_model import AnalisisCV
from services.errores import ErrorBaseDatos
from services.proveedores import ConfigModelo
from services.umbrales import evaluacion_principal, recomendacion_final

RUTA_SQLITE = Path(__file__).resolve().parent.parent / "datos" / "historial.db"


class Base(DeclarativeBase):
    pass


class RegistroAnalisis(Base):
    """Una fila = un análisis guardado."""

    __tablename__ = "analisis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID del análisis
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    nombre_candidato: Mapped[str] = mapped_column(String(200))
    archivo: Mapped[str] = mapped_column(String(255))
    huella_archivo: Mapped[str] = mapped_column(String(64), index=True)
    puesto: Mapped[str] = mapped_column(Text)
    proveedor: Mapped[str] = mapped_column(String(20))
    modelo: Mapped[str] = mapped_column(String(100))
    version_prompt: Mapped[str] = mapped_column(String(10))
    porcentaje: Mapped[int] = mapped_column(Integer, index=True)
    evaluacion: Mapped[str] = mapped_column(String(20))
    recomendacion: Mapped[str] = mapped_column(String(40))
    resultado: Mapped[dict] = mapped_column(JSON)  # AnalisisCV completo (model_dump)
    feedback: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 = 👍, 0 = 👎


@dataclass(frozen=True)
class ResumenAnalisis:
    """Lo que se muestra en la tabla del historial (sin el JSON completo)."""

    id: str
    creado_en: datetime
    nombre_candidato: str
    archivo: str
    puesto: str
    modelo: str
    porcentaje: int
    evaluacion: str
    recomendacion: str
    feedback: int | None


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------
def url_base_datos() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    return url or f"sqlite:///{RUTA_SQLITE}"


def crear_motor(url: str | None = None) -> Engine:
    """Crea el "motor" de conexión. pool_pre_ping revisa que la conexión siga viva antes de usarla."""
    url = url or url_base_datos()
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, pool_pre_ping=True)


def inicializar_bd(motor: Engine) -> None:
    """Crea la tabla si no existe (no borra datos existentes)."""
    try:
        Base.metadata.create_all(motor)
    except SQLAlchemyError as error:
        raise ErrorBaseDatos(f"No se pudo conectar con la base de datos: {error}") from error


def _resumen(registro: RegistroAnalisis) -> ResumenAnalisis:
    return ResumenAnalisis(
        id=registro.id, creado_en=registro.creado_en, nombre_candidato=registro.nombre_candidato,
        archivo=registro.archivo, puesto=registro.puesto, modelo=f"{registro.proveedor} · {registro.modelo}",
        porcentaje=registro.porcentaje, evaluacion=registro.evaluacion,
        recomendacion=registro.recomendacion, feedback=registro.feedback,
    )


# ---------------------------------------------------------------------------
# Operaciones
# ---------------------------------------------------------------------------
def guardar_analisis(
    motor: Engine, *, id_analisis: str, analisis: AnalisisCV, archivo: str, huella: str,
    puesto: str, config: ConfigModelo, version_prompt: str,
) -> bool:
    """Guarda el análisis. Devuelve False si ese id ya estaba guardado (no duplica)."""
    try:
        with Session(motor) as sesion, sesion.begin():
            if sesion.get(RegistroAnalisis, id_analisis) is not None:
                return False
            sesion.add(RegistroAnalisis(
                id=id_analisis, creado_en=datetime.now(timezone.utc),
                nombre_candidato=analisis.nombre_candidato[:200], archivo=archivo[:255], huella_archivo=huella,
                puesto=puesto, proveedor=config.proveedor, modelo=config.modelo[:100], version_prompt=version_prompt,
                porcentaje=analisis.porcentaje_ajuste,
                evaluacion=evaluacion_principal(analisis.porcentaje_ajuste).texto,
                recomendacion=recomendacion_final(analisis.porcentaje_ajuste).texto,
                resultado=analisis.model_dump(),
            ))
        return True
    except SQLAlchemyError as error:
        raise ErrorBaseDatos(f"No se pudo guardar el análisis: {error}") from error


def listar_analisis(motor: Engine, *, buscar: str = "", evaluacion: str | None = None, limite: int = 200) -> list[ResumenAnalisis]:
    """Análisis guardados, del más reciente al más antiguo, con filtros opcionales."""
    consulta = select(RegistroAnalisis).order_by(RegistroAnalisis.creado_en.desc()).limit(limite)
    if buscar.strip():
        patron = f"%{buscar.strip().lower()}%"
        consulta = consulta.where(
            func.lower(RegistroAnalisis.nombre_candidato).like(patron) | func.lower(RegistroAnalisis.puesto).like(patron)
        )
    if evaluacion:
        consulta = consulta.where(RegistroAnalisis.evaluacion == evaluacion)
    try:
        with Session(motor) as sesion:
            return [_resumen(r) for r in sesion.scalars(consulta)]
    except SQLAlchemyError as error:
        raise ErrorBaseDatos(f"No se pudo leer el historial: {error}") from error


def obtener_analisis(motor: Engine, id_analisis: str) -> tuple[ResumenAnalisis, AnalisisCV] | None:
    """El registro y el AnalisisCV reconstruido (validado otra vez con Pydantic)."""
    try:
        with Session(motor) as sesion:
            registro = sesion.get(RegistroAnalisis, id_analisis)
            if registro is None:
                return None
            return _resumen(registro), AnalisisCV.model_validate(registro.resultado)
    except SQLAlchemyError as error:
        raise ErrorBaseDatos(f"No se pudo leer el análisis: {error}") from error


def eliminar_analisis(motor: Engine, id_analisis: str) -> bool:
    try:
        with Session(motor) as sesion, sesion.begin():
            resultado = sesion.execute(delete(RegistroAnalisis).where(RegistroAnalisis.id == id_analisis))
            return resultado.rowcount > 0
    except SQLAlchemyError as error:
        raise ErrorBaseDatos(f"No se pudo eliminar el análisis: {error}") from error


def registrar_feedback(motor: Engine, id_analisis: str, valor: int | None) -> bool:
    """Guarda la opinión del reclutador sobre el análisis: 1 = 👍, 0 = 👎, None = sin opinión."""
    if valor not in (None, 0, 1):
        raise ValueError("El feedback debe ser 0, 1 o None.")
    try:
        with Session(motor) as sesion, sesion.begin():
            registro = sesion.get(RegistroAnalisis, id_analisis)
            if registro is None:
                return False
            registro.feedback = valor
            return True
    except SQLAlchemyError as error:
        raise ErrorBaseDatos(f"No se pudo guardar el feedback: {error}") from error


def estadisticas(motor: Engine) -> dict:
    """Totales para las tarjetas del historial."""
    try:
        with Session(motor) as sesion:
            total, promedio = sesion.execute(
                select(func.count(RegistroAnalisis.id), func.avg(RegistroAnalisis.porcentaje))
            ).one()
            recomendados = sesion.scalar(select(func.count()).where(RegistroAnalisis.porcentaje >= 70))
            con_feedback, positivos = sesion.execute(
                select(func.count(RegistroAnalisis.feedback), func.coalesce(func.sum(RegistroAnalisis.feedback), 0))
            ).one()
    except SQLAlchemyError as error:
        raise ErrorBaseDatos(f"No se pudieron calcular las estadísticas: {error}") from error
    return {
        "total": total,
        "promedio": round(float(promedio), 1) if promedio is not None else None,
        "recomendados": recomendados,
        "con_feedback": con_feedback,
        "feedback_positivo": positivos,
    }
