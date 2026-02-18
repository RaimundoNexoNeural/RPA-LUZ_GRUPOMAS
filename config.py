import os
from pathlib import Path
from dotenv import load_dotenv

# Cargamos el archivo .env
load_dotenv()

# === 1. CREDENCIALES Y SECRETOS (Desde .env) ===
USER_ENDESA = os.getenv("ENDESA_USER")
PASSWORD_ENDESA = os.getenv("ENDESA_PASS")

USER_ENEL = os.getenv("ENEL_USER")
PASSWORD_ENEL = os.getenv("ENEL_PASS")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# === 2. GOOGLE SERVICES (Desde .env) ===
# IDs de Google Drive/Sheets. Los dos IDs de carpeta apuntan a las
# carpetas raíz de PDFs de cada proveedor dentro de la carpeta principal
# del proyecto. El robot creará automáticamente subcarpetas AAAAMM para
# cada mes en el que se suben facturas, por lo que no hace falta
# pre‑crear ninguna carpeta adicional en Drive.
ID_SHEET_ENDESA = os.getenv("ID_SHEET_ENDESA")
ID_FOLDER_ENDESA_PDF = os.getenv("ID_FOLDER_ENDESA_PDF")

ID_SHEET_ENEL = os.getenv("ID_SHEET_ENEL")
ID_FOLDER_ENEL_PDF = os.getenv("ID_FOLDER_ENEL_PDF")

SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_PATH", "credentials.json")
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

# === 3. URLs ESTÁTICAS (No suelen cambiar) ===
URL_LOGIN_ENDESA = "https://endesa-atenea.my.site.com/miempresa/s/login/?language=es"
URL_LOGIN_ENEL = "https://zonaprivada.edistribucion.com/areaprivada/s/login/?language=es"
URL_FACTURAS_ENDESA = "https://endesa-atenea.my.site.com/miempresa/s/asistente-busqueda?tab=f"
URL_FACTURAS_ENEL = "https://zonaprivada.edistribucion.com/areaprivada/s/wp-billingchecking"

# === 4. CONFIGURACIÓN TÉCNICA ===
TABLE_LIMIT = 500
GRUPO_EMPRESARIAL = "GRUPO HERMANOS MARTIN"
MAX_LOGIN_ATTEMPTS = 5
MODEL = "gpt-4o"

# Modo sin cabeza (True para servidor, False para ver el navegador)
# El or evalúa a True si el .env dice "True"
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "True").lower() == "true"

# === 5. ESTRUCTURA DE ARCHIVOS Y RUTAS ===
TEMP_DOWNLOAD_ROOT = "temp_downloads"

# === 6. CONFIGURACIÓN GENERAL DEL SISTEMA ===
# Si REPROCESADO = True se ignorarán las marcas en el fichero de procesados
# y todas las facturas se volverán a procesar. Se puede cambiar via .env o
# directamente en el código antes del despliegue si se quiere "limpiar".
REPROCESADO = os.getenv("REPROCESADO", "False").lower() == "true"

DOWNLOAD_FOLDERS = {
    "CSV_ENDESA": os.path.join(TEMP_DOWNLOAD_ROOT, "endesa", "csv"),
    "CSV_ENEL": os.path.join(TEMP_DOWNLOAD_ROOT, "enel", "csv"),
    "PDF_ENDESA": os.path.join(TEMP_DOWNLOAD_ROOT, "endesa", "pdf"),
    "PDF_ENEL": os.path.join(TEMP_DOWNLOAD_ROOT, "enel", "pdf"),
    "XML_ENDESA": os.path.join(TEMP_DOWNLOAD_ROOT, "endesa", "xml"),
}

PROMPT_ENDESA_PATH = "prompts/prompt_endesa.txt"
PROMPT_ENEL_PATH = "prompts/prompt_enel.txt"

# === 6. RUTAS DE REGISTROS ===
# dentro de temp_downloads crearemos registros/endesa y registros/enel
REGISTRO_ROOT = os.path.join(TEMP_DOWNLOAD_ROOT, "registros")
REGISTRO_FOLDERS = {
    "endesa": os.path.join(REGISTRO_ROOT, "endesa"),
    "enel": os.path.join(REGISTRO_ROOT, "enel"),
}

# Asegurar que las carpetas existan al importar la configuración
for folder in DOWNLOAD_FOLDERS.values():
    os.makedirs(folder, exist_ok=True)
# también creamos las carpetas de registros
for folder in REGISTRO_FOLDERS.values():
    os.makedirs(folder, exist_ok=True)