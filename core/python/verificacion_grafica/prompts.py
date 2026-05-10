"""Prompts estructurados para la verificación gráfica con IA."""


def construir_prompt_verificacion(
    datos_factura: dict, campos_a_verificar: list[str]
) -> str:
    """Construye el prompt de grounding para la IA.

    La IA recibe los datos completos del XML y solo debe confirmar si los campos
    indicados están visualmente presentes en el PDF.
    """
    campos_texto = "\n".join(f"- {campo}" for campo in campos_a_verificar)

    prompt = f"""Eres un auditor experto en facturación electrónica colombiana
(Resolución 000165 de 2023, DIAN).

Te entrego la imagen de la representación gráfica (PDF) de una factura
electrónica y los datos oficiales extraídos del XML validado.

Tu tarea es verificar si cada uno de los siguientes campos está VISUALMENTE
PRESENTE en el documento. Los valores correctos están en el XML ya entregado;
no los repitas en tu respuesta.

CAMPOS A VERIFICAR:
{campos_texto}

Responde ÚNICAMENTE en JSON con esta estricta estructura:
{{
  "campos": {{
    "nombre_del_campo": {{"presente": true/false}}
  }},
  "explicacion_general": "Los siguientes campos no se encontraron en el PDF: campo1, campo2 (o 'Todos los campos verificados correctamente')."
}}"""

    return prompt
