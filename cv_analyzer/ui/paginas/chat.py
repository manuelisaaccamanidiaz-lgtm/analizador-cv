"""Chat con el CV: preguntas en lenguaje natural respondidas con RAG."""

import streamlit as st

from services.errores import ErrorChat, ErrorConfiguracion
from services.rag import responder_pregunta
from ui.cache import obtener_indice, obtener_modelo_chat
from ui.estado import config_actual

PREGUNTAS_SUGERIDAS = [
    "¿Cuántos años de experiencia tiene?",
    "¿Qué tecnologías domina?",
    "¿Dónde estudió?",
    "¿Ha trabajado con Docker?",
]


def mostrar_mensaje(mensaje: dict) -> None:
    with st.chat_message(mensaje["rol"], avatar="🧑‍💼" if mensaje["rol"] == "user" else "🤖"):
        st.markdown(mensaje["contenido"])
        if mensaje.get("fuentes"):
            with st.expander(f"📎 {len(mensaje['fuentes'])} fragmentos del CV usados"):
                for fuente in mensaje["fuentes"]:
                    st.caption(f"Página {fuente['pagina']}")
                    st.text(fuente["texto"])


st.title("💬 Chat con el CV")
evaluacion = st.session_state["evaluacion"]
if evaluacion is None:
    st.info("Primero analiza un CV en la página **Evaluar candidato**.", icon="👈")
    st.page_link("ui/paginas/evaluar.py", label="Ir a Evaluar candidato", icon="🔍")
    st.stop()
if not evaluacion.texto_cv:
    st.info("Este análisis viene del historial, que no guarda el texto del CV. Vuelve a subir el PDF en Evaluar.", icon="📄")
    st.stop()

st.caption(f"Preguntando sobre **{evaluacion.analisis.nombre_candidato}** · {evaluacion.archivo}")
with st.expander("🧠 ¿Cómo funciona? (RAG)"):
    st.markdown(
        "1. **Indexar:** el CV se divide en fragmentos y cada uno se convierte en un *embedding* guardado en **Chroma**.\n"
        "2. **Recuperar:** tu pregunta también se convierte en embedding y Chroma busca los fragmentos más parecidos.\n"
        "3. **Generar:** el modelo responde usando **solo** esos fragmentos. Si el CV no lo dice, debe responder que no lo menciona."
    )

try:
    config = config_actual()
    with st.spinner("Indexando el CV (embeddings + Chroma)…"):
        indice = obtener_indice(evaluacion.huella, evaluacion.texto_cv, config.proveedor, config.modelo, config.modelo_embeddings)
    modelo_chat = obtener_modelo_chat(config.proveedor, config.modelo)
except (ErrorConfiguracion, ErrorChat) as error:
    st.error(f"🔑 {error}")
    st.stop()

clave_chat = f"{evaluacion.huella}:{config.proveedor}"
mensajes = st.session_state["chats"].setdefault(clave_chat, [])

col_info, col_borrar = st.columns([4, 1], vertical_alignment="center")
col_info.caption(f"Modelo: {config.etiqueta} · Embeddings: {config.modelo_embeddings}")
if col_borrar.button("🧹 Borrar chat", width="stretch", disabled=not mensajes):
    mensajes.clear()
    st.rerun()

for mensaje in mensajes:
    mostrar_mensaje(mensaje)

pregunta = None
if not mensajes:
    st.markdown("**Prueba con:**")
    columnas = st.columns(len(PREGUNTAS_SUGERIDAS))
    for columna, sugerida in zip(columnas, PREGUNTAS_SUGERIDAS):
        if columna.button(sugerida, width="stretch"):
            pregunta = sugerida

escrita = st.chat_input("Pregunta algo sobre el CV…")
pregunta = escrita or pregunta

if pregunta:
    historial_previo = list(mensajes)
    nuevo = {"rol": "user", "contenido": pregunta}
    mensajes.append(nuevo)
    mostrar_mensaje(nuevo)
    with st.chat_message("assistant", avatar="🤖"), st.spinner("Buscando en el CV…"):
        try:
            respuesta = responder_pregunta(pregunta, indice, modelo_chat, historial_previo)
        except ErrorChat as error:
            mensajes.pop()  # la pregunta sin respuesta no queda en el historial
            st.error(f"🤖 {error}")
            st.stop()
    mensajes.append({
        "rol": "assistant", "contenido": respuesta.respuesta,
        "fuentes": [{"pagina": d.metadata.get("pagina", "?"), "texto": d.page_content} for d in respuesta.fuentes],
    })
    st.rerun()
