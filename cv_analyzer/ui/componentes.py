"""Componentes visuales reutilizables: tarjetas, gráfico radar, pestañas del resultado."""

import plotly.graph_objects as go
import streamlit as st

from models.cv_model import NOMBRES_CRITERIOS, PESOS_CRITERIOS, AnalisisCV, PuntajesCriterios
from prompts.cv_prompts import VERSION_PROMPT
from services.entrevista import generar_preguntas
from services.errores import ErrorBaseDatos, ErrorEvaluacion
from services.historial import guardar_analisis, registrar_feedback
from services.informe import informe_json, informe_markdown
from services.umbrales import evaluacion_principal, recomendacion_final
from ui.cache import obtener_generador_preguntas, obtener_motor
from ui.estado import ResultadoEvaluacion

COLOR_BADGE = {"success": "green", "warning": "orange", "error": "red"}
TEXTO_ESTADO = {"cumple": "✅ Cumple", "parcial": "🟡 Parcial", "no_cumple": "❌ No cumple"}
COLORES_SERIES = ["#0E7C66", "#F28C38", "#3B6FD8", "#B5446E", "#7A6C00", "#5B6B80"]


# ---------------------------------------------------------------------------
# Gráfico radar
# ---------------------------------------------------------------------------
def grafico_radar(series: dict[str, PuntajesCriterios], alto: int = 360) -> go.Figure:
    """Un polígono por candidato sobre los 4 criterios (0-100)."""
    etiquetas = [NOMBRES_CRITERIOS[c] for c in PESOS_CRITERIOS]
    figura = go.Figure()
    for i, (nombre, puntajes) in enumerate(series.items()):
        valores = [getattr(puntajes, c) for c in PESOS_CRITERIOS]
        color = COLORES_SERIES[i % len(COLORES_SERIES)]
        figura.add_trace(go.Scatterpolar(
            r=valores + valores[:1], theta=etiquetas + etiquetas[:1], name=nombre,
            fill="toself" if len(series) == 1 else "none", line={"color": color, "width": 2},
            hovertemplate="%{theta}: %{r}<extra>" + nombre + "</extra>",
        ))
    figura.update_layout(
        polar={"radialaxis": {"range": [0, 100], "tickvals": [25, 50, 75, 100]}},
        showlegend=len(series) > 1, height=alto, margin={"l": 40, "r": 40, "t": 30, "b": 30},
        legend={"orientation": "h", "y": -0.15},
    )
    return figura


# ---------------------------------------------------------------------------
# Tarjetas de resumen
# ---------------------------------------------------------------------------
def explicacion_calculo(analisis: AnalisisCV) -> None:
    with st.popover("ℹ️ ¿Cómo se calcula?"):
        st.markdown("El modelo da una **nota de 0 a 100** por criterio y **Python** calcula el promedio ponderado:")
        filas = "\n".join(
            f"| {NOMBRES_CRITERIOS[c]} | {int(p * 100)} % | {getattr(analisis.puntajes, c)} | "
            f"{getattr(analisis.puntajes, c) * p:.1f} |"
            for c, p in PESOS_CRITERIOS.items()
        )
        st.markdown(
            "| Criterio | Peso | Nota | Aporte |\n| --- | --- | --- | --- |\n"
            f"{filas}\n| **Total** | 100 % | | **{analisis.porcentaje_ajuste}** |"
        )


def mostrar_tarjetas(analisis: AnalisisCV) -> None:
    principal = evaluacion_principal(analisis.porcentaje_ajuste)
    recomendacion = recomendacion_final(analisis.porcentaje_ajuste)
    conteo = analisis.conteo_requisitos()

    with st.container(border=True):
        st.metric("🎯 Ajuste al puesto", f"{analisis.porcentaje_ajuste} %")
        st.progress(analisis.porcentaje_ajuste / 100)
        explicacion_calculo(analisis)
    with st.container(border=True):
        st.caption("Evaluación principal")
        st.badge(principal.texto.upper(), icon=principal.emoji, color=COLOR_BADGE[principal.nivel])
        st.caption("Recomendación final")
        st.badge(recomendacion.texto, icon=recomendacion.emoji, color=COLOR_BADGE[recomendacion.nivel])
    with st.container(border=True):
        st.caption(f"Requisitos del puesto ({len(analisis.requisitos)})")
        st.markdown(f"✅ **{conteo['cumple']}** cumple · 🟡 **{conteo['parcial']}** parcial · ❌ **{conteo['no_cumple']}** no cumple")


# ---------------------------------------------------------------------------
# Pestañas
# ---------------------------------------------------------------------------
def pestana_resumen(analisis: AnalisisCV) -> None:
    col_a, col_b, col_c = st.columns(3)
    col_a.info(f"**Nombre**\n\n{analisis.nombre_candidato}", icon="🧑")
    col_b.info(f"**Educación**\n\n{analisis.education}", icon="🎓")
    col_c.info(f"**Experiencia relevante**\n\n{analisis.experiencia_anios} años", icon="⏱️")
    st.markdown("#### 💼 Experiencia relevante")
    st.write(analisis.experiencia_relevante)
    col_f, col_m = st.columns(2)
    with col_f:
        st.markdown("#### 💪 Fortalezas")
        st.markdown("\n".join(f"{i}. {t}" for i, t in enumerate(analisis.fortalezas, 1)) or "—")
    with col_m:
        st.markdown("#### 📈 Áreas de desarrollo")
        st.markdown("\n".join(f"{i}. {t}" for i, t in enumerate(analisis.areas_mejora, 1)) or "—")


def pestana_requisitos(analisis: AnalisisCV) -> None:
    if not analisis.requisitos:
        st.info("El modelo no identificó requisitos en la descripción del puesto.")
        return
    filas = [
        {"Requisito": r.requisito, "Tipo": "Obligatorio" if r.obligatorio else "Deseable",
         "Estado": TEXTO_ESTADO[r.estado], "Evidencia en el CV": r.evidencia or "—"}
        for r in analisis.requisitos
    ]
    st.dataframe(
        filas, hide_index=True,
        column_config={
            "Requisito": st.column_config.TextColumn(width="medium"),
            "Tipo": st.column_config.TextColumn(width="small"),
            "Estado": st.column_config.TextColumn(width="small"),
            "Evidencia en el CV": st.column_config.TextColumn(width="large"),
        },
    )
    st.caption("La evidencia sale del CV: si un requisito aparece como cumplido sin evidencia, desconfía 🕵️.")


def pestana_habilidades(analisis: AnalisisCV) -> None:
    if not analisis.habilidades_clave:
        st.caption("El CV no muestra habilidades relevantes para este puesto.")
        return
    with st.container(horizontal=True):
        for habilidad in analisis.habilidades_clave:
            st.badge(habilidad, icon="🛠️", color="green")


@st.fragment
def pestana_entrevista(ev: ResultadoEvaluacion) -> None:
    """Fragmento: al pulsar el botón solo se vuelve a ejecutar esta parte, no toda la página."""
    preguntas = st.session_state["preguntas"].get(ev.id)
    if preguntas is None:
        st.write("Genera preguntas para aclarar en la entrevista lo que el CV no demuestra.")
        if st.button("🎤 Generar preguntas", key=f"preguntas_{ev.id}", type="primary"):
            with st.spinner("Preparando preguntas…"):
                try:
                    generador = obtener_generador_preguntas(ev.config.proveedor, ev.config.modelo)
                    preguntas = generar_preguntas(ev.analisis, ev.puesto, generador)
                except ErrorEvaluacion as error:
                    st.error(f"🤖 {error}")
                    return
            st.session_state["preguntas"][ev.id] = preguntas
    if preguntas is not None:
        for i, item in enumerate(preguntas.preguntas, 1):
            with st.container(border=True):
                st.markdown(f"**{i}. {item.pregunta}**")
                st.caption(f"🎯 {item.objetivo}")


def pestana_documento(ev: ResultadoEvaluacion) -> None:
    if ev.pdf_bytes:
        try:
            st.pdf(ev.pdf_bytes, height=600)
        except Exception:  # falta el paquete streamlit-pdf
            st.info("Instala `streamlit[pdf]` para ver el PDF aquí.")
    with st.expander("🔎 Texto extraído (lo que leyó la IA)", expanded=not ev.pdf_bytes):
        if ev.texto_cv:
            st.code(ev.texto_cv, language=None, wrap_lines=True, height=400)
        else:
            st.caption("El historial no guarda el texto del CV (datos personales).")


@st.fragment
def pestana_exportar(ev: ResultadoEvaluacion) -> None:
    """Descargas, guardado en el historial y feedback. Es un fragmento para no rehacer toda la página."""
    datos = {"puesto": ev.puesto, "archivo": ev.archivo, "modelo": ev.config.etiqueta}
    nombre_base = f"analisis_{ev.analisis.nombre_candidato.replace(' ', '_')[:40]}"
    col_json, col_md = st.columns(2)
    col_json.download_button("⬇️ Descargar JSON", informe_json(ev.analisis, **datos), f"{nombre_base}.json",
                             "application/json", on_click="ignore", width="stretch")
    col_md.download_button("⬇️ Descargar informe (Markdown)", informe_markdown(ev.analisis, **datos),
                           f"{nombre_base}.md", "text/markdown", on_click="ignore", width="stretch")
    st.divider()

    guardado = ev.id in st.session_state["guardados"]
    if not guardado:
        hueco_boton = st.empty()  # contenedor que se puede vaciar cuando ya se guardó
        if hueco_boton.button("💾 Guardar en el historial", type="primary", key=f"guardar_{ev.id}"):
            try:
                guardado = guardar_analisis(
                    obtener_motor(), id_analisis=ev.id, analisis=ev.analisis, archivo=ev.archivo,
                    huella=ev.huella, puesto=ev.puesto, config=ev.config, version_prompt=VERSION_PROMPT,
                ) or True  # False = ya existía con ese id: también cuenta como guardado
            except ErrorBaseDatos as error:
                st.error(f"🗄️ {error}")
                return
            st.session_state["guardados"].add(ev.id)
            hueco_boton.empty()
            st.toast("Análisis guardado en el historial", icon="💾")
    if guardado:
        st.success("Este análisis está guardado en el historial.", icon="💾")
        widget_feedback(ev.id)


def widget_feedback(id_analisis: str, valor_inicial: int | None = None) -> None:
    """👍/👎 del reclutador sobre la calidad del análisis (se guarda en la base de datos)."""
    clave = f"feedback_{id_analisis}"

    def al_cambiar() -> None:
        try:
            registrar_feedback(obtener_motor(), id_analisis, st.session_state[clave])
            st.toast("¡Gracias por tu opinión!", icon="🙌")
        except ErrorBaseDatos as error:
            st.toast(f"No se guardó el feedback: {error}", icon="⚠️")

    st.caption("¿El análisis fue acertado?")
    st.feedback("thumbs", key=clave, default=valor_inicial, on_change=al_cambiar)


# ---------------------------------------------------------------------------
# Resultado completo
# ---------------------------------------------------------------------------
def mostrar_resultado(ev: ResultadoEvaluacion, *, desde_historial: bool = False) -> None:
    analisis = ev.analisis
    if ev.reutilizado:
        st.caption("♻️ Resultado reutilizado de la caché: no se volvió a llamar al modelo.")

    col_tarjetas, col_radar = st.columns([1, 1.3], gap="large")
    with col_tarjetas:
        mostrar_tarjetas(analisis)
    with col_radar:
        with st.container(border=True):
            st.markdown("**🕸️ Perfil por criterio**")
            st.plotly_chart(grafico_radar({analisis.nombre_candidato: analisis.puntajes}), key=f"radar_{ev.id}")

    nombres = ["📋 Resumen", "✅ Requisitos", "🛠️ Habilidades", "🎤 Entrevista", "📄 Documento"]
    if not desde_historial:
        nombres.append("⬇️ Exportar y guardar")
    pestanas = st.tabs(nombres)
    with pestanas[0]:
        pestana_resumen(analisis)
    with pestanas[1]:
        pestana_requisitos(analisis)
    with pestanas[2]:
        pestana_habilidades(analisis)
    with pestanas[3]:
        pestana_entrevista(ev)
    with pestanas[4]:
        pestana_documento(ev)
    if not desde_historial:
        with pestanas[5]:
            pestana_exportar(ev)

    st.caption(
        f"Modelo: {ev.config.etiqueta} · Prompt v{VERSION_PROMPT}. El análisis es un apoyo generado por IA "
        "y puede variar entre ejecuciones: no reemplaza la decisión de una persona."
    )
