import os
import time
from playwright.sync_api import sync_playwright

# Carpeta para guardar la sesión de Firefox y no repetir el QR
USER_DATA_DIR = "./perfil_whatsapp_firefox"

def iniciar_guardado_mensajes():
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)

    with sync_playwright() as p:
        print("Iniciando Firefox...")
        
        # CAMBIO AQUÍ: Usamos p.firefox en lugar de p.chromium
        context = p.firefox.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            args=["--start-maximized"]
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://web.whatsapp.com")
        
        print("Esperando a que WhatsApp Web cargue en Firefox... (Escanea el QR si es necesario)")
        
        try:
            page.wait_for_selector('[data-testid="chat-list"]', timeout=60000)
            print("¡Sesión iniciada con éxito en Firefox!")
        except Exception:
            print("Tiempo de espera agotado o QR no escaneado.")
            context.close()
            return

        print("Escuchando mensajes... Presiona Ctrl+C para salir.")
        ultimo_mensaje_guardado = ""

        try:
            while True:
                    # Buscamos tanto mensajes entrantes (in) como salientes (out)
                elementos_mensajes = page.query_selector_all('.message-in .copyable-text, .message-out .copyable-text')
                
                if elementos_mensajes:
                    ultimo_elemento = elementos_mensajes[-1]
                    info_meta = ultimo_elemento.get_attribute('data-pre-plain-text')
                    texto_elemento = ultimo_elemento.query_selector('.selectable-text span')
                    
                    if texto_elemento and info_meta:
                        texto_mensaje = texto_elemento.inner_text()
                        mensaje_completo = f"{info_meta}{texto_mensaje}"
                        
                        if mensaje_completo != ultimo_mensaje_guardado:
                            ultimo_mensaje_guardado = mensaje_completo
                            
                            with open("historial_mensajes.txt", "a", encoding="utf-8") as archivo:
                                archivo.write(f"{mensaje_completo}\n")
                                
                            print(f"Guardado: {mensaje_completo}")
                
                time.sleep(3)
                
        except KeyboardInterrupt:
            print("\nDeteniendo el guardado...")
        finally:
            context.close()

if __name__ == "__main__":
    iniciar_guardado_mensajes()