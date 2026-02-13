#!/bin/bash

# 1. Configuración de rutas
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR
source venv/bin/activate

# 2. Cálculo de fechas relativas (Mes Anterior)
# Obtenemos el primer día del mes pasado
FECHA_DESDE=$(date -d "last month" +01/%m/%Y)
# Obtenemos el último día del mes pasado
FECHA_HASTA=$(date -d "$(date +%Y-%m-01) -1 day" +%d/%m/%Y)

echo "Ejecutando Robot para el periodo: $FECHA_DESDE hasta $FECHA_HASTA"

# 3. Lanzamiento del robot (usamos un pequeño script de python inline para llamar a la función)
# Puedes elegir lanzar 'endesa', 'enel' o 'ambos' pasando un argumento al script
PORTAL=${1:-"ambos"}

python3 << EOF
import asyncio
from robot import ejecutar_robot_endesa, ejecutar_robot_enel

async def run():
    portal = "$PORTAL".lower()
    desde = "$FECHA_DESDE"
    hasta = "$FECHA_HASTA"
    
    if portal == "endesa" or portal == "ambos":
        print("Lanzando Endesa...")
        await ejecutar_robot_endesa(desde, hasta)
    
    if portal == "enel" or portal == "ambos":
        print("Lanzando Enel...")
        await ejecutar_robot_enel(desde, hasta)

asyncio.run(run())
EOF

echo "Ejecución finalizada el $(date)" >> logs/cron_executions.log