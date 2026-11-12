"""Proveedores de modelos de IA: Gemini, OpenAI y Ollama.

Un proveedor está DISPONIBLE si sus variables de entorno están configuradas.
Los paquetes de cada proveedor se importan solo cuando se usan, así un error en
uno no impide usar los otros.
"""

import os
from dataclasses import dataclass

from services.errores import ErrorConfiguracion

TEMPERATURA = 0.2

# Variables de entorno que necesita cada proveedor
PROVEEDORES: dict[str, dict] = {
    "gemini": {
        "nombre": "Gemini",
        "requeridas": ["GOOGLE_API_KEY", "GEMINI_MODEL"],
        "modelo": "GEMINI_MODEL",
        "embeddings": "GEMINI_EMBEDDING_MODEL",
    },
    "openai": {
        "nombre": "OpenAI",
        "requeridas": ["OPENAI_API_KEY", "OPENAI_MODEL"],
        "modelo": "OPENAI_MODEL",
        "embeddings": "OPENAI_EMBEDDING_MODEL",
    },
    "ollama": {
        "nombre": "Ollama (local)",
        "requeridas": ["OLLAMA_MODEL"],
        "modelo": "OLLAMA_MODEL",
        "embeddings": "OLLAMA_EMBEDDING_MODEL",
    },
}

OLLAMA_URL_POR_DEFECTO = "http://host.docker.internal:11434"


@dataclass(frozen=True)
class ConfigModelo:
    """Qué proveedor y qué modelos usar. frozen=True la hace inmutable y "hasheable" (sirve como clave de caché)."""

    proveedor: str
    modelo: str
    modelo_embeddings: str | None = None

    @property
    def etiqueta(self) -> str:
        return f"{PROVEEDORES[self.proveedor]['nombre']} · {self.modelo}"


def _variable(nombre: str) -> str:
    return os.getenv(nombre, "").strip()


def proveedores_disponibles() -> list[str]:
    """Proveedores con todas sus variables obligatorias configuradas."""
    return [clave for clave, datos in PROVEEDORES.items() if all(_variable(v) for v in datos["requeridas"])]


def config_desde_entorno(proveedor: str) -> ConfigModelo:
    """Construye la configuración del proveedor leyendo el .env."""
    if proveedor not in PROVEEDORES:
        raise ErrorConfiguracion(f"Proveedor desconocido: {proveedor}.")
    datos = PROVEEDORES[proveedor]
    faltantes = [v for v in datos["requeridas"] if not _variable(v)]
    if faltantes:
        raise ErrorConfiguracion(f"Para usar {datos['nombre']} faltan en el .env: {', '.join(faltantes)}.")
    return ConfigModelo(
        proveedor=proveedor,
        modelo=_variable(datos["modelo"]),
        modelo_embeddings=_variable(datos["embeddings"]) or None,
    )


def crear_chat(config: ConfigModelo):
    """Crea el modelo de chat del proveedor elegido."""
    if config.proveedor == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=config.modelo, temperature=TEMPERATURA)
    if config.proveedor == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=config.modelo, temperature=TEMPERATURA)
    if config.proveedor == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=config.modelo, temperature=TEMPERATURA, base_url=_variable("OLLAMA_BASE_URL") or OLLAMA_URL_POR_DEFECTO)
    raise ErrorConfiguracion(f"Proveedor desconocido: {config.proveedor}.")


def crear_embeddings(config: ConfigModelo):
    """Crea el modelo de embeddings del proveedor (para el chat con el CV)."""
    if not config.modelo_embeddings:
        variable = PROVEEDORES[config.proveedor]["embeddings"]
        raise ErrorConfiguracion(f"Para chatear con el CV falta {variable} en el .env.")
    if config.proveedor == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(model=config.modelo_embeddings)
    if config.proveedor == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=config.modelo_embeddings)
    if config.proveedor == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=config.modelo_embeddings, base_url=_variable("OLLAMA_BASE_URL") or OLLAMA_URL_POR_DEFECTO)
    raise ErrorConfiguracion(f"Proveedor desconocido: {config.proveedor}.")
