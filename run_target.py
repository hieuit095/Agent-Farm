"""Run farm_agent target with environment variables set from .env"""
import os
import subprocess

# Read .env file
env_file = r"C:\Users\USER\Documents\GitHub\ContribAI\.env"
with open(env_file) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value

print(f"GITHUB_TOKEN: {os.environ.get('GITHUB_TOKEN', 'NOT SET')[:10]}...")
print(f"MINIMAX_API_KEY: {os.environ.get('MINIMAX_API_KEY', 'NOT SET')[:10]}...")

# Now import and run farm_agent
import sys
sys.path.insert(0, r"C:\Users\USER\Documents\GitHub\ContribAI\src")

from farm_agent.cli.main import cli
import click

# Run the target command
cli()
