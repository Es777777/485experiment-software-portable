@echo off
cd /d "%~dp0\.."
py -3 scripts\serial_raw_excel_logger.py --config config\raw_logger_config.json
pause
