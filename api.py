import asyncio
import sys
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Body, Response
from fastapi.responses import HTMLResponse, FileResponse
from typing import List, Optional, Union
from fastapi.staticfiles import StaticFiles
from logic.clear_logic import (
    limpiar_archivos_temporales,
    truncar_log,
    limpiar_registros_procesados,
    limpiar_registros_enviadas,
)
from logic.logs_logic import log, mail_handler
from robot import ejecutar_robot_endesa, ejecutar_robot_enel
from utils.modelos_datos import FacturaEndesa, FacturaEnel

# === 0. CONFIGURACIÓN DEL ENTORNO DE EJECUCIÓN === 

# A. Parche de compatibilidad para bucles de eventos en sistemas Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# B. Documentación descriptiva para la interfaz de FastAPI (Swagger UI)
description = """
## API de Automatización RPA - GRUPO MAS

Esta API gestiona la extracción automática de facturas desde los portales de **Endesa** y **Enel**. 
Permite la limpieza de archivos temporales, la ejecución individual por portal o la ejecución global.

### Funcionalidades:
* **Limpieza**: Mantenimiento del sistema de archivos y logs.
* **Robot Endesa**: Extracción de facturas de clientes (soporta filtrado por lista de CUPS).
* **Robot Enel**: Extracción desde el portal de distribución.
* **Ejecución Total**: Consolidación de datos de ambos portales en una sola respuesta.
"""

# C. Inicialización de la aplicación FastAPI
app = FastAPI(
    title="RPA GRUPO MAS - FACTURAS ENDESA Y ENEL",
    description=description,
    version="1.0.0",
    contact={
        "name": "Soporte Técnico - Nexo Neural",
    }
)

# D. Montaje de recursos estáticos (Favicon, CSS, imágenes)
app.mount("/static", StaticFiles(directory="static"), name="static")


# === 1. RUTAS GENERALES DE INFORMACIÓN ===

# INF.1 Página de inicio (Root)
@app.get("/", include_in_schema=False)
def root():
    '''
    Sirve una página HTML básica con información del servicio y enlace a la documentación.
    Retorna
        - HTMLResponse: Página de bienvenida con estilos integrados.
    '''
    log.debug("Acceso a la ruta raíz (/) de la API")
    # A. Definición de la estructura HTML y estilos CSS
    html = (
        "<html><head><title>API RPA GRUPO MAS</title>"
        "<link rel=\"icon\" href=\"/static/favicon.ico\" type=\"image/x-icon\"/>"
        "<style>body{font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:40px auto;line-height:1.5;}"
        "h1{color:#2c3e50;}a{color:#2980b9;text-decoration:none;}a:hover{text-decoration:underline;}" 
        "footer{margin-top:40px;font-size:0.9em;color:#7f8c8d;}" 
        "</style></head><body>"
        "<h1>API RPA GRUPO MAS</h1>"
        "<p>Bienvenido al servicio de automatización. Esta API permite lanzar los robots de extracción de facturas, limpiar archivos temporales y gestionar registros internos.</p>"
        "<p>Visita la <a href='/docs'>documentación Swagger</a> para probar los endpoints interactivos.</p>"
        "<footer>Desarrollado por Nexo Neural - &copy; 2026</footer>"
        "</body></html>"
    )
    return HTMLResponse(content=html)


# INF.2 Gestión del Favicon
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    '''
    Proporciona el icono de la pestaña para el navegador desde el directorio estático.
    Retorna
        - FileResponse: Archivo .ico con cabeceras de control de caché.
    '''
    # A. Verificación de existencia del archivo físico
    path = os.path.join("static", "favicon.ico")
    if os.path.isfile(path):
        # B. Generación de respuesta con cabeceras para evitar caché agresivo
        resp = FileResponse(path, media_type="image/x-icon")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp
    
    return Response(status_code=204)


# === 2. ENDPOINTS DE MANTENIMIENTO Y LIMPIEZA === 

# CLN.1 Limpieza integral del sistema
@app.delete("/clear-files", tags=["Mantenimiento"], summary="Limpiar archivos temporales y logs")
def clear_files(
    portal: Optional[str] = Query(None, enum=["ENDESA", "ENEL"], description="Filtrar por portal específico"),
    tipo: Optional[str] = Query(None, enum=["PDF", "XML", "CSV"], description="Filtrar por extensión de archivo"),
    fecha: Optional[str] = Query(None, description="Formato DD/MM/YYYY, MM/YYYY o YYYY. Filtra por fecha de creación del archivo."),
    limpiar_logs: bool = Query(False, description="Si es True, aplica truncado de archivos de logs."),
    nivel_log: Optional[str] = Query(None, enum=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], description="Nivel específico de log a limpiar."),
    limpiar_procesados: bool = Query(False, description="Elimina registros CSV de facturas procesadas."),
    limpiar_enviadas: bool = Query(False, description="Elimina registros CSV de facturas enviadas por email.")
):
    '''
    Coordina la eliminación de archivos descargados y la purga de registros internos de trazabilidad.
    \nParametros:
        \n- portal (str): Distribuidora objetivo.
        \n- tipo (str): Formato de archivo a eliminar.
        \n- fecha (str): Filtro temporal de creación.
        \n- limpiar_logs (bool): Flag de reseteo de logs.
        \n- nivel_log (str): Categoría de log específica.
        \n- limpiar_procesados (bool): Flag para borrar historial de procesos.
        \n- limpiar_enviadas (bool): Flag para borrar historial de correos.
    \nRetorna
        \n- dict: Resumen de elementos eliminados por categoría.
    '''
    log.info(f"[API] Solicitud de limpieza recibida. Parámetros: portal={portal}, tipo={tipo}, fecha={fecha}")
    # A. Limpieza de archivos temporales de descarga
    eliminados = limpiar_archivos_temporales(portal, tipo, fecha)
    resultado: dict = {"status": "success", "archivos_eliminados": eliminados}

    # B. Gestión de purga de logs (Truncado)
    if limpiar_logs:
        log.warning(f"[API] Truncando archivos de log. Nivel objetivo: {nivel_log or 'TODOS'}")
        resultado["logs"] = truncar_log(nivel_log)

    # C. Limpieza de registros históricos (CSVs de control)
    if limpiar_procesados:
        log.warning(f"[API] Eliminando registros CSV de facturas procesadas para {portal or 'ambos portales'}")
        resultado["registros_procesados_eliminados"] = limpiar_registros_procesados(portal)
    
    if limpiar_enviadas:
        log.warning(f"[API] Eliminando registros CSV de facturas enviadas para {portal or 'ambos portales'}")
        resultado["registros_enviadas_eliminados"] = limpiar_registros_enviadas(portal)

    return resultado


# === 3. ENDPOINTS DE EJECUCIÓN RPA (ROBOTS) === 

# RPA.1 Robot Endesa Clientes
@app.post("/run/endesa", response_model=List[FacturaEndesa], tags=["Robots"], summary="Ejecutar Robot Endesa")
async def run_endesa(
    fecha_desde: str = Query(..., examples={"default": {"value": "01/10/2025"}}, description="Fecha inicio búsqueda (DD/MM/YYYY)"),
    fecha_hasta: str = Query(..., examples={"default": {"value": "31/10/2025"}}, description="Fecha fin búsqueda (DD/MM/YYYY)"),
    cups: Optional[List[str]] = Body(None, description="Lista de CUPS específicos.")
):
    '''
    Lanza el proceso de extracción para el portal de clientes de Endesa.
    \nParametros:
        \n- fecha_desde (str): Inicio del rango.
        \n- fecha_hasta (str): Fin del rango.
        \n- cups (list): Filtro de suministros.
    \nRetorna
        \n- list[FacturaEndesa]: Datos extraídos y procesados.
    '''
    log.info(f"[API] Lanzando Robot Endesa Clientes. Periodo: {fecha_desde} - {fecha_hasta}. CUPS: {len(cups) if cups else 'Global'}")
    try:
        # A. Invocación de la lógica de negocio del robot
        return await ejecutar_robot_endesa(fecha_desde, fecha_hasta, cups)
    except Exception as e:
        # B. Gestión de errores críticos
        log.error(f"[API] Error ejecutando Robot Endesa: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en Robot Endesa: {str(e)}")


# RPA.2 Robot Enel Distribución
@app.post("/run/enel", response_model=List[FacturaEnel], tags=["Robots"], summary="Ejecutar Robot Enel")
async def run_enel(
    fecha_desde: str = Query(..., examples={"default": {"value": "01/10/2025"}}),
    fecha_hasta: str = Query(..., examples={"default": {"value": "31/10/2025"}})
):
    '''
    Lanza el proceso de extracción para el portal de distribución de Enel.
    \nParametros:
        \n- fecha_desde (str): Inicio del rango.
        \n- fecha_hasta (str): Fin del rango.
    \nRetorna
        \n- list[FacturaEnel]: Datos extraídos y procesados.
    '''
    log.info(f"[API] Lanzando Robot Enel Distribución. Periodo: {fecha_desde} - {fecha_hasta}")
    try:
        # A. Ejecución asíncrona del robot de distribución
        return await ejecutar_robot_enel(fecha_desde, fecha_hasta)
    except Exception as e:
        log.error(f"[API] Error ejecutando Robot Enel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en Robot Enel: {str(e)}")


# RPA.3 Ejecución Consolidada (Global)
@app.post("/run/all", response_model=List[Union[FacturaEndesa, FacturaEnel]], tags=["Robots"], summary="Ejecución Global")
async def run_all(
    fecha_desde: str = Query(..., examples={"default": {"value": "01/10/2025"}}),
    fecha_hasta: str = Query(..., examples={"default": {"value": "31/10/2025"}}),
    cups_endesa: Optional[List[str]] = Body(None)
):
    '''
    Ejecuta ambos robots secuencialmente y unifica los resultados.
    \nParametros:
        \n- fecha_desde (str): Inicio del rango.
        \n- fecha_hasta (str): Fin del rango.
        \n- cups_endesa (list): Filtro de suministros para Endesa (opcional).
    \nRetorna
        \n- list[Union[FacturaEndesa, FacturaEnel]]: Lista combinada de facturas extraídas.
    '''
    log.info(f"[API] Lanzando Ejecución Consolidada (Endesa + Enel). Periodo: {fecha_desde} - {fecha_hasta}")
    try:
        # A. Ejecución secuencial de portales
        # A.1. Extracción en Endesa
        resultado_endesa = await ejecutar_robot_endesa(fecha_desde, fecha_hasta, cups_endesa)
        # A.2. Extracción en Enel
        resultado_enel = await ejecutar_robot_enel(fecha_desde, fecha_hasta)
        
        # B. Consolidación de listas de resultados
        log.info(f"[API] Ejecución consolidada finalizada. Total: {len(resultado_endesa) + len(resultado_enel)} facturas.")
        return resultado_endesa + resultado_enel
    except Exception as e:
        log.error(f"[API] Error en ejecución consolidada: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en ejecución global: {str(e)}")


# === 4. INICIO DEL SERVIDOR === 

if __name__ == "__main__":
    log.info("--- Iniciando servidor FastAPI para RPA GRUPO MAS ---")
    # A. Lanzamiento de Uvicorn con configuración de red local
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False, loop="asyncio")