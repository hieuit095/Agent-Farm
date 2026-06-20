with open('tests/unit/test_reviewer.py', 'r') as f:
    content = f.read()

content = content.replace(
    '        with patch("farm_agent.core.sandbox.DockerSandbox.__init__", return_value=None):\n            sandbox = DockerSandbox()',
    '        sandbox = DockerSandbox()'
)

# And similarly for test_poc_generator
with open('tests/unit/test_poc_generator.py', 'r') as f:
    poc_content = f.read()

poc_content = poc_content.replace(
    '        with patch("farm_agent.core.sandbox.DockerSandbox.__init__", return_value=None):\n            sandbox = DockerSandbox()',
    '        sandbox = DockerSandbox()'
)

with open('tests/unit/test_reviewer.py', 'w') as f:
    f.write(content)

with open('tests/unit/test_poc_generator.py', 'w') as f:
    f.write(poc_content)
