"""Módulo que contiene funciones de utilidad para la validación del NIT en las facturas
 electrónicas."""


def calcular_dv_nit_v1(nit: str) -> int:
    """Calcula el dígito de verificación DIAN para un NIT, basado en el algoritmo
     establecido en la resolución 000165 de 2023.
    
    Args:
        nit: El NIT a validar.
        
    Returns:
        El dígito de verificación calculado.
    
    """
    pesos = [71, 67, 59, 53, 47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3]

    nit = ''.join(filter(str.isdigit, nit))
    nit_15 = nit.zfill(15)

    suma = 0
    for i in range(15):
        suma += int(nit_15[i]) * pesos[i]

    residuo = suma % 11

    if residuo == 0:
        digito_validacion = 0
    elif residuo == 1:
        digito_validacion = 1
    else:
        digito_validacion = 11 - residuo
        
    return digito_validacion


def validar_datos_persona(
    nombre: str, nit: str, scheme_name: str, dv_xml: str
    ) -> tuple[str, bool]:
    """Valida el nombre y NIT de una persona (emisor o adquiriente) según las reglas de la
     resolución 000165 de 2023.
     
    Args:
        nombre: Nombre o razón social de la persona.
        nit: NIT de la persona.
        scheme_name: Valor del atributo schemeName del nodo CompanyID.
        dv_xml: Valor del atributo schemeID del nodo CompanyID (dígito de verificación).
        
    Returns:
        Tupla (mensaje, resultado_validacion) donde:
        - mensaje: Descripción del resultado de la validación.
        - resultado_validacion: True si los datos son válidos, False en caso contrario.
    
    """
    resultado_validacion = False
    
    if not nombre:
        mensaje = 'No se encontró nombre de la persona.'

    elif scheme_name != '31':
        mensaje = f'Nombre válido: "{nombre}". No requiere validación de NIT.'
        resultado_validacion = True

    elif not nit:
        mensaje = f'Se encontró nombre "{nombre}" pero no NIT.'

    elif not (6 <= len(nit) <= 15) or not nit.isdigit():
        mensaje = (
            f'Se encontró nombre "{nombre}" pero el NIT "{nit}" no es válido.'
        )

    elif dv_xml is None or not dv_xml.isdigit():
        mensaje = (
            f'Se encontró nombre "{nombre}" y NIT "{nit}" '
            f'pero sin dígito de verificación válido.'
        )

    else:
        dv_xml = int(dv_xml)
        dv_calculado = calcular_dv_nit_v1(nit)

        if dv_calculado != dv_xml:
            mensaje = (
                f'Se encontró nombre "{nombre}" y NIT "{nit}" pero DV incorrecto '
                f'(XML: {dv_xml}, Calculado: {dv_calculado}).'
            )

        else:
            mensaje = f'Datos válidos: "{nombre}" con NIT {nit}-{dv_xml}.'
            resultado_validacion = True
    
    resultado = {
        'mensaje': mensaje,
        'resultado': resultado_validacion
    }
    
    return resultado
