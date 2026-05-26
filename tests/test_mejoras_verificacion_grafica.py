"""Tests unitarios para las mejoras avanzadas de verificación gráfica híbrida."""

import pytest
import time
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from core.python.verificacion_grafica.validador_local import comparar_nit, comparar_fecha
from core.python.verificacion_grafica.validador_ia import (
    verificar_con_ia,
    _cache_resultados_ia,
    _registrar_fallo,
    _registrar_exito,
)
from core.python.verificacion_grafica.extractor_texto_pdf import renderizar_pdf_a_base64_paginas


# ===========================================================================
# 1. Tests de Comparación Robustos (Nivel 1 Heurísticas)
# ===========================================================================

class TestCompararNit:
    """Pruebas para el normalizador inteligente de NITs."""

    def test_nit_coincidencia_exacta(self):
        assert comparar_nit("901576200", "El NIT del emisor es 901576200.")
        assert comparar_nit("901576200-3", "El NIT del emisor es 901576200-3.")

    def test_nit_con_puntos_y_guiones(self):
        # XML tiene dígitos limpios, PDF tiene formato estructurado
        assert comparar_nit("9015762003", "NIT: 901.576.200-3")
        assert comparar_nit("901576200", "NIT: 901.576.200-3")

    def test_nit_omitir_dv(self):
        # XML tiene el NIT con DV, pero el PDF solo muestra el NIT base
        assert comparar_nit("9015762003", "El proveedor con NIT 901576200 declara...")

    def test_nit_con_espacios_y_basura(self):
        assert comparar_nit("800003765", "800 . 003 . 765 - 3")


class TestCompararFecha:
    """Pruebas para el comparador flexible de fechas en español."""

    def test_fecha_formatos_numericos(self):
        texto = "FECHA DE GENERACIÓN: 26/05/2026"
        assert comparar_fecha("2026-05-26", texto.upper())

        texto = "FECHA DE EMISIÓN: 26-05-2026"
        assert comparar_fecha("2026-05-26", texto.upper())

        texto = "FECHA: 2026-05-26"
        assert comparar_fecha("2026-05-26", texto.upper())

    def test_fecha_formato_texto_espanol(self):
        texto = "Bogotá, 26 de Mayo de 2026"
        assert comparar_fecha("2026-05-26", texto.upper())

        texto = "Fecha 23 de Septiembre de 2025"
        assert comparar_fecha("2025-09-23", texto.upper())

    def test_fecha_formato_abreviado(self):
        texto = "EMISIÓN: 26/05/26"
        assert comparar_fecha("2026-05-26", texto.upper())

        texto = "Fecha: may 26 2026"
        assert comparar_fecha("2026-05-26", texto.upper())


# ===========================================================================
# 2. Tests de Circuit Breaker y Caché (Nivel 2 IA)
# ===========================================================================

def test_circuit_breaker_activacion_y_recuperacion():
    """Verifica el ciclo de vida del Circuit Breaker ante fallos recurrentes."""
    import core.python.verificacion_grafica.validador_ia as validador_ia
    
    # Reset inicial
    validador_ia._fallos_consecutivos = 0
    validador_ia._ultimo_fallo_timestamp = 0.0

    # 1. Simular 5 fallos
    for _ in range(5):
        validador_ia._registrar_fallo()

    assert validador_ia._fallos_consecutivos == 5

    # 2. Llamada debe ser abortada por Circuit Breaker activo
    resultado = asyncio.run(verificar_con_ia("fake_img", {"dummy": True}, ["campo_ejemplo"]))
    assert resultado["metodo"] == "IA_INNTI_CIRCUIT_BREAKER"
    assert resultado["aprobado"] is False

    # 3. Simular paso del tiempo (recovery de 5 mins transcurrido)
    validador_ia._ultimo_fallo_timestamp = time.time() - 310.0

    # 4. Mockear respuesta exitosa para probar la recuperación
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "choices": [{"message": {"content": '{"campos": {"campo_ejemplo": {"presente": true, "confianza": 0.95}}, "explicacion_general": "OK"}'}}]
        })
        mock_post.return_value = mock_response

        resultado_recuperado = asyncio.run(verificar_con_ia("fake_img_rec", {"dummy": True}, ["campo_ejemplo"]))
        assert resultado_recuperado["metodo"] == "IA_INNTI"
        assert validador_ia._fallos_consecutivos == 0  # Debe haber reseteado tras éxito


def test_cache_respuestas_ia():
    """Verifica que las respuestas exitosas de la IA se recuperen de la caché."""
    import core.python.verificacion_grafica.validador_ia as validador_ia
    
    validador_ia._fallos_consecutivos = 0
    _cache_resultados_ia.clear()

    # Primer llamado mockeado
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "choices": [{"message": {"content": '{"campos": {"denominacion": {"presente": true, "confianza": 0.85}}, "explicacion_general": "Encontrado"}'}}]
        })
        mock_post.return_value = mock_response

        # Primer llamado
        res1 = asyncio.run(verificar_con_ia("img_cache_test", {"dummy": True}, ["denominacion"]))
        assert res1["metodo"] == "IA_INNTI"
        assert mock_post.call_count == 1

        # Segundo llamado idéntico (debe retornar de caché sin llamar a httpx)
        res2 = asyncio.run(verificar_con_ia("img_cache_test", {"dummy": True}, ["denominacion"]))
        assert res2["metodo"] == "IA_INNTI"
        assert res2["aprobado"] == res1["aprobado"]
        assert mock_post.call_count == 1  # Sigue siendo 1, indicando uso de caché

