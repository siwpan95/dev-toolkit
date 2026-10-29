@echo off
chcp 65001 >nul
echo 启动中文字体复制工具...
python "%~dp0font_downloader.py"
pause
