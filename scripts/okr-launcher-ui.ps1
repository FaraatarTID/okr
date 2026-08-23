param()

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Resolve-Path (Join-Path $scriptDir "..")

$composeFile = Join-Path $root "deploy\docker\docker-compose.yml"
$envFile = Join-Path $root "deploy\docker\.env"
$dockerComposeUrl = "http://127.0.0.1:3000"
$hybridRunScript = Join-Path $root "run_hybrid_app_local.bat"
$hybridStopScript = Join-Path $root "stop_hybrid_app_local.bat"

$uiPrimary = [System.Drawing.Color]::FromArgb(112, 41, 99) # #702963
$uiCanvas = [System.Drawing.Color]::FromArgb(248, 243, 249)
$uiPanel = [System.Drawing.Color]::FromArgb(255, 255, 255)
$uiText = [System.Drawing.Color]::FromArgb(42, 24, 47)
$uiSubText = [System.Drawing.Color]::FromArgb(88, 62, 90)
$uiAccent = [System.Drawing.Color]::FromArgb(112, 41, 99)
$uiSuccess = [System.Drawing.Color]::FromArgb(18, 164, 84)
$uiWarning = [System.Drawing.Color]::FromArgb(217, 78, 63)
$uiButtonBg = [System.Drawing.Color]::FromArgb(112, 41, 99)
$uiFont = New-Object System.Drawing.Font("Segoe UI", 10)
$uiTitleFont = New-Object System.Drawing.Font($uiFont, [System.Drawing.FontStyle]::Bold)
$uiSectionFont = New-Object System.Drawing.Font($uiFont, [System.Drawing.FontStyle]::Bold)
$uiButtonFont = New-Object System.Drawing.Font($uiFont, [System.Drawing.FontStyle]::Bold)
$script:lblStatus = $null
$script:statusLines = @()
$script:aiModeCombo = $null

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class ConsoleWindow {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern IntPtr GetConsoleWindow();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@

function Hide-LauncherConsole {
    $hwnd = [ConsoleWindow]::GetConsoleWindow()
    if ($hwnd -ne [IntPtr]::Zero) {
        [ConsoleWindow]::ShowWindow($hwnd, 0) | Out-Null
    }
}
Hide-LauncherConsole

$launcherLogFile = Join-Path $root "tmp\launcher.log"

function Write-LauncherLog {
    param([string]$Message)
    try {
        $dir = Split-Path -Parent $launcherLogFile
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $line = "[{0:yyyy-MM-dd HH:mm:ss}] {1}" -f (Get-Date), $Message
        Add-Content -Path $launcherLogFile -Value $line -Encoding UTF8
    } catch {
    }
}

function Write-Log {
    param([string]$Message)
    if (-not $Message) { return }
    $line = "[{0:HH:mm:ss}] {1}`r`n" -f (Get-Date), $Message
    Write-LauncherLog -Message $Message
    if ($script:lblStatus) {
        $script:statusLines = @($line.Trim()) + $script:statusLines
        if ($script:statusLines.Count -gt 5) {
            $script:statusLines = $script:statusLines[0..4]
        }
        $script:lblStatus.Text = ($script:statusLines -join "`r`n")
        return
    }
    Write-Verbose $line.Trim()
}

function Update-Ui {
    # Keeps the window responsive during long operations by pumping the
    # WinForms message queue. Guards against DoEvents reentrancy: while an
    # operation is running, close/user-close messages are deferred instead of
    # tearing down the process mid-work.
    if (-not $script:lblStatus) { return }
    try {
        [System.Windows.Forms.Application]::DoEvents()
    } catch {
    }
}

$script:isBusy = $false

function Set-BusyState {
    param([bool]$Busy)
    $script:isBusy = $Busy
    # Buttons may not exist yet when this is called early in startup.
    foreach ($btn in @($btnStart, $btnStop, $btnRestart, $btnOpenWeb, $btnLocalStart, $btnLocalStop, $btnStatus)) {
        if ($btn -and -not $btn.IsDisposed) { $btn.Enabled = (-not $Busy) }
    }
    if ($form -and -not $form.IsDisposed) {
        if ($Busy) { $form.Cursor = [System.Windows.Forms.Cursors]::WaitCursor }
        else { $form.Cursor = [System.Windows.Forms.Cursors]::Default }
    }
}

function Open-AppInBrowser {
    param()
    try {
        Start-Process $dockerComposeUrl
    } catch {
        Write-Log "Unable to open app URL: $($_.Exception.Message)"
    }
}

function Wait-AppReady {
    param([int]$TimeoutSeconds = 90)

    Write-Log "Waiting for app to respond (up to $TimeoutSeconds s)..."
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastProgressSecond = -10
    do {
        $spaOk = $false
        $apiOk = $false
        try {
            $response = Invoke-WebRequest -Uri "$dockerComposeUrl/" -Method Head -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                $spaOk = $true
            }
        } catch {
        }
        # The SPA can serve pages without a working backend; require the API
        # health endpoint too so partial starts are not reported as ready.
        try {
            $apiResponse = Invoke-WebRequest -Uri "http://127.0.0.1:8100/healthz" -Method Get -UseBasicParsing -TimeoutSec 2
            if ($apiResponse.StatusCode -ge 200 -and $apiResponse.StatusCode -lt 500) {
                $apiOk = $true
            }
        } catch {
        }
        if ($spaOk -and $apiOk) {
            Write-Log "App and backend API responded on startup. Opening browser."
            return $true
        }
        Update-Ui
        Start-Sleep -Milliseconds 1200
        Update-Ui
        $elapsed = [int]((Get-Date) - $deadline).TotalSeconds + $TimeoutSeconds
        if (($elapsed - $lastProgressSecond) -ge 10) {
            $lastProgressSecond = $elapsed
            $waiting = @()
            if (-not $spaOk) { $waiting += "SPA" }
            if (-not $apiOk) { $waiting += "backend API" }
            Write-Log ("Still waiting for {0}... {1}s / {2}s" -f ($waiting -join " + "), $elapsed, $TimeoutSeconds)
        }
    } while ((Get-Date) -lt $deadline)

    Write-Log "App not fully reachable after $TimeoutSeconds seconds; opening browser anyway."
    return $false
}

function Run-CommandCapture {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Executable,
        [string[]]$Arguments,
        # Hard wall-clock limit. Network probes (e.g. jan_context.py) can stall
        # far beyond their internal timeouts on proxy/DNS issues; kill and move
        # on instead of freezing Start/Restart indefinitely.
        [int]$TimeoutSeconds = 60
    )
    try {
        $escaped = $Arguments | ForEach-Object {
            if ($_ -match '[\s"]') {
                '"' + ($_ -replace '"','\"') + '"'
            } else {
                $_
            }
        }
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Executable
        $psi.Arguments = $escaped -join " "
        $psi.WorkingDirectory = $root
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $proc = New-Object System.Diagnostics.Process
        $proc.StartInfo = $psi
        $null = $proc.Start()
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        while (-not $proc.HasExited) {
            if ($sw.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
                try { $proc.Kill($true) } catch { try { $proc.Kill() } catch {} }
                Write-LauncherLog -Message ("TIMEOUT after ${TimeoutSeconds}s: $Executable " + ($Arguments -join ' '))
                return @{ ExitCode = 124; StdOut = ""; StdErr = "Timed out after ${TimeoutSeconds}s." }
            }
            Start-Sleep -Milliseconds 200
            Update-Ui
        }
        $stdout = $proc.StandardOutput.ReadToEnd()
        $stderr = $proc.StandardError.ReadToEnd()
        $proc.WaitForExit()
        return @{ ExitCode = $proc.ExitCode; StdOut = $stdout; StdErr = $stderr }
    } catch {
        return @{ ExitCode = 1; StdOut = ""; StdErr = $_.Exception.Message }
    }
}

function Invoke-HiddenProcess {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Executable,
        [string[]]$Arguments = @(),
        [switch]$NoWait,
        # Hard wall-clock limit when waiting (ignored with -NoWait).
        [int]$TimeoutSeconds = 300
    )
    try {
        $escaped = $Arguments | ForEach-Object {
            if ($_ -match '[\s"]') {
                '"' + ($_ -replace '"','\"') + '"'
            } else {
                $_
            }
        }
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Executable
        $psi.Arguments = $escaped -join " "
        $psi.WorkingDirectory = $root
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

        $proc = New-Object System.Diagnostics.Process
        $proc.StartInfo = $psi
        $started = $proc.Start()
        if (-not $started) {
            throw "Process could not be started."
        }
        if ($NoWait) {
            return @{ ExitCode = 0; StdOut = ""; StdErr = "" }
        }
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        while (-not $proc.HasExited) {
            if ($sw.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
                try { $proc.Kill($true) } catch { try { $proc.Kill() } catch {} }
                Write-LauncherLog -Message ("TIMEOUT after ${TimeoutSeconds}s: $Executable " + ($Arguments -join ' '))
                return @{ ExitCode = 124; StdOut = ""; StdErr = "Timed out after ${TimeoutSeconds}s." }
            }
            Start-Sleep -Milliseconds 200
            Update-Ui
        }
        $proc.WaitForExit()
        return @{ ExitCode = $proc.ExitCode; StdOut = ""; StdErr = "" }
    } catch {
        Write-Log "Command failed: $Executable $Arguments"
        Write-Log $_.Exception.Message
        return @{ ExitCode = 1; StdOut = ""; StdErr = $_.Exception.Message }
    }
}

function Update-EnvValue {
    param(
        [string]$FilePath,
        [string]$Key,
        [string]$Value
    )
    if (-not (Test-Path $FilePath)) {
        throw "Env file not found: $FilePath"
    }

    $lines = Get-Content -Path $FilePath
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$([Regex]::Escape($Key))=") {
            $lines[$i] = "$Key=$Value"
            $found = $true
            break
        }
    }
    if (-not $found) {
        $lines += "$Key=$Value"
    }
    Set-Content -Path $FilePath -Value $lines -Encoding UTF8
}

function Get-EnvFileValue {
    param(
        [string]$FilePath,
        [string]$Key
    )
    if (-not (Test-Path $FilePath)) {
        return ""
    }
    $lines = Get-Content -Path $FilePath
    foreach ($line in $lines) {
        if ($line -match "^$([Regex]::Escape($Key))=(.*)$") {
            return $matches[1]
        }
    }
    return ""
}

function Normalize-JanContextValue {
    param(
        [Parameter(Mandatory=$true)]
        [object]$Value,
        [Parameter(Mandatory=$true)]
        [string]$FieldName
    )

    if ($null -eq $Value) { return "" }

    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        $property = $Value.PSObject.Properties[$FieldName]
        if ($property -and $property.Value) {
            return Normalize-JanContextValue -Value $property.Value -FieldName $FieldName
        }
    }

    if ($Value -is [System.Collections.IDictionary]) {
        if ($Value.ContainsKey($FieldName)) {
            return Normalize-JanContextValue -Value $Value[$FieldName] -FieldName $FieldName
        }
    }

    if ($Value -is [System.Array]) {
        if ($Value.Count -eq 0) { return "" }
        return Normalize-JanContextValue -Value $Value[0] -FieldName $FieldName
    }

    if ($Value -is [string]) {
        $text = $Value.Trim()
        if ($text.StartsWith("[string]@{")) {
            $clean = $text.Substring(10)
            $closeBrace = $clean.IndexOf("}")
            if ($closeBrace -ge 0) {
                $clean = $clean.Substring(0, $closeBrace)
            }

            $parts = $clean -split ';'
            foreach ($part in $parts) {
                $pair = $part.Trim()
                if ($pair.StartsWith("${FieldName}=", [System.StringComparison]::OrdinalIgnoreCase)) {
                    return $pair.Substring($FieldName.Length + 1).Trim()
                }
            }
            return ""
        }
        return $text
    }

    return [string]$Value
}


function Resolve-PythonExecutable {
    if (Test-Path (Join-Path $root ".venv\Scripts\python.exe")) {
        return (Join-Path $root ".venv\Scripts\python.exe")
    }
    if (Test-Path (Join-Path $root "venv\Scripts\python.exe")) {
        return (Join-Path $root "venv\Scripts\python.exe")
    }
    return "python"
}

function Convert-JanBaseUrlForDocker {
    param([string]$BaseUrl)
    if (-not $BaseUrl) { return "" }

    $normalized = $BaseUrl.Trim()
    if ($normalized -match "^(https?://)(127\.0\.0\.1|localhost)(:\d+)(/v1.*)?$") {
        return "{0}host.docker.internal{1}{2}" -f $matches[1], $matches[3], $matches[4]
    }
    return $normalized
}

function Test-JanGatewayStyle {
    param([string]$BaseUrl)
    if (-not $BaseUrl) { return $false }
    return $BaseUrl -match "^(https?://)(127\.0\.0\.1|localhost|host\.docker\.internal)(:\d+)(/v1)?$"
}

function Resolve-AiProviderMetadata {
    param(
        [string]$Provider,
        [string]$BaseUrl,
        [string]$Model,
        [string]$ApiKey,
        [string]$GeminiApiKey
    )

    $normalized = $Provider.Trim().ToLower()
    if (-not $normalized) { $normalized = "openai_compatible" }

    switch ($normalized) {
        "openai" { $normalized = "openai_compatible" }
        "openai-compatible" { $normalized = "openai_compatible" }
        "local" { $normalized = "openai_compatible" }
        "ollama" { $normalized = "openai_compatible" }
        "lmstudio" { $normalized = "openai_compatible" }
        "lm-studio" { $normalized = "openai_compatible" }
        "vllm" { $normalized = "openai_compatible" }
        default { }
    }

    $isJanGateway = (Test-JanGatewayStyle -BaseUrl $BaseUrl) -and $Model
    if ($isJanGateway) {
        $normalized = "openai_compatible"
    }

    return [PSCustomObject]@{
        Provider = $normalized
        IsJan = $isJanGateway
        DisplayProvider = if ($isJanGateway) { "jan" } else { $normalized }
    }
}

function Refresh-JanContext {
    param([switch]$ForDockerMode)

    $python = Resolve-PythonExecutable
    if (-not (Test-Path $python)) {
        Write-Log "Python not found; skipping Jan auto-refresh for Docker mode."
        return $false
    }

    if (-not (Test-Path (Join-Path $root "scripts\jan_context.py"))) {
        Write-Log "scripts/jan_context.py missing; skipping Jan auto-refresh."
        return $false
    }

    $result = Run-CommandCapture -Executable $python -Arguments @((Join-Path $root "scripts\jan_context.py"), "--json") -TimeoutSeconds 15
    if ($result.ExitCode -eq 124) {
        Write-Log "Jan probe timed out after 15s; skipping Jan auto-refresh."
        return $false
    }
    if ($result.ExitCode -ne 0) {
        Write-Log "Jan context refresh command failed: $($result.StdErr.Trim())"
        return $false
    }

    $payload = $result.StdOut.Trim()
    if (-not $payload) {
        Write-Log "Jan context not available yet; keeping existing AI env values."
        return $false
    }

    try {
        $report = $payload | ConvertFrom-Json -ErrorAction Stop
    } catch {
        Write-Log "Failed to parse Jan context JSON output."
        return $false
    }

    if (-not $report.AI_BASE_URL) {
        Write-Log "Jan context has no AI_BASE_URL; skipping auto-update."
        return $false
    }

    $baseUrl = Normalize-JanContextValue -Value $report.AI_BASE_URL -FieldName "AI_BASE_URL"
    if (-not $baseUrl) { $baseUrl = [string]$report.AI_BASE_URL }
    if ($ForDockerMode) {
        $baseUrl = Convert-JanBaseUrlForDocker -BaseUrl $baseUrl
    }

    $modelValue = Normalize-JanContextValue -Value $report.AI_MODEL -FieldName "AI_MODEL"
    $apiKeyValue = Normalize-JanContextValue -Value $report.AI_API_KEY -FieldName "AI_API_KEY"
    Update-EnvValue -FilePath $envFile -Key "AI_BASE_URL" -Value $baseUrl
    if ($modelValue) { Update-EnvValue -FilePath $envFile -Key "AI_MODEL" -Value $modelValue }
    if ($apiKeyValue) { Update-EnvValue -FilePath $envFile -Key "AI_API_KEY" -Value $apiKeyValue }
    Update-EnvValue -FilePath $envFile -Key "AI_PROVIDER" -Value "openai_compatible"
    Update-EnvValue -FilePath $envFile -Key "ALLOW_EXTERNAL_AI" -Value "true"

    if ($ForDockerMode) {
        Write-Log "Jan context refreshed for Docker (AI_BASE_URL=$baseUrl, AI_MODEL=$modelValue)."
    } else {
        Write-Log "Jan context refreshed (AI_BASE_URL=$baseUrl, AI_MODEL=$modelValue)."
    }
    return $true
}

function Ensure-AiFeatureReadiness {
    param([switch]$ForDockerMode)

    if (-not (Test-Path $envFile)) {
        throw "Missing env file: $envFile"
    }

    $rawProvider = (Get-EnvFileValue -FilePath $envFile -Key "AI_PROVIDER").Trim()
    $baseUrl = (Get-EnvFileValue -FilePath $envFile -Key "AI_BASE_URL").Trim()
    $model = (Get-EnvFileValue -FilePath $envFile -Key "AI_MODEL").Trim()
    $openAiApiKey = (Get-EnvFileValue -FilePath $envFile -Key "AI_API_KEY").Trim()
    $geminiKey = (Get-EnvFileValue -FilePath $envFile -Key "GEMINI_API_KEY").Trim()

    $providerMeta = Resolve-AiProviderMetadata -Provider $rawProvider -BaseUrl $baseUrl -Model $model -ApiKey $openAiApiKey -GeminiApiKey $geminiKey
    $provider = $providerMeta.Provider
    Update-EnvValue -FilePath $envFile -Key "AI_PROVIDER" -Value $provider

    Update-EnvValue -FilePath $envFile -Key "AI_PROVIDER_ALLOWLIST" -Value "gemini,openai_compatible"

    $ready = $false
    if ($provider -eq "openai_compatible") {
        if ($baseUrl -and $model) {
            if ($ForDockerMode -and $baseUrl -match "^(https?://)(127\.0\.0\.1|localhost)(:\d+)(/v1.*)?$") {
                $baseUrl = Convert-JanBaseUrlForDocker -BaseUrl $baseUrl
                Update-EnvValue -FilePath $envFile -Key "AI_BASE_URL" -Value $baseUrl
            }
            Update-EnvValue -FilePath $envFile -Key "ALLOW_EXTERNAL_AI" -Value "true"
            $ready = $true
            if ($openAiApiKey) {
                Write-Log "AI configured for OpenAI-compatible provider (model=$model, base=$baseUrl, api_key=present)."
            } else {
                Write-Log "AI configured for OpenAI-compatible provider (model=$model, base=$baseUrl, api_key=not set)."
            }
        } else {
            Write-Log "AI is set to openai_compatible but AI_BASE_URL or AI_MODEL is missing; using AI as best effort."
        }
    } elseif ($provider -eq "gemini") {
        if ($geminiKey) {
            Update-EnvValue -FilePath $envFile -Key "ALLOW_EXTERNAL_AI" -Value "true"
            $ready = $true
            Write-Log "AI configured for Gemini provider."
        } else {
            Write-Log "AI_PROVIDER=gemini is selected but GEMINI_API_KEY is missing."
        }
    } else {
        Write-Log "AI_PROVIDER '$provider' is not recognized; defaulting to openai_compatible."
        $provider = "openai_compatible"
        Update-EnvValue -FilePath $envFile -Key "AI_PROVIDER" -Value "openai_compatible"
    }

    if (-not (Get-EnvFileValue -FilePath $envFile -Key "AI_REQUEST_TIMEOUT_SECONDS")) {
        Update-EnvValue -FilePath $envFile -Key "AI_REQUEST_TIMEOUT_SECONDS" -Value "120"
    }

    return @{
        AIProvider = $provider
        AIReady = $ready
        AIBaseUrl = $baseUrl
        AIModel = $model
        AIDisplayProvider = $providerMeta.DisplayProvider
        AICanUseJan = $openAiApiKey
        AIApiKey = (Get-EnvFileValue -FilePath $envFile -Key "AI_API_KEY").Trim()
        GeminiApiKey = (Get-EnvFileValue -FilePath $envFile -Key "GEMINI_API_KEY").Trim()
        AIProviderAllowList = (Get-EnvFileValue -FilePath $envFile -Key "AI_PROVIDER_ALLOWLIST").Trim()
    }
}

function Get-JanAvailability {
    try {
        $python = Resolve-PythonExecutable
        if (-not (Test-Path $python)) { return $false }
        if (-not (Test-Path (Join-Path $root "scripts\jan_context.py"))) { return $false }

        $result = Run-CommandCapture -Executable $python -Arguments @((Join-Path $root "scripts\jan_context.py"), "--json") -TimeoutSeconds 15
        if ($result.ExitCode -ne 0) { return $false }
        $payload = $result.StdOut.Trim()
        if (-not $payload) { return $false }
        try {
            $report = $payload | ConvertFrom-Json -ErrorAction Stop
        } catch {
            return $false
        }
        return -not [string]::IsNullOrWhiteSpace($report.AI_BASE_URL)
    } catch {
        return $false
    }
}

function Set-SelectedAiMode {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Mode
    )

    $selectedMode = $Mode.Trim().ToLower()
    if ($selectedMode -ne "gemini") {
        $selectedMode = "openai_compatible"
    }

    if ($selectedMode -eq "gemini") {
        Update-EnvValue -FilePath $envFile -Key "AI_PROVIDER" -Value "gemini"
        Update-EnvValue -FilePath $envFile -Key "AI_BASE_URL" -Value ""
        Update-EnvValue -FilePath $envFile -Key "AI_MODEL" -Value ""
        Update-EnvValue -FilePath $envFile -Key "AI_API_KEY" -Value ""
        Update-EnvValue -FilePath $envFile -Key "ALLOW_EXTERNAL_AI" -Value "true"
        return "gemini"
    }

    Update-EnvValue -FilePath $envFile -Key "AI_PROVIDER" -Value "openai_compatible"
    return "openai_compatible"
}

function Get-CurrentAiMode {
    if (-not (Test-Path $envFile)) {
        return "openai_compatible"
    }
    $provider = (Get-EnvFileValue -FilePath $envFile -Key "AI_PROVIDER").Trim().ToLower()
    if ($provider -eq "gemini") { return "gemini" }
    return "openai_compatible"
}

function Get-SelectedAiModeFromUi {
    if ($script:aiModeCombo -and $script:aiModeCombo.SelectedItem) {
        return $script:aiModeCombo.SelectedItem.ToString()
    }
    return Get-CurrentAiMode
}

function Format-AiSourceLabel {
    param([string]$DisplayProvider, [string]$RawProvider, [string]$BaseUrl)
    if (-not $DisplayProvider) { return $RawProvider }
    if ($DisplayProvider -eq "jan") {
        return "jan (local endpoint: $BaseUrl)"
    }
    return $DisplayProvider
}

function Write-AiHealthLog {
    param([hashtable]$State)

    if (-not $State) {
        Write-Log "AI Health: state unavailable."
        return
    }

    $provider = ($State.AIProvider -as [string])
    $displayProvider = ($State.AIDisplayProvider -as [string])
    if (-not $displayProvider) { $displayProvider = $provider }
    $ready = [bool]$State.AIReady
    $baseUrl = ($State.AIBaseUrl -as [string])
    $model = ($State.AIModel -as [string])
    $allowList = ($State.AIProviderAllowList -as [string])
    $geminiKey = ($State.GeminiApiKey -as [string])

    $providerMode = if ($displayProvider -eq "jan" -or (Test-JanGatewayStyle -BaseUrl $baseUrl -and $provider -eq "openai_compatible")) { "LOCAL JAN" } else { "EXTERNAL" }
    if ($ready) {
        $providerLabel = Format-AiSourceLabel -DisplayProvider $displayProvider -RawProvider $provider -BaseUrl $baseUrl
        Write-Log "AI Health [SOURCE=$providerMode]: READY"
        Write-Log "AI Provider: $providerLabel | model=$model | allowlist=$allowList"
        if ($displayProvider -eq "jan") {
            Write-Log "Local Jan endpoint is configured and selected."
        }
        return
    }
    Write-Log "AI Health [SOURCE=$providerMode]: NOT READY"
    Write-Log "AI Provider: $displayProvider | base=$baseUrl | model=$model"
    $missing = @()
    if (-not $baseUrl -and ($provider -eq "openai_compatible")) {
        $missing += "set AI_BASE_URL (or use Jan refresh)"
    }
    if ($provider -eq "openai_compatible" -and (-not $model)) {
        $missing += "set AI_MODEL"
    }
    if ($provider -eq "gemini" -and (-not $geminiKey)) {
        $missing += "set GEMINI_API_KEY"
    }
    if (-not $missing.Count) {
        $missing += "select a supported AI_PROVIDER and fill required values"
    }
    if (-not $baseUrl -and ($provider -eq "openai_compatible")) {
        Write-Log "AI missing: set AI_BASE_URL (for local Jan set jan_context refresh) and AI_MODEL."
    }
    if (-not $geminiKey -and ($provider -eq "gemini")) {
        Write-Log "AI missing: GEMINI_API_KEY required for gemini provider."
    }
    if ($provider -eq "openai_compatible" -and (-not $model)) {
        Write-Log "AI missing: AI_MODEL required."
    }
    if ($provider -eq "gemini" -and (-not $geminiKey)) {
        Write-Log "AI missing: GEMINI_API_KEY required."
    }
    if ($provider -eq "openai_compatible" -and (-not $baseUrl)) {
        Write-Log "AI missing: AI_BASE_URL required."
    }
}

function Show-NotConfigured {
    param([string]$PathToRun)
    [System.Windows.Forms.MessageBox]::Show(
        "Cannot launch: missing '$PathToRun'.",
        "Missing file",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Warning
    ) | Out-Null
}

function Test-DockerDaemon {
    $result = Run-CommandCapture -Executable "docker" -Arguments @("version", "--format", "{{.Server.Version}}")
    return ($result.ExitCode -eq 0)
}

function Start-DockerServices {
    param()
    if (-not (Test-Path $composeFile)) {
        Show-NotConfigured $composeFile
        return
    }
    if (-not (Test-Path $envFile)) {
        Show-NotConfigured $envFile
        return
    }
    if (-not (Test-DockerDaemon)) {
        Write-Log "ERROR: Docker engine is not running."
        Write-Log "Start Docker Desktop first, or use 'Start Local' (no Docker) instead."
        return
    }

    Update-EnvValue -FilePath $envFile -Key "OKR_DATA_ACCESS_MODE" -Value "supabase_api"
    $selectedAiMode = Get-SelectedAiModeFromUi
    $normalizedAiMode = Set-SelectedAiMode -Mode $selectedAiMode
    if ($normalizedAiMode -eq "openai_compatible") {
        if (Get-JanAvailability) {
            $null = Refresh-JanContext -ForDockerMode
        } else {
            Write-Log "Jan not detected; keeping existing openai_compatible env values."
        }
    } else {
        Write-Log "Gemini mode selected; skipping Jan auto-refresh."
    }
    $aiState = Ensure-AiFeatureReadiness -ForDockerMode
    Write-AiHealthLog -State $aiState

    $services = @("backend-api","backend-worker","spa-bff","spa-web")
    Write-Log "Starting docker services: $($services -join ', ')"
    Write-Log "This can take a few minutes (image build, container start, health checks)..."
    $startArgs = @("compose","-f",$composeFile,"--env-file",$envFile,"up","-d")
    $startArgs += $services
    # Wait for compose to fully finish. The previous fire-and-forget (-NoWait)
    # approach could return while compose was still creating containers,
    # producing partial starts (some services missing) that the readiness
    # check then mistook for success.
    $result = Invoke-HiddenProcess -Executable "docker" -Arguments $startArgs -TimeoutSeconds 300
    if ($result.ExitCode -ne 0) {
        Write-Log "docker up failed: $($result.StdErr)"
        return
    }
    if ($result.StdOut.Trim()) {
        foreach ($line in ($result.StdOut.Trim() -split "\r?\n" | Select-Object -Last 4)) {
            Write-Log "docker: $line"
        }
    }
    Wait-AppReady -TimeoutSeconds 90 | Out-Null
    Open-AppInBrowser
    Write-Log "Start sequence complete. You can close this launcher; the app keeps running."
}

function Stop-DockerServices {
    param()
    if (-not (Test-Path $composeFile)) {
        Show-NotConfigured $composeFile
        return
    }
    if (-not (Test-DockerDaemon)) {
        Write-Log "Docker engine is not running; nothing to stop."
        return
    }
    Write-Log "Stopping docker services."
    $result = Invoke-HiddenProcess -Executable "docker" -Arguments @("compose","-f",$composeFile,"--env-file",$envFile,"down") -NoWait
    if ($result.ExitCode -ne 0) {
        Write-Log "docker down failed: $($result.StdErr)"
    }
}

function Start-LocalHybridServices {
    param()
    if (-not (Test-Path $hybridRunScript)) {
        Show-NotConfigured $hybridRunScript
        return
    }
    Write-Log "Starting local hybrid stack (backend + worker + BFF + SPA, no Docker)..."
    Start-Process -FilePath "cmd.exe" -ArgumentList "/d", "/c", "`"$hybridRunScript`"" -WorkingDirectory $root | Out-Null
    Write-Log "Local hybrid launcher started in its own window; watch it for progress."
}

function Stop-LocalHybridServices {
    param()
    if (-not (Test-Path $hybridStopScript)) {
        Show-NotConfigured $hybridStopScript
        return
    }
    Write-Log "Stopping local hybrid services..."
    $result = Invoke-HiddenProcess -Executable "cmd.exe" -Arguments "/d", "/c", "`"$hybridStopScript`""
    if ($result.ExitCode -eq 0) {
        Write-Log "Local hybrid services stopped."
    } else {
        Write-Log "Stop script exited with code $($result.ExitCode)."
    }
}

function Test-HttpEndpoint {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Get -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    } catch {
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
            return ($code -ge 200 -and $code -lt 500)
        }
        return $false
    }
}

function Show-ServiceStatus {
    $checks = @(
        @{ Name = "Backend API"; Url = "http://127.0.0.1:8100/healthz" },
        @{ Name = "SPA BFF";     Url = "http://127.0.0.1:3001/healthz" },
        @{ Name = "SPA Web";     Url = "http://127.0.0.1:3000/" }
    )
    $dockerUp = $false
    if (-not (Test-DockerDaemon)) {
        Write-Log "Docker engine is not running (Docker Desktop stopped)."
    } else {
        try {
            $psResult = Run-CommandCapture -Executable "docker" -Arguments @("compose","-f",$composeFile,"--env-file",$envFile,"ps","--services","--filter","status=running")
            if ($psResult.ExitCode -eq 0 -and $psResult.StdOut.Trim()) {
                $dockerUp = $true
                Write-Log ("Docker services running: " + (($psResult.StdOut.Trim() -split "\r?\n") -join ", "))
            }
        } catch {
        }
    }

    foreach ($check in $checks) {
        if (Test-HttpEndpoint -Url $check.Url) {
            Write-Log "[UP]   $($check.Name) ($($check.Url))"
        } else {
            Write-Log "[DOWN] $($check.Name) ($($check.Url))"
        }
    }
    if (-not $dockerUp) {
        Write-Log "No Docker compose services detected (local mode or stopped)."
    }
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "OKR App Launcher"
$form.Size = New-Object System.Drawing.Size(640, 330)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedSingle
$form.MaximizeBox = $false
$form.BackColor = $uiCanvas
$form.ForeColor = $uiText
$form.Font = $uiFont

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "OKR App Launcher"
$lblTitle.SetBounds(20, 10, 420, 32)
$lblTitle.Font = $uiTitleFont
$lblTitle.ForeColor = $uiText
$form.Controls.Add($lblTitle)
$lblSubtitle = New-Object System.Windows.Forms.Label
$lblSubtitle.Text = "Production-ready local/docker run control panel"
$lblSubtitle.SetBounds(22, 42, 520, 20)
$lblSubtitle.Font = New-Object System.Drawing.Font("Segoe UI", [float]8.75)
$lblSubtitle.ForeColor = $uiSubText
$form.Controls.Add($lblSubtitle)

$groupActions = New-Object System.Windows.Forms.GroupBox
$groupActions.Text = "Docker mode"
$groupActions.SetBounds(18, 72, 604, 150)
$groupActions.BackColor = $uiPanel
$groupActions.ForeColor = $uiText
$groupActions.Font = $uiSectionFont

# Set-BusyState is defined earlier (top of script) with reentrancy guard.

$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Text = "Start"
$btnStart.SetBounds(18, 28, 130, 34)
$btnStart.Add_Click({
    Set-BusyState -Busy $true
    Write-Log "Starting Docker stack..."
    try   { Start-DockerServices }
    finally { Set-BusyState -Busy $false }
})

$btnStop = New-Object System.Windows.Forms.Button
$btnStop.Text = "Stop"
$btnStop.SetBounds(160, 28, 130, 34)
$btnStop.Add_Click({
    $confirm = [System.Windows.Forms.MessageBox]::Show(
        "Stopping removes the containers completely (docker compose down).`n`nData in Postgres/Supabase is not deleted, but containers will disappear from Docker Desktop until you Start again.`n`nContinue?",
        "Confirm Stop",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    if ($confirm -ne [System.Windows.Forms.DialogResult]::Yes) {
        Write-Log "Stop cancelled."
        return
    }
    Set-BusyState -Busy $true
    Write-Log "Stopping Docker stack..."
    try   { Stop-DockerServices }
    finally { Set-BusyState -Busy $false }
})

$btnRestart = New-Object System.Windows.Forms.Button
$btnRestart.Text = "Restart"
$btnRestart.SetBounds(302, 28, 130, 34)
$btnRestart.Add_Click({
    Set-BusyState -Busy $true
    Write-Log "Restarting Docker stack..."
    try {
        Stop-DockerServices
        Start-Sleep -Milliseconds 700
        Start-DockerServices
    } finally { Set-BusyState -Busy $false }
})

$btnOpenWeb = New-Object System.Windows.Forms.Button
$btnOpenWeb.Text = "Open App"
$btnOpenWeb.SetBounds(444, 28, 130, 34)
$btnOpenWeb.Add_Click({
    Open-AppInBrowser
})

$groupActions.Controls.AddRange(@($btnStart, $btnStop, $btnRestart, $btnOpenWeb))
$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = "Ready."
$lblStatus.SetBounds(18, 112, 570, 26)
$lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", [float]9.25)
$lblStatus.ForeColor = $uiSubText
$lblStatus.AutoSize = $false
$lblStatus.AutoEllipsis = $true
$lblStatus.TextAlign = [System.Drawing.ContentAlignment]::TopLeft
$lblStatus.BackColor = [System.Drawing.Color]::Transparent

$actionButtons = @($btnStart, $btnStop, $btnRestart, $btnOpenWeb)
foreach ($btn in $actionButtons) {
    $btn.Font = $uiButtonFont
    $btn.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $btn.FlatAppearance.BorderColor = $uiAccent
    $btn.FlatAppearance.BorderSize = 1
    $btn.BackColor = $uiButtonBg
    $btn.ForeColor = [System.Drawing.Color]::White
    $btn.UseVisualStyleBackColor = $false
}
$groupActions.Controls.Add($lblStatus)
$form.Controls.Add($groupActions)

$groupLocal = New-Object System.Windows.Forms.GroupBox
$groupLocal.Text = "Local mode (no Docker)"
$groupLocal.SetBounds(18, 228, 604, 64)
$groupLocal.BackColor = $uiPanel
$groupLocal.ForeColor = $uiText
$groupLocal.Font = $uiSectionFont

$btnLocalStart = New-Object System.Windows.Forms.Button
$btnLocalStart.Text = "Start Local"
$btnLocalStart.SetBounds(18, 22, 130, 32)
$btnLocalStart.Add_Click({
    Start-LocalHybridServices
})

$btnLocalStop = New-Object System.Windows.Forms.Button
$btnLocalStop.Text = "Stop Local"
$btnLocalStop.SetBounds(160, 22, 130, 32)
$btnLocalStop.Add_Click({
    Set-BusyState -Busy $true
    Write-Log "Stopping local hybrid services..."
    try   { Stop-LocalHybridServices }
    finally { Set-BusyState -Busy $false }
})

$btnStatus = New-Object System.Windows.Forms.Button
$btnStatus.Text = "Status"
$btnStatus.SetBounds(302, 22, 130, 32)
$btnStatus.Add_Click({
    Set-BusyState -Busy $true
    Write-Log "Checking service status..."
    try   { Show-ServiceStatus }
    finally { Set-BusyState -Busy $false }
})

$lblLocalNote = New-Object System.Windows.Forms.Label
$lblLocalNote.Text = "Runs backend + worker + BFF + SPA directly on this PC."
$lblLocalNote.SetBounds(444, 26, 150, 28)
$lblLocalNote.Font = New-Object System.Drawing.Font("Segoe UI", [float]8)
$lblLocalNote.ForeColor = $uiSubText

foreach ($btn in @($btnLocalStart, $btnLocalStop, $btnStatus)) {
    $btn.Font = $uiButtonFont
    $btn.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $btn.FlatAppearance.BorderColor = $uiAccent
    $btn.FlatAppearance.BorderSize = 1
    $btn.BackColor = $uiButtonBg
    $btn.ForeColor = [System.Drawing.Color]::White
    $btn.UseVisualStyleBackColor = $false
}
$groupLocal.Controls.AddRange(@($btnLocalStart, $btnLocalStop, $btnStatus, $lblLocalNote))
$form.Controls.Add($groupLocal)

$lblAiMode = New-Object System.Windows.Forms.Label
$lblAiMode.Text = "AI mode:"
$lblAiMode.SetBounds(18, 74, 70, 24)
$lblAiMode.Font = New-Object System.Drawing.Font("Segoe UI", 9.5)
$lblAiMode.ForeColor = $uiText
$groupActions.Controls.Add($lblAiMode)

$aiMode = New-Object System.Windows.Forms.ComboBox
$aiMode.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
$aiMode.Items.AddRange(@("openai_compatible", "gemini"))
$aiModeIndex = $aiMode.FindStringExact((Get-CurrentAiMode))
if ($aiModeIndex -ge 0) {
    $aiMode.SelectedIndex = $aiModeIndex
} else {
    $aiMode.SelectedIndex = 0
}
$aiMode.SetBounds(90, 70, 220, 28)
$aiMode.ForeColor = [System.Drawing.Color]::White
$aiMode.BackColor = $uiButtonBg
$aiMode.Font = $uiFont
$aiMode.FlatStyle = [System.Windows.Forms.FlatStyle]::Popup
$aiMode.Add_SelectedIndexChanged({
    if ($script:aiModeCombo -and $script:aiModeCombo.SelectedItem) {
        Write-Log "AI mode selected: $($script:aiModeCombo.SelectedItem). Apply with Start/Restart."
    }
})
$groupActions.Controls.Add($aiMode)
$script:aiModeCombo = $aiMode

$lblAiModeNote = New-Object System.Windows.Forms.Label
$lblAiModeNote.Text = "Restart or Start to apply mode choice."
$lblAiModeNote.SetBounds(320, 70, 250, 28)
$lblAiModeNote.Font = New-Object System.Drawing.Font("Segoe UI", 8.75)
$lblAiModeNote.ForeColor = $uiSubText
$groupActions.Controls.Add($lblAiModeNote)

$script:lblStatus = $lblStatus

Write-LauncherLog -Message "=== Launcher session started (PID $PID) ==="
Write-Log "Launcher ready. Use Docker mode or Local mode (no Docker) to start."
Write-Log "Activity log: $launcherLogFile"
Write-Log "Docker mode uses: $composeFile"
Write-Log "Local mode uses: $hybridRunScript"
if (Test-Path $envFile) {
    Write-Log "Using env: $envFile"
} else {
    Write-Log "Notice: .env file is missing."
}

if (Test-Path $envFile) {
    try {
        Write-AiHealthLog -State (Ensure-AiFeatureReadiness -ForDockerMode)
    } catch {
        Write-Log "AI readiness check unavailable: $($_.Exception.Message)"
    }
}

# Global crash handler: any unhandled exception is written to the activity log
# before the process exits, so silent deaths leave a trace.
try {
    [System.Windows.Forms.Application]::add_ThreadException({
        param($sender, $e)
        Write-LauncherLog -Message ("CRASH (UI thread): " + $e.Exception.GetType().Name + ": " + $e.Exception.Message + " @ " + ($e.Exception.StackTrace | Select-Object -First 1))
    })
    [AppDomain]::CurrentDomain.add_UnhandledException({
        param($sender, $e)
        $ex = $e.ExceptionObject
        Write-LauncherLog -Message ("CRASH (appdomain): " + $ex.GetType().Name + ": " + $ex.Message)
    })
} catch {
    # Handler registration is best-effort; never block startup on it.
}

# Prevent closing the form while an operation is running: deferring the close
# avoids DoEvents reentrancy tearing down the process mid-work.
$form.Add_FormClosing({
    param($sender, $e)
    if ($script:isBusy) {
        $e.Cancel = $true
        Write-Log "Operation in progress - close will be allowed when it finishes."
    }
})

Write-LauncherLog -Message "Launcher UI shown."
[void]$form.ShowDialog()
Write-LauncherLog -Message "=== Launcher session ended ==="
