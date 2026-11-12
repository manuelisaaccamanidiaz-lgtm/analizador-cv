"""Extracción del texto de un CV en PDF.

Funciona con PDF de texto seleccionable. No hace OCR: un PDF hecho solo de
imágenes (escaneado) no tiene texto que extraer.
"""

import hashlib
import io

from pypdf import PdfReader

from services.errores import ErrorPDF

# Un CV normal tiene unos pocos miles de caracteres. El límite evita enviar
# documentos enormes al modelo (más tokens = más costo y más tiempo).
MAX_CARACTERES_CV = 30_000

__all__ = ["ErrorPDF", "MAX_CARACTERES_CV", "extraer_texto_pdf", "huella_archivo"]


def huella_archivo(contenido: bytes) -> str:
    """Huella SHA-256 del archivo: el mismo PDF siempre da la misma huella (sirve para la caché)."""
    return hashlib.sha256(contenido).hexdigest()


def extraer_texto_pdf(archivo) -> str:
    """Devuelve el texto del PDF con un separador por página.

    `archivo` puede ser una ruta, bytes o un objeto tipo archivo (como el de st.file_uploader).
    Lanza ErrorPDF con un mensaje claro si algo falla.
    """
    if isinstance(archivo, bytes):
        archivo = io.BytesIO(archivo)

    try:
        lector = PdfReader(archivo)
        if lector.is_encrypted:
            raise ErrorPDF("El PDF está protegido con contraseña. Sube una versión sin protección.")

        paginas = []
        for numero, pagina in enumerate(lector.pages, start=1):
            texto = (pagina.extract_text() or "").strip()
            if texto:
                paginas.append(f"--- Página {numero} ---\n{texto}")
    except ErrorPDF:
        raise
    except Exception as error:  # archivo dañado, no es un PDF, estructura inválida...
        raise ErrorPDF(f"No se pudo leer el PDF. Verifica que el archivo sea un PDF válido. Detalle: {error}") from error

    if not paginas:
        raise ErrorPDF(
            "No se encontró texto en el PDF. Probablemente es un documento escaneado (imágenes); "
            "usa un CV con texto seleccionable."
        )

    texto_completo = "\n\n".join(paginas)
    if len(texto_completo) > MAX_CARACTERES_CV:
        raise ErrorPDF(
            f"El CV tiene {len(texto_completo):,} caracteres y el máximo es {MAX_CARACTERES_CV:,}. "
            "Sube una versión más corta."
        )
    return texto_completo
