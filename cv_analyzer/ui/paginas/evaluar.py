"""Página principal: evaluar UN candidato frente a un puesto."""

import streamlit as st

from services.errores import ErrorConfiguracion, ErrorEntrada, ErrorEvaluacion, ErrorPDF
from ui.cache import obtener_plantillas
from ui.componentes import mostrar_resultado
from ui.estado import config_actual
from ui.flujo import aplicar_plantilla, evaluar_archivo


def limpiar() -> None:
    """Callback: se ejecuta antes de redibujar la página, así los widgets aparecen vacíos."""
    st.session_state["uploader_evaluar"] += 1  # nueva key -> file_uploader vacío
    st.session_state["puesto_evaluar"] = ""
    st.session_state["evaluacion"] = None
    st.session_state["plantilla_evaluar"] = None


@st.dialog("¿Limpiar el análisis?")
def confirmar_limpieza() -> None:
    st.write("Se borrarán el PDF cargado, la descripción del puesto y el resultado actual.")
    st.caption("Lo que ya guardaste en el historial no se borra.")
    col_si, col_no = st.columns(2)
    # Al pulsar cualquiera de los dos, la app se recarga y el diálogo se cierra solo.
    col_si.button("🗑️ Sí, limpiar", type="primary", width="stretch", on_click=limpiar)
    col_no.button("Cancelar", width="stretch")


def formulario() -> None:
    st.selectbox(
        "📋 Plantilla de puesto (opcional)",
        options=list(obtener_plantillas()),
        index=None,
        placeholder="Elige una plantilla para llenar la descripción…",
        key="plantilla_evaluar",
        on_change=aplicar_plantilla,
        args=("plantilla_evaluar", "puesto_evaluar"),
    )

    # st.form: los widgets de adentro NO recargan la página hasta pulsar el botón de envío
    with st.form("form_evaluar", border=True):
        col_pdf, col_puesto = st.columns([1, 1.4], gap="large")
        with col_pdf:
            archivo = st.file_uploader(
                "📤 CV del candidato (PDF)", type=["pdf"],
                key=f"cv_{st.session_state['uploader_evaluar']}",
                help="El PDF debe tener texto seleccionable (no imágenes escaneadas).",
            )
        with col_puesto:
            st.text_area(
                "💼 Descripción del puesto", key="puesto_evaluar", height=180,
                placeholder="Puesto, requisitos obligatorios, deseables y responsabilidades…",
            )
        enviado = st.form_submit_button("🔍 Analizar candidato", type="primary", width="stretch")

    if st.button("🗑️ Limpiar", type="tertiary"):
        confirmar_limpieza()

    if enviado:
        analizar(archivo, st.session_state["puesto_evaluar"])


def analizar(archivo, puesto: str) -> None:
    if archivo is None:
        st.warning("Sube el CV del candidato en PDF.", icon="⚠️")
        return
    if not puesto.strip():
        st.warning("Escribe la descripción del puesto o elige una plantilla.", icon="⚠️")
        return

    # st.status muestra los pasos mientras trabaja y se puede plegar al terminar
    with st.status("Analizando al candidato…", expanded=True) as estado:
        try:
            config = config_actual()
            estado.write(f"📄 Leyendo **{archivo.name}**…")
            estado.write(f"🤖 Evaluando con **{config.etiqueta}**…")
            resultado = evaluar_archivo(archivo.name, archivo.getvalue(), puesto, config)
        except ErrorPDF as error:
            estado.update(label="No se pudo leer el PDF", state="error")
            st.error(f"📄 {error}")
            return
        except ErrorEntrada as error:
            estado.update(label="Faltan datos", state="error")
            st.warning(f"⚠️ {error}")
            return
        except ErrorConfiguracion as error:
            estado.update(label="Configuración incompleta", state="error")
            st.error(f"🔑 {error}")
            return
        except ErrorEvaluacion as error:
            estado.update(label="El modelo no pudo evaluar el CV", state="error")
            st.error(f"🤖 {error}")  # nunca un resultado inventado
            return
        estado.update(label="Análisis listo", state="complete", expanded=False)

    st.session_state["evaluacion"] = resultado
    st.toast("Análisis listo" + (" (desde la caché ♻️)" if resultado.reutilizado else ""), icon="✅")


st.title("🔍 Evaluar candidato")
st.caption("Compara un CV con la descripción de un puesto: ajuste, requisitos, habilidades y preguntas para la entrevista.")
formulario()

evaluacion = st.session_state["evaluacion"]
if evaluacion is None:
    st.info(
        "**Cómo usarlo:** 1) sube un CV en PDF · 2) escribe el puesto o elige una plantilla · "
        "3) pulsa **Analizar candidato**. Después podrás chatear con el CV, descargar el informe y guardarlo.",
        icon="👆",
    )
else:
    st.divider()
    st.subheader(f"📊 {evaluacion.analisis.nombre_candidato}")
    st.caption(f"Archivo: {evaluacion.archivo}")
    mostrar_resultado(evaluacion)
    st.page_link("ui/paginas/chat.py", label="Hacer preguntas sobre este CV", icon="💬")
