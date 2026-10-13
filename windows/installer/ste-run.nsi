Unicode true
ManifestDPIAware true

!include "MUI2.nsh"

Name "قیمت ست کن"
OutFile "..\..\STE.exe"
InstallDir "$LOCALAPPDATA\STE"
InstallDirRegKey HKCU "Software\STE" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show
SetOverwrite on

!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_NOAUTOCLOSE
!define MUI_FINISHPAGE_RUN "$INSTDIR\STE.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Run"

!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

VIProductVersion "1.0.6.0"
VIAddVersionKey /LANG=1033 "ProductName" "Gheymat Set Kon"
VIAddVersionKey /LANG=1033 "FileDescription" "Gheymat Set Kon"
VIAddVersionKey /LANG=1033 "FileVersion" "1.0.6"
VIAddVersionKey /LANG=1033 "ProductVersion" "1.0.6"
VIAddVersionKey /LANG=1033 "LegalCopyright" "STE"

Section "STE"
  SetOutPath "$INSTDIR"
  File /r "payload\*.*"
  ClearErrors
  CreateShortCut "$DESKTOP\قیمت ست کن.lnk" "$INSTDIR\STE.bat" "" "$INSTDIR\ste.ico" 0 SW_SHOWNORMAL "" "قیمت ست کن"
  CreateShortCut "$SMPROGRAMS\قیمت ست کن.lnk" "$INSTDIR\STE.bat" "" "$INSTDIR\ste.ico" 0 SW_SHOWNORMAL "" "قیمت ست کن"
  CreateShortCut "$DESKTOP\STE.lnk" "$INSTDIR\STE.bat" "" "$INSTDIR\ste.ico" 0 SW_SHOWNORMAL "" "قیمت ست کن"
  WriteUninstaller "$INSTDIR\Uninstall-STE.exe"
  WriteRegStr HKCU "Software\STE" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE" "DisplayName" "قیمت ست کن"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE" "UninstallString" "$INSTDIR\Uninstall-STE.exe"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\STE.lnk"
  Delete "$SMPROGRAMS\STE.lnk"
  Delete "$DESKTOP\قیمت ست کن.lnk"
  Delete "$SMPROGRAMS\قیمت ست کن.lnk"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "Software\STE"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\STE"
SectionEnd
