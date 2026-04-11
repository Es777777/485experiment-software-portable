@echo off
cd /d "%~dp0\.."
py -3 scripts\serial_excel_logger.py --config config\logger_config.json
pause
