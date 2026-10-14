Unicode True
ManifestDPIAware true

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

Name "دفترچی"
OutFile "Daftarchi-Setup.exe"
InstallDir "$LOCALAPPDATA\Daftarchi"
InstallDirRegKey HKCU "Software\Daftarchi" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails nevershow
ShowUninstDetails nevershow
SetOverwrite on

!define PRODUCT_VERSION "1.0.15"

!define MUI_ICON "daftarchi.ico"
!define MUI_UNICON "daftarchi.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "نصب دفترچی روی همین رایانه"
!define MUI_WELCOMEPAGE_TEXT "اگر دفترچی از قبل نصب است، این فایل همان نسخه را به‌روز می‌کند.$\r$\n$\r$\nپوشه عوض نمی‌شود. فروش، کالا و حساب‌ها پاک نمی‌شوند.$\r$\n$\r$\nاگر برنامه باز باشد، برای نوشتن فایل‌های جدید بسته می‌شود."
!define MUI_FINISHPAGE_TITLE "دفترچی به‌روز شد"
!define MUI_FINISHPAGE_TEXT "نسخه ${PRODUCT_VERSION} روی همان پوشه قبلی نشست.$\r$\n$\r$\nآیکن دسکتاپ را باز کنید. اطلاعات فروشگاه سر جایش است.$\r$\n$\r$\nورود اولیه، فقط اگر هنوز حساب نساخته‌اید:$\r$\n09120000000$\r$\ndaftarchi"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "همین حالا دفترچی را باز کن"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchApp

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Farsi"

VIProductVersion "1.0.15.0"
VIAddVersionKey /LANG=1033 "ProductName" "Daftarchi"
VIAddVersionKey /LANG=1033 "CompanyName" "webakery"
VIAddVersionKey /LANG=1033 "FileDescription" "Daftarchi Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "1.0.15"
VIAddVersionKey /LANG=1033 "ProductVersion" "1.0.15"
VIAddVersionKey /LANG=1033 "LegalCopyright" "webakery.ir"

Function .onInit
  ReadRegStr $0 HKCU "Software\Daftarchi" "InstallDir"
  ${If} $0 != ""
    StrCpy $INSTDIR $0
  ${ElseIf} ${FileExists} "$LOCALAPPDATA\Daftarchi\app.py"
    StrCpy $INSTDIR "$LOCALAPPDATA\Daftarchi"
  ${Else}
    StrCpy $INSTDIR "$LOCALAPPDATA\Daftarchi"
  ${EndIf}
FunctionEnd

Function StopDaftarchi
  SetOutPath "$TEMP"
  File "stop-daftarchi.ps1"
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$TEMP\stop-daftarchi.ps1"'
  Sleep 1000
  Delete "$TEMP\stop-daftarchi.ps1"
FunctionEnd

Section "دفترچی"
  Call StopDaftarchi
  RMDir /r "$INSTDIR\static"
  RMDir /r "$INSTDIR\templates"
  RMDir /r "$INSTDIR\windows"
  SetOutPath "$INSTDIR"
  File /r "payload\*.*"
  WriteUninstaller "$INSTDIR\حذف دفترچی.exe"
  WriteRegStr HKCU "Software\Daftarchi" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Daftarchi" "DisplayName" "دفترچی"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Daftarchi" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Daftarchi" "Publisher" "webakery"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Daftarchi" "DisplayIcon" "$INSTDIR\daftarchi.ico"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Daftarchi" "UninstallString" "$INSTDIR\حذف دفترچی.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Daftarchi" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Daftarchi" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Daftarchi" "EstimatedSize" "$0"
  SetOutPath "$INSTDIR"
  CreateShortcut "$DESKTOP\دفترچی.lnk" "$INSTDIR\windows\runtime\pythonw.exe" '"$INSTDIR\windows\launcher.py"' "$INSTDIR\daftarchi.ico"
  CreateDirectory "$SMPROGRAMS\دفترچی"
  CreateShortcut "$SMPROGRAMS\دفترچی\دفترچی.lnk" "$INSTDIR\windows\runtime\pythonw.exe" '"$INSTDIR\windows\launcher.py"' "$INSTDIR\daftarchi.ico"
  CreateShortcut "$SMPROGRAMS\دفترچی\حذف دفترچی.lnk" "$INSTDIR\حذف دفترچی.exe"
SectionEnd

Function LaunchApp
  SetOutPath "$INSTDIR"
  Exec '"$INSTDIR\windows\runtime\pythonw.exe" "$INSTDIR\windows\launcher.py"'
FunctionEnd

Section "Uninstall"
  Call un.StopDaftarchi
  Delete "$DESKTOP\دفترچی.lnk"
  Delete "$SMPROGRAMS\دفترچی\دفترچی.lnk"
  Delete "$SMPROGRAMS\دفترچی\حذف دفترچی.lnk"
  RMDir "$SMPROGRAMS\دفترچی"
  RMDir /r "$INSTDIR\windows"
  RMDir /r "$INSTDIR\static"
  RMDir /r "$INSTDIR\templates"
  Delete "$INSTDIR\app.py"
  Delete "$INSTDIR\daftarchi.ico"
  Delete "$INSTDIR\حذف دفترچی.exe"
  ; پوشه data اگر فروش داشته باشد خالی نیست و پاک نمی‌شود.
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Daftarchi"
  DeleteRegKey HKCU "Software\Daftarchi"
SectionEnd

Function un.StopDaftarchi
  SetOutPath "$TEMP"
  File "stop-daftarchi.ps1"
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$TEMP\stop-daftarchi.ps1"'
  Sleep 800
  Delete "$TEMP\stop-daftarchi.ps1"
FunctionEnd
