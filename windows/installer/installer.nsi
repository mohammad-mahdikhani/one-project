Unicode True
ManifestDPIAware true

!include "MUI2.nsh"
!include "FileFunc.nsh"

Name "دفترچی"
OutFile "Daftarchi-Setup.exe"
InstallDir "$LOCALAPPDATA\Daftarchi"
InstallDirRegKey HKCU "Software\Daftarchi" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails nevershow
ShowUninstDetails nevershow

!define MUI_ICON "daftarchi.ico"
!define MUI_UNICON "daftarchi.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "نصب دفترچی"
!define MUI_WELCOMEPAGE_TEXT "دفترچی، صندوق فروش و حسابداری فروشگاه است.$\r$\n$\r$\nبا ادامه، برنامه روی این رایانه نصب می‌شود، میانبر روی دسکتاپ ساخته می‌شود و دفترچی در مرورگر باز می‌شود.$\r$\n$\r$\nفروش، انبار و حسابداری بدون اینترنت کار می‌کند."
!define MUI_FINISHPAGE_TITLE "دفترچی نصب شد"
!define MUI_FINISHPAGE_TEXT "نصب تمام شد.$\r$\n$\r$\nدفترچی را از آیکن دسکتاپ باز کنید. ورود اولیه:$\r$\n09120000000$\r$\ndaftarchi"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "همین حالا دفترچی را باز کن"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchApp

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Farsi"

VIProductVersion "1.0.1.0"
VIAddVersionKey /LANG=1033 "ProductName" "Daftarchi"
VIAddVersionKey /LANG=1033 "CompanyName" "webakery"
VIAddVersionKey /LANG=1033 "FileDescription" "Daftarchi Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "1.0.1"
VIAddVersionKey /LANG=1033 "ProductVersion" "1.0.1"
VIAddVersionKey /LANG=1033 "LegalCopyright" "webakery.ir"

Section "دفترچی"
  SetOutPath "$INSTDIR"
  File /r "payload\*.*"
  WriteUninstaller "$INSTDIR\حذف دفترچی.exe"
  WriteRegStr HKCU "Software\Daftarchi" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Daftarchi" "DisplayName" "دفترچی"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Daftarchi" "DisplayVersion" "1.0.1"
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
