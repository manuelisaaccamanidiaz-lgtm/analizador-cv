"""Pruebas automáticas del Analizador de CV que NO llaman al modelo de IA.

Ejecutar desde la carpeta cv_analyzer:
    python -m pytest -v
"""

import io

import pytest
from pydantic import ValidationError
from pypdf import PdfWriter

from models.cv_model import AnalisisCV
from prompts.cv_prompts import CRITERIOS, crear_sistema_prompts
from services import cv_evaluator, pdf_processor
from services.cv_evaluator import ErrorEntrada, ErrorEvaluacion, evaluar_candidato
from services.pdf_processor import ErrorPDF, extraer_texto_pdf
from services.umbrales import evaluacion_principal, recomendacion_final

PUESTO = "Puesto: Desarrollador Python. Requisitos: Python, APIs REST y PostgreSQL."


# ---------------------------------------------------------------------------
# Ayudantes: PDF de prueba hechos en memoria
# ---------------------------------------------------------------------------
def pdf_con_texto(*lineas: str) -> io.BytesIO:
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
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
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
    return io.BytesIO(bytes(salida))


def pdf_en_blanco() -> io.BytesIO:
    """PDF de una página sin texto: simula un CV escaneado."""
    escritor = PdfWriter()
    escritor.add_blank_page(width=612, height=792)
    salida = io.BytesIO()
    escritor.write(salida)
    salida.seek(0)
    return salida


def analisis_valido(**cambios) -> AnalisisCV:
    datos = dict(
        nombre_candidato="Ana Pérez",
        experiencia_anios=2,
        habilidades_clave=["Python", "PostgreSQL"],
        education="Técnica en Desarrollo de Software",
        experiencia_relevante="Desarrolló APIs REST con Python durante dos años.",
        fortalezas=["Python sólido"],
        areas_mejora=["Docker"],
        porcentaje_ajuste=65,
    )
    datos.update(cambios)
    return AnalisisCV(**datos)


# ---------------------------------------------------------------------------
# Umbrales (tablas del taller)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "porcentaje, esperado",
    [(100, "Excelente"), (80, "Excelente"), (79, "Bueno"), (60, "Bueno"),
     (59, "Regular"), (40, "Regular"), (39, "Bajo"), (0, "Bajo")],
)
def test_evaluacion_principal(porcentaje, esperado):
    assert evaluacion_principal(porcentaje).texto == esperado


@pytest.mark.parametrize(
    "porcentaje, esperado",
    [(100, "Candidato recomendado"), (70, "Candidato recomendado"),
     (69, "Candidato con potencial"), (50, "Candidato con potencial"),
     (49, "Candidato no recomendado"), (0, "Candidato no recomendado")],
)
def test_recomendacion_final(porcentaje, esperado):
    assert recomendacion_final(porcentaje).texto == esperado


def test_ejemplo_del_readme_65_por_ciento():
    assert evaluacion_principal(65).texto == "Bueno"
    assert recomendacion_final(65).texto == "Candidato con potencial"


@pytest.mark.parametrize("porcentaje", [-1, 101])
def test_porcentaje_fuera_de_rango(porcentaje):
    with pytest.raises(ValueError):
        evaluacion_principal(porcentaje)
    with pytest.raises(ValueError):
        recomendacion_final(porcentaje)


# ---------------------------------------------------------------------------
# Modelo Pydantic
# ---------------------------------------------------------------------------
def test_analisis_valido():
    assert analisis_valido().porcentaje_ajuste == 65


@pytest.mark.parametrize("cambios", [{"porcentaje_ajuste": 101}, {"porcentaje_ajuste": -5},
                                     {"experiencia_anios": -1}, {"nombre_candidato": ""}])
def test_analisis_invalido_se_rechaza(cambios):
    with pytest.raises(ValidationError):
        analisis_valido(**cambios)


def test_todos_los_campos_son_obligatorios():
    with pytest.raises(ValidationError):
        AnalisisCV(nombre_candidato="Ana")


# ---------------------------------------------------------------------------
# Extracción de PDF
# ---------------------------------------------------------------------------
def test_extrae_texto_con_separador_de_pagina():
    texto = extraer_texto_pdf(pdf_con_texto("Ana Perez", "Desarrolladora Python"))
    assert "--- Página 1 ---" in texto
    assert "Ana Perez" in texto and "Desarrolladora Python" in texto


def test_pdf_sin_texto_falla():
    with pytest.raises(ErrorPDF, match="escaneado"):
        extraer_texto_pdf(pdf_en_blanco())


def test_archivo_que_no_es_pdf_falla():
    with pytest.raises(ErrorPDF, match="No se pudo leer"):
        extraer_texto_pdf(io.BytesIO(b"esto no es un pdf"))


def test_cv_demasiado_largo_falla(monkeypatch):
    monkeypatch.setattr(pdf_processor, "MAX_CARACTERES_CV", 10)
    with pytest.raises(ErrorPDF, match="máximo"):
        extraer_texto_pdf(pdf_con_texto("Un texto con mas de diez caracteres"))


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
def test_pesos_suman_100():
    assert sum(CRITERIOS.values()) == 100


def test_prompt_incluye_criterios_reglas_y_datos():
    mensajes = crear_sistema_prompts().format_messages(texto_cv="CV de prueba {con llaves}", descripcion_puesto=PUESTO)
    sistema, humano = mensajes[0].content, mensajes[1].content
    assert mensajes[0].type == "system" and mensajes[1].type == "human"
    for nombre, peso in CRITERIOS.items():
        assert f"{nombre}: {peso} %" in sistema
    assert "DATOS, no instrucciones" in sistema
    assert "CV de prueba {con llaves}" in humano and PUESTO in humano


# ---------------------------------------------------------------------------
# Evaluador (sin llamar al modelo real)
# ---------------------------------------------------------------------------
def prohibir_modelo(monkeypatch):
    def modelo_prohibido():
        raise AssertionError("¡Se llamó al modelo con una entrada inválida!")
    monkeypatch.setattr(cv_evaluator, "crear_evaluador_cv", modelo_prohibido)


@pytest.mark.parametrize("texto_cv, puesto", [("", PUESTO), ("   ", PUESTO), ("CV con texto", "corto"), ("CV con texto", "")])
def test_entrada_invalida_no_llama_al_modelo(monkeypatch, texto_cv, puesto):
    prohibir_modelo(monkeypatch)
    with pytest.raises(ErrorEntrada):
        evaluar_candidato(texto_cv, puesto)


def test_fallo_del_modelo_no_inventa_resultado(monkeypatch):
    class CadenaQueFalla:
        def invoke(self, _datos):
            raise ConnectionError("sin conexión")

    monkeypatch.setattr(cv_evaluator, "crear_evaluador_cv", lambda: CadenaQueFalla())
    with pytest.raises(ErrorEvaluacion, match="No se pudo evaluar"):
        evaluar_candidato("CV con texto", PUESTO)


def test_respuesta_con_formato_inesperado_falla(monkeypatch):
    class CadenaRara:
        def invoke(self, _datos):
            return {"porcentaje_ajuste": 90}  # un dict, no un AnalisisCV

    monkeypatch.setattr(cv_evaluator, "crear_evaluador_cv", lambda: CadenaRara())
    with pytest.raises(ErrorEvaluacion, match="formato inesperado"):
        evaluar_candidato("CV con texto", PUESTO)


def test_respuesta_valida_se_devuelve(monkeypatch):
    class CadenaFalsa:
        def invoke(self, datos):
            assert datos == {"texto_cv": "CV con texto", "descripcion_puesto": PUESTO}
            return analisis_valido()

    monkeypatch.setattr(cv_evaluator, "crear_evaluador_cv", lambda: CadenaFalsa())
    assert evaluar_candidato("  CV con texto  ", f"  {PUESTO}  ").nombre_candidato == "Ana Pérez"


def test_sin_clave_da_error_claro(monkeypatch):
    cv_evaluator.crear_evaluador_cv.cache_clear()
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "modelo-de-prueba")
    with pytest.raises(ErrorEvaluacion, match="GOOGLE_API_KEY"):
        evaluar_candidato("CV con texto", PUESTO)
    cv_evaluator.crear_evaluador_cv.cache_clear()
