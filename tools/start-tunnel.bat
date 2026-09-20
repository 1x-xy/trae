@echo off
chcp 65001 >nul
title 物品申报系统 - 公网隧道（断线自动重连）
REM ============================================================
REM 一键启动公网隧道（Cloudflare 临时隧道，免费、无需注册）
REM 前提：后端(8000)与前端(5173)都已在本机启动
REM
REM 稳定性设置：
REM   --protocol http2  强制 TCP 协议（国内网络比默认 QUIC/UDP 稳定，避免错误1033）
REM   外层循环          隧道进程意外退出后自动重启
REM
REM 启动后在本窗口日志中找到 https://xxxx.trycloudflare.com
REM 注意：临时隧道每次【重启进程】都会换新域名
REM ============================================================
cd /d "%~dp0"

:loop
echo [%date% %time%] 正在启动隧道（HTTP/2 协议）...
cloudflared.exe tunnel --url http://localhost:5173 --protocol http2 --no-autoupdate
echo [%date% %time%] 隧道已退出，5 秒后自动重连...
timeout /t 5 /nobreak >nul
goto loop
