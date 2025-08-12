@echo off
setlocal
REM Ir a la carpeta backend
cd /d "%~dp0backend"

REM Crear el entorno si no existe
IF NOT EXIST ".venv\Scripts\python.exe" (
  echo Creando entorno virtual...
  py -3 -m venv .venv
)

REM Activar entorno
call .venv\Scripts\activate

REM Instalar/actualizar dependencias
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt

REM Abrir la documentación en el navegador
start "" http://127.0.0.1:8000/docs

REM Lanzar el servidor
python -m uvicorn app.main:app --reload
