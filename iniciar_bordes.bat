@echo off
title Window Border Highlighter
:: Usa pythonw.exe del lanzador pyw para abrir sin consola negra detras
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw "%~dp0window_borders.py"
) else (
    C:\Users\turra\AppData\Local\Programs\Python\Python313\pythonw.exe "%~dp0window_borders.py"
)
