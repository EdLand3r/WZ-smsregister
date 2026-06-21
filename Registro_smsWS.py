import os
import time
import tempfile
import json
import base64
import hashlib
from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.join(tempfile.gettempdir(), "playwright_whatsapp_firefox")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHATS_BASE_DIR = os.path.join(SCRIPT_DIR, "chats")

chat_media_hashes = {}

def get_chat_hashes(chat_dir):
    if chat_dir not in chat_media_hashes:
        hashes = {}
        media_folder = os.path.join(chat_dir, "media")
        if os.path.exists(media_folder):
            for filename in os.listdir(media_folder):
                filepath = os.path.join(media_folder, filename)
                if os.path.isfile(filepath):
                    with open(filepath, "rb") as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                        hashes[file_hash] = f"media/{filename}"
        chat_media_hashes[chat_dir] = hashes
    return chat_media_hashes[chat_dir]

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
        .media-content img, .media-content video {{
            max-width: 100%;
            border-radius: 8px;
            margin-top: 5px;
            margin-bottom: 5px;
            display: block;
            background-color: rgba(255,255,255,0.05);
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
            // Remitente
            if (!m.is_outgoing && m.sender) {{
                html += `<span class="sender">${{m.sender}}</span>`;
            }}
            
            // Multimedia
            if (m.media && m.media.length > 0) {{
                html += '<div class="media-content">';
                m.media.forEach(media => {{
                    if (media.tag === 'img') {{
                        html += `<img src="${{media.local_path}}" alt="Imagen recibida">`;
                    }} else if (media.tag === 'video') {{
                        html += `<video src="${{media.local_path}}" controls></video>`;
                    }}
                }});
                html += '</div>';
            }}
            
            // Texto
            if (m.texto) {{
                html += `<span>${{m.texto.replace(/\\n/g, '<br>')}}</span>`;
            }}
            
            // Metadatos (Hora)
            html += `<span class="meta">${{m.meta}}</span>`;
            
            div.innerHTML = html;
            container.appendChild(div);
        }});
        
        // Scroll al fondo al cargar
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
    try:
        if "]" in info_meta_raw:
            parts = info_meta_raw.split("]", 1)
            meta = parts[0].replace("[", "").strip()
            sender = parts[1].replace(":", "").strip()
            return meta, sender
    except Exception:
        pass
    return info_meta_raw, "Desconocido"

def descargar_media(page, url, chat_dir, idx):
    js_code = """
    async (url) => {
        try {
            const response = await fetch(url);
            const blob = await response.blob();
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onloadend = () => {
                    resolve({
                        data: reader.result.split(',')[1],
                        type: blob.type
                    });
                };
                reader.onerror = reject;
                reader.readAsDataURL(blob);
            });
        } catch (e) {
            return null;
        }
    }
    """
    media_result = page.evaluate(js_code, url)
    if media_result and media_result.get('data'):
        file_bytes = base64.b64decode(media_result['data'])
        file_hash = hashlib.md5(file_bytes).hexdigest()
        
        hashes = get_chat_hashes(chat_dir)
        if file_hash in hashes:
            print("  -> ¡Sticker/Media duplicado detectado! Omitiendo descarga para ahorrar espacio.")
            return hashes[file_hash]

        ext = ".bin"
        mime = media_result.get('type', '')
        if 'video' in mime: ext = '.mp4'
        elif 'webp' in mime: ext = '.webp'
        elif 'png' in mime: ext = '.png'
        elif 'image' in mime: ext = '.jpg'
        
        filename = f"media_{int(time.time())}_{idx}_{file_hash[:6]}{ext}"
        media_folder = os.path.join(chat_dir, "media")
        os.makedirs(media_folder, exist_ok=True)
        filepath = os.path.join(media_folder, filename)
        
        # Guardar archivo binario
        with open(filepath, "wb") as f:
            f.write(file_bytes)
            
        local_path = f"media/{filename}"
        hashes[file_hash] = local_path
        return local_path
    return None

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

        print("Escuchando mensajes multimedia y de texto... Presiona Ctrl+C para salir.")
        ultimo_mensaje_id = ""

        try:
            while True:
                header_title = page.query_selector('#main header [dir="auto"][title], #main header span[dir="auto"]')
                if header_title:
                    chat_name = header_title.get_attribute("title") or header_title.inner_text()
                    if chat_name:
                        chat_name_clean = limpiar_nombre(chat_name)
                        if chat_name_clean:
                            chat_dir = os.path.join(CHATS_BASE_DIR, chat_name_clean)
                            inicializar_archivos_chat(chat_dir, chat_name)
                            
                            # Buscar mensajes. Usamos un selector general (role="row") porque los stickers 
                            # sin texto no siempre tienen el atributo data-pre-plain-text
                            elementos_mensajes = page.query_selector_all('[role="row"]')
                            if elementos_mensajes:
                                ultimo_elemento = elementos_mensajes[-1]
                                
                                # Primero, sacamos SOLO el ID de manera rápida para saber si es nuevo
                                msg_id = ultimo_elemento.evaluate("el => { const c = el.querySelector('[data-id]') || el; return c ? c.getAttribute('data-id') : ''; }")
                                
                                # Ignorar filas de sistema (fechas) que no tienen data-id
                                if msg_id and msg_id != ultimo_mensaje_id:
                                    # ¡NUEVO MENSAJE DETECTADO!
                                    # Hacemos una pausa de 2 segundos antes de extraer los datos.
                                    time.sleep(2)
                                    
                                    # CRÍTICO: WhatsApp Web destruye y recrear los nodos HTML cuando el video
                                    # termina de cargar. Tenemos que volver a buscar el elemento en el DOM actualizado.
                                    fila_actualizada = page.query_selector(f'[data-id="{msg_id}"]')
                                    if not fila_actualizada:
                                        # Si no lo encuentra por ID (raro), buscamos el último nuevamente
                                        filas_nuevas = page.query_selector_all('[role="row"]')
                                        fila_actualizada = filas_nuevas[-1] if filas_nuevas else ultimo_elemento
                                        
                                    # Extraer datos usando JS ahora que ya cargó y tenemos el nodo fresco
                                    js_extractor = """el => {
                                        const row = el.closest('[role="row"]') || el;
                                        // 2. Obtener metadatos y texto (si existen)
                                        const textContainer = row.querySelector('[data-pre-plain-text]');
                                        const infoMetaRaw = textContainer ? textContainer.getAttribute('data-pre-plain-text') : '';
                                        const textoMensaje = textContainer ? textContainer.innerText : '';
                                        
                                        // 3. Extraer multimedia (ignorando emojis)
                                        const mediaNodes = row.querySelectorAll('img:not([data-plain-text]):not(.selectable-text), video');
                                        const mediaUrls = [];
                                        
                                        // DEBUG: Extraer todos los img y video sin filtros
                                        const allMediaDebug = Array.from(row.querySelectorAll('img, video')).map(n => n.outerHTML);
                                        
                                        mediaNodes.forEach(n => {
                                            let url = n.src;
                                            if (n.tagName.toLowerCase() === 'video' && !url) {
                                                const source = n.querySelector('source');
                                                if (source) url = source.src;
                                            }
                                            
                                            if (url && (url.startsWith('blob:') || url.startsWith('data:image/') || url.startsWith('data:video/'))) {
                                                mediaUrls.push({ tag: n.tagName.toLowerCase(), src: url });
                                            }
                                        });
                                        
                                        return { infoMetaRaw, textoMensaje, mediaUrls, allMediaDebug, htmlDump: row.outerHTML };
                                    }"""
                                    
                                    data_info = fila_actualizada.evaluate(js_extractor)
                                    ultimo_mensaje_id = msg_id
                                    
                                    # Extraer texto y metadata
                                    info_meta_raw = data_info.get("infoMetaRaw", "")
                                    texto_mensaje = data_info.get("textoMensaje", "")
                                    texto_limpio = texto_mensaje.strip()
                                    
                                    meta_str, sender = extraer_info(info_meta_raw) if info_meta_raw else ("", "")
                                    is_outgoing = msg_id.startswith("true_")
                                    
                                    # Procesar Multimedia
                                    media_list = []
                                    media_urls = data_info.get("mediaUrls", [])
                                    
                                    # --- PARCHE PARA VIDEOS (Click to load) ---
                                    # WhatsApp Web ya no pone el <video> en el chat, solo pone fondos de imagen.
                                    # Tenemos que simular un clic para abrirlo, robar el link, y cerrarlo.
                                    video_div = fila_actualizada.query_selector('[data-testid="video-content"]')
                                    if video_div:
                                        try:
                                            video_div.click()
                                            # Esperamos hasta 4 segundos a que el reproductor inyecte el video real
                                            video_real = page.wait_for_selector('video[src^="blob:"]', timeout=4000)
                                            if video_real:
                                                v_src = video_real.get_attribute("src")
                                                if v_src and not any(m.get("src") == v_src for m in media_urls):
                                                    media_urls.append({"tag": "video", "src": v_src})
                                        except Exception:
                                            pass
                                        finally:
                                            # Cerramos el reproductor pulsando Escape
                                            page.keyboard.press("Escape")
                                            time.sleep(0.5)
                                            
                                    all_media_debug = data_info.get("allMediaDebug", [])
                                    
                                    if media_urls:
                                        print(f"Descargando {len(media_urls)} archivo(s) multimedia...")
                                        for idx, m in enumerate(media_urls):
                                            local_path = descargar_media(page, m["src"], chat_dir, idx)
                                            if local_path:
                                                media_list.append({
                                                    "tag": m["tag"],
                                                    "local_path": local_path
                                                })
                                    elif all_media_debug:
                                        print(f"\\n[DEBUG INFO] Se encontró media pero los filtros la ignoraron. Etiquetas HTML encontradas:")
                                        for tag in all_media_debug:
                                            # Limitar a 150 caracteres para no llenar la consola si es data:image
                                            print(f" -> {tag[:150]}...")
                                            
                                    if not media_urls and not texto_limpio:
                                        html_dump = data_info.get("htmlDump", "")
                                        debug_path = os.path.join(chat_dir, "debug_row.html")
                                        with open(debug_path, "w", encoding="utf-8") as f:
                                            f.write(html_dump)
                                        print(f"\\n[SISTEMA] He guardado un reporte técnico en: {debug_path}")
                                    
                                    msg_obj = {
                                        "meta": meta_str,
                                        "sender": sender,
                                        "texto": texto_limpio,
                                        "is_outgoing": is_outgoing,
                                        "media": media_list
                                    }
                                    
                                    # Guardar en data.js
                                    js_path = os.path.join(chat_dir, "data.js")
                                    with open(js_path, "a", encoding="utf-8") as archivo:
                                        archivo.write(f"mensajes.push({json.dumps(msg_obj, ensure_ascii=False)});\n")
                                        
                                    # Guardar en historial.txt (Solo texto y aviso de media)
                                    txt_path = os.path.join(chat_dir, "historial.txt")
                                    with open(txt_path, "a", encoding="utf-8") as archivo:
                                        media_aviso = f" [+ {len(media_list)} archivo(s) multimedia]" if media_list else ""
                                        archivo.write(f"{info_meta_raw} {texto_limpio}{media_aviso}\n")
                                        
                                    log_texto = texto_limpio[:30] + "..." if texto_limpio else "[Media]"
                                    print(f"\\n[NUEVO en '{chat_name}'] Guardado: {log_texto}")
                            else:
                                print(f"Aún no hay mensajes en {chat_name}.", end="\\r")
                        else:
                            print("El chat actual no tiene un nombre válido para carpeta.", end="\\r")
                else:
                    print("Selecciona un chat en la lista de WhatsApp Web para empezar...", end="\\r")
                    
                time.sleep(3)
                
        except KeyboardInterrupt:
            print("\\nDeteniendo de forma segura...")
        finally:
            try:
                context.close()
                print("Navegador cerrado.")
            except Exception:
                pass

if __name__ == "__main__":
    iniciar_guardado_mensajes()