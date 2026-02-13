#!/bin/bash

# Obtener la ruta absoluta del directorio del script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR

# Activar entorno virtual
source venv/bin/activate

echo "Lanzando API en puerto 8000..."
# --host 0.0.0.0 permite conexiones externas
# --loop asyncio es vital para la compatibilidad con Playwright
exec uvicorn api:app --host 0.0.0.0 --port 8000 --loop asyncio