@echo off
netsh advfirewall firewall add rule name="Vite ItemApproval 5173" dir=in action=allow protocol=TCP localport=5173 > "%~dp0firewall-result.txt" 2>&1
echo EXIT=%errorlevel% >> "%~dp0firewall-result.txt"
