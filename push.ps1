# push.ps1 -- 把 model1-arch 推到 GitHub 私库
#
# 本机实测：github.com:443 不可达（DNS 污染，解析到 104.244.46.165，Twitter 的 IP 段），
# 而 baidu / pypi 可达。所以这个脚本先诊断，再按可用路径推。
#
# 前置：GitHub 上已经建好一个空私库。脚本不建仓库 —— 建仓库要调 api.github.com，
#       本机连不上。
#
# 用法：
#   .\push.ps1                    自动选路径
#   .\push.ps1 -Repo my-repo      指定仓库名
#   .\push.ps1 -Mirror            走镜像
#   .\push.ps1 -DryRun            只诊断不推
#   .\push.ps1 -Token ghp_xxx     用 token（会进 origin URL）

param(
    [string]$Owner = "GuoTzu-yang",
    [string]$Repo  = "model1-arch",
    [string]$Token = "",
    [switch]$Mirror,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$HERE = $PSScriptRoot

# ── 找 git：PATH 里没有，用 GitHub Desktop 自带的 ──
$gitCmd = (Get-Command git -ErrorAction SilentlyContinue)
if ($gitCmd) {
    $git = $gitCmd.Source
} else {
    $cand = $null
    foreach ($pat in @(
        "$env:LOCALAPPDATA\GitHubDesktop\app-*\resources\app\git\cmd\git.exe",
        "C:\Program Files\Git\cmd\git.exe",
        "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe"
    )) {
        $cand = Get-ChildItem $pat -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cand) { break }
    }
    if (-not $cand) { throw "找不到 git.exe" }
    $git = $cand.FullName
}
Write-Host ("git = " + $git) -ForegroundColor DarkGray

# ── 1. 诊断 ──
$reachable = [bool](Test-NetConnection -ComputerName "github.com" -Port 443 `
                  -InformationLevel Quiet -WarningAction SilentlyContinue)
Write-Host ""
if ($reachable) {
    Write-Host "github.com:443  可达" -ForegroundColor Green
} else {
    Write-Host "github.com:443  不可达" -ForegroundColor Yellow
    $ip = (Resolve-DnsName github.com -Type A -ErrorAction SilentlyContinue |
           Where-Object { $_.IPAddress } | Select-Object -First 1).IPAddress
    if ($ip) { Write-Host ("  解析到 " + $ip) -ForegroundColor DarkGray }
}

Push-Location $HERE
try {
    # ── 2. 本地状态 ──
    $commits = & $git rev-list --count HEAD 2>$null
    $dirty   = & $git status --porcelain 2>$null
    Write-Host ""
    Write-Host ("本地 " + $commits + " 个提交") -ForegroundColor Cyan
    if ($dirty) {
        Write-Host "  工作区有未提交改动（先 commit 再推）" -ForegroundColor Yellow
        $dirty | Select-Object -First 5 | ForEach-Object { Write-Host ("    " + $_) -ForegroundColor DarkGray }
    }

    # ── 3. 选 URL ──
    if ($Mirror -or (-not $reachable)) {
        $base = "https://ghproxy.net/https://github.com/" + $Owner + "/" + $Repo + ".git"
        Write-Host ""
        Write-Host "路径 镜像 ghproxy" -ForegroundColor Yellow
    } else {
        $base = "https://github.com/" + $Owner + "/" + $Repo + ".git"
        Write-Host ""
        Write-Host "路径 直连" -ForegroundColor Green
    }

    if ($Token) {
        $url = $base -replace "^https://", ("https://" + $Token + "@")
    } else {
        $url = $base
    }
    Write-Host ("目标 " + $base) -ForegroundColor Cyan

    if ($DryRun) {
        Write-Host ""
        Write-Host "DryRun 不推送" -ForegroundColor DarkGray
        return
    }

    # ── 4. 设远端并推 ──
    $existing = & $git remote 2>$null
    if ($existing -contains "origin") {
        & $git remote set-url origin $url
    } else {
        & $git remote add origin $url
    }

    Write-Host ""
    Write-Host "开始推送" -ForegroundColor Cyan
    & $git push -u origin main 2>&1 | ForEach-Object { Write-Host ("  " + $_) }

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host ("推送成功 https://github.com/" + $Owner + "/" + $Repo) -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "推送失败。四种走法，按顺序试：" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  A 改 hosts（需管理员权限）" -ForegroundColor White
        Write-Host "    把 github.com 指到一个可用 IP，再 .\push.ps1" -ForegroundColor DarkGray
        Write-Host "    查可用 IP: https://www.ipaddress.com/website/github.com" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  B 走镜像" -ForegroundColor White
        Write-Host "    .\push.ps1 -Mirror" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  C 用 token" -ForegroundColor White
        Write-Host "    .\push.ps1 -Token ghp_xxxx" -ForegroundColor DarkGray
        Write-Host "    推完记得清掉 URL 里的 token：" -ForegroundColor DarkGray
        Write-Host ("    " + $git + " remote set-url origin " + $base) -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  D 完全离线：用 bundle" -ForegroundColor White
        Write-Host "    上层的 model1-arch.bundle（2.7 MB）含完整历史。" -ForegroundColor DarkGray
        Write-Host "    在能联网的机器上：" -ForegroundColor DarkGray
        Write-Host "      git clone model1-arch.bundle model1-arch" -ForegroundColor DarkGray
        Write-Host "      cd model1-arch" -ForegroundColor DarkGray
        Write-Host "      git remote add origin <你的空仓库>" -ForegroundColor DarkGray
        Write-Host "      git push -u origin main" -ForegroundColor DarkGray
    }
}
finally {
    Pop-Location
}
