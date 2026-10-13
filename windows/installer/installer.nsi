Unicode true
ManifestDPIAware true

!include "MUI2.nsh"

Name "استی"
OutFile "..\..\STE-Setup.exe"
InstallDir "$LOCALAPPDATA\STE"
InstallDirRegKey HKCU "Software\STE" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails nevershow
AutoCloseWindow true
SetOverwrite on

!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "نصب استی"
!define MUI_WELCOMEPAGE_TEXT "با زدن نصب، اپ روی همین رایانه می‌نشیند و همان لحظه باز می‌شود.$\r$\n$\r$\nپایتون جدا لازم نیست."
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Farsi"

VIProductVersion "1.0.0.0"
VIAddVersionKey /LANG=1033 "ProductName" "STE"
VIAddVersionKey /LANG=1033 "FileDescription" "STE Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "1.0.0"
VIAddVersionKey /LANG=1033 "ProductVersion" "1.0.0"

Function LaunchApp
  SetOutPath "$INSTDIR"
  Exec '"$INSTDIR\استی.bat"'
FunctionEnd

Section "استی"
  SetOutPath "$INSTDIR"
  File /r "payload\*.*"
  CreateShortCut "$DESKTOP\استی.lnk" "$INSTDIR\استی.bat" "" "$INSTDIR\runtime\pythonw.exe" 0
  WriteUninstaller "$INSTDIR\حذف استی.exe"
  WriteRegStr HKCU "Software\STE" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE" "DisplayName" "استی"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE" "UninstallString" "$INSTDIR\حذف استی.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE" "NoModify" 1
  Call LaunchApp
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\استی.lnk"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "Software\STE"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE"
SectionEnd
