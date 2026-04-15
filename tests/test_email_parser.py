"""Tests del parser de asuntos de correos de facturación electrónica.

Cubre los siguientes escenarios:
    1. Asunto con formato estándar completo.
    2. Asunto con prefijo de reenvío "Fwd:".
    3. Asunto que NO sigue el formato estándar (proveedor informal).
    4. Asunto vacío.
"""

from __future__ import annotations

import pytest

from utils.email_parser import EmailParser


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def parser() -> EmailParser:
    """Instancia reutilizable de EmailParser para los tests."""
    return EmailParser()


# ---------------------------------------------------------------------------
# Caso 1: Asunto con formato estándar completo
# ---------------------------------------------------------------------------


class TestFormatoEstandarCompleto:
    """Tests para asuntos que siguen exactamente el formato estándar."""

    def test_nit_extraido_correctamente(self, parser: EmailParser) -> None:
        """El NIT debe extraerse como cadena de texto."""
        asunto = "811028188;INSTITUCION UNIVERSITARIA SALAZAR Y HERRERA;FEA46067;01;INSTITUCIÓN UNIVERSITARIA SALAZAR Y HERRERA"
        result = parser.parsear(asunto)
        assert result["nit"] == "811028188"

    def test_razon_social_extraida(self, parser: EmailParser) -> None:
        asunto = "811028188;INSTITUCION UNIVERSITARIA SALAZAR Y HERRERA;FEA46067;01;INSTITUCIÓN UNIVERSITARIA SALAZAR Y HERRERA"
        result = parser.parsear(asunto)
        assert result["razon_social"] == "INSTITUCION UNIVERSITARIA SALAZAR Y HERRERA"

    def test_num_factura_extraido(self, parser: EmailParser) -> None:
        asunto = "811028188;INSTITUCION UNIVERSITARIA SALAZAR Y HERRERA;FEA46067;01;INSTITUCIÓN UNIVERSITARIA SALAZAR Y HERRERA"
        result = parser.parsear(asunto)
        assert result["num_factura"] == "FEA46067"

    def test_tipo_extraido(self, parser: EmailParser) -> None:
        asunto = "811028188;INSTITUCION UNIVERSITARIA SALAZAR Y HERRERA;FEA46067;01;INSTITUCIÓN UNIVERSITARIA SALAZAR Y HERRERA"
        result = parser.parsear(asunto)
        assert result["tipo"] == "01"

    def test_nombre_proveedor_extraido(self, parser: EmailParser) -> None:
        asunto = "811028188;INSTITUCION UNIVERSITARIA SALAZAR Y HERRERA;FEA46067;01;INSTITUCIÓN UNIVERSITARIA SALAZAR Y HERRERA"
        result = parser.parsear(asunto)
        assert result["nombre_proveedor"] == "INSTITUCIÓN UNIVERSITARIA SALAZAR Y HERRERA"

    def test_no_es_reenvio(self, parser: EmailParser) -> None:
        asunto = "811028188;EMPRESA TEST;FAC-999;01;EMPRESA TEST"
        result = parser.parsear(asunto)
        assert result["es_reenvio"] is False

    def test_asunto_original_conservado(self, parser: EmailParser) -> None:
        asunto = "811028188;EMPRESA TEST;FAC-999;01;EMPRESA TEST"
        result = parser.parsear(asunto)
        assert result["asunto_original"] == asunto


# ---------------------------------------------------------------------------
# Caso 2: Asunto con prefijo "Fwd:"
# ---------------------------------------------------------------------------


class TestAsuntoConReenvio:
    """Tests para correos reenviados con distintos prefijos."""

    @pytest.mark.parametrize(
        "prefijo",
        ["Fwd:", "fwd:", "FWD:", "Fw:", "RV:", "rv:", "Reen:"],
    )
    def test_detecta_reenvio(self, parser: EmailParser, prefijo: str) -> None:
        """Todos los prefijos de reenvío conocidos deben marcarse como reenvío."""
        asunto = f"{prefijo} 900123456;EMPRESA NUEVA;FV-001;01;EMPRESA NUEVA"
        result = parser.parsear(asunto)
        assert result["es_reenvio"] is True

    def test_extrae_nit_tras_prefijo(self, parser: EmailParser) -> None:
        asunto = "Fwd: 900123456;EMPRESA REENVIADA;FV-002;01;EMPRESA REENVIADA"
        result = parser.parsear(asunto)
        assert result["nit"] == "900123456"

    def test_asunto_original_incluye_prefijo(self, parser: EmailParser) -> None:
        """El asunto original debe conservar el prefijo de reenvío."""
        asunto = "Fwd: 900123456;EMPRESA REENVIADA;FV-002;01;EMPRESA REENVIADA"
        result = parser.parsear(asunto)
        assert result["asunto_original"].startswith("Fwd:")

    def test_campos_correctos_tras_reenvio(self, parser: EmailParser) -> None:
        asunto = "FW: 811028188;PROVEEDOR SA;FEA001;02;PROVEEDOR SA"
        result = parser.parsear(asunto)
        assert result["razon_social"] == "PROVEEDOR SA"
        assert result["num_factura"] == "FEA001"
        assert result["tipo"] == "02"


# ---------------------------------------------------------------------------
# Caso 3: Asunto que NO sigue el formato (proveedor informal)
# ---------------------------------------------------------------------------


class TestAsuntoSinFormato:
    """Tests para asuntos que no siguen el formato estándar."""

    def test_no_rechaza_correo(self, parser: EmailParser) -> None:
        """Un asunto informal no debe lanzar excepción."""
        asunto = "Factura del mes de marzo - Proveedor Papelería Don Lucho"
        result = parser.parsear(asunto)
        assert result is not None

    def test_campos_datos_son_none(self, parser: EmailParser) -> None:
        """Cuando no hay formato, los campos estructurados deben ser None."""
        asunto = "Factura sin formato ninguno"
        result = parser.parsear(asunto)
        assert result["nit"] is None
        assert result["num_factura"] is None
        assert result["tipo"] is None

    def test_asunto_original_conservado_sin_formato(self, parser: EmailParser) -> None:
        asunto = "Papelería el Tigre - Enero 2025"
        result = parser.parsear(asunto)
        assert result["asunto_original"] == asunto

    def test_nit_invalido_retorna_none(self, parser: EmailParser) -> None:
        """Si el primer campo no es un NIT numérico, debe quedar en None."""
        asunto = "EMPRESA_ABC;EMPRESA ABC;FAC-9999;01;EMPRESA ABC"
        result = parser.parsear(asunto)
        assert result["nit"] is None

    def test_extrae_razon_social_si_hay_semicolons(self, parser: EmailParser) -> None:
        """Si hay al menos dos campos, la razón social debe extraerse."""
        asunto = "Texto libre;Nombre del proveedor informal"
        result = parser.parsear(asunto)
        assert result["razon_social"] == "Nombre del proveedor informal"


# ---------------------------------------------------------------------------
# Caso 4: Asunto vacío
# ---------------------------------------------------------------------------


class TestAsuntoVacio:
    """Tests para correos con asunto vacío o en blanco."""

    def test_asunto_vacio_no_lanza_excepcion(self, parser: EmailParser) -> None:
        result = parser.parsear("")
        assert result is not None

    def test_asunto_vacio_campos_none(self, parser: EmailParser) -> None:
        result = parser.parsear("")
        assert result["nit"] is None
        assert result["razon_social"] is None
        assert result["num_factura"] is None
        assert result["tipo"] is None
        assert result["nombre_proveedor"] is None

    def test_asunto_vacio_no_es_reenvio(self, parser: EmailParser) -> None:
        result = parser.parsear("")
        assert result["es_reenvio"] is False

    def test_asunto_solo_espacios(self, parser: EmailParser) -> None:
        result = parser.parsear("   ")
        assert result["nit"] is None
        assert result["es_reenvio"] is False

    def test_asunto_solo_prefijo_reenvio(self, parser: EmailParser) -> None:
        """Un asunto que solo tiene 'Fwd:' debe marcarse como reenvío con datos None."""
        result = parser.parsear("Fwd:")
        assert result["es_reenvio"] is True
        assert result["nit"] is None
