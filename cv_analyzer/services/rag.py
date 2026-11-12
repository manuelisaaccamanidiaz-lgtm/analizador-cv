"""Chat con el CV usando RAG (Retrieval-Augmented Generation).

1. INDEXAR: el texto del CV se divide en fragmentos, cada fragmento se convierte
   en un embedding y se guarda en una colección de Chroma (en memoria).
2. RECUPERAR: la pregunta también se convierte en embedding y Chroma devuelve
   los fragmentos más parecidos.
3. GENERAR: el modelo de chat responde usando SOLO esos fragmentos.
"""

import re
from dataclasses import dataclass

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter

from prompts.rag_prompts import crear_prompt_chat
from services.errores import ErrorChat

TAMANO_FRAGMENTO = 600     # caracteres por fragmento
SOLAPAMIENTO = 100         # caracteres repetidos entre fragmentos vecinos (no cortar ideas a la mitad)
FRAGMENTOS_A_RECUPERAR = 4
MENSAJES_DE_HISTORIAL = 4  # últimos mensajes que se envían para entender preguntas de seguimiento

_PATRON_PAGINA = re.compile(r"--- Página (\d+) ---\n")


@dataclass(frozen=True)
class RespuestaChat:
    respuesta: str
    fuentes: list[Document]


def dividir_cv(texto_cv: str) -> list[Document]:
    """Divide el texto del CV en fragmentos, guardando la página de origen en los metadatos."""
    divisor = RecursiveCharacterTextSplitter(chunk_size=TAMANO_FRAGMENTO, chunk_overlap=SOLAPAMIENTO)
    partes = _PATRON_PAGINA.split(texto_cv)  # ["", "1", "texto pág 1", "2", "texto pág 2", ...]

    paginas: list[tuple[int, str]] = []
    if len(partes) > 1:
        for i in range(1, len(partes), 2):
            paginas.append((int(partes[i]), partes[i + 1].strip()))
    else:
        paginas.append((1, texto_cv.strip()))

    documentos: list[Document] = []
    for numero, texto in paginas:
        for fragmento in divisor.split_text(texto):
            documentos.append(Document(page_content=fragmento, metadata={"pagina": numero, "fragmento": len(documentos)}))
    if not documentos:
        raise ErrorChat("El CV no tiene texto para indexar.")
    return documentos


def crear_indice(texto_cv: str, embeddings, nombre_coleccion: str) -> Chroma:
    """Crea una colección de Chroma en memoria con los fragmentos del CV."""
    documentos = dividir_cv(texto_cv)
    cliente = chromadb.EphemeralClient()  # en memoria: se borra al cerrar la app
    try:
        cliente.delete_collection(nombre_coleccion)  # si ya existía, se reconstruye (sin duplicar fragmentos)
    except Exception:
        pass  # no existía: nada que borrar
    try:
        return Chroma.from_documents(
            documents=documentos,
            embedding=embeddings,
            collection_name=nombre_coleccion,
            client=cliente,
        )
    except Exception as error:  # modelo de embeddings no disponible, clave inválida...
        raise ErrorChat(f"No se pudo crear el índice del CV (embeddings): {error}") from error


def formatear_contexto(documentos: list[Document]) -> str:
    return "\n\n".join(f"[Página {d.metadata.get('pagina', '?')}]\n{d.page_content}" for d in documentos)


def convertir_historial(mensajes: list[dict]) -> list:
    """Convierte [{"rol": "user"|"assistant", "contenido": str}] en mensajes de LangChain (solo los últimos)."""
    convertidos = []
    for mensaje in mensajes[-MENSAJES_DE_HISTORIAL:]:
        clase = HumanMessage if mensaje["rol"] == "user" else AIMessage
        convertidos.append(clase(content=mensaje["contenido"]))
    return convertidos


def responder_pregunta(pregunta: str, indice: Chroma, modelo_chat, historial: list[dict] | None = None) -> RespuestaChat:
    """Recupera los fragmentos relevantes y genera la respuesta."""
    pregunta = (pregunta or "").strip()
    if not pregunta:
        raise ErrorChat("Escribe una pregunta.")

    try:
        fuentes = indice.similarity_search(pregunta, k=FRAGMENTOS_A_RECUPERAR)
    except Exception as error:
        raise ErrorChat(f"No se pudo buscar en el CV: {error}") from error

    cadena = crear_prompt_chat() | modelo_chat | StrOutputParser()
    try:
        respuesta = cadena.invoke({
            "contexto": formatear_contexto(fuentes),
            "historial": convertir_historial(historial or []),
            "pregunta": pregunta,
        })
    except Exception as error:
        raise ErrorChat(f"No se pudo generar la respuesta: {error}") from error

    if not respuesta.strip():
        raise ErrorChat("El modelo devolvió una respuesta vacía.")
    return RespuestaChat(respuesta=respuesta.strip(), fuentes=fuentes)
