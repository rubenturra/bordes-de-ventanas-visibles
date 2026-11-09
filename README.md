# Window Border Highlighter (Bordes Apps Windows)

Aplicación ligera para Windows escrita en Python puro (sin dependencias externas, usando únicamente `ctypes` + API nativa Win32/DWM y `tkinter`) que dibuja bordes personalizados alrededor de las ventanas abiertas.

## Características
- **Borde Verde (`#00E676`)** en la ventana activa en primer plano.
- **Borde Azul (`#2979FF`)** en todas las ventanas inactivas visibles.
- **Recorte inteligente por oclusión (Z-Order Clipping)**: Los bordes de las ventanas que están detrás se recortan automáticamente cuando otra ventana las tapa parcial o totalmente.
- **Click-Through nativo (`WS_EX_TRANSPARENT` + Regiones GDI huecas)**: No interfiere con los clics del ratón ni el redimensionado de las ventanas.
- **Integración con Windows 11 DWM (`DWMWA_BORDER_COLOR`)**: Colorea también el marco nativo del sistema cuando está disponible.
- **Panel de control en tiempo real**: Permite ajustar colores, grosor del borde (1–16 px), radio de esquina redondeada (0–24 px), opacidad, ocultar en ventanas maximizadas o mostrar solo en la ventana activa.

## Ejecución
Haz doble clic en `iniciar_bordes.bat` o ejecuta:

```powershell
py window_borders.py
```
