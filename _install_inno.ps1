$versions = @('6.3.1','6.3.0','6.2.2','6.2.1','6.1.2')
foreach ($v in $versions) {
    $url = "https://files.jrsoftware.org/is/6/innosetup-$v.exe"
    try {
        $r = Invoke-WebRequest -Uri $url -Method Head -UseBasicParsing -EA Stop
        $size = $r.Headers.'Content-Length'
        Write-Host "FOUND: $url (size: $size)"
        # Télécharger
        Invoke-WebRequest -Uri $url -OutFile "C:\D\metraplan4\innosetup-installer.exe" -UseBasicParsing
        Write-Host "DOWNLOADED"
        break
    } catch {
        Write-Host "NOT_FOUND: $v"
    }
}

# Vérifier taille
$sz = (Get-Item "C:\D\metraplan4\innosetup-installer.exe" -EA SilentlyContinue).Length
Write-Host "FILE_SIZE: $sz"
