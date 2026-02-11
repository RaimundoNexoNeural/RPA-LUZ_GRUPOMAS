import re
import os
from datetime import datetime
from playwright.async_api import Page, TimeoutError, Locator
from modelos_datos import FacturaEndesa
from logs import escribir_log
from config import DOWNLOAD_FOLDERS, URL_LOGIN_ENDESA, URL_FACTURAS_ENDESA, GRUPO_EMPRESARIAL, TABLE_LIMIT
from parsers.xml_parser_endesa import procesar_xml_local_endesa
from parsers.pdf_parser_endesa import procesar_pdf_local_endesa
from parsers.exportar_datos import insertar_factura_en_csv


# === FUNCIONES AUXILIARES PARA CARGA Y PROCESADO DE DATOS DE ENDESA  === #

# AUX.1.Conversión de importes (str) a float
def _clean_and_convert_float(text: str) -> float:
    '''
    Limpia una cadena de texto de importe (ej. '4697.73 €') y la convierte a float.
    Parametros:
        text (str): Importe con formato 1000.73 € o bien 1000,73 €
    Retorna:
        float: El valor numérico del importe
    '''
    cleaned_text = re.sub(r'-?[^\d,\.]', '', text).replace(',', '.')
    try:
        return float(cleaned_text)
    except ValueError:
        return 0.0
    

# AUX.2.Extracción de texto de una celda
async def _extraer_texto_de_td(td: Locator) -> str:
    '''
    Extrae texto de una celda de tabla.
    Parametros:
        td (Locator): Localizador web de la celda a extraer
    Retorna:
        str: El valor textual de la celda
    '''
    try:
    # A. Dentro de la celda busca los siguiente elementos para extraer el texto (fechas, enlaces o botones)
        lightning_element = td.locator("lightning-formatted-date-time, button, a")
           
        # A.1 Si lo encuentra extrae el texto del elemento en cuestion (fecha, enlace o boton)
        if await lightning_element.count() > 0:
            return (await lightning_element.first.inner_text()).strip() 
        
        # A.2 Si no encuentra los localizadores extrae el texto directamente.
        text = await td.inner_text() 

        # A.3 Si hay algun tipo de fallo devuelve una cadena vacía
        return text.strip() if "No hay resultados" not in text else ""
    except Exception:
        return ""
    

# AUX.3 Espera que cargue la página de la tabla de resultados
async def _wait_for_data_load(page: Page, timeout: int = 90000) -> bool:
    '''
    Espera a que los datos dinámicos de la primera fila de la tabla de resultados estén cargados y estables.
    Parametros:
        page (Page): Pagina web del navegador
        timeout (int): Tiempo de espera a que se cargue la página
    Retorna:
        bool: Devuelve True si se han cargado los datos antes del timeout, y False en caso contrario
    '''
    # A. Definicion de selectores de datos dinámicos
    importe_cell_selector = 'table#example1 tbody tr:nth-child(1) td:nth-child(5)'
    estado_cell_selector = 'table#example1 tbody tr:nth-child(1) td:nth-child(9)'
    fraccionamiento_cell_selector = 'table#example1 tbody tr:nth-child(1) td:nth-child(10)'
    
    try:
    # B. Esperamos que se carguen los datos por un máximo de timeout definido
        await page.locator(importe_cell_selector).filter(
            has_not_text=re.compile(r"(Cargando|\.\.\.)", re.IGNORECASE)
        ).wait_for(state="visible", timeout=timeout)
        
        await page.locator(estado_cell_selector).filter(
            has_not_text=re.compile(r"(Cargando|\.\.\.)", re.IGNORECASE)
        ).wait_for(state="visible", timeout=timeout)
        
        await page.locator(fraccionamiento_cell_selector).filter(
            has_not_text=re.compile(r"(Cargando|\.\.\.)", re.IGNORECASE)
        ).wait_for(state="visible", timeout=timeout)

        await page.locator('span.pagination-flex-central').wait_for(state="visible", timeout=timeout)

    # C. Si han cargado, devolvemos True y confirmamos
        escribir_log("    -> [OK] Tabla cargada correctamente")
        return True
    
    # D. En caso de Timeout, devolvemos False e informamos
    except TimeoutError:
        escribir_log("    -->[!] Tiempo de espera agotado al cargar datos dinámicos de la tabla de facturas.")
        return False


# AUX.4 Descarga de archivos mediante botenes de la tabla de resultados
async def _descargar_archivo(page: Page, row: Locator, factura: FacturaEndesa, doc_type: str)->str | None:
    '''
    Intenta descargar un tipo de archivo (PDF, XML) haciendo clic en el botón de la fila y guardándolo localmente.
    Parametros:
        - page (Page): Pagina web del navegador
        - row (Locator): Localizador web de la fila de la que se quiere descargar los archivos
        - factura (FacturaEndesa): Objeto del tipo Factura al que se le asocian dichos archivos
        - doc_type (str): Formato del archivo que se desea descargar. PDF o XML
    Retorna:
        - str: La ruta al archivo que se ha descargado y guardado localmente
        - None: Si no se puede descargar dicho documento
    '''
    # A. Definimos los selectores web en funcion del tipo de archivo a descargar
    doc_type = doc_type.upper()
    if doc_type == 'PDF':
        button_col_index = 13
        file_ext = 'pdf'
        button_locator_selector = f'button[value*="{factura.descarga_selector}"]' 
    elif doc_type == 'XML':
        button_col_index = 11
        file_ext = 'xml'
        button_locator_selector = 'button:has-text("@")' 
    else:
        return None

    button_locator = row.locator(f'td').nth(button_col_index).locator(button_locator_selector)
    
    # B. Definimos la ruta donde se descargara el archivo
    target_folder = DOWNLOAD_FOLDERS[doc_type+"_ENDESA"]

    fecha = datetime.strptime(factura.fecha_fin_periodo, "%d/%m/%Y")
    mes = fecha.strftime("%m")
    anio = fecha.strftime("%Y")

    filename = f"{anio}{mes}_{factura.cup}_{factura.numero_factura}_ENDESA.{file_ext}" 
    save_path = os.path.join(target_folder, filename)

    # C. Proceso de descarga
    try:
        # C.1. Pulsamos el boton
        async with page.expect_download(timeout=30000) as download_info:
            await button_locator.click(timeout=10000)
        # C.2 Leemos los valores del archivo descargado en el navegador
        download = await download_info.value
        # C.3 Guardamos localmente el archivo
        await download.save_as(save_path)
        
    # D. Si se ha descargado correctamente, informamos y devolvemos la ruta del archivo descargado
        escribir_log(f"   -> [OK] [DESCARGA {doc_type}] Guardado en: {save_path}")
        return save_path
    
    # E. En caso de error en la descarga informamos
    except TimeoutError:
        factura.error_RPA = True
        factura.msg_error_RPA = f"ERROR_DESCARGA: No se ha podido descargar el archivo {doc_type} asociado a esta factura."
        return None
    
    except Exception as e:
        factura.error_RPA = True
        factura.msg_error_RPA = f"ERROR_DESCARGA: Fallo inesperado al descargar el archivo {doc_type} asociado a esta factura. Detalles: {str(e)}"
        return None
        

# AUX.5 Selector de fechas en Calendario
async def _seleccionar_fecha_flatpickr(page: Page, input_selector: Locator, fecha_str: str)-> bool:
    """
    Interactúa con el calendario dinámico de Flatpickr.
    Parametros:
        - page (Page): Pagina web del navegador
        - input_selector (Locator): Localizador web del campo de fecha a rellenar
        - fecha_str: Fecha a seleccionar, debe venir en formato DD/MM/YYYY
    Retorna:
        - bool: Devuelve True si se ha seleccionado la fecha correctamente, False en caso de cualquier error
    """
    try:
        # A. Abrir el calendario haciendo click
        await input_selector.click()
        
        # B. Localizar el calendario que acaba de abrirse (clase .open)
        calendar = page.locator('.flatpickr-calendar.open')
        await calendar.wait_for(state="visible", timeout=5000)

        # C. Separar la fecha
        dia, mes_num, anio = fecha_str.split('/')
        # Flatpickr usa meses de 0 a 11 internamente en el select
        mes_index = str(int(mes_num) - 1)

        # D. Seleccionar Año (es un input tipo number)
        await calendar.locator('input.cur-year').fill(anio)
        await calendar.locator('input.cur-year').press("Enter")

        # E. Seleccionar Mes (es un select)
        await calendar.locator('select.flatpickr-monthDropdown-months').select_option(index=int(mes_index))

        # F. Seleccionar Día (buscamos por aria-label para evitar días de meses adyacentes)
        # Los labels suelen ser "Enero 26, 2026" o similar dependiendo del idioma del navegador
        # Para ser universales, buscamos el span que NO sea de meses anteriores/posteriores
        dia_selector = calendar.locator('.flatpickr-day').filter(has_text=re.compile(f"^{int(dia)}$")).first
        await dia_selector.click()
        
        # Espera breve para que el calendario se cierre
        await page.wait_for_timeout(300)
        return True
    
    except Exception as e:
        escribir_log(f"    -->[ERROR] Fallo al seleccionar fecha '{fecha_str}': {e}")
        return False


# === FUNCIONES PARA LECTURA Y EXTRACCION DE DATOS  === #

# DATA.1 Extraccion y procesado de los datos copletos de una fila de la tabla de resultados
async def _extraer_datos_fila_endesa(page: Page, row: Locator) -> FacturaEndesa | None:
    '''
    Para una fila de la tabla de resultados, extrae los datos completos directos de la fila, 
    llama a las funciones de descarga de los archivos XML y PDF de la fila,
    llama a las funciones de parseo y procesado de los archivos XML o PDF (según corresponda) extrayendo los datos de las facturas,
    y crea y devuelve un objeto de la clase Factura con todos los datos actualizados.
    Parametros:
        - page (Page): Pagina web del navegador
        - row (Locator): Localizador web de la fila de la que se quiere procesar
    Retorna:
        - FacturaEndesa: Factura con todos los datos extraidos durante el procesado de la fila y los archivos
        - None: Unicamente si ni si quiera ha podido extrear los datos de la fila.
    '''
    
    try:
    # A. Extracción de datos de las celdas de la fila y creación del objeto Factura
        
        tds = row.locator("td")

        factura = FacturaEndesa(
            fecha_emision=await _extraer_texto_de_td(tds.nth(0)),
            numero_factura=await _extraer_texto_de_td(tds.nth(1)),
            fecha_inicio_periodo=await _extraer_texto_de_td(tds.nth(2)),
            fecha_fin_periodo=await _extraer_texto_de_td(tds.nth(3)),
            importe_total=_clean_and_convert_float(await _extraer_texto_de_td(tds.nth(4))),
            contrato=await _extraer_texto_de_td(tds.nth(5)),
            cup=await _extraer_texto_de_td(tds.nth(6)),
            secuencial=await _extraer_texto_de_td(tds.nth(7)),
            estado_factura=await _extraer_texto_de_td(tds.nth(8)),
            fraccionamiento=await _extraer_texto_de_td(tds.nth(9)),
            tipo_factura=await _extraer_texto_de_td(tds.nth(10)),
            descarga_selector=await tds.nth(13).locator('button').get_attribute("value") or ""
        )
    
        escribir_log(f"    [OK] Datos estraidos correctamente de la fila de la tabla: {factura.numero_factura}")


    # B. Descarga de archivos PDF y XML
        pdf_path = await _descargar_archivo(page, row, factura, 'PDF')
        xml_path = await _descargar_archivo(page, row, factura, 'XML')


    # C. Procesamiento de archivos descargados, extracción de datos adicionales y actualizacion de objeto Factura

        # C.1. Si se ha podido descargar el archivo XML se procesa este archivocon prioridad
        if xml_path:
            escribir_log(f"[XML PROCESSING]")
            exito_xml = procesar_xml_local_endesa(factura, xml_path)

            # C.1.1 Si no se ha podido procesar el XML se registra el error
            if not exito_xml:
                escribir_log(f"    -> [ERROR XML] Fallo al extraer datos del XML para factura {factura.numero_factura} ({factura.cup})")
                factura.error_RPA = True
                factura.msg_error_RPA = "ERROR_PARSEO: El archivo XML no contenía datos válidos o estaba incompleto."
        
        # C.2. Si no se ha descargado el XML, se procesa el PDF
        else:
            escribir_log(f"   -> [ADVERTENCIA XML] No se descargó el XML, omitiendo parseo para factura {factura.numero_factura} ({factura.cup})")
            factura.error_RPA = True
            factura.msg_error_RPA = "ERROR_FILES: El archivo XML no se ha podido descargar."
            
            # C.2.1 Procesamos el PDF mediante OCR
        if not xml_path and pdf_path:
            escribir_log(f"[PDF OCR]")
            exito_pdf = procesar_pdf_local_endesa(factura, pdf_path)
        
            # C.2.2 Si no se ha podido procesar el PDF se registra el error
            if not exito_pdf:
                escribir_log(f"    -> [ERROR PDF] Fallo al extraer datos del PDF para factura {factura.numero_factura} ({factura.cup})")
                
                
        # C.3. Si no se ha descargado ni el XML ni el PDF, se registra el error y se devuelve la factura solo con los datos básico de la tabla.
        if not xml_path and not pdf_path:
            factura.error_RPA = True
            factura.msg_error_RPA = "ERROR_DESCARGA: No se pudo descargar ningún archivo (XML/PDF) para esta factura."
        
        # D. Insertar datos en CSV
        csv_path = os.path.join(DOWNLOAD_FOLDERS["CSV_ENDESA"],"facturas_endesa.csv")
        if csv_path:
            insertar_factura_en_csv(factura, csv_path)

        # E. Devolvemos la factura con los datos extraidos y procesados.
        return factura
    
        # F. Si no se ha podido procesar nada de la fila se informa y se devuelve None
    except Exception as e:
        escribir_log(f"    -->[ERROR] Fallo al extraer datos de la fila de la tabla: {str(e)}")
        return None
    

# DATA.2 Bucle de lectura para todas las filas de una página de la tabla de resultados
async def _extraer_pagina_actual_endesa(page: Page, page_index: int) -> list[FacturaEndesa]:
    '''
    Realiza un bucle que recorre todas las filas de la página visible de la tabla de resultados, llamando en cada iteración a la funcion de procesado de dicha fila
    Parametros:
        - page (Page): Pagina web del navegador
        - page_index (int): Indice numerico de la página de la tabla en la que se encuentra
    Retorna:
        - list[FacturaEndesa]: Una lista de objetos del tipo factura donde se han registrado todos los datos de las filas que se han procesado
    '''

    facturas: list[FacturaEndesa] = []
    try:

    # A. Identificación de los localizadores web de las distintas filas 
        rows = page.locator('table#example1 tbody tr')
        row_count = await rows.count()

    # B. Bucle para recorer cada una de las filas
        for i in range(row_count):
            escribir_log(f"\n\t[ROW {(i+1)+5*(page_index-1)}] {'='*40}",mostrar_tiempo=False)
            row = rows.nth(i)
            
            # B.1 Procesado y extraccion de la fila iterada
            factura = await _extraer_datos_fila_endesa(page, row)
            
            # B.2 Si la fila se ha procesado correctamente, se añade la factura a la lista
            if factura:
                facturas.append(factura)
        
    # C. Devolvemos el listado de facturas procesadas
        return facturas
    
    # D. Si hay algún fallo se devuelve la lista en su estado actual y se informa del error
    except Exception as e:
        escribir_log(f"    -->[ERROR] Fallo al extraer datos de la Página {page_index}: {str(e)}")
        return facturas


# DATA.3 Bucle de lectura consciente para todas las páginas de la tabla
async def _extraer_tabla_facturas_endesa(page: Page) -> list[FacturaEndesa]:
    '''
    Realiza un bucle que recorre cada una de las páginas de la tabla de resultado llamando a la función que procesa dicha página.
    Parametros:
        - page (Page): Pagina web del navegador
    Retorna:
        - list[FacturaEndesaCliente]: Listado de todas las facturas que se han procesado en el proceso
    '''
    todas_facturas: list[FacturaEndesa] = []

    try:
    # A. Esperar a que la tabla sea visible
        await page.wait_for_selector('div.style-table.contenedorGeneral table#example1', timeout=60000)
        
    # B. Detectar el número total de páginas del elemento tiene el formato "PáginaActual / TotalPaginas" (ej: "1 / 37")
        pagination_text_element = page.locator('span.pagination-flex-central')
        await pagination_text_element.wait_for(state="visible", timeout=10000)
        pagination_text = await pagination_text_element.inner_text()
        

        try:
            total_paginas = int(pagination_text.split('/')[-1].strip())
            escribir_log(f"    [INFO] Tabla detectada con {total_paginas} páginas.")
        except (ValueError, IndexError):
            escribir_log("    [ADVERTENCIA] No se pudo determinar el total de páginas. Usando modo preventivo (1 página).")
            total_paginas = 1

    # C. Bucle consciente basado en el número total de páginas
        for current_page in range(1, total_paginas + 1):
            escribir_log(f"\n\n[PAGE {current_page} / {total_paginas}] ",mostrar_tiempo=False)
            
            # C.1. Esperar a que los datos de la página actual estén cargados
            await _wait_for_data_load(page)

            # C.2. Extraer datos de la página actual
            facturas_pagina = await _extraer_pagina_actual_endesa(page, current_page)
            todas_facturas.extend(facturas_pagina)

            # C.3 Navegar a la siguiente página si no es la última
            if current_page < total_paginas:
                next_button = page.locator('button.pagination-flex-siguiente')
                
                # C.3.1 Verificación extra: si el botón está deshabilitado pero el contador dice que faltan páginas
                if await next_button.is_disabled():
                    escribir_log(f"    [AVISO] El botón 'SIGUIENTE' está bloqueado en la página {current_page}. Finalizando.")
                    break
                
                # C.3.2 Pulsamos el boton de página siguiente
                
                try:
                    await next_button.click(timeout=10000)
                    await page.wait_for_timeout(1500) 
                except TimeoutError:
                    escribir_log(f"    -->[ERROR] Timeout al pulsar siguiente en página {current_page}.")
                    break
    
    # D. Si existe algún error se informa
    except TimeoutError:
        escribir_log("    -->[ERROR] Tiempo excedido esperando la tabla de resultados.")
    except Exception as e:
        escribir_log(f"    -->[ERROR] Fallo inesperado en la navegación de tabla: {str(e)}")
    
    # E. Se devuleve la lista de todas las facturas que se han procesado
    return todas_facturas



# === FUNCIONES DE NAVEGACION WEB === #

# NAV.1 Inicio de sesión en la web
async def _iniciar_sesion_endesa(page: Page, username: str, password: str) -> bool:
    '''
    Inicia sesión el la web de Endesa con las credenciales proporcionadas
    Parametros:
        - page (Page): Pagina web del navegador
        - username (str): Nombre de usuario para el acceso a la web
        - password (str): Contraseña para el acceso a la web
    Retorna:
        - bool: True si ha conseguido inicair sesión correctamente, False en caso contrario
    '''
    
    try:
    # A. Espera que se cargue el formulario de inicio de sesion
        await page.wait_for_selector('form.slds-form', timeout=10000)

    # B. Rellena los campos de Usuario y Contraseña
        await page.fill('input[name="Username"]', username)
        await page.fill('input[name="password"]', password)
        
    # C. Hace click en el botón de iniciar sesión
        await page.click('button:has-text("ACCEDER")')
        
    # D. Esperar el indicador de éxito (el botón de cookies) en la nueva página
        await page.wait_for_selector("#truste-consent-button", timeout=60000)
        
        return True

    # E. Si hay algún error, lo registra
    except TimeoutError:
        escribir_log("Fallo en el Login: El tiempo de espera para cargar el indicador de éxito (cookies o dashboard) ha expirado.")
        
        # E.1. Identifica si el error es por credenciales incorrectas
        final_url = page.url
        if final_url.startswith(URL_LOGIN_ENDESA) and await page.is_visible('div[class*="error"]'):
             escribir_log("Razón: Credenciales incorrectas.")
        return False
    
    except Exception as e:
        escribir_log(f"Error inesperado durante la autenticación: {e}")
        return False
    

# NAV.2 Aceptar Coockies y cerrar baners de promociones.
async def _aceptar_cookies_endesa(page: Page) -> bool:
    '''
    Cierra posibles ventanas modales de Salesforce y luego acepta el banner de cookies.
    Parametros:
        - page (Page): Pagina web del navegador
    Retorna:
        - bool: Devuelve True si el proceso ha sido correcto, False en caso contrario
    '''
    # A. Selectores para los botones de cerrar modales que proporcionaste
    btn_cerrar_modal_icon = 'button.slds-modal__close[title="Cerrar"]'
    btn_cerrar_modal_brand = 'button.slds-button_brand:has-text("Cerrar")'
    cookie_button_selector = '#truste-consent-button'
    modales = [btn_cerrar_modal_icon, btn_cerrar_modal_brand]

    try:

    # B. Bucle para recorrer y pulsar los distintos botones de las ventanas modales
        for selector in modales:
            try:
                # B.1. Verificamos si el botón está presente y visible
                boton_modal = page.locator(selector)
                if await boton_modal.is_visible(timeout=3000):

                # B.2. Pulsamos el boton en caso de estar visible
                    escribir_log(f"Detectada ventana modal. Pulsando cerrar ({selector}).")
                    await boton_modal.click()
                    await page.wait_for_timeout(500) 

                # B.3. Si falla o no es visible en 3s, continuamos al siguiente
            except Exception:
                continue

    # C. Aceptar Cookies
            # C.1. Verificamos si el botón está presente y visible
        if await page.locator(cookie_button_selector).is_visible(timeout=5000):
            # C.2. Pulsamos el boton en caso de estar visible
            await page.click(cookie_button_selector)
            escribir_log("Cookies aceptadas.")
            await page.wait_for_timeout(500) 
            # C.3. Si el boton no está visble, informamos y continuamos con el proceso
        else:
            escribir_log("Banner de cookies no detectado tras cerrar modales.")

        return True
            
    # D. Si El proceso falla, informamos y devolvemos False
    except TimeoutError:
        escribir_log("Tiempo de espera agotado al gestionar modales o cookies.")
        return False
    except Exception as e:
        escribir_log(f"Error al intentar aceptar las cookies o cerrar modales: {e}")
        return False


# NAV.3 Rellenar filtros y realizar busqueda de facturas
async def _realizar_busqueda_facturas_endesa(page: Page, fecha_desde: str, fecha_hasta: str, cup: str = None) -> bool:
    '''
    Aplica los filtros de búsqueda para filtrar las facturas
    Parametros:
        - page (Page): Pagina web del navegador
        - fecha_desde (str): Fecha de inicio del periodo de emision de facturas en el que se busca
        - fecha_hasta (str): Fecha de fin del periodo de emision de facturas en el que se busca
        - cup (str) : Opcinalmente si se quiere buscar las facturas asociadas a un único código CUP. Si se omite busca todas las facturas para todos los códigos CUPs
    Retorna:
        - bool: Devuelve True si el proceso ha sido correcto, False en caso contrario
    '''
    
    try:
        # A. Navegar a la página de búsqueda y esperar que carguen los filtros
        await page.goto(URL_FACTURAS_ENDESA, wait_until="domcontentloaded")
        main_filter_container_selector = 'div.filter-padd-container'
        await page.wait_for_selector(main_filter_container_selector, timeout=20000)

        # B. Rellenar filtros
            
            # B.1. Grupo Empresarial
        await page.click('button[name="periodo"]:has-text("Grupo empresarial")')
        await page.fill('input[placeholder="Buscar"]', GRUPO_EMPRESARIAL)
        await page.click(f'span[role="option"] >> text="{GRUPO_EMPRESARIAL}"')

            # B.2. Filtro CUPS
        if cup:
            escribir_log(f"    -> [INFO] Aplicando filtro para CUP: {cup}")
            await page.click('button[name="periodo"]:has-text("CUPS20/CUPS22")')
            await page.fill('input[placeholder="Buscar"]', cup)
            await page.click(f'span[role="option"] >> text="{cup}"')
        else:
            escribir_log("    -> [INFO] Sin CUP específico. Buscando todos los CUPS disponibles.")

            # B.3. Filtros de Fecha (Interacción con Calendario Real - Fecha de emisión)
        try:
            label_emision = page.locator('label', has_text="Fecha de emisión").filter(has_not=page.locator('span'))
            container_emision = page.locator('div.mt-16').filter(has=page.locator('label', has_text="Fecha de emisión")).last
            inputs_fecha = container_emision.locator('input.flatpickr-input')

            await _seleccionar_fecha_flatpickr(page, inputs_fecha.nth(0), fecha_desde)
            await _seleccionar_fecha_flatpickr(page, inputs_fecha.nth(1), fecha_hasta)
        except Exception as e:
            escribir_log(f"    --> [ERROR] Fallo al localizar los calendarios de Fecha de emisión: {e}")

    
            # B.4. Límite de Resultados
        try:
            await page.get_by_label("Limite").fill(str(TABLE_LIMIT))
        except Exception:
            await page.locator('input[max="100"]').fill(str(TABLE_LIMIT))
        

        # C. Buscar resultados
        await page.click('button.slds-button_brand:has-text("Buscar")')
        

        # D. Esperar que carguen los resultados
        tabla_selector = 'div.style-table.contenedorGeneral table#example1'
        await page.wait_for_selector(tabla_selector, timeout=60000)
        
        
        escribir_log(f"    [OK] Filtros Aplicados con éxito {'para ' + cup if cup is not None else ''}, desde {fecha_desde} hasta {fecha_hasta}.")

        return True
    

    except Exception as e:
        escribir_log(f"Error al intentar aplicar los filtros {'para'+ cup if cup is not None else ''}, desde {fecha_desde} hasta {fecha_hasta}.: {e}")
        return False
    
