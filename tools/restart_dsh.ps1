# 重启 DSH：延迟执行，避免杀掉当前命令自身
Start-Sleep -Seconds 3

# 1) 关掉所有 DeepSeek Harness 进程
Get-Process -Name "DeepSeek Harness" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

# 2) 重新拉起
$exe = "C:\Users\21246\AppData\Local\Programs\DeepSeek Harness\DeepSeek Harness.exe"
if (Test-Path $exe) {
    Start-Process -FilePath $exe
    "restarted at $(Get-Date -Format HH:mm:ss)" | Out-File "$env:USERPROFILE\.dsh\dsh-restart.log" -Encoding utf8
} else {
    "exe not found" | Out-File "$env:USERPROFILE\.dsh\dsh-restart.log" -Encoding utf8
}
