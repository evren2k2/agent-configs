@echo off
rem Windows shim for the vault CLI. Uses the py launcher to find a real Python.
py -3 "%~dp0vault" %*
