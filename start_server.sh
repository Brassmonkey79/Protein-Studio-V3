#!/bin/bash
echo "============================================================"
echo "  Protein Design Studio V3 - Server Launcher"
echo "============================================================"
echo ""
echo "Installing dependencies..."
pip install flask paramiko scp --quiet 2>/dev/null
echo "Starting server..."
echo ""
python "$(dirname "$0")/server.py"
