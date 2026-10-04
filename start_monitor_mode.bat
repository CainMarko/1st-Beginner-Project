@echo off
echo ====================================================
echo  Setting ALFA AWUS036ACS (Wi-Fi 2) to Monitor Mode
echo ====================================================
echo.
WlanHelper.exe "Wi-Fi 2" mode monitor
echo.
echo Current Mode:
WlanHelper.exe "Wi-Fi 2" mode
echo.
echo ====================================================
echo If you see "monitor", the adapter is ready!
echo If you see "Access is denied", please right-click this .bat
echo and choose "Run as administrator".
echo ====================================================
pause
