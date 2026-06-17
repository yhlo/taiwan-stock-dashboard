@echo off
set PYTHON_PATH="C:\Users\P170\AppData\Local\Programs\Python\Python311\python.exe"
cd /d "%~dp0"

:menu
cls
echo ==================================================
echo         台股法人籌碼與連買連賣查詢系統
echo ==================================================
echo  [1] 查詢大盤法人動向與「連買連賣排行榜」
echo  [2] 查詢特定個股行情與法人連買賣天數
echo  [3] 結束程式
echo ==================================================
set /p opt="請輸入選擇 (1-3): "

if "%opt%"=="1" goto option1
if "%opt%"=="2" goto option2
if "%opt%"=="3" goto option3

echo.
echo 輸入錯誤，請按任意鍵重新輸入...
pause > nul
goto menu

:option1
echo.
%PYTHON_PATH% stock_fetcher.py
echo.
echo 按任意鍵返回選單...
pause > nul
goto menu

:option2
echo.
set /p sym="請輸入股票代號 (多檔請用空白分隔，如: 2330 2454): "
echo.
%PYTHON_PATH% stock_fetcher.py %sym%
echo.
echo 按任意鍵返回選單...
pause > nul
goto menu

:option3
exit
