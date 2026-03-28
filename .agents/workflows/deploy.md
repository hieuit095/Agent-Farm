---
description: Build and deploy workflow – build Docker images, run in containers, deploy
---

# Deploy Workflow

## Steps

### Local Development
1. **Install locally**
```bash
pip install -e ".[dev]"
```

2. **Run CLI directly**
```bash
farm_agent run --dry-run
```

### Docker

3. **Build Docker image**
```bash
docker build -t farm_agent:latest .
```

4. **Run in container**
```bash
docker run --rm \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v ~/.farm_agent:/root/.farm_agent \
  farm_agent:latest run --dry-run
```

5. **Run with docker-compose**
```bash
docker-compose up
```

### Package Build

6. **Build Python package**
// turbo
```bash
python -m build
```

7. **Verify package contents**
// turbo
```bash
python -m twine check dist/*
```

8. **Test install from built package**
```bash
pip install dist/farm_agent-*.whl
farm_agent --help
```

### Production Deployment

9. **Set environment variables (alternative to config.yaml)**
```bash
export CONTRIBAI_GITHUB_TOKEN=ghp_xxx
export CONTRIBAI_LLM_API_KEY=xxx
export CONTRIBAI_LLM_PROVIDER=gemini
```

10. **Run as a scheduled job (cron)**
```bash
# Run every 6 hours
0 */6 * * * cd /path/to/farm_agent && farm_agent run >> /var/log/farm_agent.log 2>&1
```

11. **Monitor logs**
// turbo
```bash
python -c "
import pathlib
db = pathlib.Path.home() / '.farm_agent' / 'memory.db'
print(f'Memory DB exists: {db.exists()}')
if db.exists():
    print(f'Size: {db.stat().st_size / 1024:.1f} KB')
"
```
