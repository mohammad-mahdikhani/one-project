Get-Process pythonw, python -ErrorAction SilentlyContinue |
  Where-Object { $_.Path -and ($_.Path -like '*Daftarchi*windows\runtime\python*') } |
  Stop-Process -Force -ErrorAction SilentlyContinue

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object {
    $_.CommandLine -and (
      $_.CommandLine -like '*Daftarchi*launcher.py*' -or
      $_.CommandLine -like '*Daftarchi*app.py*'
    )
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
