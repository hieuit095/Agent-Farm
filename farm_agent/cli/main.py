"""Farm-Agent CLI - Rich command-line interface.

Usage:
    farm_agent run           Auto-discover repos and contribute
    farm_agent target <url>  Target a specific repo
    farm_agent analyze <url> Analyze a repo without contributing
    farm_agent solve <url>   Solve issues in a specific repo
    farm_agent status        Show status of submitted PRs
    farm_agent stats         Show overall statistics
    farm_agent config        Show current configuration
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from farm_agent import __version__
from farm_agent.core.config import load_config

# Fix Windows console encoding for emoji/unicode support
if sys.platform == "win32":
    import os

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console()


def setup_logging(verbose: bool = False, config=None):
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [
        RichHandler(console=Console(stderr=True), show_path=False, rich_tracebacks=True)
    ]

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=handlers,
    )

    # Set up daily rotating file logger (does NOT conflict with Rich console)
    if config is not None:
        from farm_agent.core.logger import setup_daily_logger

        setup_daily_logger(config.logging)
    else:
        # Fallback: attach daily logger with defaults when config isn't loaded yet
        try:
            from farm_agent.core.config import LogConfig
            from farm_agent.core.logger import setup_daily_logger

            setup_daily_logger(LogConfig())
        except Exception:
            pass  # Don't fail if file logging can't be set up


def print_banner():
    banner = (
        r"""[bold cyan]
     _                    _     _____
    / \   __ _  ___ _ __ | |_  |  ___|_ _ _ __ _ __ ___
   / _ \ / _` |/ _ \ '_ \| __| | |_ / _` | '__| '_ ` _ \
  / ___ \ (_| |  __/ | | | |_  |  _| (_| | |  | | | | | |
 /_/   \_\__, |\___|_| |_|\__| |_|  \__,_|_|  |_| |_| |_|
         |___/

"""
        + f"  [dim]Autonomous Agent Orchestration v{__version__}[/dim]\n[/bold cyan]"
    )
    console.print(banner)


@click.group()
@click.option("--config", "-c", type=click.Path(), default=None, help="Config file path")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx, config, verbose):
    """Farm-Agent - AI Agent that contributes to open source projects."""
    ctx.ensure_object(dict)
    setup_logging(verbose)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose


@cli.command()
@click.option("--language", "-l", multiple=True, help="Filter by language(s)")
@click.option("--stars", "-s", default=None, help="Star range (e.g., 100-5000)")
@click.option("--max-prs", "-m", type=int, default=None, help="Max PRs to create")
@click.option("--dry-run", is_flag=True, help="Analyze and generate without creating PRs")
@click.pass_context
def run(ctx, language, stars, max_prs, dry_run):
    """Auto-discover repositories and create contributions."""
    print_banner()

    config = load_config(ctx.obj["config_path"])

    # Apply CLI overrides
    if language:
        config.discovery.languages = list(language)
    if stars:
        parts = stars.split("-")
        config.discovery.stars_range = [int(parts[0]), int(parts[1])]
    if max_prs:
        config.github.max_prs_per_day = max_prs

    if not config.github.token:
        console.print("[red]❌ GitHub token not configured![/red]")
        console.print("Set it in config.yaml or run: farm_agent config set github.token <token>")
        sys.exit(1)

    if not config.llm.api_key:
        console.print("[red]❌ LLM API key not configured![/red]")
        sys.exit(1)

    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]LIVE[/green]"
    console.print(f"\n🚀 Starting Farm-Agent pipeline ({mode})")
    console.print(f"   Languages: {', '.join(config.discovery.languages)}")
    console.print(f"   Stars: {config.discovery.stars_range[0]}-{config.discovery.stars_range[1]}")
    console.print(f"   LLM: {config.llm.provider} ({config.llm.model})")
    console.print()

    from farm_agent.orchestrator.pipeline import FarmAgentPipeline

    pipeline = FarmAgentPipeline(config)
    result = asyncio.run(pipeline.run(dry_run=dry_run))

    # Print results
    _print_result(result, dry_run)


@cli.command()
@click.argument("url")
@click.option("--types", "-t", default=None, help="Contribution types (comma-separated)")
@click.option("--dry-run", is_flag=True, help="Analyze and generate without creating PRs")
@click.pass_context
def target(ctx, url, types, dry_run):
    """Target a specific repository for contributions."""
    print_banner()

    config = load_config(ctx.obj["config_path"])

    if types:
        config.contribution.enabled_types = types.split(",")

    if not config.github.token:
        console.print("[red]❌ GitHub token not configured![/red]")
        sys.exit(1)

    if not config.llm.api_key:
        console.print("[red]❌ LLM API key not configured![/red]")
        sys.exit(1)

    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]LIVE[/green]"
    console.print(f"\n🎯 Targeting: {url} ({mode})")
    console.print(f"   LLM: {config.llm.provider} ({config.llm.model})\n")

    from farm_agent.orchestrator.pipeline import FarmAgentPipeline

    pipeline = FarmAgentPipeline(config)
    result = asyncio.run(pipeline.run_single(url, dry_run=dry_run))
    _print_result(result, dry_run)


@cli.command()
@click.option("--rounds", "-r", type=int, default=5, help="Number of discovery rounds")
@click.option("--delay", "-d", type=int, default=30, help="Delay (sec) between rounds")
@click.option("--language", "-l", multiple=True, help="Filter by language(s)")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["analysis", "issues", "both"]),
    default="both",
    help="Hunt mode: analysis (code scan), issues (solve issues), both",
)
@click.option("--dry-run", is_flag=True, help="Analyze without creating PRs")
@click.pass_context
def hunt(ctx, rounds, delay, language, mode, dry_run):
    """🔥 Hunt mode: auto-discover repos and contribute aggressively.

    Searches GitHub for high-star, active repos that merge external PRs,
    then runs the full pipeline on each. Loops through multiple rounds
    with varied criteria for maximum coverage.

    Modes:
      analysis - Code pattern scanning only (original behavior)
      issues   - Solve open GitHub issues (v2.0.0)
      both     - Do both (default)
    """
    print_banner()

    config = load_config(ctx.obj["config_path"])

    if language:
        config.discovery.languages = list(language)

    if not config.github.token:
        console.print("[red]❌ GitHub token not configured![/red]")
        sys.exit(1)

    if not config.llm.api_key:
        console.print("[red]❌ LLM API key not configured![/red]")
        sys.exit(1)

    mode_label = "[yellow]DRY RUN[/yellow]" if dry_run else "[red]LIVE 🔥[/red]"
    console.print(f"\n🔥 Hunt Mode ({mode_label})")
    console.print(f"   Mode: {mode}")
    console.print(f"   Rounds: {rounds}")
    console.print(f"   Delay: {delay}s between rounds")
    console.print(f"   Languages: {', '.join(config.discovery.languages)}")
    console.print(f"   LLM: {config.llm.provider} ({config.llm.model})")
    console.print()

    from farm_agent.orchestrator.pipeline import FarmAgentPipeline

    pipeline = FarmAgentPipeline(config)
    result = asyncio.run(pipeline.hunt(rounds=rounds, delay_sec=delay, dry_run=dry_run, mode=mode))
    _print_result(result, dry_run)


@cli.command("hunt-circular")
@click.option(
    "--json-path",
    default="target_repo.json",
    help="Path to target_repo.json file",
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["analysis", "issues", "both"]),
    default="both",
    help="Hunt mode: analysis (code scan), issues (solve issues), both",
)
@click.option("--dry-run", is_flag=True, help="Analyze without creating PRs")
@click.pass_context
def hunt_circular(ctx, json_path, mode, dry_run):
    """Circular Target Loop: process one target from target_repo.json.

    Picks the target with the oldest scanned_at timestamp and processes
    it through the full pipeline (issues + analysis). The scanned_at is
    updated before any analysis, guaranteeing crash-safe rotation.

    For continuous operation, call this command repeatedly (e.g., from
    the SuperHumanLoop or a cron job).
    """
    print_banner()

    config = load_config(ctx.obj["config_path"])

    if not config.github.token:
        console.print("[red]GitHub token not configured[/red]")
        sys.exit(1)

    if not config.llm.api_key:
        console.print("[red]LLM API key not configured[/red]")
        sys.exit(1)

    mode_label = "[yellow]DRY RUN[/yellow]" if dry_run else "[red]LIVE[/red]"
    console.print(f"\nCircular Target Loop ({mode_label})")
    console.print(f"   Mode: {mode}")
    console.print(f"   Targets: {json_path}")
    console.print(f"   LLM: {config.llm.provider} ({config.llm.model})")
    console.print()

    from farm_agent.orchestrator.pipeline import FarmAgentPipeline

    pipeline = FarmAgentPipeline(config)
    result = asyncio.run(
        pipeline.run_circular(json_path=json_path, dry_run=dry_run, mode=mode)
    )
    _print_result(result, dry_run)


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show pending feedback without responding")
@click.option("--pr", "pr_number", type=int, default=None, help="Check a specific PR number only")
@click.pass_context
def patrol(ctx, dry_run, pr_number):
    """🔍 Patrol: check open PRs for review feedback and auto-respond.

    Scans all open PRs created by Farm-Agent, reads maintainer review
    comments, generates code fixes, and pushes updates.

    Actions:
      - CODE_CHANGE: Generate fix and push to PR branch
      - QUESTION: Answer maintainer's question
      - STYLE_FIX: Fix naming/formatting issues
      - CLA: Re-sign CLA after pushing fixes
    """
    print_banner()

    config = load_config(ctx.obj["config_path"])

    if not config.github.token:
        console.print("[red]❌ GitHub token not configured![/red]")
        sys.exit(1)

    if not config.llm.api_key:
        console.print("[red]❌ LLM API key not configured![/red]")
        sys.exit(1)

    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]LIVE[/green]"
    console.print(f"\n🔍 PR Patrol ({mode})")
    if pr_number:
        console.print(f"   Filtering: PR #{pr_number}")
    console.print(f"   LLM: {config.llm.provider} ({config.llm.model})\n")

    from farm_agent.github.client import GitHubClient
    from farm_agent.llm.provider import create_llm_provider
    from farm_agent.orchestrator.memory import Memory
    from farm_agent.pr.patrol import PRPatrol

    async def _patrol():
        memory = Memory(config.storage.resolved_db_path)
        await memory.init()
        github = GitHubClient(token=config.github.token)
        import copy
        patrol_cfg = copy.copy(config.llm)
        patrol_cfg.provider = "openrouter"
        patrol_cfg.model = "google/gemini-3.5-flash"
        llm = create_llm_provider(patrol_cfg)

        try:
            # Get all open PRs from memory
            pr_records = await memory.get_prs(status="open", limit=100)
            if not pr_records:
                console.print("[dim]No open PRs found in database.[/dim]")
                return

            console.print(f"📋 Found {len(pr_records)} open PR(s) to check\n")

            patrol_engine = PRPatrol(github=github, llm=llm, memory=memory)
            result = await patrol_engine.patrol(pr_records, dry_run=dry_run, pr_filter=pr_number)

            # Print results
            console.print()
            console.print(
                Panel(
                    f"🔍 PRs checked: [bold]{result.prs_checked}[/bold]\n"
                    f"⏭️  PRs skipped: [bold]{result.prs_skipped}[/bold]\n"
                    f"🛠️  Fixes pushed: [bold]{result.fixes_pushed}[/bold]\n"
                    f"💬 Replies sent: [bold]{result.replies_sent}[/bold]\n"
                    f"✍️  CLA signed: [bold]{result.cla_signed}[/bold]\n"
                    f"📌 Issues assigned: [bold]{result.issues_found}[/bold]"
                    + (f"\n❌ Errors: [red]{len(result.errors)}[/red]" if result.errors else ""),
                    title="🔍 Patrol Complete" + (" (DRY RUN)" if dry_run else ""),
                )
            )

            if result.assigned_issues:
                console.print("\n[bold]📌 Assigned Issues:[/bold]")
                for iss in result.assigned_issues:
                    console.print(
                        f"  • [cyan]{iss['repo']}[/cyan] #{iss['number']}: {iss['title'][:60]}"
                    )
                    console.print(f"    [dim]{iss['url']}[/dim]")

            if result.errors:
                for e in result.errors:
                    console.print(f"  • [red]{e}[/red]")

        finally:
            await github.close()
            await llm.close()
            await memory.close()

    asyncio.run(_patrol())


@cli.command(name="superhuman")
@click.option("--time-warp", is_flag=True, help="Fast test: 1-3s delays, exit after 10 iters")
@click.option("--dry-run", is_flag=True, help="Hunt/Patrol without creating real PRs")
@click.option(
    "--target-repo",
    default=None,
    help="Force Hunt to target a specific GitHub repo URL for live testing",
)
@click.pass_context
def superhuman(ctx, time_warp, dry_run, target_repo):
    """🧠 Super Human Mode: organic 24/7 operational loop.

    Mimics a dedicated human developer by dynamically setting a random daily
    PR quota, injecting unpredictable human-like delays, interleaving Hunt
    and PR Patrol, and shifting to patrol-only mode once the quota is reached.

    Use --time-warp for fast testing (10 iterations, 1-3s delays).
    """
    print_banner()

    config = load_config(ctx.obj["config_path"])

    if not config.github.token:
        console.print("[red]❌ GitHub token not configured![/red]")
        sys.exit(1)

    if not config.llm.api_key:
        console.print("[red]❌ LLM API key not configured![/red]")
        sys.exit(1)

    warp_label = " [yellow]TIME-WARP[/yellow]" if time_warp else ""
    mode_label = " [yellow]DRY RUN[/yellow]" if dry_run else " [green]LIVE[/green]"
    console.print(f"\n🧠 Super Human Mode ({mode_label}{warp_label})")
    console.print(f"   LLM: {config.llm.provider} ({config.llm.model})")
    if time_warp:
        console.print("   ⏩ Time-warp: 10 iterations, 1-3s delays")
    console.print()

    from farm_agent.orchestrator.human import SuperHumanLoop
    from farm_agent.orchestrator.memory import Memory
    from farm_agent.orchestrator.pipeline import FarmAgentPipeline

    async def _run():
        pipeline = FarmAgentPipeline(config)
        memory = Memory(config.storage.resolved_db_path)
        await memory.init()

        loop = SuperHumanLoop(
            pipeline,
            memory,
            dry_run=dry_run,
            target_repo_url=target_repo,
            target_repo_max_prs=1,
        )

        async def shutdown_hook() -> None:
            console.print("[yellow]Shutdown signal received — cleaning up...[/yellow]")
            await loop._flush_and_close()

        inner_loop = asyncio.get_running_loop()
        import sys
        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                inner_loop.add_signal_handler(sig, lambda s=sig: _handle_signal(s, shutdown_hook, inner_loop))

        def _handle_signal(sig, hook, l):
            console.print(f"[yellow]Received {sig.name} — initiating graceful shutdown...[/yellow]")
            loop.request_shutdown()  # Signal the terminator loop to drain gracefully
            l.create_task(hook())  # Fire the cleanup hook (DB flush + close)

        try:
            await loop.run_daily_routine(time_warp=time_warp)
        except (KeyboardInterrupt, asyncio.CancelledError):
            console.print("[yellow]\nKeyboardInterrupt received — initiating graceful shutdown...[/yellow]")
        finally:
            await shutdown_hook()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run())
        loop.close()
    except KeyboardInterrupt:
        console.print("\n\n🛑 Super Human Mode interrupted by user (Ctrl+C). Goodbye!")


@cli.command(name="janitor")
@click.pass_context
def janitor(ctx):
    """🧹 The Ruthless Janitor — scan and destroy garbage PRs.

    Scans all OPEN Pull Requests created by the configured GitHub user.
    Uses the Minimax LLM to evaluate each PR's title and body.
    Any PR classified as GARBAGE (exploratory, docs, formatting, low-impact)
    is automatically CLOSED and its branch DELETED.

    This command is completely independent of the main pipeline.
    It operates purely on what is physically live on GitHub right now.
    """
    print_banner()

    config = load_config(ctx.obj["config_path"])

    if not config.github.token:
        console.print("[red]❌ GitHub token not configured![/red]")
        sys.exit(1)

    if not config.llm.api_key:
        console.print("[red]❌ LLM API key not configured for Janitor![/red]")
        sys.exit(1)

    async def _fetch_username() -> str:
        from farm_agent.github.client import GitHubClient
        gh = GitHubClient(config.github.token)
        try:
            user_data = await gh.get_authenticated_user()
            username_val = user_data.get("login", "")
        finally:
            await gh.close()
        if not username_val:
            raise ValueError("Empty username from GitHub API")
        return username_val

    async def _run_janitor(username: str):
        from farm_agent.github.client import GitHubClient
        from farm_agent.pr.janitor import PRJanitor

        gh = GitHubClient(config.github.token)
        j = PRJanitor(gh, username, config.llm)
        try:
            summary = await j.sweep_and_destroy()
        finally:
            await gh.close()

        # Print summary table
        table = Table(title="Janitor Sweep Results", show_lines=True)
        table.add_column("PR", style="bold", width=12)
        table.add_column("Action", width=10)
        table.add_column("Reason", width=50)

        action_colors = {"closed": "red", "spared": "green"}
        for detail in summary["details"]:
            color = action_colors.get(detail["action"], "white")
            action_label = f"[{color}]{detail['action'].upper()}[/{color}]"
            table.add_row(detail["pr"], action_label, f"{detail['reason']} ({detail['title']})")

        console.print(table)
        console.print(
            f"\n✅ Scanned: {summary['total_scanned']}  "
            f"[red]Destroyed: {summary['garbage_closed']}[/red]  "
            f"[green]Spared: {summary['critical_spared']}[/green]  "
            f"Errors: {summary['errors']}"
        )

    async def _main():
        # Fetch username from GitHub API
        console.print("[yellow]Fetching GitHub username from API...[/yellow]")
        try:
            username = await _fetch_username()
        except Exception as exc:
            console.print(f"[red]❌ Could not determine GitHub username: {exc}[/red]")
            return

        console.print(f"\n🧹 Janitor sweep for: [bold]{username}[/bold]")
        console.print(f"   LLM: {config.llm.provider} (Minimax)\n")
        await _run_janitor(username)

    asyncio.run(_main())


@cli.command("gc")
@click.option("--days", default=90, help="Purge entries older than N days")
@click.pass_context
def gc(ctx, days):
    """Garbage Collection — purge stale knowledge base entries.

    Removes knowledge_base entries (QA lessons, audit history, etc.)
    that are older than the specified number of days.
    Default: 90 days.
    """
    print_banner()

    config = load_config(ctx.obj["config_path"])

    from farm_agent.orchestrator.memory import Memory

    async def _run_gc():
        memory = Memory(config.storage.resolved_db_path)
        try:
            await memory.init()
            deleted = await memory.run_kb_garbage_collection(days=days)
            if deleted > 0:
                console.print(
                    f"[green]🧹 Garbage Collection complete:[/green] "
                    f"Purged [bold]{deleted}[/bold] stale knowledge base entries "
                    f"(older than {days} days)."
                )
            else:
                console.print(
                    f"[dim]🧹 No stale entries found older than {days} days.[/dim]"
                )
        finally:
            await memory.close()

    asyncio.run(_run_gc())


@cli.command()
@click.argument("url")
@click.pass_context
def analyze(ctx, url):
    """Analyze a repository without creating contributions."""
    print_banner()

    config = load_config(ctx.obj["config_path"])

    if not config.github.token:
        console.print("[red]❌ GitHub token not configured![/red]")
        sys.exit(1)

    if not config.llm.api_key:
        console.print("[red]❌ LLM API key not configured![/red]")
        sys.exit(1)

    console.print(f"\n🔬 Analyzing: {url}")
    console.print(f"   LLM: {config.llm.provider} ({config.llm.model})\n")

    from farm_agent.orchestrator.pipeline import FarmAgentPipeline

    pipeline = FarmAgentPipeline(config)
    result = asyncio.run(pipeline.analyze_only(url))

    if not result:
        console.print("[red]Analysis failed[/red]")
        return

    # Display findings
    console.print(
        Panel(
            f"Analyzed [bold]{result.analyzed_files}[/bold] files "
            f"in [bold]{result.analysis_duration_sec:.1f}s[/bold]\n"
            f"Skipped {result.skipped_files} files\n"
            f"Found [bold]{len(result.findings)}[/bold] issues",
            title=f"📊 Analysis: {result.repo.full_name}",
        )
    )

    if result.findings:
        table = Table(title="Findings", show_lines=True)
        table.add_column("Severity", style="bold", width=10)
        table.add_column("Type", width=15)
        table.add_column("Title", width=35)
        table.add_column("File", width=25)

        severity_colors = {
            "critical": "red",
            "high": "yellow",
            "medium": "cyan",
            "low": "dim",
        }

        for f in result.top_findings:
            color = severity_colors.get(f.severity.value, "white")
            table.add_row(
                f"[{color}]{f.severity.value.upper()}[/{color}]",
                f.type.value,
                f.title,
                f.file_path[:25],
            )

        console.print(table)


@cli.command()
@click.argument("url")
@click.option("--max-issues", "-n", type=int, default=5, help="Max issues to process")
@click.option("--dry-run", is_flag=True, help="Analyze issues without creating PRs")
@click.pass_context
def solve(ctx, url, max_issues, dry_run):
    """Solve open issues in a specific repository."""
    print_banner()

    config = load_config(ctx.obj["config_path"])

    if not config.github.token:
        console.print("[red]❌ GitHub token not configured![/red]")
        sys.exit(1)

    if not config.llm.api_key:
        console.print("[red]❌ LLM API key not configured![/red]")
        sys.exit(1)

    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]LIVE[/green]"
    console.print(f"\n🎯 Solving issues in: {url} ({mode})")
    console.print(f"   Max issues: {max_issues}")
    console.print(f"   LLM: {config.llm.provider} ({config.llm.model})\n")

    from farm_agent.github.client import GitHubClient
    from farm_agent.issues.solver import IssueSolver
    from farm_agent.llm.provider import create_llm_provider

    async def _solve():
        parts = url.rstrip("/").split("/")
        owner, repo_name = parts[-2], parts[-1]

        llm = create_llm_provider(config.llm)
        github = GitHubClient(token=config.github.token)

        try:
            _repo = await github.get_repo_details(owner, repo_name)
            issues = await github.get_open_issues(owner, repo_name, per_page=20)

            solver = IssueSolver(llm=llm, github=github)
            solvable = solver.filter_solvable(issues, max_complexity=3)[:max_issues]

            console.print(f"Found [bold]{len(issues)}[/bold] open issues")
            console.print(f"[green]{len(solvable)}[/green] are solvable\n")

            if not solvable:
                console.print("[dim]No solvable issues found.[/dim]")
                return

            table = Table(title="🎯 Solvable Issues", show_lines=True)
            table.add_column("#", width=5)
            table.add_column("Category", width=12)
            table.add_column("Title", width=40)
            table.add_column("Labels", width=15)

            for issue in solvable:
                cat = solver.classify_issue(issue)
                table.add_row(
                    str(issue.number),
                    cat.value,
                    issue.title[:40],
                    ", ".join(issue.labels[:2]) or "-",
                )

            console.print(table)

        finally:
            await github.close()
            await llm.close()

    asyncio.run(_solve())


@cli.command()
@click.option("--status-filter", "-s", default=None, help="Filter by PR status")
@click.pass_context
def status(ctx, status_filter):
    """Show status of submitted pull requests."""
    print_banner()

    config = load_config(ctx.obj["config_path"])

    from farm_agent.orchestrator.memory import Memory

    async def _show():
        memory = Memory(config.storage.resolved_db_path)
        await memory.init()
        prs = await memory.get_prs(status=status_filter)
        await memory.close()
        return prs

    prs = asyncio.run(_show())

    if not prs:
        console.print("[dim]No PRs found.[/dim]")
        return

    table = Table(title="📋 Submitted PRs", show_lines=True)
    table.add_column("#", width=5)
    table.add_column("Repository", width=25)
    table.add_column("Title", width=35)
    table.add_column("Status", width=10)
    table.add_column("URL", width=30)

    status_colors = {
        "open": "green",
        "merged": "magenta",
        "closed": "red",
        "pending": "yellow",
    }

    for pr in prs:
        color = status_colors.get(pr["status"], "white")
        table.add_row(
            str(pr["pr_number"]),
            pr["repo"],
            pr["title"][:35],
            f"[{color}]{pr['status'].upper()}[/{color}]",
            pr["pr_url"],
        )

    console.print(table)


@cli.command()
@click.pass_context
def stats(ctx):
    """Show overall Farm-Agent statistics."""
    print_banner()

    config = load_config(ctx.obj["config_path"])

    from farm_agent.orchestrator.memory import Memory

    async def _get_stats():
        memory = Memory(config.storage.resolved_db_path)
        await memory.init()
        s = await memory.get_stats()
        await memory.close()
        return s

    s = asyncio.run(_get_stats())

    console.print(
        Panel(
            f"📊 [bold]Total Runs[/bold]: {s['total_runs']}\n"
            f"🔬 [bold]Repos Analyzed[/bold]: {s['total_repos_analyzed']}\n"
            f"📤 [bold]PRs Submitted[/bold]: {s['total_prs_submitted']}\n"
            f"✅ [bold]PRs Merged[/bold]: {s['prs_merged']}",
            title="Farm-Agent Statistics",
        )
    )


@cli.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def cleanup(ctx, yes):
    """🧹 Clean up forks created by Farm-Agent.

    Reads forks from Farm-Agent's database, checks live PR status,
    and deletes forks where all PRs are merged or closed.
    Forks with open PRs are kept.
    """
    print_banner()

    config = load_config(ctx.obj["config_path"])

    if not config.github.token:
        console.print("[red]❌ GitHub token not configured![/red]")
        sys.exit(1)

    from farm_agent.github.client import GitHubClient
    from farm_agent.orchestrator.memory import Memory

    async def _cleanup():
        memory = Memory(config.storage.resolved_db_path)
        await memory.init()
        github = GitHubClient(token=config.github.token)

        try:
            # Get all PRs from DB
            all_prs = await memory.get_prs(limit=1000)
            if not all_prs:
                console.print("[dim]No PRs in database. Nothing to clean up.[/dim]")
                return

            # Group by fork
            forks: dict[str, list[dict]] = {}
            for pr in all_prs:
                fork_name = pr.get("fork", "")
                if not fork_name:
                    continue
                forks.setdefault(fork_name, []).append(pr)

            if not forks:
                console.print("[dim]No forks recorded in database.[/dim]")
                return

            console.print(f"\n🔍 Found {len(forks)} fork(s) in database\n")

            safe_to_delete = []
            has_open = []

            for fork_name, prs in forks.items():
                console.print(f"📁 [bold]{fork_name}[/bold]")

                all_resolved = True
                for pr in prs:
                    repo = pr["repo"]
                    pr_num = pr["pr_number"]

                    # Check live status
                    try:
                        owner, name = repo.split("/", 1)
                        pr_data = await github._get(f"/repos/{owner}/{name}/pulls/{pr_num}")
                        live_status = pr_data.get("state", "unknown")
                        if pr_data.get("merged_at"):
                            live_status = "merged"

                        # Sync to DB
                        await memory.update_pr_status(repo, pr_num, live_status)

                        if live_status == "merged":
                            icon = "🟢"
                        elif live_status == "open":
                            icon = "🟡"
                            all_resolved = False
                        else:
                            icon = "🔴"

                        console.print(f"   PR #{pr_num}: {pr['title'][:50]} [{icon} {live_status}]")
                    except Exception:
                        console.print(f"   PR #{pr_num}: {pr['title'][:50]} [⚪ unknown]")

                if all_resolved:
                    console.print("   ✅ All PRs resolved — safe to delete")
                    safe_to_delete.append(fork_name)
                else:
                    console.print("   ⚠️  Has open PRs — keeping")
                    has_open.append(fork_name)
                console.print()

            # Summary
            console.print("━" * 60)
            if has_open:
                console.print(f"\n⚠️  [yellow]{len(has_open)} fork(s) with open PRs (kept)[/yellow]")
            if safe_to_delete:
                console.print(f"\n✅ [green]{len(safe_to_delete)} fork(s) safe to delete:[/green]")
                for f in safe_to_delete:
                    console.print(f"   - {f}")

                if not yes and not click.confirm(
                    f"\n🗑️  Delete {len(safe_to_delete)} fork(s)?", default=False
                ):
                    console.print("[dim]Cancelled.[/dim]")
                    return

                for f in safe_to_delete:
                    try:
                        import subprocess

                        result = subprocess.run(
                            ["gh", "repo", "delete", f, "--yes"],
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if result.returncode == 0:
                            console.print(f"   ✅ Deleted {f}")
                        else:
                            console.print(f"   ❌ Failed: {result.stderr.strip()}")
                    except Exception as e:
                        console.print(f"   ❌ Failed to delete {f}: {e}")

                console.print("\n🎉 Cleanup done!")
            else:
                console.print("\n[dim]No forks to clean up.[/dim]")

        finally:
            await github.close()
            await memory.close()

    asyncio.run(_cleanup())


@cli.command("reset-db")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt (for scripting)")
@click.pass_context
def reset_db(ctx, yes):
    """🗑️ Reset the run history database (keeps submitted_prs for Alumni Sync).

    Safely clears the run_log and analyzed_repos tables so the agent starts
    fresh. submitted_prs is preserved for the Alumni Sync patrol feature.

    Requires confirmation before executing (use --yes to skip).
    """
    from farm_agent.core.config import load_config

    config = load_config(ctx.obj["config_path"])
    db_path = config.storage.db_path

    console.print("\n[bold]Database reset[/bold]")
    console.print(f"  Path: {db_path}")
    console.print("  Tables to CLEAR: run_log, analyzed_repos")
    console.print("  Tables to KEEP: submitted_prs, blacklisted_repos, repo_preferences")

    if not yes and not click.confirm("\nProceed with reset?"):
        console.print("[dim]Cancelled.[/dim]")
        return

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute("DELETE FROM run_log")
        cur.execute("DELETE FROM analyzed_repos")
        conn.commit()
        affected = cur.rowcount
        conn.close()

        console.print("[green]✅ Reset complete.[/green]")
        console.print("   Cleared: run_log, analyzed_repos")

    except Exception as e:
        console.print(f"[red]❌ Reset failed: {e}[/red]")


@cli.command("config")
@click.pass_context
def show_config(ctx):
    """Show current configuration."""
    config = load_config(ctx.obj["config_path"])
    console.print(
        Panel(
            f"[bold]GitHub[/bold]\n"
            f"  Token: {'****' + config.github.token[-4:] if config.github.token else 'NOT SET'}\n"
            f"  Secondary tokens: {len(config.github.secondary_tokens)} configured\n"
            f"  Max repos/run: {config.github.max_repos_per_run}\n"
            f"  Max PRs/day: {config.github.max_prs_per_day}\n\n"
            f"[bold]LLM[/bold]\n"
            f"  Provider: {config.llm.provider}\n"
            f"  Model: {config.llm.model}\n"
            f"  API Key: "
            f"{'****' + config.llm.api_key[-4:] if config.llm.api_key else 'NOT SET'}\n\n"
            f"[bold]Discovery[/bold]\n"
            f"  Languages: {', '.join(config.discovery.languages)}\n"
            f"  Stars: {config.discovery.stars_range}\n\n"
            f"[bold]Analysis[/bold]\n"
            f"  Analyzers: {', '.join(config.analysis.enabled_analyzers)}\n"
            f"  Threshold: {config.analysis.severity_threshold}\n\n"
            f"[bold]Pipeline[/bold]\n"
            f"  Max concurrent: {config.pipeline.max_concurrent_repos}\n"
            f"  Timeout/repo: {config.pipeline.timeout_per_repo_sec}s\n\n"
            f"[bold]Terminator Mode[/bold]\n"
            f"  Max PRs/day (hard cap): {config.github.max_prs_per_day}",
            title="Farm-Agent Configuration",
        )
    )


@cli.command("vips")
@click.option(
    "--no-sync",
    is_flag=True,
    help="Skip Alumni Sync — show cached data only (faster, uses no API calls)",
)
@click.pass_context
def vips(ctx, no_sync):
    """🌟 VIP Roster — Alumni Sync + Full Friendly Repo List.

    Triggers the full Alumni Sync to pull merged PR history from GitHub,
    then displays every unique repository where you have merged PRs,
    with merged-PR counts and last-seen timestamps. Full list — no item cap.

    Star counts are fetched live from the GitHub API for each repo.
    Run with --no-sync to skip the API sync and just dump cached data.
    """
    print_banner()

    config = load_config(ctx.obj["config_path"])

    if not config.github.token:
        console.print("[red]❌ GitHub token not configured![/red]")
        sys.exit(1)

    async def _run():
        from farm_agent.orchestrator.human import SuperHumanLoop
        from farm_agent.orchestrator.memory import Memory
        from farm_agent.orchestrator.pipeline import FarmAgentPipeline

        # Build minimal pipeline + memory for the sync
        pipeline = FarmAgentPipeline(config)
        memory = Memory(config.storage.resolved_db_path)
        await memory.init()

        loop = SuperHumanLoop(
            pipeline,
            memory,
            dry_run=True,
            target_repo_url=None,
            target_repo_max_prs=0,
        )

        if not no_sync:
            console.print("\n[bold cyan]Syncing alumni data...[/bold cyan]")
            alumni_count = await loop._sync_vip_friendly_repos()
            console.print(f"[green]Sync complete — {alumni_count} repos indexed.[/green]\n")
        else:
            console.print("\n[dim]Skipping sync — showing cached data only.[/dim]\n")

        # ── Fetch live star counts for each unique repo ──────────────────────
        db_path = config.storage.resolved_db_path
        import sqlite3

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT repo, COUNT(*) AS merged_pr_count, MAX(updated_at) AS last_seen
            FROM submitted_prs
            WHERE status = 'merged'
            GROUP BY repo
            ORDER BY merged_pr_count DESC, repo ASC
            """,
        )
        rows = cur.fetchall()
        conn.close()

        if not rows:
            console.print("[yellow]⚠️  No merged PRs found in database.[/yellow]")
            console.print(
                "[dim]Tip: run without --no-sync to pull your GitHub history first.[/dim]"
            )
            await memory.close()
            return

        # Fetch stars live from GitHub API
        from farm_agent.github.client import GitHubClient

        gh = GitHubClient(config.github.token)

        table = Table(
            title=f"🌟 VIP Roster — {len(rows)} Friendly Repositories",
            title_style="bold cyan",
            show_lines=False,
            header_style="bold cyan",
            pad_edge=True,
            row_styles=["", "dim"],
        )
        table.add_column("#", justify="right", style="cyan", no_wrap=True)
        table.add_column("Repository", style="cyan")
        table.add_column("⭐ Stars", justify="right", style="yellow")
        table.add_column("Merged PRs", justify="right", style="green")
        table.add_column("Last Seen", style="dim")

        for idx, (repo, pr_count, last_seen) in enumerate(rows, start=1):
            stars = "—"
            try:
                owner, name = repo.split("/", 1)
                details = await gh.get_repo_details(owner, name)
                stars = f"{details.get('stargazers_count', 0):,}"
            except Exception:
                stars = "⚠️"
            table.add_row(
                str(idx),
                repo,
                stars,
                str(pr_count),
                last_seen or "unknown",
            )

        await gh.close()
        console.print(table)

        total_prs = sum(r[1] for r in rows)
        console.print(
            f"\n[dim]Total: {len(rows)} repos, {total_prs} merged PRs[/dim]"
        )

        await memory.close()

    asyncio.run(_run())


@cli.command("templates")
def list_templates():
    """List contribution generation mode."""
    console.print(
        "[bold cyan]🛠️ Agent-Farm v4.0.0 Dynamic Generator[/bold cyan]\n"
        "[dim]Static YAML templates for typo/readme fixes have been deprecated under the Zero-Garbage PR policy.[/dim]\n"
        "All contributions are generated dynamically using Omniscient Context & verified in isolated Docker sandboxes."
    )


@cli.command("profile")
@click.argument("name")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Analyze only, no PRs",
)
@click.option(
    "--list",
    "list_all",
    is_flag=True,
    help="List all profiles",
)
@click.pass_context
def run_profile(ctx, name, dry_run, list_all):
    """Run pipeline with a named profile."""
    from farm_agent.core.profiles import (
        get_profile,
        list_profiles,
    )

    if list_all or name == "list":
        profiles = list_profiles()
        table = Table(title="Contribution Profiles")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Analyzers")
        table.add_column("Threshold")
        for p in profiles:
            table.add_row(
                p.name,
                p.description,
                ", ".join(p.analyzers),
                p.severity_threshold,
            )
        console.print(table)
        return

    profile = get_profile(name)
    if not profile:
        console.print(f"[red]Profile '{name}' not found[/red]")
        console.print("Available: " + ", ".join(p.name for p in list_profiles()))
        return

    console.print(f"[bold]Running with profile: {profile.name}[/bold]\n  {profile.description}")

    from farm_agent.core.profiles import apply_profile

    config = load_config(ctx.obj["config_path"])
    config_data = config.model_dump()
    config_data = apply_profile(config_data, profile)

    from farm_agent.core.config import FarmAgentConfig

    config = FarmAgentConfig(**config_data)

    if profile.dry_run or dry_run:
        dry_run = True

    from farm_agent.orchestrator.pipeline import (
        FarmAgentPipeline,
    )

    pipeline = FarmAgentPipeline(config)
    result = asyncio.run(pipeline.run(dry_run=dry_run))
    _print_result(result, dry_run)


def _print_result(result, dry_run: bool):
    """Print pipeline execution results."""

    console.print()
    console.print(
        Panel(
            f"📦 Repos analyzed: [bold]{result.repos_analyzed}[/bold]\n"
            f"🔍 Issues found: [bold]{result.findings_total}[/bold]\n"
            f"🛠️  Contributions generated: [bold]{result.contributions_generated}[/bold]\n"
            f"📤 PRs created: [bold]{result.prs_created}[/bold]"
            + (f"\n❌ Errors: [red]{len(result.errors)}[/red]" if result.errors else ""),
            title="✅ Pipeline Complete" + (" (DRY RUN)" if dry_run else ""),
        )
    )

    if result.prs:
        console.print("\n[bold]Created PRs:[/bold]")
        for pr in result.prs:
            console.print(f"  • [green]{pr.pr_url}[/green] - {pr.contribution.title}")

    if result.errors:
        console.print("\n[bold red]Errors:[/bold red]")
        for e in result.errors:
            console.print(f"  • {e}")


@cli.command("models")
@click.option("--task", default=None, help="Filter by task type")
@click.pass_context
def show_models(ctx, task):
    """List available models and their capabilities."""
    from farm_agent.llm.models import (
        ALL_MODELS,
        TaskType,
        get_models_for_task,
    )
    from farm_agent.llm.router import TaskRouter

    if task:
        try:
            tt = TaskType(task)
        except ValueError:
            console.print(
                f"[red]Unknown task type: {task}[/red]\n"
                f"Valid: {', '.join(t.value for t in TaskType)}"
            )
            return
        models = get_models_for_task(tt)
        console.print(f"\n[bold]Best models for [cyan]{task}[/cyan]:[/bold]\n")
    else:
        models = ALL_MODELS
        console.print("\n[bold]Available Models:[/bold]\n")

    table = Table()
    table.add_column("Model", style="cyan")
    table.add_column("Tier")
    table.add_column("Code", justify="right")
    table.add_column("Analysis", justify="right")
    table.add_column("Speed", justify="right")
    table.add_column("Cost (in/out)")
    table.add_column("Best For")

    for m in models:
        tier_color = {
            "pro": "red",
            "flash": "yellow",
            "lite": "green",
        }.get(m.tier.value, "white")

        table.add_row(
            m.display_name,
            f"[{tier_color}]{m.tier.value.upper()}[/{tier_color}]",
            str(m.coding),
            str(m.analysis),
            str(m.speed),
            f"${m.input_cost:.2f}/${m.output_cost:.2f}",
            ", ".join(t.value for t in m.best_for[:3]),
        )

    console.print(table)

    # Show default assignments
    router = TaskRouter()
    defaults = router.get_default_assignments()
    console.print("\n[bold]Default Task Assignments:[/bold]")
    for task_type, model_name in defaults.items():
        console.print(f"  {task_type}: [cyan]{model_name}[/cyan]")
    console.print()


@cli.command("leaderboard")
@click.option(
    "--limit",
    default=20,
    help="Number of entries",
)
@click.pass_context
def show_leaderboard(ctx, limit):
    """Show contribution leaderboard and success rates."""
    from farm_agent.core.leaderboard import Leaderboard
    from farm_agent.orchestrator.memory import Memory

    async def _run():
        config = load_config(ctx.obj["config_path"])
        memory = Memory(config.storage.resolved_db_path)
        await memory.init()

        board = Leaderboard(memory._db)
        stats = await board.get_overall_stats()
        rankings = await board.get_repo_rankings(limit=limit)
        type_stats = await board.get_type_stats()

        console.print(
            Panel(
                f"Total PRs: [bold]{stats['total']}[/bold]\n"
                f"Merged: [green]{stats['merged']}[/green] | "
                f"Closed: [red]{stats['closed']}[/red] | "
                f"Open: [yellow]{stats['open']}[/yellow]\n"
                f"Merge Rate: [bold]{stats['merge_rate']}%[/bold]",
                title="Contribution Leaderboard",
            )
        )

        if rankings:
            table = Table(title="Repo Rankings")
            table.add_column("Repo", style="cyan")
            table.add_column("Total")
            table.add_column("Merged", style="green")
            table.add_column("Closed", style="red")
            table.add_column("Open", style="yellow")
            table.add_column("Rate")

            for r in rankings:
                rate_color = (
                    "green" if r.merge_rate >= 70 else "yellow" if r.merge_rate >= 40 else "red"
                )
                table.add_row(
                    r.repo,
                    str(r.total_prs),
                    str(r.merged),
                    str(r.closed),
                    str(r.open),
                    f"[{rate_color}]{r.merge_rate:.0f}%[/{rate_color}]",
                )
            console.print(table)

        if type_stats:
            table2 = Table(title="By Contribution Type")
            table2.add_column("Type", style="cyan")
            table2.add_column("Total")
            table2.add_column("Merged", style="green")
            table2.add_column("Rate")
            for t in type_stats:
                table2.add_row(
                    t.type,
                    str(t.total),
                    str(t.merged),
                    f"{t.merge_rate:.0f}%",
                )
            console.print(table2)

        await memory.close()

    asyncio.run(_run())


@cli.command("notify-test")
@click.pass_context
def notify_test(ctx):
    """Send a test notification to configured Telegram channel."""
    from farm_agent.core.notifier import TelegramNotifier

    config = load_config(ctx.obj["config_path"])
    nc = config.notifications

    notifier = TelegramNotifier(
        token=nc.telegram_token,
        chat_id=nc.telegram_chat_id,
    )

    if not notifier.enabled:
        console.print("[yellow]Telegram notification not configured in config.yaml[/yellow]")
        return

    async def _send():
        await notifier.send_message("🚀 <b>[TEST ALERT]</b> Farm-Agent notifications operational!")
        await notifier.close()

    asyncio.run(_send())
    console.print("[green]Test notification sent via Telegram![/green]")


@cli.command("system-status")
@click.pass_context
def sysinfo(ctx):
    """Show Farm-Agent system status — memory, PRs, rate limits."""
    print_banner()

    config = load_config(ctx.obj["config_path"])

    async def _run():
        from farm_agent.orchestrator.memory import Memory

        memory = Memory(config.storage.resolved_db_path)
        await memory.init()

        console.print("[bold]📊 Farm-Agent Status[/bold]\n")

        # Memory stats
        stats_table = Table(title="Memory Database", show_header=True)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")

        # Count repos
        cursor = await memory._db.execute("SELECT COUNT(*) FROM analyzed_repos")
        repo_count = (await cursor.fetchone())[0]
        stats_table.add_row("Repos analyzed", str(repo_count))

        # Count PRs
        cursor = await memory._db.execute("SELECT COUNT(*) FROM submitted_prs")
        pr_count = (await cursor.fetchone())[0]
        stats_table.add_row("PRs submitted", str(pr_count))

        # PR by status
        cursor = await memory._db.execute(
            "SELECT status, COUNT(*) FROM submitted_prs GROUP BY status"
        )
        for status_val, count in await cursor.fetchall():
            stats_table.add_row(f"  └─ {status_val}", str(count))

        # Outcome stats
        try:
            outcome_stats = await memory.get_outcome_stats()
            if outcome_stats:
                for outcome, count in outcome_stats.items():
                    if outcome == "avg_merge_rate":
                        stats_table.add_row("Avg merge rate", f"{count:.0%}")
                    else:
                        stats_table.add_row(f"Outcome: {outcome}", str(count))
        except Exception:
            pass

        # Findings cache
        cursor = await memory._db.execute("SELECT COUNT(*) FROM findings_cache")
        findings_count = (await cursor.fetchone())[0]
        stats_table.add_row("Cached findings", str(findings_count))

        console.print(stats_table)

        # Recent PRs
        cursor = await memory._db.execute(
            "SELECT repo, pr_number, title, status, type "
            "FROM submitted_prs ORDER BY id DESC LIMIT 10"
        )
        recent = await cursor.fetchall()
        if recent:
            console.print()
            pr_table = Table(title="Recent PRs (last 10)")
            pr_table.add_column("Repo", style="cyan")
            pr_table.add_column("#", style="yellow")
            pr_table.add_column("Title", max_width=40)
            pr_table.add_column("Status")
            pr_table.add_column("Type", style="dim")
            for row in recent:
                status_style = (
                    "green" if row[3] == "merged" else "red" if row[3] == "closed" else "yellow"
                )
                pr_table.add_row(
                    row[0],
                    str(row[1]),
                    row[2],
                    f"[{status_style}]{row[3]}[/{status_style}]",
                    row[4],
                )
            console.print(pr_table)

        # GitHub rate limit
        try:
            from farm_agent.github.client import GitHubClient

            gh = GitHubClient(token=config.github.token)
            remaining = await gh.check_rate_limit()
            console.print(f"\n🔑 GitHub API rate limit remaining: [bold]{remaining}[/bold]")
            await gh.close()
        except Exception:
            console.print("\n[dim]Could not check GitHub rate limit[/dim]")

        await memory.close()

    asyncio.run(_run())


@cli.command()
@click.pass_context
def advisories(ctx):
    """List all Bug Bounty security advisory dossiers generated in bounty_reports/."""
    from datetime import datetime
    from pathlib import Path

    config = load_config(ctx.obj["config_path"])
    bounty_dir = Path(getattr(config.bounty, "bounty_reports_dir", "bounty_reports"))

    if not bounty_dir.exists():
        console.print(f"[yellow]No advisories directory found at `{bounty_dir}`[/yellow]")
        return

    reports = sorted(bounty_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        console.print(f"[yellow]No security advisory reports found in `{bounty_dir}`[/yellow]")
        return

    table = Table(title=f"🛡️ Bug Bounty Security Advisories ({len(reports)} files in `{bounty_dir}`)")
    table.add_column("Dossier File", style="cyan")
    table.add_column("Last Modified", style="dim")
    table.add_column("Size", justify="right")

    for r in reports:
        mtime = datetime.fromtimestamp(r.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        size_kb = f"{r.stat().st_size / 1024:.1f} KB"
        table.add_row(r.name, mtime, size_kb)

    console.print(table)


@cli.command("security-candidates")
@click.option("--db-path", type=click.Path(), default=None)
@click.option("--limit", type=click.IntRange(1, 500), default=50)
@click.pass_context
def security_candidates(ctx, db_path, limit):
    """List stored security candidates with scan IDs and proof states."""
    import json

    from farm_agent.orchestrator.memory import Memory

    config = load_config(ctx.obj["config_path"])

    async def run_query():
        memory = Memory(db_path or config.storage.db_path)
        await memory.init()
        try:
            return await memory.list_security_candidates(limit=limit)
        finally:
            await memory.close()

    click.echo(json.dumps(asyncio.run(run_query()), ensure_ascii=False))


@cli.command("register-live-scan")
@click.argument("repo")
@click.argument("target_commit")
@click.option("--db-path", type=click.Path(), default=None)
@click.pass_context
def register_live_scan(ctx, repo, target_commit, db_path):
    """Register an explicitly authorized live scan and its coverage matrix."""
    import json
    import uuid

    from farm_agent.orchestrator.memory import Memory
    from farm_agent.security.scope import manifest_for_scan
    from farm_agent.security.threat_model import ThreatModel

    config = load_config(ctx.obj["config_path"])
    if not config.bounty.live_testing_enabled:
        raise click.ClickException("Global live testing switch is disabled")
    scan_id = uuid.uuid4().hex
    try:
        manifest = manifest_for_scan(
            scan_id, repo, target_commit, config.bounty.program_scopes, mode="live",
        )
        if manifest is None:
            raise ValueError("No exact program authorization for repository and SHA")
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    async def store_scan():
        memory = Memory(db_path or config.storage.db_path)
        await memory.init()
        try:
            await memory.store_scan_manifest(manifest)
            await memory.store_threat_model(ThreatModel.from_manifest(manifest))
            await memory.initialize_coverage(manifest)
        finally:
            await memory.close()

    try:
        asyncio.run(store_scan())
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps({"scan_id": scan_id, "repo": repo, "target_commit": target_commit}))


@cli.command("register-candidate")
@click.argument("scan_id")
@click.option("--file-path", required=True)
@click.option("--title", required=True)
@click.option("--db-path", type=click.Path(), default=None)
@click.pass_context
def register_candidate(ctx, scan_id, file_path, title, db_path):
    """Record an operator-identified candidate under an authorized scan."""
    import json
    from pathlib import PurePosixPath, PureWindowsPath

    from farm_agent.orchestrator.memory import Memory

    path = PurePosixPath(file_path)
    windows = PureWindowsPath(file_path)
    if (not file_path or path.is_absolute() or ".." in path.parts
            or "\\" in file_path or windows.drive or windows.root
            or not title.strip()):
        raise click.ClickException("Candidate needs a relative file path and a title")
    config = load_config(ctx.obj["config_path"])

    async def store_candidate():
        memory = Memory(db_path or config.storage.db_path)
        await memory.init()
        try:
            manifest = await memory.get_scan_manifest(scan_id)
            if manifest is None or manifest.mode != "live":
                raise ValueError("Candidate requires an authorized live scan")
            return await memory.create_security_candidate(
                scan_id=scan_id, repo=manifest.scope.repo,
                target_commit=manifest.scope.target_commit,
                file_path=file_path, title=title,
            )
        finally:
            await memory.close()

    try:
        candidate_id = asyncio.run(store_candidate())
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps({"candidate_id": candidate_id, "scan_id": scan_id}))


@cli.command("register-oracle")
@click.argument("spec_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--store-dir", type=click.Path(), default=None)
@click.pass_context
def register_oracle(ctx, spec_path, store_dir):
    """Validate and content-address an operator-authored four-phase oracle."""
    import json
    from pathlib import Path

    from farm_agent.security.artifacts import ArtifactStore
    from farm_agent.security.oracles import OracleSpec

    config = load_config(ctx.obj["config_path"])
    try:
        spec = OracleSpec.model_validate_json(Path(spec_path).read_bytes())
        ref = ArtifactStore(store_dir or config.bounty.oracle_store_dir).save(spec)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps({"digest": ref.digest, "path": str(ref.path)}))


@cli.command("verify-candidate")
@click.argument("candidate_id")
@click.option("--oracle-digest", required=True)
@click.option("--role-headers-file", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--witness-file", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--store-dir", type=click.Path(), default=None)
@click.option("--db-path", type=click.Path(), default=None)
@click.pass_context
def verify_candidate(
    ctx, candidate_id, oracle_digest, role_headers_file, witness_file, store_dir, db_path,
):
    """Run an authorized live semantic proof against a stored candidate."""
    import json
    import re
    from pathlib import Path

    from farm_agent.orchestrator.memory import Memory
    from farm_agent.security.artifacts import ArtifactRef, ArtifactStore
    from farm_agent.security.oracles import ProofOutcome
    from farm_agent.security.verifier import SemanticVerifier

    if not re.fullmatch(r"[0-9a-f]{64}", oracle_digest):
        raise click.ClickException("Oracle digest must be a lowercase SHA-256")
    config = load_config(ctx.obj["config_path"])
    try:
        role_headers = json.loads(Path(role_headers_file).read_text(encoding="utf-8"))
        if (not isinstance(role_headers, dict)
                or not all(isinstance(role, str) and isinstance(headers, dict)
                           and all(isinstance(k, str) and isinstance(v, str)
                                   for k, v in headers.items())
                           for role, headers in role_headers.items())):
            raise ValueError("Role headers must map role names to string header maps")
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"Invalid role headers file: {exc}") from exc

    def witness_counter():
        count = int(Path(witness_file).read_text(encoding="utf-8").strip())
        if count < 0:
            raise ValueError("Witness count cannot be negative")
        return count

    async def run_proof():
        memory = Memory(db_path or config.storage.db_path)
        await memory.init()
        try:
            store = ArtifactStore(store_dir or config.bounty.oracle_store_dir)
            artifact = ArtifactRef(store.root / f"{oracle_digest}.json", oracle_digest)
            return await SemanticVerifier(memory).verify_candidate(
                candidate_id, artifact, store, role_headers=role_headers,
                witness_counter=witness_counter if witness_file else None,
            )
        finally:
            await memory.close()

    try:
        result = asyncio.run(run_proof())
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps({
        "candidate_id": candidate_id, "outcome": result.outcome.value,
        "reason": result.reason, "evidence_hash": result.evidence_hash,
    }))
    if result.outcome != ProofOutcome.VERIFIED:
        raise SystemExit(2)


@cli.command("scope-report")
@click.argument("scan_id")
@click.option("--db-path", type=click.Path(), default=None)
@click.pass_context
def scope_report(ctx, scan_id, db_path):
    """Show a scan's exact authorized scope and incomplete coverage."""
    import json

    from farm_agent.orchestrator.memory import Memory

    config = load_config(ctx.obj["config_path"])

    async def run_query():
        memory = Memory(db_path or config.storage.db_path)
        await memory.init()
        try:
            manifest = await memory.get_scan_manifest(scan_id)
            if manifest is None:
                raise click.ClickException("No authorized manifest for this scan")
            summary = await memory.get_coverage_summary(scan_id)
            return {
                "scan_id": scan_id, "repo": manifest.scope.repo,
                "target_commit": manifest.scope.target_commit, "mode": manifest.mode,
                "policy_reference": manifest.scope.policy_reference,
                "coverage": summary.__dict__, "statement": summary.statement,
            }
        finally:
            await memory.close()

    click.echo(json.dumps(asyncio.run(run_query()), ensure_ascii=False))


if __name__ == "__main__":
    cli()
