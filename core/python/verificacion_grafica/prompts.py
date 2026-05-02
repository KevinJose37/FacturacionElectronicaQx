"""Prompts estructurados para la verificación gráfica con IA."""

def construir_prompt_verificacion(
    datos_factura: dict, campos_a_verificar: list[str]
) -> str:
    """Construye el prompt de grounding para la IA.

    La IA recibe los datos exactos y solo debe confirmar si los ve
    en la imagen. NO se le pide que extraiga datos libremente.
    """
    campos_texto = "\n".join(
        f"- {campo}: {datos_factura.get(campo, 'N/A')}"
        for campo in campos_a_verificar
    )

    prompt = f"""Eres un auditor experto en facturación electrónica colombiana
(Resolución 000165 de 2023, DIAN).

Te entrego la imagen de la representación gráfica (PDF) de una factura
electrónica y una lista de datos oficiales extraídos del XML validado.

Tu tarea es verificar si cada dato de la lista está VISUALMENTE PRESENTE
en el documento. No extraigas datos nuevos; solo confirma o niega visualmente los datos provistos.

DATOS A VERIFICAR:
{campos_texto}

Responde ÚNICAMENTE en JSON con esta estricta estructura:
{{
  "campos": {{
    "nombre_del_campo": {{"presente": true/false, "valor_visto": "el valor exacto que lograste ver en la imagen si difiere o es el mismo"}}
  }},
  "explicacion_general": "Resumen de hallazgos, si hay diferencias indica cuáles"
}}"""

    return prompt
