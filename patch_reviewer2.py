with open('tests/unit/test_reviewer.py', 'r') as f:
    content = f.read()

content = content.replace(
    '        with patch("farm_agent.core.sandbox.DockerSandbox.__init__", return_value=None):\n            sandbox = DockerSandbox()',
    '        with patch("farm_agent.core.sandbox.DockerSandbox.__init__", return_value=None):\n            sandbox = DockerSandbox()' # Wait I just need to remove SIM117 error which means I should combine with statements
)

# Wait SIM117 error is: "Use a single `with` statement with multiple contexts instead of nested `with` statements"
# Let me use regex or sed to fix SIM117
