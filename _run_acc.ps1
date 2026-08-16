$py = Join-Path $PSScriptRoot "..\mm_bot\.venv\Scripts\python.exe"
$dir = $PSScriptRoot
$cmds = @(
  @("accuracy.py", "--out", "accuracy.json"),
  @("accuracy.py", "--period", "6-12", "--out", "accuracy_morning.json"),
  @("accuracy.py", "--model", "rp5", "--out", "accuracy_rp5.json"),
  @("accuracy.py", "--model", "rp5", "--period", "6-12", "--out", "accuracy_rp5_morning.json")
)
$procs = @()
$i = 0
foreach ($c in $cmds) {
  $i++
  $p = Start-Process -FilePath $py -ArgumentList $c -WorkingDirectory $dir -RedirectStandardOutput "$dir\_acc_out$i.log" -RedirectStandardError "$dir\_acc_err$i.log" -PassThru -WindowStyle Hidden
  $procs += $p
}
foreach ($p in $procs) { $p.WaitForExit() }
Write-Output "all done"