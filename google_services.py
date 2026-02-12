import os
import re
from fastapi import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from modelos_datos import FacturaEndesa, FacturaEnel
from config import ID_SHEET_ENDESA, ID_FOLDER_ENDESA_PDF, ID_SHEET_ENEL, ID_FOLDER_ENEL_PDF, SERVICE_ACCOUNT_FILE, SCOPES

class GoogleServiceManager:
    def __init__(self, spreadsheet_id):
        self.creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        self.drive = build('drive', 'v3', credentials=self.creds)
        self.sheets = build('sheets', 'v4', credentials=self.creds)
        self.spreadsheet_id = spreadsheet_id
        
        self.cabecera_fija = [
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
            "VENCIMIENTO DEL ACUERDO"
        ]

    def _aplicar_formato_hoja(self, sheet_id, tipo_robot):
        """Aplica estilos de cabecera (colores por parseo), anchos de columna y recorte."""
        
        # Definición de índices de columnas parseadas (Listados proporcionados)
        if tipo_robot == "ENDESA":
            # Columnas indicadas: A,B,D,E, F, H-M, N, O, P-U, V, Y, AA, AB, AC, AD, AG, AH, AN, AQ, AR, AS
            # Índices (letra - 1): 4, 5, 7-12, 13, 14, 15-20, 21, 24, 26, 27, 28, 29, 32, 33, 39, 42, 43, 44
            cols_parseadas = {0, 1, 3 ,4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 24, 26, 27, 28, 29, 32, 33, 39, 42, 43, 44}
        else: # ENEL
            # Columnas indicadas: A, D, E, F, H-M, N, O, Z, AB, AC, AD, AG, AH
            # Índices: 0, 3, 4, 5, 7-12, 13, 14, 25, 27, 28, 29, 32, 33
            cols_parseadas = {0, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 25, 27, 28, 29, 32, 33}

        requests = []
        
        # 1. Aplicar color a la cabecera celda por celda
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

        # 2. Configuración de Anchos de Columna
        anchos_200 = [0, 3, 4, 6, 14, 15, 16, 17, 18, 19, 20, 39, 40, 42, 43, 44, 45] # G, O, P, Q, R, A, T, U, AN, AO, AQ, AR, AS, AT
        anchos_250 = [24, 27, 28, 29, 30, 32, 33, 34, 35, 36, 37, 38, 46] # Y, AB..AM, AP, AU
        anchos_300 = [31]
        anchos_400 = [5, 41]
        
        for col_idx in anchos_200:
            requests.append({"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": col_idx, "endIndex": col_idx + 1}, "properties": {"pixelSize": 200}, "fields": "pixelSize"}})
        
        for col_idx in anchos_250:
            requests.append({"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": col_idx, "endIndex": col_idx + 1}, "properties": {"pixelSize": 250}, "fields": "pixelSize"}})

        for col_idx in anchos_300:
            requests.append({"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": col_idx, "endIndex": col_idx + 1}, "properties": {"pixelSize": 300}, "fields": "pixelSize"}})
        
        for col_idx in anchos_400:
            requests.append({"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": col_idx, "endIndex": col_idx + 1}, "properties": {"pixelSize": 400}, "fields": "pixelSize"}})


        # 3. Forzar Texto Recortado (CLIP) en toda la fila de datos
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1000},
                "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP"}},
                "fields": "userEnteredFormat.wrapStrategy"
            }
        })

        self.sheets.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body={"requests": requests}).execute()

    def _aplicar_formato_datos(self, sheet_id, fila_index):
        """Aplica formato de moneda, fecha y unidades a las celdas de la fila recién insertada."""
        
        
        cols_moneda = [7, 8, 9, 10, 11, 12, 14, 24,26,27,28,29,32,33,39,42]
        
        
        cols_fecha = [43,44]
        
        
        cols_kwh = [15,16,17,18,19,20,21]

        requests = []

        # 1. Formato Moneda (€) - Pattern: #,##0.00 " €"
        for col in cols_moneda:
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id, 
                        "startRowIndex": fila_index - 1, "endRowIndex": fila_index, 
                        "startColumnIndex": col, "endColumnIndex": col + 1
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "CURRENCY", "pattern": "#,##0.00\" €\""}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat"
                }
            })

        # 2. Formato Fecha - Pattern: dd/mm/yyyy
        for col in cols_fecha:
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id, 
                        "startRowIndex": fila_index - 1, "endRowIndex": fila_index, 
                        "startColumnIndex": col, "endColumnIndex": col + 1
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "DATE", "pattern": "dd/mm/yyyy"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat"
                }
            })

        # 3. Formato kWh - Pattern: #,##0 " kWh"
        for col in cols_kwh:
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id, 
                        "startRowIndex": fila_index - 1, "endRowIndex": fila_index, 
                        "startColumnIndex": col, "endColumnIndex": col + 1
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "NUMBER", "pattern": "#,##0\" kWh\""}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat"
                }
            })

        if requests:
            self.sheets.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id, 
                body={"requests": requests}
            ).execute()


    def _colorear_fila_datos(self, sheet_id, fila_index, datos_fila):
        """Pinta de blanco humo las celdas con datos reales."""
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

    def asegurar_hoja_cups(self, cup: str, tipo_robot):
        spreadsheet = self.sheets.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        hojas = {s['properties']['title']: s['properties']['sheetId'] for s in spreadsheet.get('sheets', [])}

        if cup not in hojas:
            body = {'requests': [{'addSheet': {'properties': {'title': cup}}}]}
            res = self.sheets.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body=body).execute()
            sheet_id = res['replies'][0]['addSheet']['properties']['sheetId']
            
            self.sheets.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id, range=f"'{cup}'!A1",
                valueInputOption="RAW", body={'values': [self.cabecera_fija]}).execute()
            
            self._aplicar_formato_hoja(sheet_id, tipo_robot)
            return sheet_id
        return hojas[cup]

    def upsert_factura(self, cup, numero_factura, datos, tipo_robot):
        sheet_id = self.asegurar_hoja_cups(cup, tipo_robot)
        res = self.sheets.spreadsheets().values().get(spreadsheetId=self.spreadsheet_id, range=f"'{cup}'!E:E").execute()
        valores_e = res.get('values', [])
        
        fila_index = -1
        for i, fila in enumerate(valores_e):
            if fila and fila[0] == numero_factura:
                fila_index = i + 1
                break
        
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

        self._colorear_fila_datos(sheet_id, fila_index, datos)
        self._aplicar_formato_datos(sheet_id, fila_index)

    def subir_pdf(self, folder_id, ruta_local):
        if not ruta_local or not os.path.exists(ruta_local): return
        nombre = os.path.basename(ruta_local)
        query = f"name = '{nombre}' and '{folder_id}' in parents and trashed = false"
        res = self.drive.files().list(q=query, spaces='drive', supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        media = MediaFileUpload(ruta_local, mimetype='application/pdf', resumable=True)
        if res.get('files'):
            self.drive.files().update(fileId=res['files'][0]['id'], media_body=media, supportsAllDrives=True).execute()
        else:
            meta = {'name': nombre, 'parents': [folder_id]}
            self.drive.files().create(body=meta, media_body=media, supportsAllDrives=True).execute()

# --- FUNCIONES DE ACCESO ---

def registrar_factura_google_endesa(factura: FacturaEndesa, ruta_pdf: str = None):
    mgr = GoogleServiceManager(ID_SHEET_ENDESA)
    f = [None] * len(mgr.cabecera_fija)
    # Mapeo idéntico al anterior...
    f[0], f[1], f[3], f[4], f[5] = factura.mes_facturado, factura.tarifa, factura.cup, factura.numero_factura, factura.direccion_suministro
    f[7:13] = [factura.potencia_p1, factura.potencia_p2, factura.potencia_p3, factura.potencia_p4, factura.potencia_p5, factura.potencia_p6]
    f[13], f[14] = factura.num_dias, factura.importe_de_potencia
    f[15:21] = [factura.consumo_kw_p1, factura.consumo_kw_p2, factura.consumo_kw_p3, factura.consumo_kw_p4, factura.consumo_kw_p5, factura.consumo_kw_p6]
    f[21], f[24], f[26], f[27], f[28], f[29] = factura.kw_totales, factura.importe_consumo, factura.importe_bono_social, factura.importe_impuesto_electrico, factura.importe_alquiler_equipos, factura.importe_otros_conceptos
    f[32], f[33], f[39], f[42], f[43], f[44] = factura.importe_exceso_potencia, factura.importe_reactiva, factura.importe_base_imponible, factura.importe_facturado, factura.fecha_de_factura, factura.fecha_de_vencimiento
    
    mgr.upsert_factura(factura.cup, factura.numero_factura, f, "ENDESA")
    if ruta_pdf: mgr.subir_pdf(ID_FOLDER_ENDESA_PDF, ruta_pdf)

def registrar_factura_google_enel(factura: FacturaEnel, ruta_pdf: str = None):
    mgr = GoogleServiceManager(ID_SHEET_ENEL)
    f = [None] * len(mgr.cabecera_fija)
    # Mapeo idéntico al anterior...
    f[0], f[3], f[4], f[5] = factura.mes_facturado, factura.cup, factura.numero_factura, factura.direccion_suministro
    f[7:13] = [factura.potencia_p1, factura.potencia_p2, factura.potencia_p3, factura.potencia_p4, factura.potencia_p5, factura.potencia_p6]
    f[13], f[14], f[25], f[27], f[28], f[29], f[32], f[33] = factura.num_dias, factura.importe_de_potencia, factura.importe_atr, factura.importe_impuesto_electrico, factura.importe_alquiler_equipos, factura.importe_otros_conceptos, factura.importe_exceso_potencia, factura.importe_reactiva
    
    mgr.upsert_factura(factura.cup, factura.numero_factura, f, "ENEL")
    if ruta_pdf: mgr.subir_pdf(ID_FOLDER_ENEL_PDF, ruta_pdf)