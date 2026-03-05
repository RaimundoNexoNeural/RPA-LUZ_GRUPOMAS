from playwright.async_api import async_playwright, Playwright, Browser, Page, BrowserContext
from urllib.parse import urlparse
from config import TEMP_DOWNLOAD_ROOT, HEADLESS_MODE
import os

### NAVEGADOR ASINCRONO
class NavegadorAsync:
    """
    Clase que encapsula la inicialización de Playwright con captura de FQDNs.
    Se han eliminado las restricciones de carga para identificar todos los recursos externos.
    """

    # === 0. INICIALIZACION DE LA CLASE ===
    def __init__(self):
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.page: Page | None = None
        self.context: BrowserContext | None = None
        # Set para almacenar los hostnames (FQDN) únicos detectados durante la sesión
        self.fqdns = set() 
        
        # Aseguramos que el directorio para descargas exista
        os.makedirs(TEMP_DOWNLOAD_ROOT, exist_ok=True)

     # === AUX. REGISTRO DE FQDNs ===
    def _registrar_fqdn(self, url: str):
        """
        Extrae el hostname de una URL y lo añade al set de seguimiento.
        """
        if url.startswith(("http://", "https://")): 
            try:
                hostname = urlparse(url).hostname 
                if hostname:
                    self.fqdns.add(hostname)
            except Exception:
                pass

    # === 1. INICIALIZACION DEL NAVEGADOR ===
    async def iniciar(self):
        """
        Inicializa la sesión de Playwright y activa el sistema de escucha de red 
        permitiendo la carga de todos los recursos externos.
        """
        # A. Iniciación en modo asíncrono y headless
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=HEADLESS_MODE) 
        
        # B. Configuración del contexto del navegador
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
            accept_downloads=True
        )

        # C. ESCUCHADORES DE RED PARA CAPTURA DE RUTAS (SEGÚN PDF) ===
        # Registra todas las peticiones salientes (scripts, apis, librerías externas)
        self.context.on("request", lambda req: self._registrar_fqdn(req.url)) 
        # Registra las respuestas para capturar redirecciones finales
        self.context.on("response", lambda res: self._registrar_fqdn(res.url)) 
        # Registra peticiones fallidas para identificar bloqueos del firewall actual
        self.context.on("requestfailed", lambda req: self._registrar_fqdn(req.url)) 
        

        # D. Creación de una nueva página en el contexto
        self.page = await self.context.new_page()

        # Nota: Se ha eliminado page.route("**/*") para no restringir ningún recurso.
        
        return self 

    # === 2. NAVEGACION A UNA URL ===
    async def goto_url(self, url: str, timeout_ms: int = 60000) -> Page:
        """
        Navega a la URL especificada.
        """
        await self.page.goto(
            url, 
            wait_until="domcontentloaded", 
            timeout=timeout_ms
        ) 
        return self.page

    # === 3. CIERRE DEL NAVEGADOR ===
    async def cerrar(self):
        """
        Guarda el listado de FQDNs capturados en rutas.txt y cierra el navegador.
        """
        if self.fqdns:
            try:
                # Guardar el listado deduplicado y ordenado alfabéticamente
                with open("rutas.txt", "w", encoding="utf-8") as f: 
                    for host in sorted(self.fqdns):
                        f.write(host + "\n") 
                print(f"INFO: Diagnóstico de red completado. Se han guardado {len(self.fqdns)} dominios en rutas.txt")
            except Exception as e:
                print(f"ERROR al guardar rutas.txt: {e}")

        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    # === 4. OBTENER LA PAGINA ACTUAL ===
    def get_page(self) -> Page:
        """Devuelve el objeto Page actual."""
        if not self.page:
            raise RuntimeError("El navegador no ha sido inicializado.")
        return self.page