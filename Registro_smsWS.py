import os
import time
import tempfile
import json
from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.join(tempfile.gettempdir(), "playwright_whatsapp_firefox")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHATS_BASE_DIR = os.path.join(SCRIPT_DIR, "chats")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat - {chat_name}</title>
    <style>
        body {{
            font-family: 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            background-color: #0b141a;
            color: #e9edef;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
        }}
        .chat-container {{
            width: 100%;
            max-width: 800px;
            background-color: #0b141a;
            background-image: url('https://user-images.githubusercontent.com/15075759/28719144-86dc0f70-73b1-11e7-911d-60d70fcded21.png');
            background-repeat: repeat;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            display: flex;
            flex-direction: column;
            gap: 10px;
            height: 90vh;
            overflow-y: auto;
            position: relative;
        }}
        .header {{
            background-color: #202c33;
            padding: 15px;
            text-align: center;
            border-radius: 8px;
            position: sticky;
            top: 0;
            z-index: 10;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            margin-bottom: 20px;
            font-size: 1.2em;
            font-weight: bold;
        }}
        .msg {{
            max-width: 75%;
            padding: 8px 12px;
            border-radius: 8px;
            position: relative;
            font-size: 0.95em;
            line-height: 1.4;
            word-wrap: break-word;
        }}
        .msg-in {{
            background-color: #202c33;
            align-self: flex-start;
            border-top-left-radius: 0;
        }}
        .msg-out {{
            background-color: #005c4b;
            align-self: flex-end;
            border-top-right-radius: 0;
        }}
        .meta {{
            font-size: 0.75em;
            color: #8696a0;
            margin-top: 4px;
            text-align: right;
            display: block;
        }}
        .sender {{
            font-size: 0.8em;
            font-weight: bold;
            color: #53bdeb;
            margin-bottom: 4px;
            display: block;
        }}
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="header">Chat con {chat_name}</div>
        <div id="messages"></div>
    </div>

    <script src="data.js"></script>
    <script>
        const container = document.getElementById('messages');
        mensajes.forEach(m => {{
            const div = document.createElement('div');
            div.className = 'msg ' + (m.is_outgoing ? 'msg-out' : 'msg-in');
            
            let html = '';
            if (!m.is_outgoing && m.sender) {{
                html += `<span class="sender">${{m.sender}}</span>`;
            }}
            html += `<span>${{m.texto.replace(/\\n/g, '<br>')}}</span>`;
            html += `<span class="meta">${{m.meta}}</span>`;
            
            div.innerHTML = html;
            container.appendChild(div);
        }});
        // Scroll al fondo
        const chatContainer = document.querySelector('.chat-container');
        chatContainer.scrollTop = chatContainer.scrollHeight;
    </script>
</body>
</html>
"""

def limpiar_nombre(nombre):
    return "".join([c for c in nombre if c.isalpha() or c.isdigit() or c==' ']).strip()

def inicializar_archivos_chat(chat_dir, chat_name):
    if not os.path.exists(chat_dir):
        os.makedirs(chat_dir)
        
    js_path = os.path.join(chat_dir, "data.js")
    if not os.path.exists(js_path):
        with open(js_path, "w", encoding="utf-8") as f:
            f.write("const mensajes = [];\n")
            
    html_path = os.path.join(chat_dir, "index.html")
    if not os.path.exists(html_path):
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(HTML_TEMPLATE.format(chat_name=chat_name))

def extraer_info(info_meta_raw):
    # Formato típico: "[12:34 p. m., 20/6/2026] Nombre:"
    try:
        if "]" in info_meta_raw:
            parts = info_meta_raw.split("]", 1)
            meta = parts[0].replace("[", "").strip()
            sender = parts[1].replace(":", "").strip()
            return meta, sender
    except Exception:
        pass
    return info_meta_raw, "Desconocido"

def iniciar_guardado_mensajes():
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)
        
    if not os.path.exists(CHATS_BASE_DIR):
        os.makedirs(CHATS_BASE_DIR)

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
                # 1. Obtener el nombre del chat actual
                # WhatsApp suele poner el nombre en el header
                header_title = page.query_selector('#main header [dir="auto"][title], #main header span[dir="auto"]')
                if header_title:
                    chat_name = header_title.get_attribute("title")
                    if not chat_name:
                        chat_name = header_title.inner_text()
                        
                    if chat_name:
                        chat_name_clean = limpiar_nombre(chat_name)
                        if chat_name_clean:
                            chat_dir = os.path.join(CHATS_BASE_DIR, chat_name_clean)
                            inicializar_archivos_chat(chat_dir, chat_name)
                            
                            # 2. Buscar mensajes
                            elementos_mensajes = page.query_selector_all('[data-pre-plain-text]')
                            if elementos_mensajes:
                                ultimo_elemento = elementos_mensajes[-1]
                                info_meta_raw = ultimo_elemento.get_attribute('data-pre-plain-text')
                                texto_mensaje = ultimo_elemento.inner_text()
                                
                                if texto_mensaje and info_meta_raw:
                                    texto_limpio = texto_mensaje.strip()
                                    mensaje_completo = f"{info_meta_raw} {texto_limpio}"
                                    
                                    if mensaje_completo != ultimo_mensaje_guardado:
                                        ultimo_mensaje_guardado = mensaje_completo
                                        
                                        meta_str, sender = extraer_info(info_meta_raw)
                                        
                                        # Determinar si el mensaje lo enviamos nosotros o lo recibimos
                                        # WhatsApp usa "true_" en el ID para mensajes enviados y "false_" para recibidos
                                        data_id = ultimo_elemento.evaluate("el => { const parent = el.closest('[data-id]'); return parent ? parent.getAttribute('data-id') : ''; }")
                                        is_outgoing = data_id.startswith("true_")
                                        
                                        msg_obj = {
                                            "meta": meta_str,
                                            "sender": sender,
                                            "texto": texto_limpio,
                                            "is_outgoing": is_outgoing
                                        }
                                        
                                        # Guardar en data.js
                                        js_path = os.path.join(chat_dir, "data.js")
                                        with open(js_path, "a", encoding="utf-8") as archivo:
                                            # Añadir un salto de linea al final para evitar errores
                                            archivo.write(f"mensajes.push({json.dumps(msg_obj, ensure_ascii=False)});\n")
                                            
                                        # Guardar en historial.txt (Respaldo)
                                        txt_path = os.path.join(chat_dir, "historial.txt")
                                        with open(txt_path, "a", encoding="utf-8") as archivo:
                                            archivo.write(f"{mensaje_completo}\n")
                                            
                                        print(f"\\n[NUEVO en '{chat_name}'] Guardado: {texto_limpio[:40]}...")
                                else:
                                    print(f"Mensaje sin texto detectado en {chat_name}.", end="\\r")
                            else:
                                print(f"Aún no hay mensajes en {chat_name}.", end="\\r")
                        else:
                            print("El chat actual no tiene un nombre válido para carpeta.", end="\\r")
                else:
                    print("Selecciona un chat en la lista de WhatsApp Web para empezar...", end="\\r")
                    
                time.sleep(3)
                
        except KeyboardInterrupt:
            print("\\nDeteniendo el guardado de mensajes de forma segura...")
        finally:
            try:
                context.close()
                print("Navegador cerrado correctamente.")
            except Exception:
                print("Proceso finalizado.")

if __name__ == "__main__":
    iniciar_guardado_mensajes()