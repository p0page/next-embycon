$KODIPATH = "c:\tools\Kodi21"
$PORTABLE_DATA = "$KODIPATH\portable_data"

$REPOROOT = git rev-parse --show-toplevel
$PLUGINROOT = "$REPOROOT\plugin.video.nextembycon"

# Remove existing plugin directory
if (Test-Path "$PORTABLE_DATA\addons\plugin.video.nextembycon") {
    Remove-Item -Path "$PORTABLE_DATA\addons\plugin.video.nextembycon" -Recurse -Force
}

# Create the plugin directory
New-Item -Path "$PORTABLE_DATA\addons\plugin.video.nextembycon" -ItemType Directory -Force | Out-Null

# Copy individual files
Copy-Item -Path "$PLUGINROOT\addon.xml" -Destination "$PORTABLE_DATA\addons\plugin.video.nextembycon\" -Force
Copy-Item -Path "$PLUGINROOT\default.py" -Destination "$PORTABLE_DATA\addons\plugin.video.nextembycon\" -Force
Copy-Item -Path "$PLUGINROOT\fanart.jpg" -Destination "$PORTABLE_DATA\addons\plugin.video.nextembycon\" -Force -ErrorAction SilentlyContinue
Copy-Item -Path "$PLUGINROOT\icon.png" -Destination "$PORTABLE_DATA\addons\plugin.video.nextembycon\" -Force -ErrorAction SilentlyContinue
# Copy-Item -Path "$PLUGINROOT\kodi.png" -Destination "$PORTABLE_DATA\addons\plugin.video.nextembycon\" -Force
Copy-Item -Path "$PLUGINROOT\service.py" -Destination "$PORTABLE_DATA\addons\plugin.video.nextembycon\" -Force
Copy-Item -Path "$PLUGINROOT\context.py" -Destination "$PORTABLE_DATA\addons\plugin.video.nextembycon\" -Force

# Copy resources directory recursively
Copy-Item -Path "$PLUGINROOT\resources" -Destination "$PORTABLE_DATA\addons\plugin.video.nextembycon\resources" -Recurse -Force

# Change to Kodi directory and launch Kodi in portable mode
#Set-Location "$KODIPATH"
Start-Process "$KODIPATH\kodi.exe" -ArgumentList "-p"
