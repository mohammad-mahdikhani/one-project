Unicode true
ManifestDPIAware true

!include "MUI2.nsh"

Name "STE"
OutFile "..\..\STE-Setup.exe"
InstallDir "$LOCALAPPDATA\STE"
InstallDirRegKey HKCU "Software\STE" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show
SetOverwrite on

!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_NOAUTOCLOSE
!define MUI_FINISHPAGE_RUN "$INSTDIR\STE.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Run STE"

!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

VIProductVersion "1.0.4.0"
VIAddVersionKey /LANG=1033 "ProductName" "STE"
VIAddVersionKey /LANG=1033 "FileDescription" "STE Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "1.0.4"
VIAddVersionKey /LANG=1033 "ProductVersion" "1.0.4"
VIAddVersionKey /LANG=1033 "LegalCopyright" "STE"

Section "STE"
  SetOutPath "$INSTDIR"
  File /r "payload\*.*"
  ClearErrors
  CreateShortCut "$DESKTOP\STE.lnk" "$INSTDIR\STE.bat" "" "$INSTDIR\ste.ico" 0 SW_SHOWNORMAL "" "STE"
  CreateShortCut "$SMPROGRAMS\STE.lnk" "$INSTDIR\STE.bat" "" "$INSTDIR\ste.ico" 0 SW_SHOWNORMAL "" "STE"
  WriteUninstaller "$INSTDIR\Uninstall-STE.exe"
  WriteRegStr HKCU "Software\STE" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE" "DisplayName" "STE"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE" "UninstallString" "$INSTDIR\Uninstall-STE.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE" "NoModify" 1
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\STE.lnk"
  Delete "$SMPROGRAMS\STE.lnk"
  Delete "$DESKTOP\استی.lnk"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "Software\STE"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE"
SectionEnd
