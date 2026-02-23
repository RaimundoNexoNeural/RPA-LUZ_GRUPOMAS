import os
import re
from fastapi import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from modelos_datos import FacturaEndesa, FacturaEnel
from config import ID_SHEET_ENDESA, ID_FOLDER_ENDESA_PDF, ID_SHEET_ENEL, ID_FOLDER_ENEL_PDF, SERVICE_ACCOUNT_FILE, SCOPES

# === 1. GESTIÓN DE SERVICIOS DE GOOGLE (DRIVE & SHEETS) === 

class GoogleServiceManager:
    '''
    Clase que encapsula la lógica de interacción con Google Drive y Google Sheets.
    Gestiona la autenticación, subida de archivos y actualización de datos en hojas de cálculo.
    '''

    # GGL.1 Inicialización del gestor de servicios
    def __init__(self, spreadsheet_id):
        '''
        Configura las credenciales y construye los servicios de API necesarios.
        Parametros:
            - spreadsheet_id (str): ID de la hoja de cálculo de Google Sheets a gestionar.
        '''
        # A. Configuración de credenciales de cuenta de servicio
        self.creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        
        # B. Construcción de servicios de API
        self.drive = build('drive', 'v3', credentials=self.creds)
        self.sheets = build('sheets', 'v4', credentials=self.creds)
        self.spreadsheet_id = spreadsheet_id
        
        # C. Definición de la estructura de cabecera estándar para el reporte
        self.cabecera_fija = [
            "PROCESADA","ENVIADA", "AÑO",
            "MES FACTURADO", "TARIFA", "PG", "CUP", "NUMERO DE FACTURA", "DIRECCIÓN SUMINISTRO", 
            "TIPO DE TIENDA", "POTENCIA P1", "POTENCIA P2", "POTENCIA P3", "POTENCIA P4", 
            "POTENCIA P5", "POTENCIA P6", "Nº DÍAS", "IMPORTE POTENCIA", "CONSUMO KW P1", 
            "CONSUMO KW P2", "CONSUMO KW P3", "CONSUMO KW P4", "CONSUMO KW P5", "CONSUMO KW P6", 
            "KW TOTALES", "KW CURVA", "KW GESTINEL", "IMPORTE CONSUMO", "IMPORTE ATR", "BONO SOCIAL", 
            "IMPUESTO ELECTRICO", "ALQUILER DE EQUIPOS", "OTROS CONCEPTOS", "IMPORTE POTENCIA CONTRATADA", 
            "DIFERENCIA POTENCIA CONTRATADA Y FACTURADA", "EXCESO DE POTENCIA", "IMPORTE DE REACTIVA", 
            "PRECIO MEDIO", "PRECIO CALCULADO", "DIFERENCIA DE PRECIO", "IMPUESTO ELECTRICO CALCULADO", 
            "DIFERENCIA DE IE", "BASE IMPONIBLE", "IMPORTE TOTAL CALCULADO", 
            "DIFERENCIA ENTRE IMPORTE TOTAL Y BASE IMPONIBLE", "IMPORTE FACTURADO", "FECHA DE FACTURA", 
            "FECHA DE VENCIMIENTO", "FECHA DE PAGO EN BANCO", "FECHA DE DEVOLUCIÓN", "ACUERDO", 
            "VENCIMIENTO DEL ACUERDO","ERROR"
        ]

    # GGL.2 Aplicación de formato visual a la hoja
    def _aplicar_formato_hoja(self, sheet_id, tipo_robot):
        '''
        Aplica estilos de cabecera (colores), anchos de columna, recorte de texto y validaciones de datos.
        Parametros:
            - sheet_id (int): ID interno de la pestaña de la hoja.
            - tipo_robot (str): Tipo de robot ejecutado ("ENDESA" o "ENEL").
        '''
        
        # A. Definición de índices de columnas que provienen del parseo automático
        if tipo_robot == "ENDESA":
            cols_parseadas = {0, 1, 2, 3, 4, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 27, 29, 30, 31, 32, 35, 36, 42, 54, 46, 47, 52} 
        else: # ENEL
            cols_parseadas = {0, 1 ,2, 3, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 28, 30, 31, 32, 35, 36, 52}

        requests = []
        
        # B. Aplicación de color y negrita a la fila de cabecera
        for i in range(len(self.cabecera_fija)):
            color = {"red": 0.75, "green": 0.75, "blue": 0.75} if i in cols_parseadas else {"red": 0.88, "green": 0.88, "blue": 0.88}
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": i, "endColumnIndex": i + 1},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": color,
                            "textFormat": {"bold": True}
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)"
                }
            })

        # C. Configuración de dimensiones (Anchos de Columna)
        anchos_config = [
            (200, [3, 6, 7, 9, 17, 18, 19, 20, 21, 22, 23, 42, 43, 45, 46, 47, 48, 49, 50]),
            (250, [24, 27, 28, 29, 30, 32, 33, 34, 35, 36, 37, 38, 46]),
            (300, [34]),
            (400, [8, 44, 52])
        ]
        
        for pixel_size, cols in anchos_config:
            for col_idx in cols:
                requests.append({"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": col_idx, "endIndex": col_idx + 1}, "properties": {"pixelSize": pixel_size}, "fields": "pixelSize"}})

        # D. Configuración de estrategia de ajuste de texto (CLIP)
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1000},
                "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP"}},
                "fields": "userEnteredFormat.wrapStrategy"
            }
        })

        # E. Inserción de casillas de verificación (Checkboxes) para estado de proceso y envío
        for col in (0, 1):
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 1000, "startColumnIndex": col, "endColumnIndex": col + 1},
                    "cell": {
                        "dataValidation": {
                            "condition": {"type": "BOOLEAN"},
                            "showCustomUi": True
                        }
                    },
                    "fields": "dataValidation"
                }
            })

        # F. Ejecución de la actualización por lotes
        self.sheets.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body={"requests": requests}).execute()

    # GGL.3 Aplicación de formato a datos numéricos y fechas
    def _aplicar_formato_datos(self, sheet_id, fila_index):
        '''
        Aplica formatos de moneda, fecha y unidades a las celdas de una fila recién insertada.
        Parametros:
            - sheet_id (int): ID de la pestaña.
            - fila_index (int): Índice de la fila a formatear.
        '''
        # A. Definición de grupos de columnas por tipo de formato
        cols_moneda = [10, 11, 12, 13, 13, 15, 17, 27, 29, 30, 31, 32, 35, 36, 42, 45]
        cols_fecha = [46, 47]
        cols_kwh = [18, 19, 20, 21, 22, 23, 24]

        requests = []

        # B. Formato Moneda (€)
        for col in cols_moneda:
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": fila_index - 1, "endRowIndex": fila_index, "startColumnIndex": col, "endColumnIndex": col + 1},
                    "cell": {"userEnteredFormat": {"numberFormat": {"type": "CURRENCY", "pattern": "#,##0.00\" €\""}}},
                    "fields": "userEnteredFormat.numberFormat"
                }
            })

        # C. Formato Fecha (dd/mm/yyyy)
        for col in cols_fecha:
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": fila_index - 1, "endRowIndex": fila_index, "startColumnIndex": col, "endColumnIndex": col + 1},
                    "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "dd/mm/yyyy"}}},
                    "fields": "userEnteredFormat.numberFormat"
                }
            })

        # D. Formato Unidades Eléctricas (kWh)
        for col in cols_kwh:
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": fila_index - 1, "endRowIndex": fila_index, "startColumnIndex": col, "endColumnIndex": col + 1},
                    "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0\" kWh\""}}},
                    "fields": "userEnteredFormat.numberFormat"
                }
            })

        # E. Ejecución de la actualización
        if requests:
            self.sheets.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body={"requests": requests}).execute()

    # GGL.4 Resaltado de celdas con datos
    def _colorear_fila_datos(self, sheet_id, fila_index, datos_fila):
        '''
        Resalta con un color de fondo tenue las celdas que contienen información real (no vacía o por defecto).
        Parametros:
            - sheet_id (int): ID de la pestaña.
            - fila_index (int): Índice de la fila.
            - datos_fila (list): Lista de valores de la fila.
        '''
        requests = []
        for i, valor in enumerate(datos_fila):
            if valor not in [None, "", "N/A", 0.0]:
                requests.append({
                    "updateCells": {
                        "range": {"sheetId": sheet_id, "startRowIndex": fila_index - 1, "endRowIndex": fila_index, "startColumnIndex": i, "endColumnIndex": i + 1},
                        "rows": [{"values": [{"userEnteredFormat": {"backgroundColor": {"red": 0.96, "green": 0.96, "blue": 0.96}}}]}],
                        "fields": "userEnteredFormat.backgroundColor"
                    }
                })
        if requests:
            self.sheets.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body={"requests": requests}).execute()

    # GGL.5 Gestión de pestañas por CUP
    def asegurar_hoja_cups(self, cup: str, tipo_robot):
        '''
        Garantiza que existe una pestaña con el nombre del CUP; si no, la crea e inicializa.
        Parametros:
            - cup (str): Nombre del CUP que servirá como título de la pestaña.
            - tipo_robot (str): Origen de datos para el formato inicial.
        Retorna
            - int: ID de la pestaña (existente o nueva).
        '''
        # A. Obtención del listado de hojas actuales
        spreadsheet = self.sheets.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        hojas = {s['properties']['title']: s['properties']['sheetId'] for s in spreadsheet.get('sheets', [])}

        # B. Creación e inicialización si el CUP es nuevo
        if cup not in hojas:
            body = {'requests': [{'addSheet': {'properties': {'title': cup}}}]}
            res = self.sheets.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body=body).execute()
            sheet_id = res['replies'][0]['addSheet']['properties']['sheetId']
            
            # B.1. Inserción de cabecera fija
            self.sheets.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id, range=f"'{cup}'!A1",
                valueInputOption="RAW", body={'values': [self.cabecera_fija]}).execute()
            
            # B.2. Aplicación de formato global a la nueva pestaña
            self._aplicar_formato_hoja(sheet_id, tipo_robot)
            return sheet_id
            
        return hojas[cup]

    # GGL.6 Inserción o actualización de facturas (Upsert)
    def upsert_factura(self, cup, numero_factura, datos, tipo_robot):
        '''
        Busca si una factura ya existe en la hoja del CUP para actualizarla o añadirla al final.
        Parametros:
            - cup (str): Identificador de la pestaña.
            - numero_factura (str): Clave de búsqueda en la columna de facturas.
            - datos (list): Valores a insertar.
            - tipo_robot (str): Origen de los datos.
        '''
        # A. Asegurar pestaña y obtener listado de números de factura
        sheet_id = self.asegurar_hoja_cups(cup, tipo_robot)
        res = self.sheets.spreadsheets().values().get(spreadsheetId=self.spreadsheet_id, range=f"'{cup}'!H:H").execute()
        valores_e = res.get('values', [])
        
        # B. Localización de fila por coincidencia de número de factura
        fila_index = -1
        for i, fila in enumerate(valores_e):
            if fila and fila[0] == numero_factura:
                fila_index = i + 1
                break
        
        # C. Ejecución de actualización (Update) o adición (Append)
        if fila_index != -1:
            self.sheets.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id, range=f"'{cup}'!A{fila_index}",
                valueInputOption="USER_ENTERED", body={'values': [datos]}).execute()
        else:
            res_append = self.sheets.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id, range=f"'{cup}'!A1",
                valueInputOption="USER_ENTERED", body={'values': [datos]}).execute()
            rango = res_append.get('updates', {}).get('updatedRange', "")
            match = re.search(r'A(\d+)', rango.split('!')[-1])
            fila_index = int(match.group(1)) if match else 1

        # D. Post-procesamiento visual de la fila
        self._colorear_fila_datos(sheet_id, fila_index, datos)
        self._aplicar_formato_datos(sheet_id, fila_index)

    # GGL.7 Navegación y creación de carpetas en Drive
    def _get_or_create_folder(self, parent_id: str, folder_name: str) -> str:
        '''
        Verifica la existencia de una subcarpeta y la crea en caso negativo.
        Parametros:
            - parent_id (str): ID de la carpeta contenedora.
            - folder_name (str): Nombre de la carpeta a buscar/crear.
        Retorna
            - str: ID de la carpeta en Google Drive.
        '''
        # A. Búsqueda de carpeta existente
        query = (
            f"name = '{folder_name}' and '{parent_id}' in parents "
            "and mimeType = 'application/vnd.google-apps.folder' "
            "and trashed = false"
        )
        res = self.drive.files().list(q=query, spaces='drive', supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        files = res.get('files', [])
        
        if files:
            return files[0]['id']
            
        # B. Creación si no se encontró coincidencia
        meta = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
        created = self.drive.files().create(body=meta, supportsAllDrives=True).execute()
        return created.get('id')

    # GGL.8 Subida de archivos PDF a Drive
    def subir_pdf(self, folder_id, ruta_local):
        '''
        Sube un archivo PDF local a Drive, organizándolo en subcarpetas por mes (AAAAMM).
        Parametros:
            - folder_id (str): ID de la carpeta raíz en Drive.
            - ruta_local (str): Ruta al archivo en el sistema de archivos local.
        '''
        # A. Validaciones iniciales
        if not ruta_local or not os.path.exists(ruta_local):
            return

        nombre = os.path.basename(ruta_local)

        # B. Determinación de subcarpeta mensual basada en el prefijo del nombre (AAAAMM)
        mes_folder = None
        m = re.match(r"^(\d{6})", nombre)
        if m:
            mes_folder = m.group(1)

        if mes_folder:
            try:
                folder_id = self._get_or_create_folder(folder_id, mes_folder)
            except Exception:
                pass

        # C. Verificación de existencia del archivo para decidir entre subida nueva o actualización
        query = f"name = '{nombre}' and '{folder_id}' in parents and trashed = false"
        res = self.drive.files().list(q=query, spaces='drive', supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        media = MediaFileUpload(ruta_local, mimetype='application/pdf', resumable=True)
        
        if res.get('files'):
            self.drive.files().update(fileId=res['files'][0]['id'], media_body=media, supportsAllDrives=True).execute()
        else:
            meta = {'name': nombre, 'parents': [folder_id]}
            self.drive.files().create(body=meta, media_body=media, supportsAllDrives=True).execute()


# === 2. FUNCIONES DE ACCESO PÚBLICO (WRAPPERS) === 

# PUB.1 Registro de facturas para portal Endesa
def registrar_factura_google_endesa(factura: FacturaEndesa, ruta_pdf: str = None):
    '''
    Prepara el mapeo de datos y ejecuta la subida para facturas del portal Endesa.
    Parametros:
        - factura (FacturaEndesa): Objeto con los datos extraídos.
        - ruta_pdf (str): Ruta local del PDF asociado.
    '''
    # A. Inicialización del gestor y preparación de fila
    mgr = GoogleServiceManager(ID_SHEET_ENDESA)
    f = [None] * len(mgr.cabecera_fija)
    
    # B. Mapeo exhaustivo de campos de FacturaEndesa a la cabecera fija de Sheets
    f[0], f[1], f[2] = factura.procesada, factura.enviada, factura.anno_facturado
    f[3], f[4], f[6], f[7], f[8] = factura.mes_facturado, factura.tarifa, factura.cup, factura.numero_factura, factura.direccion_suministro
    f[10:16] = [factura.potencia_p1, factura.potencia_p2, factura.potencia_p3, factura.potencia_p4, factura.potencia_p5, factura.potencia_p6]
    f[16], f[17] = factura.num_dias, factura.importe_de_potencia
    f[18:24] = [factura.consumo_kw_p1, factura.consumo_kw_p2, factura.consumo_kw_p3, factura.consumo_kw_p4, factura.consumo_kw_p5, factura.consumo_kw_p6]
    f[24], f[27], f[29], f[30], f[31], f[32] = factura.kw_totales, factura.importe_consumo, factura.importe_bono_social, factura.importe_impuesto_electrico, factura.importe_alquiler_equipos, factura.importe_otros_conceptos
    f[35], f[36], f[41], f[45], f[46], f[47] = factura.importe_exceso_potencia, factura.importe_reactiva, factura.importe_base_imponible, factura.importe_facturado, factura.fecha_de_factura, factura.fecha_de_vencimiento
    f[52] = factura.msg_error_RPA

    # C. Ejecución de guardado de datos y subida de archivo
    mgr.upsert_factura(factura.cup, factura.numero_factura, f, "ENDESA")
    if ruta_pdf: 
        mgr.subir_pdf(ID_FOLDER_ENDESA_PDF, ruta_pdf)


# PUB.2 Registro de facturas para portal Enel
def registrar_factura_google_enel(factura: FacturaEnel, ruta_pdf: str = None):
    '''
    Prepara el mapeo de datos y ejecuta la subida para facturas del portal Enel.
    Parametros:
        - factura (FacturaEnel): Objeto con los datos extraídos.
        - ruta_pdf (str): Ruta local del PDF asociado.
    '''
    # A. Inicialización y preparación
    mgr = GoogleServiceManager(ID_SHEET_ENEL)
    f = [None] * len(mgr.cabecera_fija)
    
    # B. Mapeo específico de campos de FacturaEnel (Distribución) a Sheets
    f[0], f[1], f[2] = factura.procesada, factura.enviada, factura.anno_facturado
    f[3], f[6], f[7], f[8] = factura.mes_facturado, factura.cup, factura.numero_factura, factura.direccion_suministro
    f[10:16] = [factura.potencia_p1, factura.potencia_p2, factura.potencia_p3, factura.potencia_p4, factura.potencia_p5, factura.potencia_p6]
    f[16], f[17], f[28], f[30], f[31], f[32], f[35], f[36] = factura.num_dias, factura.importe_de_potencia, factura.importe_atr, factura.importe_impuesto_electrico, factura.importe_alquiler_equipos, factura.importe_otros_conceptos, factura.importe_exceso_potencia, factura.importe_reactiva
    f[52] = factura.msg_error_RPA

    # C. Ejecución de guardado y subida
    mgr.upsert_factura(factura.cup, factura.numero_factura, f, "ENEL")
    if ruta_pdf: 
        mgr.subir_pdf(ID_FOLDER_ENEL_PDF, ruta_pdf)