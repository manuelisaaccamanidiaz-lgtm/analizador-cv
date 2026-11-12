"""Historial de análisis guardados en la base de datos."""

import pandas as pd
import streamlit as st

from services.errores import ErrorBaseDatos
from services.historial import eliminar_analisis, estadisticas, listar_analisis, obtener_analisis
from services.proveedores import ConfigModelo
from ui.cache import obtener_motor
from ui.componentes import mostrar_resultado, widget_feedback
from ui.estado import ResultadoEvaluacion

EVALUACIONES = ["Excelente", "Bueno", "Regular", "Bajo"]


def eliminar(id_analisis: str) -> None:
    """Callback del botón Eliminar del diálogo."""
    try:
        eliminar_analisis(obtener_motor(), id_analisis)
    except ErrorBaseDatos as error:
        st.toast(f"No se pudo eliminar: {error}", icon="⚠️")
        return
    st.session_state["guardados"].discard(id_analisis)
    st.toast("Análisis eliminado", icon="🗑️")


@st.dialog("¿Eliminar este análisis?")
def confirmar_eliminacion(id_analisis: str, nombre: str) -> None:
    st.write(f"Se eliminará el análisis de **{nombre}**. Esta acción no se puede deshacer.")
    col_si, col_no = st.columns(2)
    col_si.button("🗑️ Eliminar", type="primary", width="stretch", on_click=eliminar, args=(id_analisis,))
    col_no.button("Cancelar", width="stretch")


st.title("🗂️ Historial")
st.caption("Análisis guardados con el botón **Guardar en el historial**. No se guarda el PDF ni su texto, solo el análisis.")

try:
    motor = obtener_motor()
    resumen = estadisticas(motor)
except ErrorBaseDatos as error:
    st.error(f"🗄️ {error}")
    st.info("Si usas Docker, revisa que el servicio `db` esté encendido (`docker compose ps`).")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Análisis guardados", resumen["total"], border=True)
col2.metric("Ajuste promedio", f"{resumen['promedio']} %" if resumen["promedio"] is not None else "—", border=True)
col3.metric("Recomendados (≥ 70 %)", resumen["recomendados"], border=True)
col4.metric("Feedback positivo", f"{resumen['feedback_positivo']}/{resumen['con_feedback']}", border=True)

col_buscar, col_filtro = st.columns([2, 3], vertical_alignment="bottom")
buscar = col_buscar.text_input("🔎 Buscar por candidato o puesto", placeholder="Ej.: Python, Ana…")
filtro = col_filtro.segmented_control("Evaluación", EVALUACIONES, key="filtro_evaluacion")

try:
    registros = listar_analisis(motor, buscar=buscar, evaluacion=filtro)
except ErrorBaseDatos as error:
    st.error(f"🗄️ {error}")
    st.stop()

if not registros:
    st.info("No hay análisis que coincidan." if (buscar or filtro) else "Todavía no has guardado análisis.", icon="📭")
    st.stop()

tabla = pd.DataFrame([{
    "Fecha (UTC)": r.creado_en.strftime("%Y-%m-%d %H:%M"), "Candidato": r.nombre_candidato,
    "Puesto": r.puesto.splitlines()[0][:60], "Ajuste": r.porcentaje, "Evaluación": r.evaluacion,
    "Recomendación": r.recomendacion, "Modelo": r.modelo,
    "Feedback": {1: "👍", 0: "👎"}.get(r.feedback, "—"),
} for r in registros])

seleccion = st.dataframe(
    tabla, hide_index=True, on_select="rerun", selection_mode="single-row", key="tabla_historial",
    column_config={"Ajuste": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d %%")},
)
st.download_button("⬇️ Descargar historial (CSV)", tabla.to_csv(index=False).encode("utf-8"),
                   "historial_analisis.csv", "text/csv", on_click="ignore")

filas = seleccion.selection.rows
if not filas or filas[0] >= len(registros):  # sin selección, o la fila ya no existe (se eliminó)
    st.caption("👆 Selecciona una fila para ver el análisis completo.")
    st.stop()

registro = registros[filas[0]]
try:
    encontrado = obtener_analisis(motor, registro.id)
except ErrorBaseDatos as error:
    st.error(f"🗄️ {error}")
    st.stop()
if encontrado is None:
    st.warning("El análisis ya no existe.")
    st.stop()

_, analisis = encontrado
proveedor, _, modelo = registro.modelo.partition(" · ")
ev = ResultadoEvaluacion(
    id=registro.id, analisis=analisis, texto_cv="", pdf_bytes=None, archivo=registro.archivo,
    huella="", puesto=registro.puesto, config=ConfigModelo(proveedor, modelo),
)

st.divider()
col_titulo, col_fb, col_borrar = st.columns([3, 2, 1], vertical_alignment="center")
col_titulo.subheader(f"📊 {analisis.nombre_candidato}")
with col_fb:
    widget_feedback(registro.id, valor_inicial=registro.feedback)
if col_borrar.button("🗑️ Eliminar", width="stretch"):
    confirmar_eliminacion(registro.id, analisis.nombre_candidato)
mostrar_resultado(ev, desde_historial=True)
