import asyncio
import sys
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Body
from typing import List, Optional, Union
from logic.clear_logic import limpiar_archivos_temporales, truncar_log
from robot import ejecutar_robot_endesa, ejecutar_robot_enel
from modelos_datos import FacturaEndesa, FacturaEnel

# --- PARCHE PARA WINDOWS ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Descripción general para la parte superior de /docs
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

app = FastAPI(
    title="RPA GRUPO MAS - Sistema de Extracción",
    description=description,
    version="1.0.0",
    contact={
        "name": "Soporte Técnico - Nexo Neural",
    }
)

# --- ENDPOINTS DE LIMPIEZA ---
@app.delete("/clear-files", tags=["Mantenimiento"], summary="Limpiar archivos temporales y logs")
def clear_files(
    portal: Optional[str] = Query(None, enum=["ENDESA", "ENEL"], description="Filtrar por portal específico"),
    tipo: Optional[str] = Query(None, enum=["PDF", "XML", "CSV"], description="Filtrar por extensión de archivo"),
    fecha: Optional[str] = Query(None, description="Formato DD/MM/YYYY, MM/YYYY o YYYY. Filtra por fecha de creación del archivo."),
    limpiar_logs: bool = Query(False, description="Si es True, vacía el contenido de logs/log.txt sin borrar el archivo.")
):
    """
    Borra archivos descargados en las carpetas temporales sin eliminar las carpetas raíz.
    - **Portal**: Filtra si quieres borrar solo lo de Endesa o Enel.
    - **Tipo**: Filtra por el formato del archivo.
    - **Fecha**: Puedes borrar por día exacto, mes completo o año.
    """
    eliminados = limpiar_archivos_temporales(portal, tipo, fecha)
    if limpiar_logs:
        truncar_log()
    return {"status": "success", "archivos_eliminados": eliminados}

# --- EJECUCIÓN DE ROBOTS ---
@app.post("/run/endesa", response_model=List[FacturaEndesa], tags=["Robots"], summary="Ejecutar Robot Endesa")
async def run_endesa(
    fecha_desde: str = Query(..., example="01/10/2025", description="Fecha inicio búsqueda (DD/MM/YYYY)"),
    fecha_hasta: str = Query(..., example="31/10/2025", description="Fecha fin búsqueda (DD/MM/YYYY)"),
    cups: Optional[List[str]] = Body(None, description="Lista de CUPS específicos. Si se omite, busca en todos los CUPS disponibles.")
):
    """
    Lanza el proceso RPA para el portal de Endesa Clientes.
    Devuelve un listado JSON con los datos extraídos de cada factura encontrada.
    """
    try:
        return await ejecutar_robot_endesa(fecha_desde, fecha_hasta, cups)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en Robot Endesa: {str(e)}")

@app.post("/run/enel", response_model=List[FacturaEnel], tags=["Robots"], summary="Ejecutar Robot Enel")
async def run_enel(
    fecha_desde: str = Query(..., example="01/10/2025"),
    fecha_hasta: str = Query(..., example="31/10/2025")
):
    """
    Lanza el proceso RPA para el portal de Enel Distribución.
    """
    try:
        return await ejecutar_robot_enel(fecha_desde, fecha_hasta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en Robot Enel: {str(e)}")

@app.post("/run/all", response_model=List[Union[FacturaEndesa, FacturaEnel]], tags=["Robots"], summary="Ejecución Global")
async def run_all(
    fecha_desde: str = Query(..., example="01/10/2025"),
    fecha_hasta: str = Query(..., example="31/10/2025"),
    cups_endesa: Optional[List[str]] = Body(None)
):
    """
    Ejecuta ambos robots de forma secuencial:
    1. Primero Endesa.
    2. Luego Enel.
    Consolida todos los resultados en una única lista JSON.
    """
    try:
        resultado_endesa = await ejecutar_robot_endesa(fecha_desde, fecha_hasta, cups_endesa)
        resultado_enel = await ejecutar_robot_enel(fecha_desde, fecha_hasta)
        return resultado_endesa + resultado_enel
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en ejecución global: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False, loop="asyncio")