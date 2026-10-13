Set o = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
desk = o.SpecialFolders("Desktop")
Set s = o.CreateShortcut(desk & "\STE.lnk")
s.TargetPath = root & "\STE.bat"
s.WorkingDirectory = root
ico = root & "\ste.ico"
If fso.FileExists(ico) Then s.IconLocation = ico
s.WindowStyle = 1
s.Description = "STE"
s.Save
