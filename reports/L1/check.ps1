param([ValidateSet('All','Balance','Failover','Limit')][string]$Mode = 'All')

function Check([string]$Name, [string[]]$Arguments) {
    Write-Output "`n--- $Name ---"
    Write-Output ('curl.exe ' + ($Arguments -join ' '))
    & curl.exe --noproxy '*' --connect-timeout 3 --max-time 15 -sS @Arguments 2>&1
}

if ($Mode -eq 'All') {
    Check 'HTTP redirect' @('-I','http://shop.test/')
    Check 'HTTPS' @('-k','-I','https://shop.test/')
    Check 'Static CSS' @('-k','-I','https://shop.test/static/styles.css')
    Check 'Alias' @('-k','-i','https://shop.test/docs/')
    Check 'Admin: expect 401' @('-k','-i','https://shop.test/admin')
    Check 'Second site' @('-k','-i','https://second.test/')
    Check 'Second site API: expect 404' @('-k','-i','https://second.test/api/products')
    Check 'Unknown Host: expect 404' @('-k','-i','--resolve','unknown.test:443:127.0.0.1','https://unknown.test/')
    Check 'Custom 404' @('-k','-i','https://shop.test/no-such-page')
}

if ($Mode -in 'All','Balance','Failover') {
    Write-Output "`n--- $Mode : GET /api/health ---"
    if ($Mode -eq 'Failover') {
        Write-Output 'Backend-1 port 8001 listening (expect False):'
        [bool](Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue)
    }
    1..6 | ForEach-Object {
        & curl.exe --noproxy '*' -k -sS -D - -o NUL https://shop.test/api/health 2>&1 |
            Select-String -Pattern '^HTTP/','^x-backend-id:' | ForEach-Object { $_.Line }
        Start-Sleep -Seconds 1
    }
    if ($Mode -eq 'Failover') {
        Check 'Catalog after backend-1 stopped' @('-k','-D','-','-o','NUL','https://shop.test/api/products')
    }
}

if ($Mode -in 'All','Limit') {
    Write-Output "`n--- Rate limit: 40 parallel requests ---"
    Start-Sleep -Seconds 3
    $requests = @()
    1..40 | ForEach-Object { $requests += @('--url','https://shop.test/api/health','--output','NUL') }
    & curl.exe --noproxy '*' -k -sS --parallel --parallel-immediate --parallel-max 20 -w '%{http_code}\n' @requests 2>&1 |
        Group-Object | Sort-Object Name | ForEach-Object { "HTTP $($_.Name): $($_.Count) responses" }
    Start-Sleep -Seconds 3
    Check 'After pause: expect 200' @('-k','-D','-','-o','NUL','https://shop.test/api/health')
}
