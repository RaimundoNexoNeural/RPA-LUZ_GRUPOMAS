import os
from pathlib import Path
from dotenv import load_dotenv

# === 0. INICIALIZACIÓN DE ENTORNO ===
# Carga de variables de entorno desde el archivo .env
load_dotenv()

# === 1. CONFIGURACIÓN GENERAL DEL SISTEMA ===

# CFG.1 Control de flujo y entorno
# Determina si el robot debe procesar facturas que ya han sido registradas anteriormente
REPROCESADO = os.getenv("REPROCESADO", "False").lower() == "true"

# Define el entorno de ejecución (DESARROLLO, PRODUCCIÓN, etc.)
ENTORNO = os.getenv("ENTORNO", "DESARROLLO").upper()

# CFG.2 Parámetros del navegador (Playwright)
# Modo sin cabeza: True para ejecución en servidor (sin interfaz), False para visualizar el navegador
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "True").lower() == "true"

# Número máximo de reintentos de inicio de sesión antes de lanzar un error crítico
MAX_LOGIN_ATTEMPTS = 5


# === 2. CREDENCIALES Y SECRETOS (Desde .env) ===

# ACC.1 Portales de Energía
USER_ENDESA = os.getenv("ENDESA_USER")
PASSWORD_ENDESA = os.getenv("ENDESA_PASS")

USER_ENEL = os.getenv("ENEL_USER")
PASSWORD_ENEL = os.getenv("ENEL_PASS")

# ACC.2 Inteligencia Artificial (OpenAI)
# Clave de API para el procesamiento de OCR y extracción de datos mediante LLM
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Modelo específico de OpenAI a utilizar
MODEL = "gpt-4o"


# === 3. SERVICIOS DE COMUNICACIÓN (Email) ===

# MAIL.1 Mailchimp Transactional (Mandrill)
MAILCHIMP_API_KEY = os.getenv("MAILCHIMP_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL") 

# Lista de destinatarios que recibirán las facturas procesadas
DESTINATARIOS_FACTURAS = [
    addr.strip()
    for addr in os.getenv("DESTINATARIOS_FACTURAS", "").split(",")
    if addr.strip()
]

# MAIL.2 Configuración SMTP (Alertas de sistema)
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")


# === 4. GOOGLE SERVICES (Drive y Sheets) ===

# GGL.1 Identificadores de Endesa
ID_SHEET_ENDESA = os.getenv("ID_SHEET_ENDESA")
ID_FOLDER_ENDESA_PDF = os.getenv("ID_FOLDER_ENDESA_PDF")

# GGL.2 Identificadores de Enel
ID_SHEET_ENEL = os.getenv("ID_SHEET_ENEL")
ID_FOLDER_ENEL_PDF = os.getenv("ID_FOLDER_ENEL_PDF")

# GGL.3 Autenticación y Permisos
# Ruta al archivo de credenciales JSON de la cuenta de servicio
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_PATH", "credentials.json")
# Alcances necesarios para operar en Drive y Sheets
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]


# === 5. URLs Y PARÁMETROS DE BÚSQUEDA ===

# URL.1 Direcciones de acceso
URL_LOGIN_ENDESA = "https://endesa-atenea.my.site.com/miempresa/s/login/?language=es"
URL_LOGIN_ENEL = "https://zonaprivada.edistribucion.com/areaprivada/s/login/?language=es"

# URL.2 Direcciones de consulta de facturas
URL_FACTURAS_ENDESA = "https://endesa-atenea.my.site.com/miempresa/s/asistente-busqueda?tab=f"
URL_FACTURAS_ENEL = "https://zonaprivada.edistribucion.com/areaprivada/s/wp-billingchecking"

# URL.3 Configuración de filtros en los portales
# Límite de filas a cargar en la tabla de resultados del portal
TABLE_LIMIT = 500
# Nombre del grupo empresarial para filtrar la búsqueda
GRUPO_EMPRESARIAL = "GRUPO HERMANOS MARTIN"


# === 6. ESTRUCTURA DE ARCHIVOS Y RUTAS LOCALES ===

# PATH.1 Directorios raíz
TEMP_DOWNLOAD_ROOT = "temp_downloads"
REGISTRO_ROOT = os.path.join(TEMP_DOWNLOAD_ROOT, "registros")

# PATH.2 Carpetas de descarga por tipo de documento y portal
DOWNLOAD_FOLDERS = {
    "CSV_ENDESA": os.path.join(TEMP_DOWNLOAD_ROOT, "endesa", "csv"),
    "CSV_ENEL": os.path.join(TEMP_DOWNLOAD_ROOT, "enel", "csv"),
    "PDF_ENDESA": os.path.join(TEMP_DOWNLOAD_ROOT, "endesa", "pdf"),
    "PDF_ENEL": os.path.join(TEMP_DOWNLOAD_ROOT, "enel", "pdf"),
    "XML_ENDESA": os.path.join(TEMP_DOWNLOAD_ROOT, "endesa", "xml"),
}

# PATH.3 Historial de trazabilidad (Facturas ya procesadas/enviadas)
REGISTRO_FOLDERS_PROCESADAS = {
    "endesa": os.path.join(REGISTRO_ROOT, "endesa_procesadas"),
    "enel": os.path.join(REGISTRO_ROOT, "enel_procesadas"),
}
REGISTRO_FOLDERS_ENVIADAS = {
    "endesa": os.path.join(REGISTRO_ROOT, "endesa_enviadas"),
    "enel": os.path.join(REGISTRO_ROOT, "enel_enviadas"),
}

# PATH.4 Recursos para Inteligencia Artificial
PROMPT_ENDESA_PATH = "prompts/prompt_endesa.txt"
PROMPT_ENEL_PATH = "prompts/prompt_enel.txt"


# === 7. INICIALIZACIÓN DE DIRECTORIOS ===
# A. Garantizar la existencia de todas las carpetas de descarga necesarias
for folder in DOWNLOAD_FOLDERS.values():
    os.makedirs(folder, exist_ok=True)

# B. Garantizar la existencia de las carpetas de registro de trazabilidad
for folder in REGISTRO_FOLDERS_PROCESADAS.values():
    os.makedirs(folder, exist_ok=True)

for folder in REGISTRO_FOLDERS_ENVIADAS.values():
    os.makedirs(folder, exist_ok=True)