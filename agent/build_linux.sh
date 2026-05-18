#!/bin/bash
set -e

echo "Installing dependencies..."
pip install pyinstaller psutil

echo "Building agent..."
pyinstaller --onefile --name assetmanager-agent agent.py

echo ""
echo "Done! Binary: dist/assetmanager-agent"
echo "Copy dist/assetmanager-agent and agent.ini to the target machine."
