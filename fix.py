import re

with open("farm_agent/cli/main.py", "r") as f:
    content = f.read()

# Instead of `f"""`, use a regular raw string `r"""` to avoid escape sequence issues
new_banner = '''def print_banner():
    banner = r"""[bold cyan]
     _                    _     _____
    / \\   __ _  ___ _ __ | |_  |  ___|_ _ _ __ _ __ ___
   / _ \\ / _` |/ _ \\ '_ \\| __| | |_ / _` | '__| '_ ` _ \\
  / ___ \\ (_| |  __/ | | | |_  |  _| (_| | |  | | | | | |
 /_/   \\_\\__, |\\___|_| |_|\\__| |_|  \\__,_|_|  |_| |_| |_|
         |___/

  [dim]Autonomous Agent Orchestration v{__version__}[/dim]
[/bold cyan]""".replace("{__version__}", __version__)
    console.print(banner)'''

content = re.sub(r'def print_banner\(\):.*?console\.print\(banner\)', new_banner, content, flags=re.DOTALL)

with open("farm_agent/cli/main.py", "w") as f:
    f.write(content)
