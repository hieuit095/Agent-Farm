with open("tests/test_omni_e2e_pipeline.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "# create an AsyncMock for aclose so await self._client.aclose() works correctly" in line:
        continue
    if "mock_async_client_instance.aclose = mock_aclose" in line and i > 50:
        continue
    if "mock_httpx.AsyncClient = MagicMock(return_value=mock_async_client_instance)" in line and i > 50:
        continue
    if 'sys.modules["httpx"] = mock_httpx' in line and i > 50:
        continue
    if "mock_async_client_instance.aclose = AsyncMock(return_value=None)" in line:
        continue
    if "mock_async_client_instance.aclose = AsyncMock()" in line:
        continue
    new_lines.append(line)

with open("tests/test_omni_e2e_pipeline.py", "w") as f:
    f.writelines(new_lines)
