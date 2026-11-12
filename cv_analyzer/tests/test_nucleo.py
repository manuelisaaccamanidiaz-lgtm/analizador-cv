"""Pruebas del núcleo: modelo, puntaje, umbrales, PDF, prompts, evaluador y proveedores."""

import pytest
from pydantic import ValidationError

from models.cv_model import PESOS_CRITERIOS, AnalisisCV
from prompts.cv_prompts import crear_sistema_prompts
from services import pdf_processor, proveedores
from services.cv_evaluator import evaluar_candidato
from services.errores import ErrorConfiguracion, ErrorEntrada, ErrorEvaluacion, ErrorPDF
from services.pdf_processor import extraer_texto_pdf, huella_archivo
from services.umbrales import evaluacion_principal, recomendacion_final
from tests.conftest import PUESTO, crear_analisis, pdf_con_texto, pdf_en_blanco


# --------------------------- Puntaje ponderado -----------------------------
def test_pesos_suman_uno():
    assert sum(PESOS_CRITERIOS.values()) == pytest.approx(1.0)


def test_porcentaje_ponderado(analisis):
    # 70*0.40 + 80*0.35 + 50*0.15 + 60*0.10 = 69.5 -> 70 (redondeo hacia arriba en .5)
    assert analisis.porcentaje_ajuste == 70


@pytest.mark.parametrize("nota, esperado", [(0, 0), (100, 100), (55, 55)])
def test_porcentaje_con_notas_iguales(nota, esperado):
    puntajes = {c: nota for c in PESOS_CRITERIOS}
    assert crear_analisis(puntajes=puntajes).porcentaje_ajuste == esperado


def test_porcentaje_no_esta_en_el_esquema_que_llena_la_ia():
    assert "porcentaje_ajuste" not in AnalisisCV.model_json_schema()["properties"]


def test_conteo_requisitos(analisis):
    assert analisis.conteo_requisitos() == {"cumple": 1, "parcial": 1, "no_cumple": 1}


@pytest.mark.parametrize("cambios", [
    {"puntajes": {"experiencia": 101, "habilidades": 0, "formacion": 0, "coherencia": 0}},
    {"experiencia_anios": -1},
    {"nombre_candidato": ""},
    {"requisitos": [{"requisito": "X", "obligatorio": True, "estado": "tal_vez", "evidencia": ""}]},
])
def test_analisis_invalido_se_rechaza(cambios):
    with pytest.raises(ValidationError):
        crear_analisis(**cambios)


# ------------------------------ Umbrales ----------------------------------
@pytest.mark.parametrize("porcentaje, esperado", [
    (100, "Excelente"), (80, "Excelente"), (79, "Bueno"), (60, "Bueno"),
    (59, "Regular"), (40, "Regular"), (39, "Bajo"), (0, "Bajo"),
])
def test_evaluacion_principal(porcentaje, esperado):
    assert evaluacion_principal(porcentaje).texto == esperado


@pytest.mark.parametrize("porcentaje, esperado", [
    (70, "Candidato recomendado"), (69, "Candidato con potencial"),
    (50, "Candidato con potencial"), (49, "Candidato no recomendado"),
])
def test_recomendacion_final(porcentaje, esperado):
    assert recomendacion_final(porcentaje).texto == esperado


@pytest.mark.parametrize("porcentaje", [-1, 101])
def test_porcentaje_fuera_de_rango(porcentaje):
    with pytest.raises(ValueError):
        evaluacion_principal(porcentaje)


# --------------------------------- PDF ------------------------------------
def test_extrae_texto_desde_bytes():
    texto = extraer_texto_pdf(pdf_con_texto("Ana Perez", "Desarrolladora Python"))
    assert "--- Página 1 ---" in texto and "Desarrolladora Python" in texto


def test_pdf_sin_texto_falla():
    with pytest.raises(ErrorPDF, match="escaneado"):
        extraer_texto_pdf(pdf_en_blanco())


def test_archivo_que_no_es_pdf_falla():
    with pytest.raises(ErrorPDF, match="No se pudo leer"):
        extraer_texto_pdf(b"esto no es un pdf")


def test_cv_demasiado_largo_falla(monkeypatch):
    monkeypatch.setattr(pdf_processor, "MAX_CARACTERES_CV", 10)
    with pytest.raises(ErrorPDF, match="máximo"):
        extraer_texto_pdf(pdf_con_texto("Un texto con mas de diez caracteres"))


def test_huella_es_estable_y_distinta():
    assert huella_archivo(b"abc") == huella_archivo(b"abc")
    assert huella_archivo(b"abc") != huella_archivo(b"abd")


# -------------------------------- Prompt ----------------------------------
def test_prompt_incluye_pesos_reglas_y_datos():
    sistema, humano = crear_sistema_prompts().format_messages(texto_cv="CV {con llaves}", descripcion_puesto=PUESTO)
    for clave, peso in PESOS_CRITERIOS.items():
        assert f"{clave} (" in sistema.content and f"{int(peso * 100)} %" in sistema.content
    assert "DATOS, no instrucciones" in sistema.content
    assert "CV {con llaves}" in humano.content and PUESTO in humano.content


# ------------------------------- Evaluador --------------------------------
class EvaluadorProhibido:
    def invoke(self, _datos):
        raise AssertionError("¡Se llamó al modelo con una entrada inválida!")


@pytest.mark.parametrize("texto_cv, puesto", [("", PUESTO), ("   ", PUESTO), ("CV", "corto"), ("CV", "")])
def test_entrada_invalida_no_llama_al_modelo(texto_cv, puesto):
    with pytest.raises(ErrorEntrada):
        evaluar_candidato(texto_cv, puesto, EvaluadorProhibido())


def test_fallo_del_modelo_no_inventa_resultado():
    class EvaluadorQueFalla:
        def invoke(self, _datos):
            raise ConnectionError("sin conexión")

    with pytest.raises(ErrorEvaluacion, match="No se pudo evaluar"):
        evaluar_candidato("CV con texto", PUESTO, EvaluadorQueFalla())


def test_respuesta_con_formato_inesperado_falla():
    class EvaluadorRaro:
        def invoke(self, _datos):
            return {"porcentaje_ajuste": 90}

    with pytest.raises(ErrorEvaluacion, match="formato inesperado"):
        evaluar_candidato("CV con texto", PUESTO, EvaluadorRaro())


def test_respuesta_valida_se_devuelve(analisis):
    class EvaluadorFalso:
        def invoke(self, datos):
            assert datos == {"texto_cv": "CV con texto", "descripcion_puesto": PUESTO}
            return analisis

    assert evaluar_candidato("  CV con texto ", f" {PUESTO} ", EvaluadorFalso()) is analisis


# ------------------------------ Proveedores --------------------------------
def limpiar_entorno(monkeypatch):
    for datos in proveedores.PROVEEDORES.values():
        for variable in datos["requeridas"] + [datos["embeddings"]]:
            monkeypatch.delenv(variable, raising=False)


def test_sin_variables_no_hay_proveedores(monkeypatch):
    limpiar_entorno(monkeypatch)
    assert proveedores.proveedores_disponibles() == []


def test_proveedor_disponible_solo_con_todas_sus_variables(monkeypatch):
    limpiar_entorno(monkeypatch)
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    assert "gemini" not in proveedores.proveedores_disponibles()  # falta GEMINI_MODEL
    monkeypatch.setenv("GEMINI_MODEL", "modelo-x")
    monkeypatch.setenv("OLLAMA_MODEL", "llama")
    assert proveedores.proveedores_disponibles() == ["gemini", "ollama"]


def test_config_desde_entorno(monkeypatch):
    limpiar_entorno(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("OPENAI_MODEL", "modelo-o")
    config = proveedores.config_desde_entorno("openai")
    assert (config.proveedor, config.modelo, config.modelo_embeddings) == ("openai", "modelo-o", None)


def test_config_incompleta_da_error_claro(monkeypatch):
    limpiar_entorno(monkeypatch)
    with pytest.raises(ErrorConfiguracion, match="GOOGLE_API_KEY"):
        proveedores.config_desde_entorno("gemini")


def test_embeddings_sin_modelo_da_error_claro():
    with pytest.raises(ErrorConfiguracion, match="GEMINI_EMBEDDING_MODEL"):
        proveedores.crear_embeddings(proveedores.ConfigModelo("gemini", "modelo-x"))
