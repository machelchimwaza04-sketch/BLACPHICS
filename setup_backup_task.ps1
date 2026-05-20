# PowerShell script to set up daily PostgreSQL backup
# Run this script as Administrator to create the scheduled task

$backupScript = "C:\Users\Nettz Energy\Desktop\Blacphics\backup_postgres.bat"
$taskName = "Blacphics_PostgreSQL_Backup"

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Scheduled task '$taskName' already exists. Removing it first..."
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Create new scheduled task
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$backupScript`""
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType InteractiveToken

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Daily backup of Blacphics PostgreSQL database"

Write-Host "Scheduled task '$taskName' created successfully."
Write-Host "The task will run daily at 2:00 AM."
Write-Host "You can modify the schedule using Task Scheduler (taskschd.msc)"