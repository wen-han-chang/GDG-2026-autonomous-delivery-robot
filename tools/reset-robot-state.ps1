param(
    [string]$RobotId = "R001",
    [string]$StartNode = "A",
    [switch]$PreserveCurrentNode,
    [switch]$SkipOrderClear
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir "..")

Push-Location $projectRoot
try {
    Write-Host "[1/5] Project root: $projectRoot"

    if (-not (Test-Path (Join-Path $projectRoot "docker-compose.yml"))) {
        throw "docker-compose.yml not found in project root."
    }

    $targetNode = $StartNode
    $robotCountRaw = docker compose exec -T db psql -U robot_user -d robot_db -t -A -c "SELECT COUNT(*) FROM robot_states WHERE robot_id='$RobotId';"
    $robotCount = (($robotCountRaw | Out-String).Trim() -as [int])

    if ($robotCount -eq 0) {
        Write-Host "[2/5] Robot $RobotId not found in DB, initializing via /planner/init at node $targetNode"
        $body = @{ robot_id = $RobotId; start_node = $targetNode } | ConvertTo-Json -Compress
        Invoke-RestMethod -Method Post -Uri "http://localhost:8001/planner/init" -ContentType "application/json" -Body $body | Out-Null
    } elseif ($PreserveCurrentNode) {
        Write-Host "[2/5] Reading current node from DB for robot $RobotId"
        $currentNode = docker compose exec -T db psql -U robot_user -d robot_db -t -A -c "SELECT current_node FROM robot_states WHERE robot_id='$RobotId' LIMIT 1;"
        $currentNode = ($currentNode | Out-String).Trim()
        if ([string]::IsNullOrWhiteSpace($currentNode)) {
            throw "Robot $RobotId not found in robot_states."
        }
        $targetNode = $currentNode
    } else {
        Write-Host "[2/5] Robot $RobotId exists, using start node $targetNode"
    }

    if (-not $SkipOrderClear) {
        Write-Host "[3/5] Clearing all orders"
        docker compose exec -T db psql -U robot_user -d robot_db -c "TRUNCATE TABLE orders;"
    } else {
        Write-Host "[3/5] Skip clearing orders"
    }

    Write-Host "[4/5] Resetting robot state for $RobotId to node $targetNode"
    $updateSql = @"
UPDATE robot_states
SET current_node='$targetNode',
    next_deliver_k=1,
    picked_mask=0,
    plan_actions='[]'::json,
    plan_stops='[]'::json,
    last_plan_cost=0,
    updated_at=NOW()
WHERE robot_id='$RobotId';
"@
    docker compose exec -T db psql -U robot_user -d robot_db -c "$updateSql"

    Write-Host "[5/5] Restart backend and verify"
    docker compose restart backend | Out-Host

    Write-Host "\n--- planner/status ---"
    curl.exe -s "http://localhost:8001/planner/status?robot_id=$RobotId" | Out-Host

    Write-Host "\n--- robot_states row ---"
    docker compose exec -T db psql -U robot_user -d robot_db -c "SELECT robot_id,current_node,next_deliver_k,picked_mask,plan_actions,plan_stops,last_plan_cost FROM robot_states WHERE robot_id='$RobotId';" | Out-Host

    Write-Host "\nDone."
}
finally {
    Pop-Location
}
