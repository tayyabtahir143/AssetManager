@echo off
echo Installing dependencies...
pip install pyinstaller psutil

echo Building agent...
pyinstaller --onefile --name assetmanager-agent --icon NONE agent.py

echo.
echo Done! Binary: dist\assetmanager-agent.exe
echo Copy dist\assetmanager-agent.exe and agent.ini to the target machine.
pause
