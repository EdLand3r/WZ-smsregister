import os
import time
import tempfile
from playwright.sync_api import sync_playwright

# Los datos de sesión se van a la carpeta temporal del sistema operativo
USER_DATA_DIR = os.path.join(tempfile.gettempdir(), "playwright_whatsapp_firefox")

# Ruta absoluta donde se encuentra este script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TXT_PATH = os.path.join(SCRIPT_DIR, "historial_mensajes.txt")


def iniciar_guardado_mensajes():
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)

    with sync_playwright() as p:
        print("Iniciando Firefox...")
        context = p.firefox.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            args=["--start-maximized"]
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://web.whatsapp.com")
        
        print("Esperando a que WhatsApp Web cargue... (Escanea el QR si es necesario)")
        
        try:
            page.wait_for_selector('[data-testid="chat-list"]', timeout=60000)
            print("¡Sesión iniciada con éxito!")
        except Exception:
            print("Tiempo de espera agotado o QR no escaneado.")
            context.close()
            return

        print("Escuchando mensajes en el chat activo... Presiona Ctrl+C para salir.")
        ultimo_mensaje_guardado = ""

        try:
            while True:
                # Busca cualquier elemento que tenga el atributo 'data-pre-plain-text'
                # WhatsApp suele poner este atributo en los contenedores de los mensajes de texto
                elementos_mensajes = page.query_selector_all('[data-pre-plain-text]')
                
                if elementos_mensajes:
                    ultimo_elemento = elementos_mensajes[-1]
                    info_meta = ultimo_elemento.get_attribute('data-pre-plain-text')
                    
                    # El texto del mensaje suele estar dentro de este mismo contenedor
                    # Usamos inner_text() para capturar todo el texto visible dentro de él
                    texto_mensaje = ultimo_elemento.inner_text()
                    
                    if texto_mensaje and info_meta:
                        # Limpiamos saltos de línea extra para que el log se vea limpio
                        texto_limpio = texto_mensaje.strip()
                        mensaje_completo = f"{info_meta} {texto_limpio}"
                        
                        if mensaje_completo != ultimo_mensaje_guardado:
                            ultimo_mensaje_guardado = mensaje_completo
                            
                            # Guarda el archivo TXT directamente en la misma carpeta del script
                            with open(TXT_PATH, "a", encoding="utf-8") as archivo:
                                archivo.write(f"{mensaje_completo}\n")
                                
                            print(f"\n[NUEVO] Guardado en TXT: {mensaje_completo}")
                    else:
                        print(f"Mensaje detectado pero sin texto. Info meta: {info_meta}", end="\r")
                else:
                    # Intento alternativo para depurar si WhatsApp cambió todo
                    filas = page.query_selector_all('[role="row"]')
                    print(f"Aún no detecto [data-pre-plain-text]. Filas detectadas: {len(filas)}. Abre un chat.", end="\r")
                
                time.sleep(3)
                
        except KeyboardInterrupt:
            print("\nDeteniendo el guardado de mensajes de forma segura...")
        finally:
            try:
                context.close()
                print("Navegador cerrado correctamente.")
            except Exception:
                print("Proceso finalizado.")

if __name__ == "__main__":
    iniciar_guardado_mensajes()