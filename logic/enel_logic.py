import re
import os
from datetime import datetime
import asyncio
from playwright.async_api import Page, TimeoutError, Locator
from modelos_datos import FacturaEnel
from logs import escribir_log
from config import DOWNLOAD_FOLDERS, URL_FACTURAS_ENEL
from parsers.pdf_parser_enel import procesar_pdf_local_enel
from parsers.exportar_datos import insertar_factura_en_csv


# === FUNCIONES AUXILIARES PARA CARGA Y PROCESADO DE DATOS DE ENDESA CLIENTE  === #

# AUX.1.Conversión de importes (str) a float
def _clean_and_convert_float(text: str) -> float:
    """
    Limpia importes complejos como '-631.04€ / 0€'.
        1. Toma la parte antes de la barra.
        2. Captura el signo negativo y los números.
        3. Maneja correctamente los separadores decimales.
    Parametros:
        text (str): Importe con formato -631.04€ / 0€
    Retorna:
        float: El valor numérico del importe
    """
    try:
        
        parte_interesante = text.split('/')[0].strip()
        match = re.search(r'(-?[\d\.,]+)', parte_interesante)
        if not match:
            return 0.0
        val_str = match.group(1)
        if ',' in val_str and '.' in val_str:
            val_str = val_str.replace('.', '').replace(',', '.')
        elif ',' in val_str:
            val_str = val_str.replace(',', '.')
        
        return float(val_str)
    
    except Exception as e:
        escribir_log(f"Error al convertir importe '{text}': {e}")
        return 0.0
    

# AUX.2.Descarga de archivos mediante botenes de la tabla de resultados
async def _descargar_archivo_fila(page: Page, row_locator: Locator, factura: FacturaEnel) -> str | None:
    """
    Intenta descargar el archivo PDF haciendo clic en el botón de la fila, y guardándolo localmente.
    Parametros:
        - page (Page): Pagina web del navegador
        - row (Locator): Localizador web de la fila de la que se quiere descargar los archivos
        - factura (FacturaEnel): Objeto del tipo Factura al que se le asocia dicho archivo
    Retorna:
        - str: Ruta local del archivo descargado si se ha descargado correctamente
        - None: Si no se ha podido descargar el archivo (ej. no existe botón PDF)
    """
    
    # A. Localizamos el botón PDF dentro de la fila iterada
    button_locator = row_locator.locator('button[name="PDF"]')

    if await button_locator.count() == 0:
        return None

    # B. Definimos la ruta donde se descargará el archivo
    target_folder = DOWNLOAD_FOLDERS["PDF_ENEL"]
    fecha = datetime.strptime(factura.fecha_emision, "%d/%m/%Y")
    mes = fecha.strftime("%m")
    anio = fecha.strftime("%Y")

    filename = f"{anio}{mes}_{factura.cup}_{factura.numero_factura}_ENEL.pdf" 
    save_path = os.path.join(target_folder, filename)

    # C. Proceso de descarga
    try:
        # C.1. Pulsamos el boton
        async with page.expect_download(timeout=20000) as download_info:
            await button_locator.click(timeout=20000)
        # C.2. Leemos los valores del archivo descargado en el navegador
        download = await download_info.value
        # C.3. Guardamos localmente el archivo
        await download.save_as(save_path)
        
    # D. Si se ha descargado correctamente, informamos y devolvemos la ruta del archivo descargado
        escribir_log(f"    -> [OK] [DESCARGA PDF] Guardado en: {save_path}")
        return save_path
    
    # E. En caso de error en la descarga informamos
    except TimeoutError:
        factura.error_RPA = True
        factura.msg_error_RPA += f"ERROR_DESCARGA: No se ha podido descargar el archivo PDF asociado a esta factura."
        return None
        
    except Exception as e:
        factura.error_RPA = True
        factura.msg_error_RPA += f"ERROR_DESCARGA: Fallo inesperado al descargar el archivo PDF asociado a esta factura. Detalles: {str(e)}"
        return None
    



# === FUNCIONES PARA LECTURA Y EXTRACCION DE DATOS  === #

# DATA.1 Extraccion y procesado de los datos copletos de una fila de la tabla de resultados
async def _extraer_datos_fila_enel(page: Page, row: Locator) -> FacturaEnel | None:
    '''
    Para una fila de la tabla de resultados, extrae los datos completos directos de la fila, 
    llama a la funcion de descarga del archivo PDF de la fila,
    llama a la funcion de parseo y procesado de los archivos PDF extrayendo los datos de las facturas,
    y crea y devuelve un objeto de la clase Factura con todos los datos actualizados.
    Parametros:
        - page (Page): Pagina web del navegador
        - row (Locator): Localizador web de la fila de la que se quiere procesar
    Retorna:
        - FacturaEnel: Factura con todos los datos extraidos durante el procesado de la fila y los archivos
        - None: Unicamente si ni si quiera ha podido extrear los datos de la fila.
    '''
    try:
    # A. Extracción de datos de las celdas de la fila y creación del objeto Factura

        # A.1. Extracción de datos de la fila
        cups_val = (await row.locator('th[data-label="CUPS"]').inner_text()).strip()
        f_fiscal = (await row.locator('td[data-label="FACTURA FISCAL"]').inner_text()).strip()
        fecha_em = (await row.locator('td[data-label="FECHA"]').inner_text()).strip()
        imp_raw = await row.locator('td[data-label="TOTAL/PDTE"]').inner_text()
        est = (await row.locator('td[data-label="Estado"]').inner_text()).strip()
        tipo_f = (await row.locator('td[data-label="Tipo"]').inner_text()).strip()

        factura = FacturaEnel(
            cup = cups_val,
            numero_factura = f_fiscal,
            fecha_emision = fecha_em,
            importe_total = _clean_and_convert_float(imp_raw),
            estado_factura = est,
            tipo_factura = tipo_f,
            descarga_selector = f_fiscal
            )
        
        escribir_log(f"    [OK] Datos extraídos correctamente de la fila de la tabla: {factura.numero_factura}")

    # B. Validación de importe positivo (Requisito de negocio)
            
        if factura.importe_total < 0:
            factura.error_RPA = True
            factura.msg_error_RPA = "IMPORTE_NEGATIVO: El importe total de la factura es negativo, por lo que no se procesará su PDF."
            escribir_log(f"    [!] Importe total negativo para la factura {factura.numero_factura} ({factura.importe_total} €). No se procesará el PDF de esta factura.")
            return factura
    
    # C. Descarga de archivo PDF 
        pdf_path = await _descargar_archivo_fila(page, row, factura)
           
    # D. Procesado del archivo PDF descargado, extracción de datos adicionales y actualizacion de objeto Factura
        if pdf_path:
            escribir_log(f"[PDF OCR]")
            exito_pdf = procesar_pdf_local_enel(factura, pdf_path)

            if not exito_pdf:
                escribir_log(f"    -> [ERROR PDF] Fallo al extraer datos del PDF para factura {factura.numero_factura} ({factura.cup})")
                factura.error_RPA = True
                
    # E. Insertar datos en CSV
        csv_path = os.path.join(DOWNLOAD_FOLDERS["CSV_ENEL"],"facturas_enel.csv")
        if csv_path:
            insertar_factura_en_csv(factura, csv_path)
        
    # F. Devolvemos la factura con los datos extraidos y procesados.
        return factura
    
    # G. Si no se ha podido procesar nada de la fila se informa y se devuelve None
    except Exception as e:
        escribir_log(f"    -->[ERROR] Fallo al extraer datos de la fila de la tabla: {str(e)}")
        return None
        
               
# DATA.2 Bucle de lectura para todas las filas de una página de la tabla de resultados
async def _extraer_pagina_actual_enel(page: Page, contador: int) -> list[FacturaEnel]:
    '''
    Realiza un bucle que recorre todas las filas de la página visible de la tabla de resultados, llamando en cada iteración a la funcion de procesado de dicha fila
    Parametros:
        - page (Page): Pagina web del navegador
    Retorna:
        - list[FacturaEnel]: Una lista de objetos del tipo factura donde se han registrado todos los datos de las filas que se han procesado
    '''

    facturas: list[FacturaEnel] = []
    try:

    # A. Identificación de los localizadores web de las distintas filas 
        rows = page.locator('table[lwc-392cvb27u8q] tbody tr')
        row_count = await rows.count()

        # A.1. Si no hay filas, devolvemos la lista vacía
        if row_count == 0:
            return facturas
    
        escribir_log(f"    [INFO] Tabla detectada con {row_count} filas")

    # B. Bucle para recorer cada una de las filas
        for i in range(row_count):
            escribir_log(f"\n\t[ROW {(i+contador+1)}] {'='*40}",mostrar_tiempo=False)
            row = rows.nth(i)
            
            # B.1 Procesado y extraccion de la fila iterada
            factura = await _extraer_datos_fila_enel(page, row)
        
            # B.2 Si la fila se ha procesado correctamente, se añade la factura a la lista
            if factura:
                facturas.append(factura)

    # C. Devolvemos el listado de facturas procesadas
        return facturas
        
    # D. Si hay algún fallo se devuelve la lista en su estado actual y se informa del error
    except Exception as e:
        escribir_log(f"    -->[ERROR] Fallo al extraer datos de la Tabla: {str(e)}")
        return facturas


# DATA 3. Bucle de lectura para todas las páginas de la tabla de resultados
async def _extraer_tabla_facturas_enel(page: Page, contador_facturas: int = 0) -> list[FacturaEnel]:
    '''
    Realiza un bucle que recorre cada una de las páginas de la tabla de resultado llamando a la función que procesa dicha página.
    Parametros:
        - page (Page): Pagina web del navegador
    Retorna:
        - list[FacturaEndesaCliente]: Listado de todas las facturas que se han procesado en el proceso
        - int: Número total de facturas procesadas en todas las páginas

    '''
    todas_facturas: list[FacturaEnel] = []
    

    try:
    # A. Esperar a que la tabla sea visible
        await page.wait_for_selector('table[lwc-392cvb27u8q]', timeout=60000)
    
    # B. Lectura de la página actual 
        facturas_pagina = await _extraer_pagina_actual_enel(page, contador_facturas)
        todas_facturas.extend(facturas_pagina)
        contador_facturas += len(facturas_pagina)

    # C. Verificar si existe el botón "Siguiente" y si está habilitado
        next_button = page.locator('div.wp-pagination button').filter(has_text="Siguiente")
    
    # D, Si no hay botón o está deshabilitado, devolvemos los resultados actuales
        if await next_button.count() == 0 or await next_button.is_disabled():
            return todas_facturas 
    
    # E. Si el botón "Siguiente" está habilitado, pulsamos y esperamos a que se cargue la siguiente página para continuar el proceso de extracción de datos
        try:
            await next_button.click(timeout=10000)
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000) 
        except TimeoutError:
            escribir_log("    -->[ERROR] Tiempo excedido esperando la siguiente página de resultados.")
            return todas_facturas
            
        
    # F. Llamada recursiva para procesar la siguiente página, y acumulación de resultados
        facturas_siguientes = await _extraer_tabla_facturas_enel(page, contador_facturas)
        todas_facturas.extend(facturas_siguientes)
        return todas_facturas
        
    
    except TimeoutError:
        escribir_log("    -->[ERROR] Tiempo excedido esperando la tabla de resultados.")

    except Exception as e:
        escribir_log(f"    -->[ERROR] Fallo inesperado en la navegación de tabla: {str(e)}")
        return todas_facturas 



# === 2. FUNCIONES DE NAVEGACION WEB === #

# NAV.1 Inicio de sesión en la web
async def _iniciar_sesion_enel(page: Page, username: str, password: str) -> bool:
    '''
    Inicia sesión el la web de Enel con las credenciales proporcionadas
    Parametros:
        - page (Page): Pagina web del navegador
        - username (str): Nombre de usuario para el acceso a la web
        - password (str): Contraseña para el acceso a la web
    Retorna:
        - bool: True si ha conseguido inicair sesión correctamente, False en caso contrario
    '''
    try:
    # A. Espera que se cargue el formulario de inicio de sesión
        await page.wait_for_selector('input[name="username"]', timeout=20000)

    # B. Rellena los campos de Usuario y Contraseña
        await page.fill('input[name="username"]', username)
        await page.fill('input[name="password"]', password)

    # C. Hace click en el botón de iniciar sesión
        await page.click('button:has-text("ENTRAR")')

    # D. Esperar el indicador de éxito
        await page.wait_for_load_state("networkidle")

        return True
    
     # E. Si hay algún error, lo registra
    except TimeoutError:
        escribir_log("Fallo en el Login: El tiempo de espera para cargar el indicador de éxito (cookies o dashboard) ha expirado.")
        return False
    
    except Exception as e:
        escribir_log(f"Error inesperado durante la autenticación: {e}")
        return False


# NAV.2 Obtención de roles
async def _obtener_todos_los_roles(page: Page) -> list[str]:
    '''
    Obtiene la lista de roles disponibles para el usuario haciendo click en el desplegable de cambio de rol y extrayendo los nombres de cada uno de los roles disponibles.
    Parametros:
        - page (Page): Pagina web del navegador
    Retorna:
        - list[str]: Lista con los nombres de los roles disponibles para el usuario
    '''
    roles = []

    try:

    # A. Hacemos click en el desplegable de cambio de rol para mostrar las opciones disponibles
        await page.locator('button[title="Cambio de rol"]').click()
        
    # B. Esperamos a que los elementos del menú sean visibles
        await page.wait_for_selector('a[role="menuitem"]', timeout=15000)
        
        roles_elements = page.locator('a[role="menuitem"]')
        count = await roles_elements.count()
        
        
    # C. Iteramos sobre cada una de las opciones disponibles en el menú, obteniendo el nombre del rol y añadiéndolo a la lista de roles si es un nombre válido (no vacío, no "None", etc)
        for i in range(count):
            # C.1. Obtenemos el atributo title
            nombre = await roles_elements.nth(i).get_attribute("title")
            
            # C.2. Solo añadimos a la lista si el nombre existe y no es una cadena vacía o "None"
            if nombre and str(nombre).strip().lower() != "none" and str(nombre).strip() != "":
                roles.append(nombre.strip())
                escribir_log(f"   - ROL {i+1}: {nombre.strip()}", mostrar_tiempo=False)
        
    # D. Cerramos el menú volviendo a pulsar el botón para que no bloquee la pantalla
        await page.locator('button[title="Cambio de rol"]').click()
        
    # E. Devolvemos la lista de roles válidos obtenidos
        escribir_log(f"    -> [OK] Total de roles válidos a procesar: {len(roles)}")
        return roles
    

    except TimeoutError:
        escribir_log("Fallo al obtener roles: El tiempo de espera para cargar las opciones de rol ha expirado.")
        return roles
    except Exception as e:
        escribir_log(f"Error inesperado al obtener roles: {e}")
        return roles


# NAV.3 Selección de roles
async def _seleccionar_rol_especifico(page: Page, nombre_rol: str) -> bool:
    '''
    Selecciona un rol específico haciendo click en el desplegable de cambio de rol y luego en la opción que corresponda al nombre del rol que se quiere seleccionar.
    Parametros:
        - page (Page): Pagina web del navegador
        - nombre_rol (str): Nombre del rol que se desea seleccionar
    Retorna:
        - bool: True si ha conseguido seleccionar el rol correctamente, False en caso contrario
    '''
    try:
    # A. Hacemos click en el desplegable de cambio de rol para mostrar las opciones disponibles
        await page.locator('button[title="Cambio de rol"]').click()
        #input(f"DEBUG: Se ha hecho click en el desplegable de roles para seleccionar el rol '{nombre_rol}'. Presiona Enter para continuar con la selección del rol...")

    # B. Esperamos a que los elementos del menú sean visibles
        await page.wait_for_selector(f'a[role="menuitem"][title="{nombre_rol}"]', timeout=15000)
        opcion = page.locator(f'a[role="menuitem"][title="{nombre_rol}"]')
        await opcion.wait_for(state="visible")
        #input(f"DEBUG: La opción de rol '{nombre_rol}' es visible. Presiona Enter para continuar con la selección del rol...")
        
    # C. Seleccionamos el rol especificado
        clases = await opcion.get_attribute("class")
        #input(f"DEBUG: Clases del elemento de opción de rol '{nombre_rol}': {clases}. Presiona Enter para continuar con la selección del rol...")
        if "wp-roleSelected" in (clases or ""):
            await page.locator('button[title="Cambio de rol"]').click()
            #input(f"DEBUG: El rol '{nombre_rol}' ya estaba seleccionado, se ha cerrado el desplegable. Presiona Enter para continuar con el proceso...")
        else:
            await opcion.click()
            #input(f"DEBUG: Se ha hecho click en la opción de rol '{nombre_rol}' para seleccionarlo. Presiona Enter para continuar y esperar a que se cargue el rol seleccionado...")
            await page.wait_for_load_state("networkidle")

    
        return True
    
    # D. Manejo de errores específicos para la selección de rol
    except TimeoutError:
        escribir_log(f"Fallo al seleccionar el rol '{nombre_rol}': El tiempo de espera para cargar las opciones de rol ha expirado o el rol no existe.")
        return False
    except Exception as e:
        escribir_log(f"Error inesperado al seleccionar el rol '{nombre_rol}': {e}")
        return False


# NAV.4 Rellenar filtros y realizar busqueda de facturas
async def _aplicar_filtros_fechas(page: Page, f_desde, f_hasta) -> bool:
    '''
    Rellena los campos de fecha de los filtros de búsqueda de facturas, aplicando el rango de fechas deseado, y espera a que se carguen los resultados.
    Parametros:
        - page (Page): Pagina web del navegador
        - f_desde (str): Fecha de inicio del rango en formato dd/mm/yyyy
        - f_hasta (str): Fecha de fin del rango en formato dd/mm/yyyy
    Retorna:
        - bool: True si se han aplicado los filtros y se han cargado los resultados correctamente, False en caso contrario (ej. sin resultados, fallo en la aplicación de filtros, etc)
    '''
    try:
    
    # A. Navega a la página de facturas
        await page.goto(URL_FACTURAS_ENEL, wait_until="networkidle")
        
    # B. Activa la opcion de filtro por rango de fechas
        await page.locator('span.slds-form-element__label:has-text("Rango de fechas")').click()
        await page.wait_for_timeout(1000)
        
    # C. Rellena los campos de fecha
        await page.fill('.filter-date-from input', "")
        await page.type('.filter-date-from input', f_desde, delay=60)
        await page.fill('.filter-date-to input', "")
        await page.type('.filter-date-to input', f_hasta, delay=60)
        
    # D. Aplica los filtros y espera a que se carguen los resultados
        await page.locator('button:has-text("Aplicar")').last.click()
        #input(f"DEBUG: Se han aplicado los filtros de fecha desde '{f_desde}' hasta '{f_hasta}'. Presiona Enter para esperar a que se carguen los resultados y verificar si se han cargado correctamente o si no hay resultados para el periodo seleccionado...")
        

    # E. Esperamos a que se cargue la tabla de resultados, verificando que se ha cargado correctamente o que no hay resultados para el periodo seleccionado
            
        selector_exito = 'lightning-primitive-cell-factory'
        selector_vacio = 'div:has-text("No se encuentran resultados")'
        
        # E.1. Esperamos a que se muestre alguno de los dos indicadores (tabla de resultados o mensaje de sin resultados)
        try:
            await page.locator(f"{selector_exito}, {selector_vacio}").first.wait_for(state="visible", timeout=90000)
        except TimeoutError:
            escribir_log("    --> [ERROR] La página no respondió tras aplicar filtros.")
            return False

        
        # E.2. Si se muestra la tabla de resultados, confirmamos que se ha cargado correctamente y devolvemos True. 
        if await page.locator(selector_exito).count() > 0:
            escribir_log("    [OK] Tabla cargada con éxito.")
            return True
        
        # E.3. Si se muestra el mensaje de "No se encuentran resultados", lo confirmamos y devolvemos False (aunque la página haya respondido, no hay datos que extraer)
        if await page.locator(selector_vacio).count() > 0:
            escribir_log("    [OK] Tabla cargada con éxito.")
            return True

        escribir_log("    [ERROR] La página respondió pero no se pudo confirmar la carga de la tabla de resultados ni el mensaje de 'No se encuentran resultados'.")
        return False
    
    except TimeoutError:
        escribir_log("    [ERROR] Tiempo excedido esperando la tabla de resultados o el mensaje de 'No se encuentran resultados'.")
        return False
    except Exception as e:
        escribir_log(f"    [ERROR] Error inesperado al aplicar filtros o cargar resultados: {e}")
        return False

