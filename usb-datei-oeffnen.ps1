$Dateiname = "start.html"

Write-Host "USB-Ueberwachung aktiv. Datei: $Dateiname"
Write-Host "Zum Beenden: Strg+C"

Register-WmiEvent -Class Win32_VolumeChangeEvent -SourceIdentifier "UsbDateiOeffnen" -Action {
    if ($Event.SourceEventArgs.NewEvent.EventType -ne 2) {
        return
    }

    $laufwerk = $Event.SourceEventArgs.NewEvent.DriveName
    if ([string]::IsNullOrWhiteSpace($laufwerk)) {
        return
    }

    $dateipfad = Join-Path $laufwerk $using:Dateiname
    Start-Sleep -Milliseconds 750

    if (Test-Path -LiteralPath $dateipfad -PathType Leaf) {
        Start-Process -FilePath $dateipfad
    }
}

try {
    while ($true) {
        Wait-Event -Timeout 5 | Out-Null
    }
}
finally {
    Unregister-Event -SourceIdentifier "UsbDateiOeffnen" -ErrorAction SilentlyContinue
    Get-Job | Where-Object { $_.Name -like "UsbDateiOeffnen*" } | Remove-Job -Force -ErrorAction SilentlyContinue
}