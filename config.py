import os

# ===0. DEFINICION DE CONSTANTES ===

    # A. URLs
        # URLs de Login
URL_LOGIN_ENDESA =  "https://endesa-atenea.my.site.com/miempresa/s/login/?language=es" 
URL_LOGIN_ENEL = "https://zonaprivada.edistribucion.com/areaprivada/s/login/?language=es"
        # URLs de Facturas
URL_FACTURAS_ENDESA = "https://endesa-atenea.my.site.com/miempresa/s/asistente-busqueda?tab=f"
URL_FACTURAS_ENEL = "https://zonaprivada.edistribucion.com/areaprivada/s/wp-billingchecking"


    # B. Credenciales (Variables de Entorno)
        # Usuarios
USER_ENDESA = os.getenv("ENDESA_USER_ENDESA", "pfombellav@somosgrupomas.com")
USER_ENEL = os.getenv("ENDESA_USER_ENEL", "27298340P")
        # Contraseñas
PASSWORD_ENDESA = os.getenv("ENDESA_PASSWORD_ENDESA", "Guillena2024*")
PASSWORD_ENEL = os.getenv("ENDESA_PASSWORD_ENEL", "z5!tWZWzTDQ6rx9")


    # C. Configuración de Procesamiento de Datos Endesa
TABLE_LIMIT = 500
GRUPO_EMPRESARIAL = "GRUPO HERMANOS MARTIN"


    # D. Configuración del Navegador
TEMP_DOWNLOAD_ROOT = "temp_downloads" 
HEADLESS_MODE = False


    # E. Archivos Temporales
DOWNLOAD_FOLDERS = {
    "CSV_ENDESA": os.path.join(TEMP_DOWNLOAD_ROOT, "endesa", "csv"),
    "CSV_ENEL": os.path.join(TEMP_DOWNLOAD_ROOT, "enel", "csv"),
    "PDF_ENDESA": os.path.join(TEMP_DOWNLOAD_ROOT, "endesa", "pdf"),
    "PDF_ENEL": os.path.join(TEMP_DOWNLOAD_ROOT, "enel", "pdf"),
    "XML_ENDESA": os.path.join(TEMP_DOWNLOAD_ROOT, "endesa", "xml"),
}

    # F Prompts y modelos para OCR
PROMPT_ENDESA_PATH = "prompts/prompt_endesa.txt"
PROMPT_ENEL_PATH = "prompts/prompt_enel.txt"
MODEL = "gpt-4o"

    # F. Numero Máximo de Intentos de Inicio de Sesión
MAX_LOGIN_ATTEMPTS = 5

    # G. Configuración de Google Services
ID_SHEET_ENDESA = '1S86D8puK1IQEDyamEVAeprr4jSyprPMb9__saIzSmJk'
ID_FOLDER_ENDESA_PDF = '1SKEEQhMOeoMOozcGB2rUaHru0po1MtiA'

ID_SHEET_ENEL = '1fTHymm8Sfn-Pa_YwEQPHec45cJoG0z0zC33tfqhmV9E'
ID_FOLDER_ENEL_PDF = '1lSbFfyqCSDieCzZ3Bv7iTEk56uPExxj_'

SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
