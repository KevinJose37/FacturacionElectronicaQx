---
name: python-dev
description: Lineamientos de desarrollo Python para este proyecto. Usa este skill siempre que el usuario solicite escribir, modificar, refactorizar o revisar código Python, incluyendo endpoints FastAPI, helpers, utilidades, consultas MongoDB, procesamiento con Pandas/Polars y clases de configuración.
---

# Lineamientos de desarrollo Python

Aplica estas reglas en todo código Python que generes o modifiques.

## Estilo general
- Sigue PEP 8. Código limpio, profesional y legible.
- Usa comillas simples para strings; prefiere f-strings.
- Los type hints son obligatorios en argumentos de funciones, tipos de retorno y atributos de clases Pydantic. No uses type hints en variables locales.
- Los type hints van a primer nivel únicamente, usando tipos nativos de Python siempre que se pueda: `list`, `dict`, `tuple`, `set`, `Generator`. No parametrices con genéricos (e.g., `list` en vez de `list[str]`, `dict` en vez de `dict[str, int]`, `Generator` en vez de `Generator[str, None, None]`). Uniones como `dict | None` sí se permiten.
- Prefiere lo explícito sobre lo implícito; sé consistente y predecible.
- Evita cadenas largas/complejas de métodos; usa variables intermedias con nombres claros.

## Documentación
- Docstrings en español, estilo Google. Sin espacio después de las triples comillas de apertura (e.g., `"""Descripción...`).
- Primera línea: descripción breve de lo que hace la función.
- Usa secciones `Args:`, `Returns:`, `Raises:` cuando la función tenga argumentos no triviales, retornos que necesiten explicación, o excepciones que lance.
- Cada argumento con su tipo y descripción en la línea siguiente indentada.
- No agregues comentarios de una línea para "explicar" código autoexplicativo; solo agrega comentarios cuando realmente se necesite contexto adicional.

Ejemplo:
```python
def consultar_placas(operacion: str) -> None:
    """Consulta las placas de interés requeridas por la policía.

    Args:
        operacion: La operación de tránsito a consultar.

    Raises:
        KeyError: Si la consulta SQL no se puede formar correctamente.
        DatabaseError: Si ocurre un error al ejecutar la consulta.
    """
```

## Retornos
- Un solo return por función y al final (excepto recursión).
- No escribas expresiones, cálculos o llamadas a funciones directamente en un return.
  Asigna el resultado a una variable con nombre claro y retorna esa variable.

Ejemplo correcto:
```python
resultado = calcular_total(items)
return resultado
```

Ejemplo incorrecto:
```python
return calcular_total(items)
```

## Strings largos y longitud de línea
- Al envolver strings largos (PEP 8), no dividas un f-string a mitad de oración.

Correcto:
```python
mensaje_error_duplicado = (
    f'Error de clave duplicada al crear usuario {usuario_data.user_name}: {e}'
)
```

Incorrecto:
```python
mensaje_error_duplicado = (f'Error de clave duplicada al crear usuario '
                            f'{usuario_data.user_name}: {e}')
```

## Números, fechas y locale
- Usa Babel para formatear números de presentación (format_decimal, format_percent, etc.).
- Almacena valores numéricos sin formato; formatea solo en el límite (UI/serialización).
- Mantén datetimes como tipos nativos (datetime/pandas.Timestamp).
- Almacena datetimes en Parquet como timestamps, no como strings.
- Sé explícito con las zonas horarias cuando sea necesario (UTC por defecto).

## Pandas / Polars
- Valida que los DataFrames no estén vacíos antes de groupby/merge/join.
- Evita .copy() innecesarios; no uses operaciones inplace.
- Prefiere operaciones vectorizadas; evita loops fila por fila.
- Selecciona con .loc y listas explícitas de columnas.
- Usa merge con keys y suffixes explícitos.
- No encadenes groupby/agg/sort en una sola expresión; separa en pasos con nombres claros.
- Calcula porcentajes como numéricos primero; formatea para presentación con Babel al final.

## MongoDB / SQL
- Proyecta solo los campos necesarios; prefiere agregación del lado del servidor.
- Valida que los campos requeridos existan antes de operar.

## FastAPI / APIs
- Usa modelos Pydantic con type hints para requests y responses.
- Mantén los docstrings de endpoints cortos: propósito, parámetros clave, ejemplos mínimos.

## Arquitectura de routers (CRÍTICO)
- Los archivos de router SOLO deben contener las funciones que definen los endpoints (decoradas con @router.get, @router.post, etc.).
- Toda lógica de negocio, transformaciones de datos, consultas a base de datos y procesamiento debe ir en módulos separados según corresponda:
  - `core/`: Lógica de negocio principal y reglas de dominio.
  - `helpers/`: Funciones auxiliares reutilizables y utilitarios del proyecto.
  - `utils/` o `utilidades/`: Funciones genéricas de propósito general (formateo, conversiones, etc.).
- Los endpoints deben ser delegadores: reciben la request, llaman a la lógica correspondiente en core/helpers/utils, y retornan la respuesta.
- Esto mantiene los routers delgados, testables y con responsabilidad única.

Ejemplo correcto de endpoint:
```python
@router.get('/reporte-rendimiento')
async def obtener_reporte_rendimiento(
    fecha_inicio: date,
    fecha_fin: date
) -> dict:
    """Obtiene reporte de rendimiento del equipo."""
    reporte = generar_reporte_rendimiento(fecha_inicio, fecha_fin)
    return reporte
```

Ejemplo incorrecto (lógica en el router):
```python
@router.get('/reporte-rendimiento')
async def obtener_reporte_rendimiento(
    fecha_inicio: date,
    fecha_fin: date
) -> dict:
    """Obtiene reporte de rendimiento del equipo."""
    datos = await db.find({'fecha': {'$gte': fecha_inicio}})
    df = pd.DataFrame(datos)
    df['rendimiento'] = df['completados'] / df['asignados']
    resultado = df.groupby('equipo').agg({'rendimiento': 'mean'})
    return resultado.to_dict()
```

## Errores y logging
- Lanza excepciones específicas (ValueError, TypeError, etc.) con mensajes accionables.
- Usa logging.info/warning/error/exception con contexto significativo.
- No silencies excepciones.

## Funciones anidadas
- No definas funciones dentro de otras funciones salvo que sea estrictamente necesario (decoradores, wrappers, closures que realmente capturen variables del scope).
- Si la función interna no usa variables del closure, extráela como función de módulo o helper reutilizable.
- Los generadores auxiliares (e.g., para crear un stream de error) deben vivir en helpers/, no como funciones anidadas ad-hoc.

Ejemplo incorrecto (función anidada innecesaria):
```python
def endpoint_stream(datos: str) -> StreamingResponse:
    if not datos:
        def error_stream():
            yield formatear_evento_sse({'tipo': 'error', 'mensaje': 'Sin datos.'})
        return StreamingResponse(error_stream(), ...)
```

Ejemplo correcto (helper reutilizable):
```python
# En helpers/sse.py
def generar_stream_error(mensaje: str) -> Generator:
    evento = formatear_evento_sse({'tipo': 'error', 'mensaje': mensaje})
    yield evento

# En el router
def endpoint_stream(datos: str) -> StreamingResponse:
    if not datos:
        respuesta = StreamingResponse(generar_stream_error('Sin datos.'), ...)
        return respuesta
```

## Variables de configuración
- NUNCA hardcodees valores configurables (umbrales, límites, cantidades, días, etc.) directamente en el código Python. Toda variable de configuración de la aplicación debe vivir en los archivos YAML de `config/`.
- Usa las funciones de `config.py` (`get_notificaciones_config()`, `get_performance_config()`, `get_time_tracking_config()`, etc.) para leer los valores en tiempo de ejecución.
- Al agregar un nuevo parámetro configurable, ubícalo en el YAML existente que corresponda temáticamente (umbrales de notificación en `notificaciones_config.yaml`, rendimiento en `performance_config.yaml`, etc.).
- Siempre proporciona un valor por defecto con `.get()` al leer del config para evitar errores si el YAML aún no tiene la clave.

Correcto:
```python
config = get_notificaciones_config()
max_items = config['umbrales'].get('max_issues_listados', 3)
```

Incorrecto:
```python
MAX_ITEMS = 3  # hardcodeado en el módulo
```

## Rendimiento y estructura
- Mantén funciones pequeñas y enfocadas; extrae helpers cuando crezcan.
- Evita código muerto y bloques comentados.
- Ordena imports: stdlib, terceros, proyecto (alfabéticamente dentro de cada grupo).

## Clases de metadatos
- Para clases de metadatos/contenedoras de constantes (config, rutas, configuración de sesión):
  1. Nombre de clase en PascalCase.
  2. Atributos en lowercase_with_underscores.
  3. Cada atributo seguido de un docstring corto que indique significado y unidades si aplica.
  4. Deriva valores relacionados de otras constantes para evitar duplicación.
  5. Evita números mágicos; explícalos en el docstring.
  6. Centraliza estos valores aquí; no disperses constantes por el codebase.
- No declares constantes, diccionarios de mapeo, sets ni listas como variables sueltas a nivel de módulo. Toda constante debe vivir dentro de una clase de metadatos en `metadata/` o en los archivos YAML de `config/`.
