from playwright.async_api import async_playwright, Playwright, Browser, Page, BrowserContext
from config import TEMP_DOWNLOAD_ROOT, HEADLESS_MODE
import os


### NAVEGADOR ASINCRONO
class NavegadorAsync:
    """
    Clase que encapsula la inicialización, uso y cierre de una sesión 
    de Playwright Asíncrona.
    """

    # === 0. INICIALIZACION DE LA CLASE ===
    def __init__(self):
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.page: Page | None = None
        self.context: BrowserContext | None = None
        
        # Aseguramos que el directorio para descargas exista
        os.makedirs(TEMP_DOWNLOAD_ROOT, exist_ok=True)

    # === 1. INICIALIZACION DEL NAVEGADOR ===
    async def iniciar(self):
        """
        Inicializa la sesión de Playwright y lanza el navegador.
        """

        # A. Iniciación en modo asíncrono y headless
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=HEADLESS_MODE) 
        
        # B. Configuración del contexto del navegador
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36", # User Agent real (Chrome en Windows 10)
            #viewport={'width': 1920, 'height': 1080}, # Resolución de pantalla estándar
            extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"}, # Idioma aceptado (evita que la web cargue versiones raras)
            accept_downloads=True # Permitir descargas
        )
        # C. Creación de una nueva página en el contexto
        self.page = await self.context.new_page()
        
        return self 


    # === 2. NAVEGACION A UNA URL ===
    async def goto_url(self, url: str, timeout_ms: int = 60000) -> Page:
        """
        Navega a la URL especificada.
        """

        await self.page.goto(
            url, 
            wait_until="networkidle", # Cambiado de domcontentloaded a networkidle
            timeout=timeout_ms
        ) 
        return self.page


    # === 3. CIERRE DEL NAVEGADOR ===
    async def cerrar(self):
        """
        Cierra el navegador y detiene el contexto.
        """

        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    

    # === 4. OBTENER LA PAGINA ACTUAL ===
    def get_page(self) -> Page:
        """
        Devuelve el objeto Page actual.
        """

        if not self.page:
            raise RuntimeError("El navegador no ha sido inicializado.")
        return self.page