Unicode True
ManifestDPIAware true

!include "LogicLib.nsh"

Name "دفترچی"
OutFile "Daftarchi.exe"
InstallDir "$LOCALAPPDATA\Daftarchi"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SilentInstall silent
ShowInstDetails nevershow
AutoCloseWindow true
SetOverwrite on
Icon "daftarchi.ico"

!define PRODUCT_VERSION "1.1.3"

VIProductVersion "1.1.3.0"
VIAddVersionKey /LANG=1033 "ProductName" "Daftarchi"
VIAddVersionKey /LANG=1033 "CompanyName" "webakery"
VIAddVersionKey /LANG=1033 "FileDescription" "Daftarchi"
VIAddVersionKey /LANG=1033 "FileVersion" "1.1.3"
VIAddVersionKey /LANG=1033 "ProductVersion" "1.1.3"
VIAddVersionKey /LANG=1033 "LegalCopyright" "webakery.ir"

Function .onInit
  ReadRegStr $0 HKCU "Software\Daftarchi" "InstallDir"
  ${If} $0 != ""
    StrCpy $INSTDIR $0
  ${Else}
    StrCpy $INSTDIR "$LOCALAPPDATA\Daftarchi"
  ${EndIf}
FunctionEnd

Function StopDaftarchi
  SetOutPath "$TEMP"
  File "stop-daftarchi.ps1"
  nsExec::Exec '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "$TEMP\stop-daftarchi.ps1"'
  Sleep 800
  Delete "$TEMP\stop-daftarchi.ps1"
FunctionEnd

Function LaunchApp
  Exec '"$INSTDIR\windows\runtime\pythonw.exe" "$INSTDIR\windows\launcher.py"'
FunctionEnd

Section
  IfFileExists "$INSTDIR\version.txt" 0 copy
  FileOpen $1 "$INSTDIR\version.txt" r
  FileRead $1 $2
  FileClose $1
  ${If} $2 == "${PRODUCT_VERSION}"
    Call LaunchApp
    Quit
  ${EndIf}
  copy:
  Call StopDaftarchi
  RMDir /r "$INSTDIR\static"
  RMDir /r "$INSTDIR\templates"
  RMDir /r "$INSTDIR\windows"
  SetOutPath "$INSTDIR"
  File /r "payload\*.*"
  FileOpen $1 "$INSTDIR\version.txt" w
  FileWrite $1 "${PRODUCT_VERSION}"
  FileClose $1
  WriteRegStr HKCU "Software\Daftarchi" "InstallDir" "$INSTDIR"
  Call LaunchApp
SectionEnd
