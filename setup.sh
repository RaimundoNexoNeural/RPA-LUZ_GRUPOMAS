#!/bin/bash

echo "=== Iniciando instalación de RPA GRUPO MAS ==="

# 1. Actualizar sistema e instalar Python 3.11 si no existe
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3-pip

# 2. Crear entorno virtual
echo "Creando entorno virtual..."
python3.11 -m venv venv

# 3. Activar entorno e instalar librerías de Python
source venv/bin/activate
echo "Instalando dependencias de Python..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configurar Playwright (Navegadores y dependencias de sistema Linux)
echo "Configurando navegadores de Playwright..."
playwright install chromium
playwright install-deps chromium

# 5. Crear estructura de carpetas necesaria
mkdir -p logs results temp_downloads prompts

echo "=== Instalación completada con éxito ==="
echo "Recuerda configurar tu archivo .env antes de lanzar la API o los Robots."