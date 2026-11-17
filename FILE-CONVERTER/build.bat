@echo off
chcp 65001 >nul
cd /d %~dp0
echo FILE-CONVERTER の exe を作ります。
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Python が見つかりません。先に https://www.python.org/ から
  echo Python 3.12 を入れてください（"Add python.exe to PATH" にチェック）。
  pause
  exit /b 1
)

pip install pymupdf pillow pyinstaller
if errorlevel 1 (
  echo ライブラリのインストールに失敗しました。
  pause
  exit /b 1
)

pyinstaller --clean --noconfirm FILE-CONVERTER.spec
if errorlevel 1 (
  echo ビルドに失敗しました。
  pause
  exit /b 1
)

echo.
echo できました： dist\FILE-CONVERTER.exe
pause
