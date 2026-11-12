"""Estado de la sesión y barra lateral compartida por todas las páginas."""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import streamlit as st

from models.cv_model import AnalisisCV
from services.errores import ErrorConfiguracion
from services.proveedores import PROVEEDORES, ConfigModelo, config_desde_entorno, proveedores_disponibles


@dataclass
class ResultadoEvaluacion:
    """Todo lo de UN análisis: el resultado de la IA y los datos para el chat, la descarga y el historial."""

    id: str                      # UUID: identifica el análisis (evita guardarlo dos veces)
    analisis: AnalisisCV
    texto_cv: str
    pdf_bytes: bytes | None      # None cuando viene del historial
    archivo: str
    huella: str                  # SHA-256 del PDF
    puesto: str
    config: ConfigModelo
    reutilizado: bool = False    # True si salió de la caché (sin llamar al modelo)
    creado: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


VALORES_INICIALES = {
    "evaluacion": None,           # ResultadoEvaluacion actual (página Evaluar y Chat)
    "comparacion": None,          # resultados de la página Comparar
    "guardados": set(),           # ids ya guardados en el historial
    "preguntas": {},              # id del análisis -> PreguntasEntrevista
    "chats": {},                  # huella:proveedor -> lista de mensajes
    "claves_analizadas": set(),   # para avisar cuando un resultado viene de la caché
    "uploader_evaluar": 0,        # cambiarlo "reinicia" el file_uploader
    "uploader_comparar": 0,
    "puesto_evaluar": "",
    "puesto_comparar": "",
}


def inicializar_estado() -> None:
    """Crea las claves de session_state la primera vez (setdefault no pisa valores existentes)."""
    for clave, valor in VALORES_INICIALES.items():
        st.session_state.setdefault(clave, valor.copy() if isinstance(valor, (set, dict)) else valor)
    disponibles = proveedores_disponibles()
    if st.session_state.get("proveedor") not in disponibles:
        st.session_state["proveedor"] = disponibles[0] if disponibles else None


def config_actual() -> ConfigModelo:
    """Configuración del proveedor elegido en la barra lateral."""
    proveedor = st.session_state.get("proveedor")
    if not proveedor:
        raise ErrorConfiguracion(
            "No hay ningún proveedor de IA configurado. Crea cv_analyzer/.env a partir de .env.example."
        )
    return config_desde_entorno(proveedor)


def mostrar_barra_lateral() -> None:
    with st.sidebar:
        st.markdown("### ⚙️ Modelo de IA")
        disponibles = proveedores_disponibles()
        if not disponibles:
            st.error("No hay proveedores configurados. Revisa el archivo `.env`.", icon="🔑")
        else:
            st.segmented_control(
                "Proveedor",
                options=disponibles,
                format_func=lambda clave: PROVEEDORES[clave]["nombre"],
                key="proveedor",
                required=True,
                help="Solo aparecen los proveedores con sus variables configuradas en el .env.",
            )
            try:
                config = config_actual()
                st.caption(f"Modelo: `{config.modelo}`")
                st.caption(f"Embeddings (chat): `{config.modelo_embeddings or 'no configurado'}`")
            except ErrorConfiguracion as error:
                st.warning(str(error))

        st.divider()
        evaluacion = st.session_state.get("evaluacion")
        if evaluacion is not None:
            st.markdown("### 📄 CV actual")
            st.caption(f"{evaluacion.analisis.nombre_candidato} · {evaluacion.archivo}")
            st.caption(f"Ajuste: **{evaluacion.analisis.porcentaje_ajuste} %**")
        base = "PostgreSQL" if os.getenv("DATABASE_URL", "").startswith("postgresql") else "SQLite (local)"
        st.caption(f"🗄️ Historial en {base}")
