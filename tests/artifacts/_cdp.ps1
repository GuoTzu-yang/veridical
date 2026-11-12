# CDP 单次调用（PowerShell 5.1 兼容）
param(
    [string]$TargetId,
    [string]$Method = "Runtime.evaluate",
    [string]$Expr = "1+1",
    [string]$ExprFile = "",
    [int]$TimeoutSec = 15
)

if ($ExprFile -ne "") {
    $Expr = [IO.File]::ReadAllText($ExprFile, [Text.Encoding]::UTF8)
}

$ErrorActionPreference = "Stop"

function Invoke-CDP {
    param([string]$WsUrl, [string]$Method, [hashtable]$Params, [int]$TimeoutSec)

    $ws = New-Object System.Net.WebSockets.ClientWebSocket
    $ct = [Threading.CancellationToken]::None
    try {
        $ws.ConnectAsync([Uri]$WsUrl, $ct).Wait($TimeoutSec * 1000) | Out-Null
        if ($ws.State -ne [System.Net.WebSockets.WebSocketState]::Open) {
            throw "ws not open: $($ws.State)"
        }

        $payload = @{ id = 1; method = $Method; params = $Params } | ConvertTo-Json -Depth 12 -Compress
        $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
        $seg = New-Object 'System.ArraySegment[byte]' -ArgumentList (,$bytes)
        $ws.SendAsync($seg, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $ct).Wait($TimeoutSec * 1000) | Out-Null

        $buf = New-Object byte[] 262144
        $sb = New-Object System.Text.StringBuilder
        $deadline = (Get-Date).AddSeconds($TimeoutSec)
        while ((Get-Date) -lt $deadline) {
            $rseg = New-Object 'System.ArraySegment[byte]' -ArgumentList (,$buf)
            $task = $ws.ReceiveAsync($rseg, $ct)
            if (-not $task.Wait(3000)) { continue }
            if ($task.Result.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close) { break }
            $n = $task.Result.Count
            if ($n -gt 0) { [void]$sb.Append([Text.Encoding]::UTF8.GetString($buf, 0, $n)) }
            if ($task.Result.EndOfMessage -and $sb.Length -gt 0) {
                $txt = $sb.ToString()
                $parsed = $txt | ConvertFrom-Json
                if (($parsed.PSObject.Properties.Name -contains "id") -and ($parsed.id -eq 1)) {
                    return $parsed
                }
                [void]$sb.Clear()
            }
        }
        throw "no response within ${TimeoutSec}s"
    }
    finally {
        try {
            if ($ws.State -eq [System.Net.WebSockets.WebSocketState]::Open) {
                $ws.CloseAsync([System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure, "done", $ct).Wait(2000) | Out-Null
            }
        } catch {}
        $ws.Dispose()
    }
}

$wsUrl = "ws://127.0.0.1:9333/devtools/page/$TargetId"

switch ($Method) {
    "Runtime.evaluate" {
        $p = @{ expression = $Expr; returnByValue = $true; awaitPromise = $true }
    }
    "Page.navigate" {
        $p = @{ url = $Expr }
    }
    "Page.captureScreenshot" {
        $p = @{ format = "png" }
    }
    "Page.reload" {
        $p = @{}
    }
    default {
        $p = @{ expression = $Expr; returnByValue = $true }
    }
}

$resp = Invoke-CDP -WsUrl $wsUrl -Method $Method -Params $p -TimeoutSec $TimeoutSec

if ($Method -eq "Runtime.evaluate") {
    $res = $resp.result
    if ($res.PSObject.Properties.Name -contains "exceptionDetails") {
        Write-Output "JS_ERROR: $($res.exceptionDetails.text)"
    } else {
        $v = $res.result.value
        if ($null -ne $v) {
            if ($v -is [string]) { Write-Output $v } else { $v | ConvertTo-Json -Depth 8 }
        } else {
            Write-Output ($res.result | ConvertTo-Json -Depth 6)
        }
    }
} elseif ($Method -eq "Page.captureScreenshot") {
    $out = Join-Path $env:TEMP "cdp_shot.png"
    [IO.File]::WriteAllBytes($out, [Convert]::FromBase64String($resp.result.data))
    Write-Output "SHOT $out $((Get-Item $out).Length) bytes"
} else {
    $resp | ConvertTo-Json -Depth 8
}
