"""Comparar varios candidatos para el mismo puesto y obtener un ranking."""

import pandas as pd
import streamlit as st

from models.cv_model import NOMBRES_CRITERIOS, PESOS_CRITERIOS
from services.errores import ErrorAplicacion, ErrorConfiguracion
from services.umbrales import evaluacion_principal, recomendacion_final
from ui.cache import obtener_plantillas
from ui.componentes import grafico_radar
from ui.estado import config_actual
from ui.flujo import aplicar_plantilla, evaluar_archivo

MAX_ARCHIVOS = 10


def formulario() -> None:
    st.selectbox(
        "📋 Plantilla de puesto (opcional)", options=list(obtener_plantillas()), index=None,
        placeholder="Elige una plantilla para llenar la descripción…", key="plantilla_comparar",
        on_change=aplicar_plantilla, args=("plantilla_comparar", "puesto_comparar"),
    )
    with st.form("form_comparar", border=True):
        col_pdf, col_puesto = st.columns([1, 1.4], gap="large")
        with col_pdf:
            archivos = st.file_uploader(
                f"📤 CV de los candidatos (hasta {MAX_ARCHIVOS} PDF)", type=["pdf"], accept_multiple_files=True,
                key=f"cvs_{st.session_state['uploader_comparar']}",
            )
        with col_puesto:
            st.text_area("💼 Descripción del puesto", key="puesto_comparar", height=180)
        enviado = st.form_submit_button("📊 Comparar candidatos", type="primary", width="stretch")
    if enviado:
        comparar(archivos or [], st.session_state["puesto_comparar"])


def comparar(archivos, puesto: str) -> None:
    if len(archivos) < 2:
        st.warning("Sube al menos 2 CV para comparar.", icon="⚠️")
        return
    if len(archivos) > MAX_ARCHIVOS:
        st.warning(f"Sube como máximo {MAX_ARCHIVOS} CV a la vez.", icon="⚠️")
        return
    if not puesto.strip():
        st.warning("Escribe la descripción del puesto o elige una plantilla.", icon="⚠️")
        return
    try:
        config = config_actual()
    except ErrorConfiguracion as error:
        st.error(f"🔑 {error}")
        return

    resultados, errores = [], []
    barra = st.progress(0.0, text="Preparando…")
    with st.status(f"Evaluando {len(archivos)} candidatos con {config.etiqueta}…", expanded=True) as estado:
        for i, archivo in enumerate(archivos, start=1):
            barra.progress((i - 1) / len(archivos), text=f"Analizando {archivo.name} ({i}/{len(archivos)})")
            try:
                resultado = evaluar_archivo(archivo.name, archivo.getvalue(), puesto, config)
                resultados.append(resultado)
                estado.write(f"✅ {archivo.name}: {resultado.analisis.porcentaje_ajuste} %"
                             + (" ♻️" if resultado.reutilizado else ""))
            except ErrorAplicacion as error:  # un CV con problemas no detiene a los demás
                errores.append((archivo.name, str(error)))
                estado.write(f"❌ {archivo.name}: {error}")
        barra.progress(1.0, text="Listo")
        estado.update(label=f"{len(resultados)} de {len(archivos)} candidatos evaluados",
                      state="complete" if resultados else "error", expanded=bool(errores))

    resultados.sort(key=lambda r: r.analisis.porcentaje_ajuste, reverse=True)
    st.session_state["comparacion"] = {"puesto": puesto, "resultados": resultados, "errores": errores}
    if resultados:
        st.toast("Comparación lista", icon="📊")


def tabla_ranking(resultados) -> pd.DataFrame:
    filas = []
    for posicion, r in enumerate(resultados, start=1):
        a = r.analisis
        conteo = a.conteo_requisitos()
        fila = {
            "#": posicion, "Candidato": a.nombre_candidato, "Archivo": r.archivo,
            "Ajuste": a.porcentaje_ajuste,
            "Evaluación": evaluacion_principal(a.porcentaje_ajuste).texto,
            "Recomendación": recomendacion_final(a.porcentaje_ajuste).texto,
        }
        fila.update({NOMBRES_CRITERIOS[c]: getattr(a.puntajes, c) for c in PESOS_CRITERIOS})
        fila["Requisitos cumplidos"] = f"{conteo['cumple']}/{len(a.requisitos)}"
        fila["Años relevantes"] = a.experiencia_anios
        filas.append(fila)
    return pd.DataFrame(filas)


def mostrar_comparacion(datos: dict) -> None:
    resultados = datos["resultados"]
    if datos["errores"]:
        with st.expander(f"⚠️ {len(datos['errores'])} CV no se pudieron evaluar"):
            for nombre, mensaje in datos["errores"]:
                st.markdown(f"- **{nombre}:** {mensaje}")
    if not resultados:
        return

    mejor = resultados[0]
    st.success(f"🏆 Mejor ajuste: **{mejor.analisis.nombre_candidato}** con **{mejor.analisis.porcentaje_ajuste} %**")

    tabla = tabla_ranking(resultados)
    st.dataframe(
        tabla, hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn(width="small"),
            "Ajuste": st.column_config.ProgressColumn("Ajuste", min_value=0, max_value=100, format="%d %%"),
            **{NOMBRES_CRITERIOS[c]: st.column_config.NumberColumn(format="%d") for c in PESOS_CRITERIOS},
        },
    )
    st.download_button("⬇️ Descargar ranking (CSV)", tabla.to_csv(index=False).encode("utf-8"),
                       "ranking_candidatos.csv", "text/csv", on_click="ignore")

    with st.container(border=True):
        st.markdown("**🕸️ Comparación por criterio**")
        series = {f"{i}. {r.analisis.nombre_candidato}": r.analisis.puntajes for i, r in enumerate(resultados[:6], 1)}
        st.plotly_chart(grafico_radar(series, alto=420), key="radar_comparacion")
        if len(resultados) > 6:
            st.caption("Se muestran los 6 primeros para que el gráfico sea legible.")

    st.markdown("#### 🔎 Ver un candidato en detalle")
    col_sel, col_btn = st.columns([3, 1], vertical_alignment="bottom")
    opciones = {f"{i}. {r.analisis.nombre_candidato} ({r.archivo})": r for i, r in enumerate(resultados, 1)}
    elegido = col_sel.selectbox("Candidato", list(opciones))
    if col_btn.button("Abrir en Evaluar →", width="stretch"):
        st.session_state["evaluacion"] = opciones[elegido]
        st.switch_page("ui/paginas/evaluar.py")


st.title("📊 Comparar candidatos")
st.caption("Evalúa varios CV contra el mismo puesto y obtén un ranking. Los CV ya analizados se reutilizan de la caché.")
formulario()
if st.session_state["comparacion"]:
    st.divider()
    mostrar_comparacion(st.session_state["comparacion"])
