$configName = "usb_auto_start.json"

function Get-RemovableDrives {
    return Get-WmiObject Win32_LogicalDisk | Where-Object { $_.DriveType -eq 2 } | Select-Object -ExpandProperty DeviceID
}

function Open-ConfiguredFileForDrive {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DriveLetter
    )

    $driveRoot = $DriveLetter.TrimEnd('\\')
    $configPath = Join-Path $driveRoot $configName
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        return
    }

    try {
        $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        if (-not $config.datei) {
            return
        }

        $targetPath = Join-Path $driveRoot $config.datei
        Start-Sleep -Milliseconds 800

        if ((Test-Path -LiteralPath $targetPath -PathType Leaf)) {
            Start-Process -FilePath $targetPath
            Write-Host "USB-Datei gestartet: $targetPath"
        }
    }
    catch {
        Write-Host "USB-Stick ignoriert: $DriveLetter ($($_.Exception.Message))"
    }
}

$knownDrives = Get-RemovableDrives
Write-Host "USB-Ueberwachung aktiv. Neue vorbereitete USB-Sticks werden automatisch gestartet."
Write-Host "Zum Beenden: Strg+C"

Register-WmiEvent -Class Win32_VolumeChangeEvent -SourceIdentifier "UsbDateiOeffnen" -Action {
    $eventType = $Event.SourceEventArgs.NewEvent.EventType
    if ($eventType -ne 2) {
        return
    }

    $driveLetter = $Event.SourceEventArgs.NewEvent.DriveName
    if ([string]::IsNullOrWhiteSpace($driveLetter)) {
        return
    }

    Open-ConfiguredFileForDrive -DriveLetter $driveLetter
}

try {
    while ($true) {
        $currentDrives = Get-RemovableDrives
        $newDrives = $currentDrives | Where-Object { $_ -notin $knownDrives }
        $knownDrives = $currentDrives

        foreach ($drive in $newDrives) {
            Open-ConfiguredFileForDrive -DriveLetter $drive
        }

        Start-Sleep -Seconds 1
    }
}
finally {
    Unregister-Event -SourceIdentifier "UsbDateiOeffnen" -ErrorAction SilentlyContinue
    Remove-Job -Name "UsbDateiOeffnen*" -Force -ErrorAction SilentlyContinue
}