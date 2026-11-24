# Synthetic-only PostgreSQL 16 base-backup, verification, and PITR rehearsal.
# Creates a dedicated local Docker container and named volumes; never reads EIMS .env or production URLs.
$ErrorActionPreference = 'Stop'
$runId = (Get-Date -Format 'yyyyMMddHHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$container = "eims-pitr-rehearsal-$runId"
$dataVolume = "eims-pitr-data-$runId"
$walVolume = "eims-pitr-wal-$runId"
$image = 'pgvector/pgvector:pg16'
$password = 'pitr-' + [guid]::NewGuid().ToString('N')
$restoreStarted = $false

foreach ($name in @($container, $dataVolume, $walVolume)) {
    $existing = if ($name -eq $container) { docker ps -a --format '{{.Names}}' } else { docker volume ls --format '{{.Name}}' }
    if ($existing -contains $name) { throw "Refusing to reuse pre-existing synthetic rehearsal resource: $name" }
}

try {
    docker volume create $dataVolume | Out-Null
    docker volume create $walVolume | Out-Null
    $entry = 'mkdir -p /var/lib/postgresql/wal-archive && chown postgres:postgres /var/lib/postgresql/wal-archive && exec /usr/local/bin/docker-entrypoint.sh postgres -c wal_level=replica -c archive_mode=on -c archive_timeout=5s'
    $args = @('run','-d','--name',$container,'-e','POSTGRES_USER=eims_pitr','-e',"POSTGRES_PASSWORD=$password",'-e','POSTGRES_DB=eims_pitr','-v',($dataVolume + ':/var/lib/postgresql/data'),'-v',($walVolume + ':/var/lib/postgresql/wal-archive'),'--entrypoint','bash',$image,'-c',$entry)
    & docker @args | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not start isolated PostgreSQL rehearsal container' }

    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        $running = & docker inspect $container --format '{{.State.Running}}'
        if ($running.Trim() -ne 'true') {
            & docker logs $container
            throw 'Synthetic PostgreSQL container exited during startup'
        }
        & docker exec $container pg_isready -U eims_pitr -d eims_pitr *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw 'Synthetic PostgreSQL did not become ready' }

    $archiveSql = "ALTER SYSTEM SET archive_command TO 'if [ -f /var/lib/postgresql/wal-archive/%f ]; then cmp -s %p /var/lib/postgresql/wal-archive/%f; else cp %p /var/lib/postgresql/wal-archive/%f; fi'"
    & docker exec -e "PGPASSWORD=$password" $container psql -U eims_pitr -d eims_pitr -v ON_ERROR_STOP=1 -c $archiveSql -c 'SELECT pg_reload_conf()' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not configure synthetic WAL archive command' }

    & docker exec -e "PGPASSWORD=$password" $container psql -U eims_pitr -d eims_pitr -v ON_ERROR_STOP=1 -c 'CREATE TABLE recovery_probe(marker text PRIMARY KEY)' -c "INSERT INTO recovery_probe VALUES ('before_backup')" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not create PITR probe rows' }

    & docker exec -u postgres -e "PGPASSWORD=$password" $container pg_basebackup -h 127.0.0.1 -U eims_pitr -D /tmp/eims-base -Fp -X stream -P
    if ($LASTEXITCODE -ne 0) { throw 'pg_basebackup failed' }
    & docker exec -u postgres $container pg_verifybackup /tmp/eims-base
    if ($LASTEXITCODE -ne 0) { throw 'pg_verifybackup failed' }

    & docker exec -e "PGPASSWORD=$password" $container psql -U eims_pitr -d eims_pitr -v ON_ERROR_STOP=1 -c "INSERT INTO recovery_probe VALUES ('before_target')" -c "SELECT pg_create_restore_point('eims_pitr_target')" -c "INSERT INTO recovery_probe VALUES ('after_target')" -c 'SELECT pg_switch_wal()' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not generate post-backup WAL and named restore point' }

    $archived = $false
    for ($i = 0; $i -lt 60; $i++) {
        $last = & docker exec -e "PGPASSWORD=$password" $container psql -U eims_pitr -d eims_pitr -Atqc "SELECT COALESCE(last_archived_wal,'') FROM pg_stat_archiver"
        if ($last -and $last.Trim()) { $archived = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $archived) { throw 'No WAL segment was confirmed archived' }

    $configPath = Join-Path $env:TEMP 'eims-pitr-restore-config-20261115.conf'
    @'
restore_command = 'cp /var/lib/postgresql/wal-archive/%f %p'
recovery_target_name = 'eims_pitr_target'
recovery_target_action = 'promote'
port = 55432
listen_addresses = ''
unix_socket_directories = '/tmp/eims-restore-sock'
'@ | Set-Content -Path $configPath -Encoding ascii
    & docker exec -u postgres $container cp -a /tmp/eims-base /tmp/eims-restore
    & docker exec -u postgres $container mkdir -p /tmp/eims-restore-sock
    & docker cp $configPath ($container + ':/tmp/eims-restore.conf') | Out-Null
    & docker exec -u postgres $container bash -c 'cat /tmp/eims-restore.conf >> /tmp/eims-restore/postgresql.auto.conf'
    & docker exec -u postgres $container touch /tmp/eims-restore/recovery.signal
    $pgctlArgs = @('exec','-u','postgres',$container,'pg_ctl','-D','/tmp/eims-restore','-o',"-p 55432 -k /tmp/eims-restore-sock -c listen_addresses=''",
        '-l','/tmp/eims-restore.log','start')
    & docker @pgctlArgs
    if ($LASTEXITCODE -ne 0) { throw 'Could not start isolated PITR restore instance' }
    $restoreStarted = $true

    $restoredReady = $false
    for ($i = 0; $i -lt 60; $i++) {
        & docker exec -u postgres $container pg_isready -h /tmp/eims-restore-sock -p 55432 -U eims_pitr -d eims_pitr *> $null
        if ($LASTEXITCODE -eq 0) { $restoredReady = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $restoredReady) {
        & docker exec $container tail -80 /tmp/eims-restore.log
        throw 'PITR restore instance did not become ready'
    }

    $rows = & docker exec -u postgres $container psql -h /tmp/eims-restore-sock -p 55432 -U eims_pitr -d eims_pitr -Atqc "SELECT string_agg(marker, ',' ORDER BY marker) FROM recovery_probe"
    Write-Output "PITR_RESTORED_ROWS=$rows"
    if ($rows.Trim() -ne 'before_backup,before_target') { throw "PITR boundary mismatch; unexpected rows: $rows" }
    Write-Output 'PG_BASEBACKUP=PASS'
    Write-Output 'PG_VERIFYBACKUP=PASS'
    Write-Output "WAL_ARCHIVED=$($last.Trim())"
    Write-Output 'PITR_NAMED_TARGET=PASS'
    Write-Output 'POST_TARGET_TRANSACTION_EXCLUDED=PASS'

    & docker exec -u postgres $container pg_ctl -D /tmp/eims-restore stop -m fast | Out-Null
    $restoreStarted = $false
}
finally {
    if ($restoreStarted) {
        & docker exec -u postgres $container pg_ctl -D /tmp/eims-restore stop -m immediate *> $null
    }
    & docker stop $container *> $null
    Write-Output "SYNTHETIC_CONTAINER_STOPPED=$container"
    Write-Output "SYNTHETIC_VOLUMES_PRESERVED=$dataVolume,$walVolume"
}
