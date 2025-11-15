#!/usr/bin/env python3
import subprocess
import sys

print("📦 Instalando dependencias...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "streamlit"])
print("✅ Instalación completa")
