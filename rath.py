import flet as ft
from pathlib import Path
import json, threading, yt_dlp, platform
import time
import os
import sys
import os

def obtener_ruta_ffmpeg():
    # Si se ejecuta como .exe empaquetado
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, "bin")

CONF_FILE = Path.home() / ".RATH" / "conf.json"
CONF_FILE.parent.mkdir(exist_ok=True, parents=True)
DEFAULTS = {
    "folder": str(Path.home() / "Downloads"), 
    "format": "video",
    "video_quality": "best_mp4",
    "audio_quality": "mp3_192",
    "accent_color": "#FF6B35",  # ← Añadido
}

def cargar_config():
    """Carga la configuración del archivo."""
    try:
        c = json.loads(CONF_FILE.read_text())
        return {**DEFAULTS, **c}
    except:
        return DEFAULTS.copy()

def guardar_config(config):
    """Guarda la configuración en el archivo."""
    CONF_FILE.write_text(json.dumps(config, indent=4))

# --- 2. Lógica de Descarga (FFmpeg incluido) ---
descargando = False
bloqueo_descarga = threading.Lock()

def descargar(page, url, config, barra, texto, aviso, color_acento, boton_descarga):
    """Ejecuta la descarga en un hilo separado."""
    global descargando
    
    with bloqueo_descarga:
        if descargando:
            aviso.content = ft.Row([
                ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400),
                ft.Text("Ya hay una descarga en curso.")
            ])
            aviso.open = True
            page.update()
            return
        descargando = True

    carpeta = Path(config["folder"])
    carpeta.mkdir(exist_ok=True)
    plantilla = str(carpeta / "%(title)s.%(ext)s")

    def hook(d, barra, texto, page):
        if d["status"] == "downloading":
            barra.visible = True
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            done = d.get("downloaded_bytes", 0)
            percent = d.get("_percent_str", "0%")
            done_mb = round(done / (1024 * 1024), 2)
            total_mb = round(total / (1024 * 1024), 2) if total > 0 else 0
            texto.value = f"{percent} ({done_mb}MB/{total_mb}MB)"
            barra.value = done / total if total else None
        elif d["status"] == "finished":
            texto.value = "Descarga finalizada ✓"
        page.update()

    ydl_opts = {
        "outtmpl": plantilla,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "progress_hooks": [lambda d: hook(d, barra, texto, page)]
    }
    ydl_opts["ffmpeg_location"] = obtener_ruta_ffmpeg()
    
    if config["format"] == "video":
        if config["video_quality"] == "best_mp4":
            ydl_opts["format"] = "best[ext=mp4]/best[ext=webm]/best"
        elif config["video_quality"] == "720p":
            ydl_opts["format"] = "best[height<=720]/best[ext=mp4]/best"
        elif config["video_quality"] == "480p":
            ydl_opts["format"] = "best[height<=480]/best[ext=mp4]/best"
        elif config["video_quality"] == "360p":
            ydl_opts["format"] = "best[height<=360]/best[ext=mp4]/best"
        ydl_opts["merge_output_format"] = "mp4"
    else:
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3" if "mp3" in config["audio_quality"] else "flac",
            "preferredquality": config["audio_quality"].split('_')[-1] if "mp3" in config["audio_quality"] else "192"
        }]

    def actualizar_ui_al_finalizar():
        global descargando
        barra.visible = False
        boton_descarga.disabled = False
        boton_descarga.text = "DESCARGAR"
        boton_descarga.bgcolor = color_acento
        descargando = False
        page.update()

    try:
        texto.value = "Conectando..."
        barra.visible = True
        boton_descarga.disabled = True
        boton_descarga.text = "DESCARGANDO..."
        boton_descarga.bgcolor = ft.Colors.GREY_700
        page.update()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            texto.value = "Descargando metadata..."
            page.update()
            ydl.download([url])
        aviso.content = ft.Row([
            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=ft.Colors.GREEN_400),
            ft.Text("Descarga completada.", weight=ft.FontWeight.BOLD)
        ])
        aviso.open = True
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "ffprobe" in error_msg.lower() or "ffmpeg" in error_msg.lower():
            texto.value = f"Error: FFmpeg no encontrado. Necesario para {config['format']}."
            aviso.content = ft.Row([
                ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400),
                ft.Text("ERROR: Falta FFmpeg (Post-procesamiento).")
            ])
        else:
            texto.value = f"Error de Descarga: {e}"
            aviso.content = ft.Row([
                ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400),
                ft.Text("ERROR: Revisa el link.")
            ])
        aviso.open = True
    except Exception as e:
        texto.value = f"Error inesperado: {e}"
        aviso.content = ft.Row([
            ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400),
            ft.Text("ERROR: Un error inesperado ocurrió.")
        ])
        aviso.open = True
    finally:
        page.run_thread(actualizar_ui_al_finalizar)

# --- 3. Vistas de la Aplicación ---

def pantalla_inicio(page):
    anillo_progreso = ft.ProgressRing(color=ft.Colors.WHITE, width=20, height=20)
    texto_cargando = ft.Text("Cargando RATH", size=16, color=ft.Colors.WHITE)
    contenedor = ft.Container(
        content=ft.Column(
            [
                ft.Row([ft.Icon(ft.Icons.VIDEO_LIBRARY_ROUNDED, size=64, color=ft.Colors.WHITE)], alignment=ft.MainAxisAlignment.CENTER),
                texto_cargando,
                anillo_progreso,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20
        ),
        expand=True,
        alignment=ft.alignment.center,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_center,
            end=ft.alignment.bottom_center,
            colors=["#1a1a1a", "#2d2d2d"]
        )
    )
    return contenedor

def inicio(page, config, aviso, color_acento, ref_boton_descarga):
    entrada_url = ft.TextField(
        label="Link de YouTube", 
        expand=True, 
        border_radius=12,
        prefix_icon=ft.Icons.LINK_ROUNDED,
        bgcolor=ft.Colors.WHITE10,
        border_color=ft.Colors.WHITE24,
        focused_border_color=color_acento,
        color=ft.Colors.WHITE,
        label_style=ft.TextStyle(color=ft.Colors.WHITE70),
        height=50
    )
    barra = ft.ProgressBar(
        visible=False,
        color=color_acento,
        bgcolor=ft.Colors.WHITE12,
        height=6,
        border_radius=4
    )
    texto_estado = ft.Text(size=14, opacity=0.8)

    selector = ft.SegmentedButton(
        selected={config["format"]},
        on_change=lambda e: config.update(format=e.control.selected.pop()),
        segments=[
            ft.Segment("video", ft.Text("🎬 Video")),
            ft.Segment("audio", ft.Text("🎵 Audio (MP3/FLAC)"))
        ],
    )

    texto_carpeta_actual = ft.Text(
        f"📁 Carpeta de Destino: {config['folder']}",
        size=12,
        color=ft.Colors.WHITE70,
        selectable=True
    )

    def iniciar_descarga(_):
        if not entrada_url.value:
            entrada_url.error_text = "Link vacío"
            page.update()
            return
        entrada_url.error_text = None
        threading.Thread(
            target=descargar,
            args=(page, entrada_url.value, config, barra, texto_estado, aviso, color_acento, ref_boton_descarga["btn"]),
            daemon=True
        ).start()

    boton_descarga = ft.ElevatedButton(
        "DESCARGAR", 
        on_click=iniciar_descarga, 
        expand=True, 
        height=50, 
        bgcolor=color_acento, 
        color=ft.Colors.BLACK,
        elevation=2,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
        )
    )
    ref_boton_descarga["btn"] = boton_descarga  # Guardar referencia

    contenido = ft.Column([
        ft.Text("RATH", size=34, weight=ft.FontWeight.BOLD, color=color_acento),
        ft.Text("Descarga rápida y elegante", size=12, color=ft.Colors.WHITE60),
        ft.Divider(height=10, color=ft.Colors.WHITE24),
        entrada_url,
        selector,
        ft.Container(texto_carpeta_actual, padding=ft.padding.only(top=10, bottom=10)),
        boton_descarga,
        barra,
        texto_estado
    ], spacing=28, horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.ADAPTIVE)

    return ft.Container(
        content=ft.Card(
            content=ft.Container(contenido, padding=24),
            color=ft.Colors.BLACK26
        ),
        padding=20,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_center,
            end=ft.alignment.bottom_center,
            colors=["#1a1a1a", "#2d2d2d"]
        ),
        expand=True,
        visible=True
    )

def ajustes(page, config, color_acento, on_accent_change):
    campo_ruta = ft.TextField(
        label="Ruta de Descarga", 
        value=config["folder"], 
        expand=True,
        hint_text="Introduce la ruta o edita la existente",
        prefix_icon=ft.Icons.FOLDER_OPEN_ROUNDED,
        bgcolor=ft.Colors.BLACK38,
        filled=True,
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=color_acento,
        color=ft.Colors.WHITE,
        label_style=ft.TextStyle(color=ft.Colors.WHITE70),
        border_radius=12
    )

    desplegable_calidad_video = ft.Dropdown(
        label="Calidad de Video",
        filled=True,
        bgcolor=ft.Colors.BLACK,
        focused_border_color=color_acento,
        color=ft.Colors.WHITE,
        label_style=ft.TextStyle(color=ft.Colors.WHITE70),
        border_radius=12,
        options=[
            ft.dropdown.Option("best_mp4", "Mejor calidad MP4"),
            ft.dropdown.Option("720p", "HD 720p"),
            ft.dropdown.Option("480p", "480p"),
            ft.dropdown.Option("360p", "360p")
        ],
        value=config.get("video_quality", "best_mp4"),
        on_change=lambda e: config.update(video_quality=e.control.value),
    )

    desplegable_calidad_audio = ft.Dropdown(
        label="Calidad de Audio (Requiere FFmpeg)",
        filled=True,
        bgcolor=ft.Colors.BLACK,
        focused_border_color=color_acento,
        color=ft.Colors.WHITE,
        label_style=ft.TextStyle(color=ft.Colors.WHITE70),
        border_radius=12,
        options=[
            ft.dropdown.Option("mp3_192", "MP3 192kbps (Estándar)"),
            ft.dropdown.Option("mp3_320", "MP3 320kbps (Alta Calidad)"),
            ft.dropdown.Option("flac", "FLAC (Sin Pérdida)")
        ],
        value=config["audio_quality"],
        on_change=lambda e: config.update(audio_quality=e.control.value),
    )


    def guardar(_):
        config["folder"] = campo_ruta.value
        guardar_config(config)
        aviso = ft.SnackBar(
            content=ft.Row([
                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, color=ft.Colors.GREEN_400),
                ft.Text("Configuración guardada correctamente.",color="white")
            ], spacing=10),
            bgcolor=ft.Colors.BLACK54,
            duration=3000
        )
        page.open(aviso)
        page.update()


    def abrir_carpeta_descargas(_):
        ruta_carpeta = Path(config["folder"])
        try:
            if platform.system() == "Windows":
                os.startfile(ruta_carpeta)
            elif platform.system() == "Darwin":
                os.system(f'open "{ruta_carpeta}"')
            else:
                os.system(f'xdg-open "{ruta_carpeta}"')
        except Exception as e:
            print(f"Error al abrir carpeta: {e}")

    boton_abrir_carpeta = ft.ElevatedButton(
        "Abrir Carpeta de Descargas",
        icon=ft.Icons.FOLDER_OPEN_OUTLINED,
        on_click=abrir_carpeta_descargas,
        expand=True,
        height=45,
        bgcolor=color_acento,
        color=ft.Colors.BLACK,
        elevation=2,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
        )
    )

    tarjeta_creditos = ft.Card(
        ft.Container(
            ft.Column([
                ft.Text("Informacion", weight=ft.FontWeight.W_500, size=16),
                ft.Divider(height=10, color=ft.Colors.WHITE24),
                ft.Row([
                    ft.Icon(ft.Icons.CODE_ROUNDED, color=color_acento, size=20),
                    ft.Text("Desarrollado en Python 3.12", size=14, color=ft.Colors.WHITE70)
                ], spacing=10),
                ft.Text("RATH - Descargador de YouTube con el poder de [Ytdlp]", size=12, color=ft.Colors.WHITE54, italic=True)
            ], spacing=12),
            padding=20
        ),
        color=ft.Colors.BLACK26,
        margin=ft.margin.only(top=20)
    )

    contenido = ft.Column([
        ft.Text("Ajustes Avanzados", size=24, weight=ft.FontWeight.BOLD, color=color_acento),
        ft.Divider(height=10, color=ft.Colors.WHITE24),
        ft.Card(ft.Container(ft.Column([ft.Text("Carpeta de Destino", weight=ft.FontWeight.W_500), campo_ruta], spacing=10), padding=15), color=ft.Colors.BLACK26),
        ft.Card(ft.Container(ft.Column([ft.Text("Calidad de Video", weight=ft.FontWeight.W_500), desplegable_calidad_video], spacing=10), padding=15), color=ft.Colors.BLACK26),
        ft.Card(ft.Container(ft.Column([ft.Text("Opciones de Audio", weight=ft.FontWeight.W_500), desplegable_calidad_audio], spacing=10), padding=15), color=ft.Colors.BLACK26),
        boton_abrir_carpeta,
        ft.ElevatedButton(
            "GUARDAR AJUSTES", 
            on_click=guardar, 
            expand=True, 
            height=50, 
            bgcolor=color_acento, 
            color=ft.Colors.BLACK,
            elevation=2,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        ),
        tarjeta_creditos
    ], spacing=16, scroll=ft.ScrollMode.ADAPTIVE)

    return ft.Container(
        content=contenido,
        padding=24, 
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_center,
            end=ft.alignment.bottom_center,
            colors=["#1a1a1a", "#2d2d2d"]
        ),
        expand=True,
        visible=True
    )


# --- 4. Función Principal ---
def main(page: ft.Page):
    page.title = "RATH PW"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#2d2d2d"
    page.padding = 0
    page.window.icon = "iconapp.ico"
    page.window.maximized = True

    config = cargar_config()
    aviso = ft.SnackBar(content=ft.Text(""), duration=4000, bgcolor=ft.Colors.BLACK87)
    page.snack_bar = aviso

    # Pantalla de carga
    splash = pantalla_inicio(page)
    page.add(splash)
    page.update()
    time.sleep(1.5)
    page.controls.clear()
    page.update()

    # Referencia para el botón de descarga (para actualizar desde otro hilo)
    ref_boton_descarga = {"btn": None}

    # Vistas
    vista_inicio = None
    vista_ajustes = None
    vista_actual = 0

    def cambiar_vista(ix):
        nonlocal vista_actual, vista_inicio, vista_ajustes
        vista_actual = ix
        color_acento = config["accent_color"]

        if vista_inicio is None:
            vista_inicio = inicio(page, config, aviso, color_acento, ref_boton_descarga)
        if vista_ajustes is None:
            vista_ajustes = ajustes(page, config, color_acento, lambda: cambiar_vista(vista_actual))

        vista_inicio.visible = (ix == 0)
        vista_ajustes.visible = (ix == 1)

        if stack.controls != [vista_inicio, vista_ajustes]:
            stack.controls = [vista_inicio, vista_ajustes]
        page.update()

    stack = ft.Stack(expand=True)
    nav = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_ROUNDED, label="Inicio"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_ROUNDED, label="Ajustes")
        ],
        on_change=lambda e: cambiar_vista(e.control.selected_index),
        bgcolor="#2d2d2d"
    )

    page.add(stack, nav)
    cambiar_vista(0)

if __name__ == "__main__":
    ft.app(target=main,assets_dir="assets")
