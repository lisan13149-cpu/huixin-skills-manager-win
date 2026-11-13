@echo off
setlocal
chcp 65001 >nul
title Huixin Skills Manager
cd /d "%~dp0"

set "PYEXE="
where py >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3"
if not defined PYEXE (
  where python >nul 2>nul
  if not errorlevel 1 set "PYEXE=python"
)
if not defined PYEXE (
  echo.
  echo Python 3 was not found on this computer.
  echo Install it from https://www.python.org/downloads/windows/ and run this file again.
  echo.
  pause
  exit /b 1
)

%PYEXE% "%~dp0server.py" %*
if errorlevel 1 pause
