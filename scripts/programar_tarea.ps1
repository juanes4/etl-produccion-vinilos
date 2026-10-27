# Registra el ETL en el Programador de tareas de Windows para que corra cada 24 horas.
# Uso (PowerShell):  .\scripts\programar_tarea.ps1 -Hora "02:00"
# Para quitarla:     Unregister-ScheduledTask -TaskName "ETL Vinilos" -Confirm:$false
param(
    [string]$Hora = "02:00",
    [string]$Nombre = "ETL Vinilos"
)

$proyecto = Split-Path -Parent $PSScriptRoot
$bat = Join-Path $proyecto "scripts\ejecutar_etl.bat"

$accion = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`"" -WorkingDirectory $proyecto
$disparador = New-ScheduledTaskTrigger -Daily -At $Hora
# StartWhenAvailable: si el PC estaba apagado a esa hora, corre apenas se encienda.
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $Nombre -Action $accion -Trigger $disparador -Settings $ajustes `
    -Description "Extrae el Excel de máquinas de vinilos, lo limpia y lo carga a MySQL" -Force | Out-Null

Write-Host "Tarea '$Nombre' programada todos los días a las $Hora."
Write-Host "Probarla ahora: Start-ScheduledTask -TaskName '$Nombre'"
