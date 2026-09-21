' HEXA Silent Launcher — double-click this to start HEXA with NO terminal window
' This VBScript wrapper uses pythonw.exe (windows python, no console)
' so no black terminal window flashes when you launch HEXA

Dim objShell, strDir
Set objShell = CreateObject("WScript.Shell")
strDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\") - 1)
objShell.Run "pythonw """ & strDir & "\hexa_launcher.py""", 0, False
Set objShell = Nothing
