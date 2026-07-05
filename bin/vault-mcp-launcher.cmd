@echo off
setlocal enabledelayedexpansion
set "S=%~dp0vault-mcp.py"

rem `if %ERRORLEVEL%` expands at parse time inside a block (always the pre-block
rem value). `if not errorlevel 1` tests the live code; !ERRORLEVEL! (delayed) reads
rem the real exit code to propagate it.
where python3 >nul 2>&1
if not errorlevel 1 (
    python3 -c "" >nul 2>&1
    if not errorlevel 1 (
        python3 "%S%"
        exit /b !ERRORLEVEL!
    )
)

where python >nul 2>&1
if not errorlevel 1 (
    python -c "" >nul 2>&1
    if not errorlevel 1 (
        python "%S%"
        exit /b !ERRORLEVEL!
    )
)

where py >nul 2>&1
if not errorlevel 1 (
    py -c "" >nul 2>&1
    if not errorlevel 1 (
        py "%S%"
        exit /b !ERRORLEVEL!
    )
)

echo vault-mcp: no working python in PATH >&2
exit /b 1
