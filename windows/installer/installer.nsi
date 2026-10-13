Unicode true
ManifestDPIAware true

!include "MUI2.nsh"

Name "STE"
OutFile "..\..\STE-Setup.exe"
InstallDir "$LOCALAPPDATA\STE"
InstallDirRegKey HKCU "Software\STE" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails nevershow
AutoCloseWindow true
SetOverwrite on

!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

VIProductVersion "1.0.2.0"
VIAddVersionKey /LANG=1033 "ProductName" "STE"
VIAddVersionKey /LANG=1033 "FileDescription" "STE Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "1.0.2"
VIAddVersionKey /LANG=1033 "ProductVersion" "1.0.2"
VIAddVersionKey /LANG=1033 "LegalCopyright" "STE"

Section "STE"
  SetOutPath "$INSTDIR"
  File /r "payload\*.*"
  CreateShortCut "$DESKTOP\استی.lnk" "$INSTDIR\runtime\pythonw.exe" "ste_boot.py" "$INSTDIR\ste.ico" 0 SW_SHOWNORMAL "" "استی"
  CreateShortCut "$SMPROGRAMS\استی.lnk" "$INSTDIR\runtime\pythonw.exe" "ste_boot.py" "$INSTDIR\ste.ico" 0 SW_SHOWNORMAL "" "استی"
  WriteUninstaller "$INSTDIR\Uninstall-STE.exe"
  WriteRegStr HKCU "Software\STE" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE" "DisplayName" "استی"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE" "UninstallString" "$INSTDIR\Uninstall-STE.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE" "NoModify" 1
  Exec '"$INSTDIR\runtime\pythonw.exe" "$INSTDIR\ste_boot.py"'
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\استی.lnk"
  Delete "$SMPROGRAMS\استی.lnk"
  Delete "$DESKTOP\STE.lnk"
  Delete "$SMPROGRAMS\STE.lnk"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "Software\STE"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE"
SectionEnd
