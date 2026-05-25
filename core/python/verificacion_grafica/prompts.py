"""Prompts estructurados para la verificación gráfica con IA."""


def construir_prompt_verificacion(
    datos_factura: dict, campos_a_verificar: list[str]
) -> str:
    """Construye el prompt de grounding para la IA.

    La IA recibe los datos completos del XML y debe confirmar si los campos
    indicados están visualmente presentes en el PDF, con nivel de confianza.
    """
    campos_texto = "\n".join(f"- {campo}" for campo in campos_a_verificar)

    # Build a reference section with expected values for the fields
    valores_ref = []
    for campo in campos_a_verificar:
        valor = datos_factura.get(campo)
        if valor:
            valores_ref.append(f"- {campo}: {valor}")
    valores_texto = "\n".join(valores_ref) if valores_ref else "(sin valores de referencia)"

    prompt = f"""Eres un auditor experto en facturación electrónica colombiana
(Resolución 000165 de 2023, DIAN).

Te entrego la imagen de la representación gráfica (PDF) de una factura
electrónica y los datos oficiales extraídos del XML validado.

Tu tarea es verificar si cada uno de los siguientes campos está VISUALMENTE
PRESENTE en el documento. Evalúa cada campo con un nivel de CONFIANZA.

CAMPOS A VERIFICAR:
{campos_texto}

VALORES ESPERADOS (del XML):
{valores_texto}

Responde ÚNICAMENTE en JSON con esta estricta estructura:
{{
  "campos": {{
    "nombre_del_campo": {{
      "presente": true/false,
      "confianza": 0.0 a 1.0,
      "detalle": "Breve explicación de por qué se considera presente o ausente"
    }}
  }},
  "explicacion_general": "Resumen de la verificación."
}}

REGLAS DE CONFIANZA:
- 1.0 = El valor exacto del XML aparece claramente en el PDF
- 0.7-0.9 = El valor aparece pero con diferencias menores (formato, truncamiento)
- 0.3-0.6 = Hay información similar pero no se puede confirmar con certeza
- 0.0-0.2 = El campo no se encuentra en el PDF"""

    return prompt

