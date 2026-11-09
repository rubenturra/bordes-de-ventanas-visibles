"""
Windows App Border Drawer
Dibuja bordes personalizados alrededor de todas las ventanas visibles de Windows:
- Ventana activa (en primer plano): Borde verde (configurable)
- Ventanas inactivas visibles: Borde azul (configurable)

Implementa las ventanas de borde con la API nativa pura de Win32 (CreateWindowExW + Regiones GDI huecas),
evitando por completo los artefactos de posicionamiento (0,0) de Tkinter y garantizando que el centro
de cada ventana sea 100% hueco y clicable.
"""

import ctypes
from ctypes import wintypes
import json
import os
import tkinter as tk
from tkinter import colorchooser, ttk

# Habilitar Per-Monitor DPI Awareness para coordenadas físicas exactas en todos los monitores
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
dwmapi = ctypes.windll.dwmapi
kernel32 = ctypes.windll.kernel32

# Constantes Win32
GWL_EXSTYLE = -20
GWL_STYLE = -16
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOPMOST = 0x00000008
WS_POPUP = 0x80000000

LWA_ALPHA = 0x00000002

DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
DWMWA_BORDER_COLOR = 34

HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_HIDEWINDOW = 0x0080
SW_HIDE = 0

GW_OWNER = 4
GA_ROOT = 2
RGN_DIFF = 4
NULLREGION = 1
WM_ERASEBKGND = 0x0014
WM_PAINT = 0x000F

# Tipos seguros para 64 bits
WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wintypes.HDC),
        ("fErase", wintypes.BOOL),
        ("rcPaint", wintypes.RECT),
        ("fRestore", wintypes.BOOL),
        ("fIncUpdate", wintypes.BOOL),
        ("rgbReserved", wintypes.BYTE * 32),
    ]


# Firmas explícitas de funciones Win32/GDI para arquitecturas de 64 bits
user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_uint,
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetLayeredWindowAttributes.argtypes = [
    wintypes.HWND,
    wintypes.COLORREF,
    wintypes.BYTE,
    wintypes.DWORD,
]
user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
user32.SetWindowRgn.restype = ctypes.c_int
user32.InvalidateRect.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.RECT),
    wintypes.BOOL,
]
user32.InvalidateRect.restype = wintypes.BOOL
user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.UpdateWindow.restype = wintypes.BOOL
user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.BeginPaint.restype = wintypes.HDC
user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.EndPaint.restype = wintypes.BOOL
user32.FillRect.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(wintypes.RECT),
    wintypes.HBRUSH,
]
user32.FillRect.restype = ctypes.c_int
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetClientRect.restype = wintypes.BOOL
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
user32.GetWindow.restype = wintypes.HWND
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.CreateRoundRectRgn.argtypes = [
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
]
gdi32.CreateRoundRectRgn.restype = wintypes.HRGN
gdi32.CreateRectRgn.argtypes = [
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
]
gdi32.CreateRectRgn.restype = wintypes.HRGN
gdi32.CombineRgn.argtypes = [
    wintypes.HRGN,
    wintypes.HRGN,
    wintypes.HRGN,
    ctypes.c_int,
]
gdi32.CombineRgn.restype = ctypes.c_int

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "active_color": "#00E676",      # Verde brillante para ventana activa
    "inactive_color": "#2979FF",    # Azul brillante para ventanas inactivas
    "thickness": 4,                 # Grosor del borde en píxeles
    "corner_radius": 10,            # Radio de esquina redondeada (estilo Windows 11)
    "opacity": 240,                 # Opacidad (80 - 255)
    "padding": 0,                   # Desplazamiento hacia afuera/adentro del borde
    "hide_maximized": True,         # Si es True, no dibuja borde en ventanas maximizadas
    "only_active": False,           # Si es True, solo dibuja en la ventana activa
    "refresh_ms": 16,               # ~60 FPS seguimiento fluido
}


def hex_to_colorref(hex_str: str) -> int:
    """Convierte '#RRGGBB' a COLORREF de Win32 (0x00BBGGRR)."""
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return 0x00E676
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def get_class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def get_window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def is_window_cloaked(hwnd: int) -> bool:
    cloaked = ctypes.c_int(0)
    res = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
    )
    return res == 0 and cloaked.value != 0


def get_window_frame_rect(hwnd: int):
    """Obtiene el rectángulo visual real de la ventana en pantalla (sin sombras invisibles de DWM)."""
    rect = wintypes.RECT()
    res = dwmapi.DwmGetWindowAttribute(
        hwnd,
        DWMWA_EXTENDED_FRAME_BOUNDS,
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )
    if res != 0:
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
    return (rect.left, rect.top, rect.right, rect.bottom)


EXCLUDED_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "NotifyIconOverflowWindow",
    "Windows.UI.Core.CoreWindow",
    "XamlExplorerHostIslandWindow",
    "TopLevelWindowForOverflowXamlIsland",
    "TaskListThumbnailWnd",
    "ForegroundStaging",
    "ApplicationManager_DesktopShellWindow",
    "CEF-OSC-WIDGET",
    "NarratorHelperWindow",
    "RainmeterMeterWindow",
    "SideBar_HTMLHostWindow",
    "WinBorderOverlayNativeClass",
}

# Mapa global de HWNDs de overlays a su color actual (COLORREF) para pintar en WM_PAINT
_OVERLAY_COLORS: dict[int, int] = {}
_CLASS_REGISTERED = False


def _overlay_wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_ERASEBKGND:
        return 1
    if msg == WM_PAINT:
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        colorref = _OVERLAY_COLORS.get(hwnd, 0x0076E600)
        brush = gdi32.CreateSolidBrush(colorref)
        rc = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rc))
        user32.FillRect(hdc, ctypes.byref(rc), brush)
        gdi32.DeleteObject(brush)
        user32.EndPaint(hwnd, ctypes.byref(ps))
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


_WNDPROC_REF = WNDPROC(_overlay_wnd_proc)


def _ensure_overlay_class():
    global _CLASS_REGISTERED
    if _CLASS_REGISTERED:
        return
    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.style = 0
    wc.lpfnWndProc = _WNDPROC_REF
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.hIcon = None
    wc.hCursor = None
    wc.hbrBackground = None
    wc.lpszMenuName = None
    wc.lpszClassName = "WinBorderOverlayNativeClass"
    wc.hIconSm = None
    user32.RegisterClassExW(ctypes.byref(wc))
    _CLASS_REGISTERED = True


class NativeBorderOverlay:
    """
    Ventana nativa Win32 pura (sin Tkinter) con una región GDI hueca (RGN_DIFF).
    Solo existen los píxeles del marco; el interior no existe físicamente para el sistema operativo,
    garantizando cero interferencia con el ratón y coordenadas exactas sin jamás saltar a (0,0).
    """

    def __init__(self):
        _ensure_overlay_class()
        hinst = kernel32.GetModuleHandleW(None)
        ex_style = (
            WS_EX_LAYERED
            | WS_EX_TRANSPARENT
            | WS_EX_TOOLWINDOW
            | WS_EX_NOACTIVATE
            | WS_EX_TOPMOST
        )
        self.hwnd = user32.CreateWindowExW(
            ex_style,
            "WinBorderOverlayNativeClass",
            "",
            WS_POPUP,
            -32000,
            -32000,
            10,
            10,
            None,
            None,
            hinst,
            None,
        )
        _OVERLAY_COLORS[self.hwnd] = 0x0076E600
        self.visible = False
        self.last_rect_state = None
        self.last_color = None
        self.last_opacity = None

    def update_border(
        self,
        rect: tuple[int, int, int, int],
        color_hex: str,
        thickness: int,
        corner_radius: int,
        opacity: int,
        padding: int,
        is_active: bool,
        occluding_rects: tuple[tuple[int, int, int, int], ...] = (),
    ):
        if not self.hwnd:
            return

        left, top, right, bottom = rect
        pad = padding + (thickness // 2)
        x = left - pad
        y = top - pad
        w = (right - left) + pad * 2
        h = (bottom - top) + pad * 2

        if w <= 30 or h <= 30:
            self.hide()
            return

        # Filtrar únicamente los rectángulos de ventanas superiores que realmente se solapan con este borde
        relevant_occluders = []
        r_right = x + w
        r_bottom = y + h
        for ol, ot, oright, obottom in occluding_rects:
            if ol < r_right and oright > x and ot < r_bottom and obottom > y:
                relevant_occluders.append((ol - x, ot - y, oright - x, obottom - y))
        relevant_occluders_tuple = tuple(relevant_occluders)

        colorref = hex_to_colorref(color_hex)
        clamped_opacity = max(60, min(255, int(opacity)))

        if self.last_opacity != clamped_opacity:
            self.last_opacity = clamped_opacity
            user32.SetLayeredWindowAttributes(
                self.hwnd, 0, clamped_opacity, LWA_ALPHA
            )

        color_changed = self.last_color != colorref
        if color_changed:
            self.last_color = colorref
            _OVERLAY_COLORS[self.hwnd] = colorref

        rect_state = (x, y, w, h, thickness, corner_radius, relevant_occluders_tuple)
        if rect_state != self.last_rect_state:
            self.last_rect_state = rect_state

            # Construir la región hueca del borde (Exterior menos Interior)
            d_out = max(0, int(corner_radius) * 2)
            d_in = max(0, (int(corner_radius) - int(thickness)) * 2)

            if d_out > 0:
                rgn_outer = gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, d_out, d_out)
            else:
                rgn_outer = gdi32.CreateRectRgn(0, 0, w, h)

            if d_in > 0:
                rgn_inner = gdi32.CreateRoundRectRgn(
                    thickness,
                    thickness,
                    w - thickness + 1,
                    h - thickness + 1,
                    d_in,
                    d_in,
                )
            else:
                rgn_inner = gdi32.CreateRectRgn(
                    thickness, thickness, w - thickness, h - thickness
                )

            gdi32.CombineRgn(rgn_outer, rgn_outer, rgn_inner, RGN_DIFF)
            gdi32.DeleteObject(rgn_inner)

            # Restar (recortar) las regiones de todas las ventanas que están por delante en el orden Z
            region_type = None
            for ox1, oy1, ox2, oy2 in relevant_occluders_tuple:
                rgn_occ = gdi32.CreateRectRgn(ox1, oy1, ox2, oy2)
                region_type = gdi32.CombineRgn(rgn_outer, rgn_outer, rgn_occ, RGN_DIFF)
                gdi32.DeleteObject(rgn_occ)
                if region_type == NULLREGION:
                    break

            if region_type == NULLREGION:
                # La ventana está 100% tapada por otras ventanas encima
                gdi32.DeleteObject(rgn_outer)
                user32.ShowWindow(self.hwnd, SW_HIDE)
                self.visible = False
                return

            # SetWindowRgn toma posesión de rgn_outer (el sistema lo libera automáticamente)
            user32.SetWindowRgn(self.hwnd, rgn_outer, True)

            user32.SetWindowPos(
                self.hwnd,
                HWND_TOPMOST,
                x,
                y,
                w,
                h,
                SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
            self.visible = True
            user32.InvalidateRect(self.hwnd, None, True)
            user32.UpdateWindow(self.hwnd)
        else:
            if not self.visible:
                return
            if is_active:
                user32.SetWindowPos(
                    self.hwnd,
                    HWND_TOPMOST,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                )

            if color_changed:
                user32.InvalidateRect(self.hwnd, None, True)
                user32.UpdateWindow(self.hwnd)

    def hide(self):
        if self.visible and self.hwnd:
            user32.ShowWindow(self.hwnd, SW_HIDE)
            self.visible = False
            self.last_rect_state = None

    def destroy(self):
        if self.hwnd:
            _OVERLAY_COLORS.pop(self.hwnd, None)
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
            self.visible = False


class WindowBorderManager:
    """Rastrea todas las ventanas de aplicaciones y coordina los bordes activo/inactivos."""

    def __init__(self, config: dict, control_panel_hwnd: int = 0):
        self.config = config
        self.control_panel_hwnd = control_panel_hwnd
        self.enabled = True
        self.overlays: dict[int, NativeBorderOverlay] = {}
        self.own_pid = os.getpid()
        self.last_active_hwnd = None

    def set_native_dwm_border(self, hwnd: int, color_hex: str | None):
        """Restaura el borde nativo de Windows 11 cuando se desactiva o cierra un overlay."""
        try:
            if color_hex is None:
                val = ctypes.c_uint(0xFFFFFFFF)  # DWMWA_COLOR_DEFAULT
                dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_BORDER_COLOR, ctypes.byref(val), ctypes.sizeof(val)
                )
        except Exception:
            pass

    def classify_window(self, hwnd: int) -> tuple[bool, bool, tuple[int, int, int, int] | None]:
        """
        Evalúa una ventana del orden Z y devuelve:
        (should_draw_border, can_occlude_others, rect)
        """
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return (False, False, None)

        if is_window_cloaked(hwnd):
            return (False, False, None)

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == self.own_pid:
            if self.control_panel_hwnd and hwnd == self.control_panel_hwnd:
                rc = get_window_frame_rect(hwnd)
                return (False, rc is not None, rc)
            return (False, False, None)

        class_name = get_class_name(hwnd)
        # Las barras de tareas también tapan bordes de ventanas que pasen por debajo
        if class_name in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
            rc = get_window_frame_rect(hwnd)
            return (False, rc is not None, rc)

        if class_name in EXCLUDED_CLASSES:
            return (False, False, None)

        rect = get_window_frame_rect(hwnd)
        if not rect:
            return (False, False, None)
        left, top, right, bottom = rect
        w = right - left
        h = bottom - top
        if w < 60 or h < 40:
            return (False, False, None)

        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        owner = user32.GetWindow(hwnd, GW_OWNER)
        title = get_window_title(hwnd)
        is_zoomed = bool(user32.IsZoomed(hwnd))

        # Cualquier ventana o widget flotante visible (como el monitor de SISTEMA/CPU/CLAUDE)
        # aunque sea WS_EX_TOOLWINDOW o tenga owner, tapa visualmente lo que tenga detrás:
        # Pero NO lleva borde si es toolwindow, subventana, sin título, pequeña o está maximizada.
        if (ex_style & WS_EX_TOOLWINDOW) and not (ex_style & WS_EX_APPWINDOW):
            return (False, True, rect)

        if owner and not (ex_style & WS_EX_APPWINDOW):
            return (False, True, rect)

        if not title.strip() or w < 120 or h < 80:
            return (False, True, rect)

        if self.config.get("hide_maximized", True) and is_zoomed:
            # No se le dibuja borde porque está maximizada, pero sí tapa todas las ventanas detrás de ella
            return (False, True, rect)

        return (True, True, rect)

    def enumerate_windows_z_order(self) -> list[tuple[int, tuple[int, int, int, int], bool]]:
        """
        Recorre las ventanas de delante hacia atrás (orden Z real de Windows) y devuelve:
        (hwnd, rect, should_draw_border) para todas las ventanas y widgets visibles que pueden tapar a otras.
        """
        windows_z = []

        def callback(hwnd, lparam):
            should_draw, can_occlude, rc = self.classify_window(hwnd)
            if can_occlude and rc:
                windows_z.append((hwnd, rc, should_draw))
            return True

        user32.EnumWindows(WNDENUMPROC(callback), 0)
        return windows_z

    def get_active_root_hwnd(self) -> int:
        fg = user32.GetForegroundWindow()
        if not fg:
            return self.last_active_hwnd or 0

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
        if pid.value == self.own_pid:
            return self.last_active_hwnd or 0

        root_hwnd = user32.GetAncestor(fg, GA_ROOT) or fg
        self.last_active_hwnd = root_hwnd
        return root_hwnd

    def tick(self) -> tuple[int, str]:
        if not self.enabled:
            self.hide_all()
            return (0, "En pausa")

        active_hwnd = self.get_active_root_hwnd()
        z_windows = self.enumerate_windows_z_order()

        only_active = self.config.get("only_active", False)

        # Construir lista de ventanas con su lista de rectángulos oclusores (las ventanas que están por delante de ella)
        target_items = []
        occluders_so_far: list[tuple[int, int, int, int]] = []

        for hwnd, rect, should_draw in z_windows:
            if should_draw and (not only_active or hwnd == active_hwnd):
                target_items.append((hwnd, rect, tuple(occluders_so_far)))
            # Toda ventana visible en este nivel Z tapa a las ventanas que están detrás de ella
            occluders_so_far.append(rect)

        active_set = {item[0] for item in target_items}

        # Limpiar overlays de ventanas que se cerraron o minimizaron
        stale_hwnds = [h for h in list(self.overlays.keys()) if h not in active_set]
        for h in stale_hwnds:
            self.set_native_dwm_border(h, None)
            self.overlays[h].destroy()
            del self.overlays[h]

        thickness = int(self.config.get("thickness", 4))
        radius = int(self.config.get("corner_radius", 10))
        opacity = int(self.config.get("opacity", 240))
        padding = int(self.config.get("padding", 0))
        active_color = self.config.get("active_color", "#00E676")
        inactive_color = self.config.get("inactive_color", "#2979FF")

        # Actualizar de atrás hacia adelante para mantener coherencia visual
        visible_count = 0
        for hwnd, rect, occluding_rects in reversed(target_items):
            is_active = (hwnd == active_hwnd)
            color = active_color if is_active else inactive_color

            self.set_native_dwm_border(hwnd, color)

            if hwnd not in self.overlays:
                self.overlays[hwnd] = NativeBorderOverlay()

            self.overlays[hwnd].update_border(
                rect=rect,
                color_hex=color,
                thickness=thickness,
                corner_radius=radius,
                opacity=opacity,
                padding=padding,
                is_active=is_active,
                occluding_rects=occluding_rects,
            )
            if self.overlays[hwnd].visible:
                visible_count += 1

        active_title = get_window_title(active_hwnd) if active_hwnd else "Ninguna"
        return (visible_count, active_title)

    def hide_all(self):
        for hwnd, overlay in self.overlays.items():
            self.set_native_dwm_border(hwnd, None)
            overlay.hide()

    def destroy_all(self):
        for hwnd, overlay in self.overlays.items():
            self.set_native_dwm_border(hwnd, None)
            overlay.destroy()
        self.overlays.clear()


class ControlPanelApp:
    """Interfaz gráfica adaptable al DPI para personalizar colores, grosor y opciones en tiempo real."""

    def __init__(self):
        self.config = self.load_config()
        self.root = tk.Tk()
        self.root.title("Bordes de Ventanas - Configuración")
        self.root.resizable(True, True)
        self.root.configure(bg="#181824")

        self.manager = WindowBorderManager(self.config)
        self._build_ui()

        # Ajustar tamaño de la ventana automáticamente según el escalado DPI del monitor
        self.root.update_idletasks()
        req_w = max(460, self.main_container.winfo_reqwidth() + 24)
        req_h = self.main_container.winfo_reqheight() + 24
        self.root.geometry(f"{req_w}x{req_h}")
        self.root.minsize(req_w, req_h)

        wid = self.root.winfo_id()
        self.manager.control_panel_hwnd = user32.GetAncestor(wid, GA_ROOT) or wid

        self._schedule_loop()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_config(self) -> dict:
        cfg = DEFAULT_CONFIG.copy()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    cfg.update(saved)
            except Exception:
                pass
        return cfg

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        bg_main = "#181824"
        bg_card = "#232336"
        fg_text = "#F0F2F8"
        fg_muted = "#9BA1B8"

        self.main_container = tk.Frame(self.root, bg=bg_main, padx=16, pady=12)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Encabezado
        header = tk.Frame(self.main_container, bg=bg_main)
        header.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            header,
            text="Window Border Highlighter",
            font=("Segoe UI", 13, "bold"),
            bg=bg_main,
            fg=fg_text,
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Borde verde en la ventana activa y azul en las ventanas inactivas",
            font=("Segoe UI", 9),
            bg=bg_main,
            fg=fg_muted,
        ).pack(anchor="w", pady=(2, 0))

        # Tarjeta de Estado / Activar-Desactivar
        status_frame = tk.Frame(self.main_container, bg=bg_card, padx=14, pady=10)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        status_left = tk.Frame(status_frame, bg=bg_card)
        status_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.status_label = tk.Label(
            status_left,
            text="● Bordes Activos",
            font=("Segoe UI", 10, "bold"),
            bg=bg_card,
            fg="#00E676",
        )
        self.status_label.pack(anchor="w")

        self.info_label = tk.Label(
            status_left,
            text="Detectando ventanas...",
            font=("Segoe UI", 8),
            bg=bg_card,
            fg=fg_muted,
        )
        self.info_label.pack(anchor="w", pady=(2, 0))

        self.toggle_btn = tk.Button(
            status_frame,
            text="Pausar Bordes",
            font=("Segoe UI", 9, "bold"),
            bg="#353552",
            fg=fg_text,
            activebackground="#46466B",
            activeforeground=fg_text,
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
            command=self.toggle_enabled,
        )
        self.toggle_btn.pack(side=tk.RIGHT)

        # Tarjeta de Colores
        colors_card = tk.Frame(self.main_container, bg=bg_card, padx=14, pady=10)
        colors_card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            colors_card,
            text="Colores de Borde",
            font=("Segoe UI", 10, "bold"),
            bg=bg_card,
            fg=fg_text,
        ).pack(anchor="w", pady=(0, 8))

        # Selector Ventana Activa
        row_active = tk.Frame(colors_card, bg=bg_card)
        row_active.pack(fill=tk.X, pady=3)
        tk.Label(
            row_active,
            text="Ventana Activa (en foco):",
            font=("Segoe UI", 9),
            bg=bg_card,
            fg=fg_text,
        ).pack(side=tk.LEFT)

        self.active_color_btn = tk.Button(
            row_active,
            text=self.config["active_color"].upper(),
            font=("Consolas", 9, "bold"),
            bg=self.config["active_color"],
            fg="#000000",
            width=10,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.pick_active_color,
        )
        self.active_color_btn.pack(side=tk.RIGHT)

        # Selector Ventanas Inactivas
        row_inactive = tk.Frame(colors_card, bg=bg_card)
        row_inactive.pack(fill=tk.X, pady=3)
        tk.Label(
            row_inactive,
            text="Ventanas Inactivas:",
            font=("Segoe UI", 9),
            bg=bg_card,
            fg=fg_text,
        ).pack(side=tk.LEFT)

        self.inactive_color_btn = tk.Button(
            row_inactive,
            text=self.config["inactive_color"].upper(),
            font=("Consolas", 9, "bold"),
            bg=self.config["inactive_color"],
            fg="#FFFFFF",
            width=10,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.pick_inactive_color,
        )
        self.inactive_color_btn.pack(side=tk.RIGHT)

        # Tarjeta de Ajustes de Geometría
        sliders_card = tk.Frame(self.main_container, bg=bg_card, padx=14, pady=10)
        sliders_card.pack(fill=tk.X, pady=(0, 10))

        self._create_slider(
            sliders_card,
            label="Grosor del borde (px)",
            key="thickness",
            min_v=1,
            max_v=16,
            bg=bg_card,
            fg=fg_text,
        )
        self._create_slider(
            sliders_card,
            label="Radio de esquina redondeada (px)",
            key="corner_radius",
            min_v=0,
            max_v=24,
            bg=bg_card,
            fg=fg_text,
        )
        self._create_slider(
            sliders_card,
            label="Opacidad del borde",
            key="opacity",
            min_v=80,
            max_v=255,
            bg=bg_card,
            fg=fg_text,
        )

        # Opciones adicionales
        opts_card = tk.Frame(self.main_container, bg=bg_card, padx=14, pady=10)
        opts_card.pack(fill=tk.X, pady=(0, 10))

        self.hide_max_var = tk.BooleanVar(value=self.config.get("hide_maximized", False))
        cb_max = tk.Checkbutton(
            opts_card,
            text="Ocultar borde en ventanas maximizadas",
            variable=self.hide_max_var,
            bg=bg_card,
            fg=fg_text,
            selectcolor="#181824",
            activebackground=bg_card,
            activeforeground=fg_text,
            font=("Segoe UI", 9),
            command=self.on_options_change,
        )
        cb_max.pack(anchor="w")

        self.only_active_var = tk.BooleanVar(value=self.config.get("only_active", False))
        cb_only = tk.Checkbutton(
            opts_card,
            text="Mostrar únicamente en la ventana activa",
            variable=self.only_active_var,
            bg=bg_card,
            fg=fg_text,
            selectcolor="#181824",
            activebackground=bg_card,
            activeforeground=fg_text,
            font=("Segoe UI", 9),
            command=self.on_options_change,
        )
        cb_only.pack(anchor="w", pady=(4, 0))

        # Botón Restablecer
        tk.Button(
            self.main_container,
            text="Restablecer valores por defecto (Verde / Azul)",
            font=("Segoe UI", 9, "bold"),
            bg="#2B2B40",
            fg=fg_text,
            activebackground="#383854",
            activeforeground=fg_text,
            relief=tk.FLAT,
            pady=7,
            cursor="hand2",
            command=self.reset_defaults,
        ).pack(fill=tk.X)

    def _create_slider(self, parent, label, key, min_v, max_v, bg, fg):
        row = tk.Frame(parent, bg=bg)
        row.pack(fill=tk.X, pady=3)

        top_row = tk.Frame(row, bg=bg)
        top_row.pack(fill=tk.X)

        tk.Label(top_row, text=label, font=("Segoe UI", 9), bg=bg, fg=fg).pack(
            side=tk.LEFT
        )
        val_lbl = tk.Label(
            top_row,
            text=str(self.config[key]),
            font=("Consolas", 9, "bold"),
            bg=bg,
            fg="#00E676",
        )
        val_lbl.pack(side=tk.RIGHT)

        def on_slide(val):
            iv = int(float(val))
            self.config[key] = iv
            val_lbl.config(text=str(iv))
            self.save_config()

        scale = tk.Scale(
            row,
            from_=min_v,
            to=max_v,
            orient=tk.HORIZONTAL,
            bg=bg,
            fg=fg,
            highlightthickness=0,
            troughcolor="#14141F",
            activebackground="#00E676",
            showvalue=False,
            command=on_slide,
        )
        scale.set(self.config[key])
        scale.pack(fill=tk.X)
        setattr(self, f"scale_{key}", scale)

    def pick_active_color(self):
        color = colorchooser.askcolor(
            color=self.config["active_color"],
            title="Seleccionar color para la ventana activa",
        )[1]
        if color:
            self.config["active_color"] = color
            self.active_color_btn.config(text=color.upper(), bg=color)
            self.save_config()

    def pick_inactive_color(self):
        color = colorchooser.askcolor(
            color=self.config["inactive_color"],
            title="Seleccionar color para las ventanas inactivas",
        )[1]
        if color:
            self.config["inactive_color"] = color
            self.inactive_color_btn.config(text=color.upper(), bg=color)
            self.save_config()

    def on_options_change(self):
        self.config["hide_maximized"] = self.hide_max_var.get()
        self.config["only_active"] = self.only_active_var.get()
        self.save_config()

    def toggle_enabled(self):
        self.manager.enabled = not self.manager.enabled
        if self.manager.enabled:
            self.status_label.config(text="● Bordes Activos", fg="#00E676")
            self.toggle_btn.config(text="Pausar Bordes")
        else:
            self.status_label.config(text="○ Bordes en Pausa", fg="#FF5252")
            self.info_label.config(text="Bordes desactivados temporalmente")
            self.toggle_btn.config(text="Activar Bordes")
            self.manager.hide_all()

    def reset_defaults(self):
        self.config.update(DEFAULT_CONFIG)
        self.active_color_btn.config(
            text=self.config["active_color"].upper(),
            bg=self.config["active_color"],
        )
        self.inactive_color_btn.config(
            text=self.config["inactive_color"].upper(),
            bg=self.config["inactive_color"],
        )
        self.scale_thickness.set(self.config["thickness"])
        self.scale_corner_radius.set(self.config["corner_radius"])
        self.scale_opacity.set(self.config["opacity"])
        self.hide_max_var.set(self.config["hide_maximized"])
        self.only_active_var.set(self.config["only_active"])
        self.save_config()

    def _schedule_loop(self):
        try:
            count, active_title = self.manager.tick()
            if self.manager.enabled:
                short_title = (
                    (active_title[:28] + "...")
                    if len(active_title) > 28
                    else active_title
                )
                self.info_label.config(
                    text=f"{count} ventanas con borde | Activa: {short_title}"
                )
        except Exception as e:
            self.info_label.config(text=f"Error: {str(e)[:40]}")
        self.root.after(self.config.get("refresh_ms", 16), self._schedule_loop)

    def on_close(self):
        self.manager.destroy_all()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ControlPanelApp()
    app.run()
