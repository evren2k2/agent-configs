Set objShell = CreateObject("WScript.Shell")
strCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & objShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\agent-configs\hooks\server-sync.ps1"""
objShell.Run strCommand, 0, False
