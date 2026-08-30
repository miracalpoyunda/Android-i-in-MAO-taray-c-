import os
import json
import uuid
import tempfile
import zipfile
import sqlite3
import logging
from urllib.parse import quote_plus
import flet as ft

# ==========================================
# 1. PROFESYONEL LOGLAMA SİSTEMİ
# ==========================================
def setup_logger():
    if not os.path.exists("logs"):
        os.makedirs("logs", exist_ok=True)
    log_obj = logging.getLogger("MAOMobileV2_1")
    log_obj.setLevel(logging.DEBUG)
    fh = logging.FileHandler("logs/mobile_v2_1.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    if not log_obj.handlers:
        log_obj.addHandler(fh)
        log_obj.addHandler(ch)
    return log_obj

logger = setup_logger()

# ==========================================
# 2. VERİTABANI YÖNETİCİSİ (SQLITE)
# ==========================================
class DatabaseManager:
    """Geçmiş, yer imleri ve kalıcı ayarları yöneten gelişmiş SQLite veritabanı yöneticisi."""
    def __init__(self):
        if not os.path.exists("data"):
            os.makedirs("data", exist_ok=True)
        self.db_path = "data/browser_v2_1.db"
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        url TEXT,
                        visit_time DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS bookmarks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        url TEXT,
                        added_time DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                conn.commit()
            logger.info("Veritabanı tabloları başarıyla oluşturuldu.")
        except Exception as e:
            logger.error(f"Veritabanı başlatma hatası: {e}")

    def add_history(self, title, url):
        if not url or url.startswith("mao://") or url.startswith("file://"): return
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO history (title, url) VALUES (?, ?)", (title or url, url))
                conn.commit()
        except Exception as e:
            logger.error(f"Geçmiş ekleme hatası: {e}")

    def get_history(self, limit=100):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title, url, visit_time FROM history ORDER BY visit_time DESC LIMIT ?", (limit,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Geçmiş okuma hatası: {e}")
            return []

    def clear_history(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM history")
                conn.commit()
        except Exception as e:
            logger.error(f"Geçmiş temizleme hatası: {e}")

    def add_bookmark(self, title, url):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM bookmarks WHERE url = ?", (url,))
                if cursor.fetchone():
                    return False, "Bu sayfa zaten yer imlerinde!"
                cursor.execute("INSERT INTO bookmarks (title, url) VALUES (?, ?)", (title or url, url))
                conn.commit()
                return True, "Yer imi eklendi."
        except Exception as e:
            logger.error(f"Yer imi ekleme hatası: {e}")
            return False, str(e)

    def get_bookmarks(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, title, url, added_time FROM bookmarks ORDER BY added_time DESC")
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Yer imi okuma hatası: {e}")
            return []

    def delete_bookmark(self, bookmark_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Yer imi silme hatası: {e}")

    def get_setting(self, key, default="true"):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row[0] if row else default
        except Exception as e:
            logger.error(f"Ayar okuma hatası ({key}): {e}")
            return default

    def save_setting(self, key, value):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
                conn.commit()
        except Exception as e:
            logger.error(f"Ayar kaydetme hatası ({key}): {e}")

# ==========================================
# 3. GELİŞMİŞ REKLAM ENGELLEYİCİ
# ==========================================
class AdvancedAdBlocker:
    """URL filtreleme ve DOM element gizleme betikleri barındıran engelleyici."""
    def __init__(self):
        self.enabled = True
        self.blocked_domains = [
            "doubleclick.net", "googleadservices.com", "googlesyndication.com",
            "adservice.google.com", "ads.youtube.com", "s.youtube.com/api/stats/ads",
            "adsystem.com", "amazon-adsystem.com", "adnxs.com",
            "criteo.com", "taboola.com", "outbrain.com", "pubmatic.com",
            "rubiconproject.com", "ads-twitter.com", "analytics.google.com",
            "google-analytics.com", "popads.net", "adsterra.com",
            "propellerads.com", "yandex.ru/ads", "ads.yahoo.com",
            "facebook.com/tr", "hotjar.com"
        ]
        
    def is_ad(self, url):
        if not self.enabled: return False
        url_lower = url.lower()
        for domain in self.blocked_domains:
            if domain in url_lower:
                return True
        return False

    def get_element_hiding_js(self):
        """Sayfa içi standart reklam elementlerini (banner, pop-up) gizlemek için CSS/DOM enjeksiyonu."""
        return """
        (function() {
            const adSelectors = [
                'iframe[src*="ad"]', 'div[id*="google_ads"]', 'ins.adsbygoogle',
                'div[class*="banner-ad"]', 'div[class*="sponsored"]', 'div[id*="banner-ad"]'
            ];
            adSelectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => {
                    el.style.display = 'none';
                });
            });
        })();
        """

# ==========================================
# 4. GÜVENLİ UZANTI YÖNETİCİSİ
# ==========================================
class MobileExtensionManager:
    """Güvenli ZIP ayıklama, path traversal koruması ve manifest doğrulama mekanizmalı uzantı yöneticisi."""
    def __init__(self):
        self.extensions = {} 

    def load_from_zip(self, zip_path):
        try:
            temp_dir = tempfile.mkdtemp(prefix="mao_m_ext_")
            abs_temp_dir = os.path.abspath(temp_dir)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    member_path = os.path.abspath(os.path.join(abs_temp_dir, member))
                    # Güvenlik Kontrolü: os.path.commonpath kullanarak path traversal engelleme
                    try:
                        common = os.path.commonpath([abs_temp_dir, member_path])
                        if common != abs_temp_dir:
                            return False, "Güvenlik Hatası: Tehlikeli ZIP yolu (Path Traversal) tespit edildi!"
                    except ValueError:
                        return False, "Güvenlik Hatası: Geçersiz dosya yolu!"
                zip_ref.extractall(abs_temp_dir)
            return self.load_from_folder(abs_temp_dir)
        except Exception as e:
            logger.error(f"ZIP uzantı açma hatası: {e}")
            return False, f"ZIP Hatası: {str(e)}"

    def load_from_folder(self, folder_path):
        manifest_path = os.path.join(folder_path, "manifest.json")
        abs_folder_path = os.path.abspath(folder_path)
        if not os.path.exists(manifest_path):
            return False, "Klasörde manifest.json bulunamadı!"
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            if "content_scripts" not in manifest and "background" not in manifest:
                return False, "Uzantı geçerli bir 'content_scripts' veya betik içermiyor."

            ext_id = str(uuid.uuid4()).replace("-", "")[:16] 
            ext_name = manifest.get('name', 'Bilinmeyen Uzantı')
            
            ext_data = {
                "id": ext_id,
                "name": ext_name,
                "version": manifest.get("version", "1.0"),
                "description": manifest.get("description", ""),
                "enabled": True,
                "js_codes": []
            }

            if "content_scripts" in manifest:
                for script_info in manifest["content_scripts"]:
                    for js_file in script_info.get("js", []):
                        js_path = os.path.abspath(os.path.join(abs_folder_path, js_file))
                        try:
                            common = os.path.commonpath([abs_folder_path, js_path])
                            if common != abs_folder_path:
                                logger.warning(f"Güvenlik uyarısı: Uzantı dosyası klasör dışına erişmeye çalıştı: {js_file}")
                                continue
                        except ValueError:
                            continue

                        if os.path.exists(js_path):
                            with open(js_path, "r", encoding="utf-8") as js_f:
                                ext_data["js_codes"].append(js_f.read())
            
            self.extensions[ext_id] = ext_data
            return True, f"'{ext_name}' başarıyla yüklendi."
        except Exception as e:
            return False, f"Uzantı yükleme hatası: {str(e)}"

# ==========================================
# 5. GÜVENLİ WEBVIEW VE SEKME MİMARİSİ
# ==========================================
class SafeWebView:
    """Masaüstü geliştirme ortamında çökme yaşamamak için güvenli WebView sarmalayıcısı."""
    def __init__(self, initial_url, on_start, on_end, on_error):
        self._url = initial_url
        self._visible = True
        try:
            self.control = ft.WebView(
                url=initial_url,
                expand=True,
                on_page_started=on_start,
                on_page_ended=on_end,
                on_web_resource_error=on_error
            )
            self.is_real = True
        except Exception as e:
            logger.warning(f"Masaüstü WebView simülasyona alındı: {e}")
            self.is_real = False
            self.control = ft.Container(
                expand=True,
                bgcolor=ft.Colors.SURFACE_VARIANT,
                alignment=ft.alignment.center,
                content=ft.Column([
                    ft.Icon(ft.Icons.PHONE_ANDROID, size=64, color=ft.Colors.PRIMARY),
                    ft.Text("MAO Mobil Tarayıcı V2.1 Simülatörü", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text("WebView sadece Mobil cihazlarda yerel çalışır.", color=ft.Colors.GREY_700),
                    ft.Text(f"Hedef URL: {initial_url}", size=12, color=ft.Colors.BLUE, italic=True)
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            )

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value):
        self._visible = value
        self.control.visible = value

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, val):
        self._url = val
        if self.is_real:
            try:
                self.control.url = val
            except:
                pass

    def reload(self):
        if self.is_real:
            try:
                self.control.reload()
            except:
                pass

    def evaluate_javascript(self, code):
        if self.is_real:
            try:
                self.control.evaluate_javascript(code)
            except:
                pass

class BrowserTab:
    """Çoklu sekme mimarisi için sekme sınıfı."""
    def __init__(self, initial_url="https://www.google.com", on_start=None, on_end=None, on_error=None):
        self.id = str(uuid.uuid4())
        self.url = initial_url
        self.history_stack = [initial_url]
        self.history_index = 0
        self.title = "Yeni Sekme"
        self.webview = SafeWebView(initial_url, on_start, on_end, on_error)

# ==========================================
# 6. ANA UYGULAMA MİMARİSİ
# ==========================================
def main(page: ft.Page):
    page.title = "MAO Tarayıcı V2.1 Mobil"
    page.padding = 0
    page.window_width = 420
    page.window_height = 850
    page.bgcolor = ft.Colors.BACKGROUND

    db = DatabaseManager()
    adblocker = AdvancedAdBlocker()
    ext_manager = MobileExtensionManager()

    # Veritabanından kalıcı ayarları yükle
    saved_adblock = db.get_setting("adblock_enabled", "true") == "true"
    adblocker.enabled = saved_adblock

    saved_theme = db.get_setting("dark_mode", "false") == "true"
    page.theme_mode = ft.ThemeMode.DARK if saved_theme else ft.ThemeMode.LIGHT

    tabs = []
    current_tab_index = 0

    def get_current_tab():
        if not tabs:
            raise RuntimeError("Aktif sekme bulunamadı.")
        return tabs[current_tab_index]

    def show_toast(message, icon=ft.Icons.INFO):
        snack = ft.SnackBar(
            content=ft.Row([ft.Icon(icon, color=ft.Colors.WHITE), ft.Text(message)]),
            bgcolor=ft.Colors.ON_SURFACE,
            behavior=ft.SnackBarBehavior.FLOATING,
            shape=ft.RoundedRectangleBorder(radius=10),
            duration=2000
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()

    progress_bar = ft.ProgressBar(width=page.width, visible=False, color=ft.Colors.BLUE)
    
    url_input = ft.TextField(
        value="https://www.google.com",
        hint_text="Arayın veya URL girin...",
        expand=True,
        height=45,
        content_padding=ft.padding.only(left=15, right=15, top=5, bottom=5),
        border_radius=25,
        text_size=15,
        bgcolor=ft.Colors.SURFACE_VARIANT,
        border_color=ft.Colors.TRANSPARENT,
        on_submit=lambda e: navigate(url_input.value)
    )

    extensions_view = ft.Column(visible=False, expand=True, scroll=ft.ScrollMode.AUTO, padding=20)
    history_view = ft.Column(visible=False, expand=True, scroll=ft.ScrollMode.AUTO, padding=20)
    bookmarks_view = ft.Column(visible=False, expand=True, scroll=ft.ScrollMode.AUTO, padding=20)
    downloads_view = ft.Column(visible=False, expand=True, padding=20)
    settings_view = ft.Column(visible=False, expand=True, scroll=ft.ScrollMode.AUTO, padding=20)
    tabs_view = ft.Column(visible=False, expand=True, scroll=ft.ScrollMode.AUTO, padding=20)

    main_content = ft.Stack(expand=True, controls=[])

    def on_page_load_start(tab_obj, url):
        if tab_obj == get_current_tab():
            url_input.value = url
            progress_bar.visible = True
            page.update()

    def on_page_load_end(tab_obj, url):
        progress_bar.visible = False
        tab_obj.url = url
        tab_obj.title = url
        db.add_history(tab_obj.title, url)
        
        # Reklam engelleyici gizleme scripti
        tab_obj.webview.evaluate_javascript(adblocker.get_element_hiding_js())
        
        # Uzantı scriptlerini enjekte et
        for ext in ext_manager.extensions.values():
            if ext["enabled"]:
                for js_code in ext["js_codes"]:
                    try:
                        tab_obj.webview.evaluate_javascript(js_code)
                    except Exception as e:
                        logger.error(f"Uzantı JS Hatası: {e}")
        
        if tab_obj == get_current_tab():
            url_input.value = url
            page.update()

    def create_new_tab(url="https://www.google.com"):
        nonlocal current_tab_index
        
        new_tab = None
        def handle_start(e):
            u = e.data if hasattr(e, 'data') else url
            on_page_load_start(new_tab, u)

        def handle_end(e):
            u = e.data if hasattr(e, 'data') else new_tab.url
            on_page_load_end(new_tab, u)

        def handle_error(e):
            show_toast("Sayfa yükleme hatası!", ft.Icons.ERROR)

        new_tab = BrowserTab(url, handle_start, handle_end, handle_error)
        tabs.append(new_tab)
        current_tab_index = len(tabs) - 1
        
        main_content.controls.insert(0, new_tab.webview.control)
        switch_view("browser")
        load_url(url)

    def navigate(url):
        tab = get_current_tab()
        url = url.strip()
        if not url: return

        if not url.startswith("http://") and not url.startswith("https://"):
            if "." in url and " " not in url:
                url = "https://" + url
            else:
                url = f"https://www.google.com/search?q={quote_plus(url)}"
                
        if adblocker.is_ad(url):
            show_toast("Reklam/İzleyici engellendi!", ft.Icons.SHIELD)
            return

        del tab.history_stack[tab.history_index + 1:]
        tab.history_stack.append(url)
        tab.history_index = len(tab.history_stack) - 1
        load_url(url)

    def load_url(url):
        tab = get_current_tab()
        tab.url = url
        url_input.value = url
        tab.webview.url = url
        switch_view("browser")
        page.update()

    def go_back(e):
        tab = get_current_tab()
        if tab.history_index > 0:
            tab.history_index -= 1
            load_url(tab.history_stack[tab.history_index])
        else:
            show_toast("En geridesiniz.", ft.Icons.WARNING)

    def go_forward(e):
        tab = get_current_tab()
        if tab.history_index < len(tab.history_stack) - 1:
            tab.history_index += 1
            load_url(tab.history_stack[tab.history_index])
        else:
            show_toast("En ileridesiniz.", ft.Icons.INFO)

    def add_current_to_bookmarks(e):
        tab = get_current_tab()
        success, msg = db.add_bookmark(tab.title, tab.url)
        show_toast(msg, ft.Icons.BOOKMARK if success else ft.Icons.WARNING)

    def on_file_picked(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            success, msg = ext_manager.load_from_zip(e.files[0].path)
            show_toast(msg, ft.Icons.CHECK_CIRCLE if success else ft.Icons.ERROR)
            if success:
                build_extensions_ui()

    file_picker = ft.FilePicker(on_result=on_file_picked)
    page.overlay.append(file_picker)

    def build_extensions_ui():
        extensions_view.controls.clear()
        extensions_view.controls.append(ft.Text("🧩 Uzantı Yöneticisi", size=24, weight=ft.FontWeight.BOLD))
        extensions_view.controls.append(ft.ElevatedButton("ZIP'ten Uzantı Yükle", icon=ft.Icons.UPLOAD_FILE, on_click=lambda _: file_picker.pick_files(allowed_extensions=["zip"])))
        extensions_view.controls.append(ft.Divider())

        if not ext_manager.extensions:
            extensions_view.controls.append(ft.Text("Henüz uzantı yüklenmedi.", color=ft.Colors.GREY))
            
        for ext_id, ext in ext_manager.extensions.items():
            def toggle_ext(e, eid=ext_id):
                ext_manager.extensions[eid]["enabled"] = e.control.value
                show_toast(f"Uzantı {'aktif' if e.control.value else 'devre dışı'}.")
                
            extensions_view.controls.append(
                ft.Card(elevation=2, content=ft.Container(padding=15, content=ft.Row([
                    ft.Column([
                        ft.Text(ext["name"], weight=ft.FontWeight.BOLD, size=16),
                        ft.Text(f"v{ext['version']} - {ext['description'][:40]}", size=12, color=ft.Colors.GREY_700)
                    ], expand=True),
                    ft.Switch(value=ext["enabled"], on_change=toggle_ext)
                ])))
            )
        page.update()

    def build_history_ui():
        history_view.controls.clear()
        history_view.controls.append(ft.Row([
            ft.Text("🕒 Geçmiş", size=24, weight=ft.FontWeight.BOLD),
            ft.IconButton(ft.Icons.DELETE_FOREVER, icon_color=ft.Colors.RED, tooltip="Temizle", 
                          on_click=lambda _: (db.clear_history(), build_history_ui(), show_toast("Geçmiş temizlendi.")))
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
        history_view.controls.append(ft.Divider())
        
        for title, url, time in db.get_history():
            history_view.controls.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.HISTORY),
                    title=ft.Text(url, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    subtitle=ft.Text(time, size=11),
                    on_click=lambda e, u=url: load_url(u)
                )
            )
        page.update()

    def build_bookmarks_ui():
        bookmarks_view.controls.clear()
        bookmarks_view.controls.append(ft.Text("⭐ Yer İmleri", size=24, weight=ft.FontWeight.BOLD))
        bookmarks_view.controls.append(ft.Divider())

        bmarks = db.get_bookmarks()
        if not bmarks:
            bookmarks_view.controls.append(ft.Text("Henüz yer imi kaydedilmedi.", color=ft.Colors.GREY))

        for bid, title, url, time in bmarks:
            def delete_b(e, b_id=bid):
                db.delete_bookmark(b_id)
                build_bookmarks_ui()
                show_toast("Yer imi silindi.")

            bookmarks_view.controls.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.BOOKMARK, color=ft.Colors.AMBER),
                    title=ft.Text(title or url, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    subtitle=ft.Text(url, size=11, color=ft.Colors.BLUE),
                    trailing=ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED, on_click=delete_b),
                    on_click=lambda e, u=url: load_url(u)
                )
            )
        page.update()

    downloads_view.controls = [
        ft.Text("📥 İndirmeler", size=24, weight=ft.FontWeight.BOLD),
        ft.Divider(),
        ft.Text("Mobil cihazınızdaki tüm dosyalar sistem indirme yöneticisine kaydedilir.", color=ft.Colors.GREY),
        ft.Icon(ft.Icons.DOWNLOAD_DONE, size=80, color=ft.Colors.GREEN)
    ]

    def build_settings_ui():
        settings_view.controls.clear()
        settings_view.controls.append(ft.Text("⚙️ Ayarlar", size=24, weight=ft.FontWeight.BOLD))
        settings_view.controls.append(ft.Divider())
        
        def toggle_adblock(e):
            adblocker.enabled = e.control.value
            db.save_setting("adblock_enabled", str(adblocker.enabled).lower())
            show_toast(f"Reklam Engelleyici {'Açık' if adblocker.enabled else 'Kapalı'}")

        def toggle_theme(e):
            is_dark = e.control.value
            page.theme_mode = ft.ThemeMode.DARK if is_dark else ft.ThemeMode.LIGHT
            db.save_setting("dark_mode", str(is_dark).lower())
            page.update()

        settings_view.controls.append(
            ft.Switch(label="Gelişmiş Reklam & İzleyici Engelleyici", value=adblocker.enabled, on_change=toggle_adblock)
        )
        settings_view.controls.append(
            ft.Switch(label="Koyu Tema (Dark Mode)", value=(page.theme_mode == ft.ThemeMode.DARK), on_change=toggle_theme)
        )
        settings_view.controls.append(ft.Divider())
        settings_view.controls.append(ft.Text("MAO Tarayıcı V2.1 Mobil - Sürüm 2.1.0", size=12, color=ft.Colors.GREY))
        page.update()

    def build_tabs_ui():
        tabs_view.controls.clear()
        tabs_view.controls.append(ft.Row([
            ft.Text("📑 Açık Sekmeler", size=24, weight=ft.FontWeight.BOLD),
            ft.IconButton(ft.Icons.ADD, icon_color=ft.Colors.PRIMARY, tooltip="Yeni Sekme", on_click=lambda _: create_new_tab())
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
        tabs_view.controls.append(ft.Divider())

        for idx, tab in enumerate(tabs):
            def select_t(e, i=idx):
                nonlocal current_tab_index
                current_tab_index = i
                url_input.value = tabs[i].url
                switch_view("browser")
            
            def close_t(e, i=idx):
                nonlocal current_tab_index
                if len(tabs) > 1:
                    removed_tab = tabs.pop(i)
                    if removed_tab.webview.control in main_content.controls:
                        main_content.controls.remove(removed_tab.webview.control)
                    if current_tab_index >= len(tabs):
                        current_tab_index = len(tabs) - 1
                    build_tabs_ui()
                else:
                    show_toast("Son sekme kapatılamaz!", ft.Icons.WARNING)

            tabs_view.controls.append(
                ft.Card(elevation=2, content=ft.Container(padding=10, content=ft.Row([
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.WEB),
                        title=ft.Text(tab.url, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        on_click=select_t,
                        expand=True
                    ),
                    ft.IconButton(ft.Icons.CLOSE, icon_color=ft.Colors.RED, on_click=close_t)
                ])))
            )
        page.update()

    def switch_view(view_name):
        for i, t in enumerate(tabs):
            t.webview.visible = (view_name == "browser" and i == current_tab_index)
            
        extensions_view.visible = (view_name == "extensions")
        history_view.visible = (view_name == "history")
        bookmarks_view.visible = (view_name == "bookmarks")
        downloads_view.visible = (view_name == "downloads")
        settings_view.visible = (view_name == "settings")
        tabs_view.visible = (view_name == "tabs_overview")
        
        if view_name == "extensions": build_extensions_ui()
        elif view_name == "history": build_history_ui()
        elif view_name == "bookmarks": build_bookmarks_ui()
        elif view_name == "settings": build_settings_ui()
        elif view_name == "tabs_overview": build_tabs_ui()
        
        page.update()

    app_bar = ft.Container(
        padding=ft.padding.only(left=10, right=10, top=10, bottom=5),
        bgcolor=ft.Colors.SURFACE,
        content=ft.Row([
            ft.IconButton(ft.Icons.HOME, on_click=lambda e: load_url("https://www.google.com")),
            url_input,
            ft.IconButton(ft.Icons.BOOKMARK_ADD, tooltip="Yer İmlerine Ekle", icon_color=ft.Colors.AMBER, on_click=add_current_to_bookmarks),
            ft.PopupMenuButton(
                items=[
                    ft.PopupMenuItem(icon=ft.Icons.BOOKMARKS, text="Yer İmleri", on_click=lambda e: switch_view("bookmarks")),
                    ft.PopupMenuItem(icon=ft.Icons.EXTENSION, text="Uzantılar", on_click=lambda e: switch_view("extensions")),
                    ft.PopupMenuItem(icon=ft.Icons.HISTORY, text="Geçmiş", on_click=lambda e: switch_view("history")),
                    ft.PopupMenuItem(icon=ft.Icons.DOWNLOAD, text="İndirmeler", on_click=lambda e: switch_view("downloads")),
                    ft.PopupMenuItem(icon=ft.Icons.SETTINGS, text="Ayarlar", on_click=lambda e: switch_view("settings")),
                ]
            )
        ])
    )

    bottom_bar = ft.Container(
        padding=ft.padding.symmetric(horizontal=15, vertical=5),
        bgcolor=ft.Colors.SURFACE,
        border=ft.border.only(top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW, on_click=go_back, tooltip="Geri", icon_size=20),
                ft.IconButton(ft.Icons.ARROW_FORWARD_IOS, on_click=go_forward, tooltip="İleri", icon_size=20),
                ft.IconButton(ft.Icons.SEARCH, on_click=lambda e: url_input.focus(), icon_size=24, icon_color=ft.Colors.PRIMARY),
                ft.IconButton(ft.Icons.TAB, tooltip="Sekmeler", icon_size=20, on_click=lambda e: switch_view("tabs_overview")),
                ft.IconButton(ft.Icons.REFRESH, on_click=lambda e: get_current_tab().webview.reload(), tooltip="Yenile", icon_size=20),
            ]
        )
    )

    main_content.controls.extend([
        extensions_view,
        history_view,
        bookmarks_view,
        downloads_view,
        settings_view,
        tabs_view
    ])

    # 1. Önce temel arayüz bileşenlerini sayfaya ekle (Mounting)
    page.add(
        app_bar,
        progress_bar,
        main_content,
        bottom_bar
    )

    # 2. Sayfa kurulduktan sonra ilk sekmeyi güvenle oluştur
    create_new_tab("https://www.google.com")

if __name__ == "__main__":
    ft.app(target=main)