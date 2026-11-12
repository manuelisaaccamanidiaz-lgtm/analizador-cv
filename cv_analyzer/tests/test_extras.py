"""Pruebas de las funcionalidades nuevas: historial, RAG, entrevista, informe y plantillas."""

import json

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from models.cv_model import PreguntasEntrevista
from services import historial
from services.entrevista import generar_preguntas, resumir_para_entrevista
from services.errores import ErrorAplicacion, ErrorChat, ErrorEvaluacion
from services.informe import informe_json, informe_markdown
from services.plantillas import cargar_plantillas
from services.proveedores import ConfigModelo
from services.rag import crear_indice, dividir_cv, responder_pregunta
from tests.conftest import PUESTO, crear_analisis

CONFIG = ConfigModelo("gemini", "modelo-prueba")
CV = (
    "--- Página 1 ---\nAna Pérez. Desarrolladora Python con 3 años creando APIs REST con FastAPI.\n"
    "Usa Docker y PostgreSQL a diario.\n\n"
    "--- Página 2 ---\nEducación: Ingeniería de Sistemas. Inglés B2."
)


# ------------------------------- Historial --------------------------------
@pytest.fixture
def motor():
    motor = historial.crear_motor("sqlite:///:memory:")  # misma lógica que PostgreSQL, pero en memoria
    historial.inicializar_bd(motor)
    return motor


def guardar(motor, id_analisis="a1", **cambios):
    datos = dict(id_analisis=id_analisis, analisis=crear_analisis(), archivo="ana.pdf", huella="h" * 64,
                 puesto=PUESTO, config=CONFIG, version_prompt="2.0")
    datos.update(cambios)
    return historial.guardar_analisis(motor, **datos)


def test_guardar_y_leer(motor):
    assert guardar(motor) is True
    resumen, analisis = historial.obtener_analisis(motor, "a1")
    assert resumen.porcentaje == 70 and resumen.evaluacion == "Bueno"
    assert analisis == crear_analisis()  # se reconstruye igual desde el JSON


def test_mismo_id_no_se_duplica(motor):
    guardar(motor)
    assert guardar(motor) is False
    assert len(historial.listar_analisis(motor)) == 1


def test_filtros_del_listado(motor):
    guardar(motor, "a1")
    guardar(motor, "a2", analisis=crear_analisis(nombre_candidato="Luis Gómez",
                                                 puntajes={"experiencia": 90, "habilidades": 90, "formacion": 90, "coherencia": 90}))
    assert [r.id for r in historial.listar_analisis(motor, buscar="luis")] == ["a2"]
    assert [r.id for r in historial.listar_analisis(motor, evaluacion="Excelente")] == ["a2"]
    assert len(historial.listar_analisis(motor, buscar="python")) == 2  # busca también en el puesto


def test_feedback_y_estadisticas(motor):
    guardar(motor)
    assert historial.registrar_feedback(motor, "a1", 1) is True
    assert historial.registrar_feedback(motor, "no-existe", 1) is False
    estad = historial.estadisticas(motor)
    assert estad == {"total": 1, "promedio": 70.0, "recomendados": 1, "con_feedback": 1, "feedback_positivo": 1}
    with pytest.raises(ValueError):
        historial.registrar_feedback(motor, "a1", 5)


def test_eliminar(motor):
    guardar(motor)
    assert historial.eliminar_analisis(motor, "a1") is True
    assert historial.eliminar_analisis(motor, "a1") is False
    assert historial.obtener_analisis(motor, "a1") is None


def test_estadisticas_vacias(motor):
    assert historial.estadisticas(motor)["promedio"] is None


# ---------------------------------- RAG -----------------------------------
def test_dividir_cv_conserva_la_pagina():
    documentos = dividir_cv(CV)
    assert {d.metadata["pagina"] for d in documentos} == {1, 2}
    assert any("Ingeniería" in d.page_content and d.metadata["pagina"] == 2 for d in documentos)


def test_dividir_texto_vacio_falla():
    with pytest.raises(ErrorChat):
        dividir_cv("   ")


def test_recrear_indice_no_duplica_fragmentos():
    embeddings = DeterministicFakeEmbedding(size=32)
    crear_indice(CV, embeddings, "cv-prueba-duplicados")
    indice = crear_indice(CV, embeddings, "cv-prueba-duplicados")
    assert indice._collection.count() == len(dividir_cv(CV))


def test_responder_usa_fragmentos_y_devuelve_fuentes():
    indice = crear_indice(CV, DeterministicFakeEmbedding(size=32), "cv-prueba-respuesta")
    modelo = FakeListChatModel(responses=["Estudió Ingeniería de Sistemas (página 2)."])
    respuesta = responder_pregunta("¿Qué estudió?", indice, modelo, [{"rol": "user", "contenido": "hola"}])
    assert "Ingeniería" in respuesta.respuesta
    assert 1 <= len(respuesta.fuentes) <= 4


def test_pregunta_vacia_falla():
    indice = crear_indice(CV, DeterministicFakeEmbedding(size=32), "cv-prueba-vacia")
    with pytest.raises(ErrorChat):
        responder_pregunta("  ", indice, FakeListChatModel(responses=["x"]))


# ------------------------------- Entrevista -------------------------------
def test_resumen_para_entrevista_incluye_dudas(analisis):
    resumen = resumir_para_entrevista(analisis)
    assert "Docker (deseable): no cumple" in resumen and "70 %" in resumen


def test_generar_preguntas_valida_formato(analisis):
    class GeneradorFalso:
        def invoke(self, datos):
            assert set(datos) == {"descripcion_puesto", "resumen_analisis"}
            return PreguntasEntrevista(preguntas=[{"pregunta": "¿Cómo usó PostgreSQL?", "objetivo": "Verificar SQL"}])

    class GeneradorRaro:
        def invoke(self, _datos):
            return "texto libre"

    assert generar_preguntas(analisis, PUESTO, GeneradorFalso()).preguntas[0].objetivo == "Verificar SQL"
    with pytest.raises(ErrorEvaluacion):
        generar_preguntas(analisis, PUESTO, GeneradorRaro())


# -------------------------------- Informe ---------------------------------
def test_informe_json_incluye_calculos(analisis):
    datos = json.loads(informe_json(analisis, puesto=PUESTO, archivo="ana.pdf", modelo="Gemini · x"))
    assert datos["porcentaje_ajuste"] == 70
    assert datos["evaluacion_principal"] == "Bueno" and datos["recomendacion_final"] == "Candidato recomendado"
    assert datos["analisis"]["puntajes"]["experiencia"] == 70


def test_informe_markdown(analisis):
    texto = informe_markdown(analisis, puesto=PUESTO, archivo="ana.pdf", modelo="Gemini · x")
    assert "# Informe de evaluación de CV" in texto and "❌ No cumple" in texto and "70 %" in texto


# ------------------------------- Plantillas -------------------------------
def test_plantillas_reales_son_validas():
    plantillas = cargar_plantillas()
    assert len(plantillas) >= 5
    assert all(len(descripcion) >= 20 for descripcion in plantillas.values())


def test_plantilla_incompleta_falla(tmp_path):
    ruta = tmp_path / "plantillas.json"
    ruta.write_text(json.dumps({"plantillas": [{"nombre": "X"}]}), encoding="utf-8")
    with pytest.raises(ErrorAplicacion, match="incompleta"):
        cargar_plantillas(ruta)
