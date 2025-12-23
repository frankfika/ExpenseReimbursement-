#!/bin/bash
cd "$(dirname "$0")"

clear
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║       📋 报销助手 - 网页版           ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  正在启动网页服务..."
echo "  浏览器将自动打开 http://localhost:5000"
echo ""
echo "  按 Ctrl+C 可停止服务"
echo ""
echo "  ──────────────────────────────────────"
echo ""

python3 web_app.py
