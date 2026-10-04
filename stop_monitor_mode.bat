@echo off
echo ====================================================
echo  Restoring ALFA AWUS036ACS (Wi-Fi 2) to Managed Mode
echo ====================================================
echo.
WlanHelper.exe "Wi-Fi 2" mode managed
echo.
echo Current Mode:
WlanHelper.exe "Wi-Fi 2" mode
echo ====================================================
pause
