import os
os.environ['GITHUB_TOKEN'] = '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'

import httpx

# Check proxy settings
print("Proxy settings:")
print(f"  HTTP_PROXY: {os.environ.get('HTTP_PROXY', 'not set')}")
print(f"  HTTPS_PROXY: {os.environ.get('HTTPS_PROXY', 'not set')}")
print(f"  http_proxy: {os.environ.get('http_proxy', 'not set')}")
print(f"  https_proxy: {os.environ.get('https_proxy', 'not set')}")
print(f"  NO_PROXY: {os.environ.get('NO_PROXY', 'not set')}")

# Check httpx default transport
print("\nhttpx default transport info:")
transport = httpx.DefaultTransport()
print(f"  Transport: {transport}")

# Check urllib3 proxy settings
import urllib3
print(f"\nurllib3 version: {urllib3.__version__}")
print(f"  ProxyManager: {urllib3.ProxyManager}")

# Check if there's a proxy in urllib3
try:
    from urllib3 import ProxyManager
    pm = ProxyManager('http://proxy.example.com:8080')
    print(f"  ProxyManager can be created: yes")
except Exception as e:
    print(f"  ProxyManager error: {e}")
