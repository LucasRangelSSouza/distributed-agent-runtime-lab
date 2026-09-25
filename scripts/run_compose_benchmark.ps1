param(
    [int]$RequestCount = 48,
    [int]$Concurrency = 6,
    [string]$BaseUrl = "http://127.0.0.1:8080",
    [string]$RunId = ([guid]::NewGuid().ToString("N").Substring(0, 12))
)

$ErrorActionPreference = "Stop"

if ($RequestCount -lt 1) { throw "RequestCount must be at least 1." }
if ($Concurrency -lt 1) { throw "Concurrency must be at least 1." }

$wall = [Diagnostics.Stopwatch]::StartNew()
$results = 1..$RequestCount | ForEach-Object -Parallel {
    $stopwatch = [Diagnostics.Stopwatch]::StartNew()
    $requestId = "compose-benchmark-$using:RunId-$_"
    $body = @{
        request_id = $requestId
        conversation_id = "compose-benchmark-$using:RunId"
        message = "Benchmark request $_"
    } | ConvertTo-Json -Compress

    try {
        $response = Invoke-RestMethod -Method Post -Uri "$using:BaseUrl/api/messages" -ContentType "application/json" -Body $body -TimeoutSec 20
        [PSCustomObject]@{
            request_id = $requestId
            completed = ($response.status -eq "completed" -and -not $response.cache_hit)
            milliseconds = [math]::Round($stopwatch.Elapsed.TotalMilliseconds, 2)
            worker_id = $response.worker_id
            error = $null
        }
    }
    catch {
        [PSCustomObject]@{
            request_id = $requestId
            completed = $false
            milliseconds = [math]::Round($stopwatch.Elapsed.TotalMilliseconds, 2)
            worker_id = $null
            error = $_.Exception.Message
        }
    }
} -ThrottleLimit $Concurrency
$wall.Stop()

$completed = @($results | Where-Object completed)
$latencies = @($completed | ForEach-Object milliseconds | Sort-Object)
if ($latencies.Count -eq 0) { throw "No request completed successfully." }

$summary = [PSCustomObject]@{
    run_id = $RunId
    requests = $RequestCount
    concurrency = $Concurrency
    completed = $completed.Count
    errors = $RequestCount - $completed.Count
    elapsed_seconds = [math]::Round($wall.Elapsed.TotalSeconds, 2)
    throughput_rps = [math]::Round($completed.Count / $wall.Elapsed.TotalSeconds, 2)
    p50_ms = $latencies[[math]::Ceiling($latencies.Count * 0.50) - 1]
    p95_ms = $latencies[[math]::Ceiling($latencies.Count * 0.95) - 1]
    workers = @($completed | Group-Object worker_id | ForEach-Object { [PSCustomObject]@{ worker_id = $_.Name; completed = $_.Count } })
    failures = @($results | Where-Object { -not $_.completed })
}

$summary | ConvertTo-Json -Depth 5
