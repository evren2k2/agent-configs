@echo off
set "S=%~dp0vault-mcp.py"

where python3 >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python3 -c "" >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        python3 "%S%"
        exit /b %ERRORLEVEL%
    )
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python -c "" >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        python "%S%"
        exit /b %ERRORLEVEL%
    )
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py -c "" >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        py "%S%"
        exit /b %ERRORLEVEL%
    )
)

echo vault-mcp: no working python in PATH >&2
exit /b 1
