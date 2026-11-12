"""Interfaz de Streamlit: entradas, validaciones y presentación del análisis.

El resultado se guarda en st.session_state para que no desaparezca cuando
Streamlit vuelve a ejecutar el script (por ejemplo, al pulsar otro botón).
"""

import streamlit as st

from models.cv_model import AnalisisCV
from services.cv_evaluator import ErrorEntrada, ErrorEvaluacion, evaluar_candidato
from services.pdf_processor import ErrorPDF, extraer_texto_pdf
from services.umbrales import evaluacion_principal, recomendacion_final

EJEMPLO_PUESTO = (
    "Puesto: Desarrollador Python\n"
    "Requisitos obligatorios: 3 años de experiencia, Python, APIs REST y PostgreSQL.\n"
    "Deseables: Docker, pruebas automatizadas y experiencia con LangChain.\n"
    "Responsabilidades: desarrollar servicios, integrar APIs y mantener pruebas."
)


# ---------------------------------------------------------------------------
# Estado de la sesión
# ---------------------------------------------------------------------------
def inicializar_estado() -> None:
    """Crea las claves de session_state que usa la app (solo la primera vez)."""
    st.session_state.setdefault("uploader_id", 0)      # cambiarlo "reinicia" el file_uploader
    st.session_state.setdefault("descripcion_puesto", "")
    st.session_state.setdefault("analisis", None)       # último AnalisisCV
    st.session_state.setdefault("archivo_analizado", None)


def limpiar() -> None:
    """Callback del botón Limpiar: borra el PDF, la descripción y el resultado."""
    st.session_state["uploader_id"] += 1
    st.session_state["descripcion_puesto"] = ""
    st.session_state["analisis"] = None
    st.session_state["archivo_analizado"] = None


# ---------------------------------------------------------------------------
# Acción principal
# ---------------------------------------------------------------------------
def analizar(archivo, descripcion: str) -> None:
    """Valida las entradas, extrae el texto, llama al modelo y guarda el resultado."""
    if archivo is None:
        st.warning("⚠️ Sube el CV del candidato en PDF.")
        return
    if not descripcion.strip():
        st.warning("⚠️ Escribe la descripción del puesto.")
        return

    with st.spinner("Leyendo el PDF y evaluando al candidato..."):
        try:
            texto_cv = extraer_texto_pdf(archivo)
            analisis = evaluar_candidato(texto_cv, descripcion)
        except ErrorPDF as error:
            st.error(f"📄 {error}")
            return
        except ErrorEntrada as error:
            st.warning(f"⚠️ {error}")
            return
        except ErrorEvaluacion as error:
            # Nunca se muestra un resultado inventado: solo el error.
            st.error(f"🤖 {error}")
            return

    st.session_state["analisis"] = analisis
    st.session_state["archivo_analizado"] = archivo.name


# ---------------------------------------------------------------------------
# Secciones de la pantalla
# ---------------------------------------------------------------------------
def mostrar_encabezado() -> None:
    st.title("📄 Sistema de Evaluación de CV")
    st.markdown(
        "Compara el CV de un candidato con la descripción de un puesto para:\n"
        "- Analizar la experiencia y habilidades del candidato\n"
        "- Evaluar el ajuste al puesto específico\n"
        "- Proporcionar recomendaciones objetivas de contratación"
    )
    st.divider()


def mostrar_entradas() -> None:
    st.header("📋 Datos de Entrada")

    archivo = st.file_uploader(
        "1. Sube el CV del candidato (PDF)",
        type=["pdf"],
        key=f"cv_pdf_{st.session_state['uploader_id']}",
        help="El PDF debe tener texto seleccionable (no imágenes escaneadas).",
    )
    if archivo is not None:
        st.success(f"Archivo cargado: {archivo.name}", icon="✅")
        st.info(f"Tamaño: {archivo.size:,} bytes", icon="📊")

    st.divider()
    descripcion = st.text_area(
        "2. Descripción del puesto de trabajo",
        key="descripcion_puesto",
        height=200,
        placeholder=EJEMPLO_PUESTO,
        help="Incluye requisitos obligatorios, deseables y responsabilidades.",
    )

    col_analizar, col_limpiar = st.columns(2)
    with col_analizar:
        if st.button("🔍 Analizar Candidato", type="primary", use_container_width=True):
            analizar(archivo, descripcion)
    with col_limpiar:
        st.button("🗑️ Limpiar", on_click=limpiar, use_container_width=True)

    # Aviso si el PDF cargado ya no es el que se analizó
    analizado = st.session_state["archivo_analizado"]
    if st.session_state["analisis"] is not None and archivo is not None and archivo.name != analizado:
        st.warning(f"El resultado mostrado corresponde a «{analizado}». Pulsa Analizar para evaluar el nuevo CV.")


def mostrar_instrucciones() -> None:
    st.info(
        "**Instrucciones:**\n"
        "1. Sube un CV en formato PDF en la columna izquierda\n"
        "2. Describe detalladamente el puesto de trabajo\n"
        "3. Haz clic en «Analizar Candidato»\n"
        "4. Aquí aparecerá el análisis completo del candidato\n\n"
        "**Consejos para mejores resultados:**\n"
        "- Usa CV con texto seleccionable (no imágenes escaneadas)\n"
        "- Sé específico en la descripción del puesto\n"
        "- Incluye tanto requisitos obligatorios como deseables",
        icon="👈",
    )


def mostrar_lista_numerada(elementos: list[str]) -> None:
    if not elementos:
        st.caption("Sin elementos.")
        return
    st.markdown("\n".join(f"{i}. {texto}" for i, texto in enumerate(elementos, start=1)))


def mostrar_resultado(analisis: AnalisisCV) -> None:
    principal = evaluacion_principal(analisis.porcentaje_ajuste)
    recomendacion = recomendacion_final(analisis.porcentaje_ajuste)

    # Evaluación principal
    st.subheader("🎯 Evaluación Principal")
    st.metric("Porcentaje de ajuste al puesto", f"{analisis.porcentaje_ajuste} %")
    st.progress(analisis.porcentaje_ajuste / 100)
    st.markdown(f"{principal.emoji} **{principal.texto.upper()}**")
    st.divider()

    # Perfil
    st.subheader("👤 Perfil del Candidato")
    col_a, col_b = st.columns(2)
    with col_a:
        st.info(f"**Nombre:** {analisis.nombre_candidato}", icon="🧑")
        st.info(f"**Experiencia relevante:** {analisis.experiencia_anios} años", icon="⏱️")
    with col_b:
        st.info(f"**Educación:** {analisis.education}", icon="🎓")

    st.subheader("💼 Experiencia Relevante")
    st.info(analisis.experiencia_relevante, icon="📋")
    st.divider()

    # Habilidades en filas de 4
    st.subheader("🛠️ Habilidades Técnicas Clave")
    if analisis.habilidades_clave:
        for inicio in range(0, len(analisis.habilidades_clave), 4):
            columnas = st.columns(4)
            for columna, habilidad in zip(columnas, analisis.habilidades_clave[inicio:inicio + 4]):
                columna.success(habilidad, icon="✅")
    else:
        st.caption("El CV no muestra habilidades relevantes para este puesto.")
    st.divider()

    # Fortalezas y áreas de desarrollo
    col_f, col_m = st.columns(2)
    with col_f:
        st.subheader("💪 Fortalezas Principales")
        mostrar_lista_numerada(analisis.fortalezas)
    with col_m:
        st.subheader("📈 Áreas de Desarrollo")
        mostrar_lista_numerada(analisis.areas_mejora)
    st.divider()

    # Recomendación final
    st.subheader("📝 Recomendación Final")
    aviso = {"success": st.success, "warning": st.warning, "error": st.error}[recomendacion.nivel]
    aviso(f"**{recomendacion.texto}** ({analisis.porcentaje_ajuste} % de ajuste)", icon=recomendacion.emoji)
    st.caption(
        "El porcentaje lo estima un modelo de IA y puede variar entre ejecuciones. "
        "Úsalo como apoyo, no como decisión final de contratación."
    )

    if st.button("💾 Guardar Análisis"):
        st.info("La opción de guardar análisis está en desarrollo.", icon="🚧")


# ---------------------------------------------------------------------------
# Punto de entrada de la interfaz
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Sistema de Evaluación de CV", page_icon="📄", layout="wide")
    inicializar_estado()
    mostrar_encabezado()

    col_entrada, col_resultado = st.columns(2, gap="large")
    with col_entrada:
        mostrar_entradas()
    with col_resultado:
        st.header("📊 Resultado del Análisis")
        if st.session_state["analisis"] is None:
            mostrar_instrucciones()
        else:
            mostrar_resultado(st.session_state["analisis"])
