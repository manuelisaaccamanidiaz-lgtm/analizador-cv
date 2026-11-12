"""Datos y ayudantes compartidos por las pruebas (pytest los encuentra solo)."""

import io

import pytest
from pypdf import PdfWriter

from models.cv_model import AnalisisCV

PUESTO = "Puesto: Desarrollador Python. Requisitos: Python, APIs REST y PostgreSQL."


def pdf_con_texto(*lineas: str) -> bytes:
    """Construye un PDF mínimo de una página con las líneas indicadas (texto seleccionable)."""
    comandos = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
    for linea in lineas:
        segura = linea.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        comandos.append(f"({segura}) '")
    comandos.append("ET")
    contenido = "\n".join(comandos).encode("latin-1")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(contenido) + contenido + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    salida = bytearray(b"%PDF-1.4\n")
    posiciones = []
    for numero, objeto in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += b"%d 0 obj\n" % numero + objeto + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for posicion in posiciones:
        salida += b"%010d 00000 n \n" % posicion
    salida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, inicio_xref)
    return bytes(salida)


def pdf_en_blanco() -> bytes:
    """PDF de una página sin texto: simula un CV escaneado."""
    escritor = PdfWriter()
    escritor.add_blank_page(width=612, height=792)
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


def crear_analisis(**cambios) -> AnalisisCV:
    datos = dict(
        nombre_candidato="Ana Pérez",
        experiencia_anios=2,
        habilidades_clave=["Python", "PostgreSQL"],
        education="Técnica en Desarrollo de Software",
        experiencia_relevante="Desarrolló APIs REST con Python durante dos años.",
        fortalezas=["Python sólido"],
        areas_mejora=["Docker"],
        requisitos=[
            {"requisito": "Python", "obligatorio": True, "estado": "cumple", "evidencia": "2 años con Python"},
            {"requisito": "PostgreSQL", "obligatorio": True, "estado": "parcial", "evidencia": "Cursos de SQL"},
            {"requisito": "Docker", "obligatorio": False, "estado": "no_cumple", "evidencia": ""},
        ],
        puntajes={"experiencia": 70, "habilidades": 80, "formacion": 50, "coherencia": 60},
    )
    datos.update(cambios)
    return AnalisisCV(**datos)


@pytest.fixture
def analisis() -> AnalisisCV:
    return crear_analisis()
