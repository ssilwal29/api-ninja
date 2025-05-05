import json
import sys
import time
import yaml
import logging
import click
import requests
from io import StringIO
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    SpinnerColumn,
)
from api_ninja.core import APINinja
from api_ninja.agents.flow_generator import FlowGeneratorAgent

console = Console()

# ─── Suppress HTTPX & OpenAI INFO logs ──────────────────────────
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def collect_flows(cfg: dict) -> dict[str, dict]:
    defaults = cfg.get("defaults", [])
    out = {}
    for coll_name, coll in cfg["collections"].items():
        for flow_id in coll["flows"]:
            flow = dict(cfg["flows"][flow_id])
            flow.update(
                flow_id=flow_id,
                collection=coll_name,
                defaults=defaults,
            )
            out[flow_id] = flow
    return out


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def cli(ctx):
    """🧪 APINinja CLI"""
    pass


@cli.command("run-all")
@click.option("-c", "--config", default="config.yaml", help="Path to config.yaml")
@click.option("--openapi-spec-url", help="URL to fetch OpenAPI spec from")
@click.option(
    "--openapi-spec-path",
    type=click.Path(exists=True),
    help="Path to local OpenAPI JSON/YAML file",
)
@click.option(
    "--base-url",
    help="Base URL for the API (overrides config.yaml)",
)
@click.pass_context
def run_all(ctx, config, openapi_spec_url, openapi_spec_path, base_url):
    if not openapi_spec_url and not openapi_spec_path:
        raise click.UsageError(
            "Either --openapi-spec-url or --openapi-spec-path must be provided"
        )
    if not base_url:
        raise click.UsageError("Base URL must be provided using --base-url")
    cfg = load_config(config)
    spec = {}
    if openapi_spec_url:
        spec = requests.get(openapi_spec_url).json()
    if openapi_spec_path:
        with open(openapi_spec_path, "r") as f:
            if openapi_spec_path.endswith(".json"):
                spec = json.load(f)
            else:
                spec = yaml.safe_load(f)
    ninja = APINinja(openapi_spec=spec, api_base_url=base_url)
    flows = collect_flows(cfg)
    ctx.obj = {"ninja": ninja, "flows": flows}

    ninja = ctx.obj["ninja"]
    flows = list(ctx.obj["flows"].items())
    total = len(flows)
    passed = 0

    console.rule("🧪  Running All Flows", style="magenta")
    console.print()
    start_all = time.time()

    # Single Progress (spinner + bar) — no nested Lives!
    with Progress(
        SpinnerColumn(style="progress.spinner", spinner_name="dots"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("API Ninja", total=total)
        completed = 0
        for flow_id, flow in flows:
            # update spinner description
            progress.update(
                task, description=f"{flow_id}", completed=completed, refresh=True
            )

            # capture stdout from plan_and_run
            buf = StringIO()
            old_stdout = sys.stdout
            sys.stdout = buf

            try:
                ninja.plan_and_run(flow)
                success = True
            except AssertionError as e:
                success = False
                buf.write(f"\n✖ Step failed: {e}\n")
            finally:
                sys.stdout = old_stdout

            # render panel
            output = buf.getvalue().rstrip() or "[dim]— no output —[/dim]"
            title = f"🧪 {flow_id}  {'✅' if success else '❌'}"
            panel = Panel(
                f"\n{output}\n",
                title=title,
                subtitle=f"[yellow]{flow['collection']}[/yellow]",
                border_style="green" if success else "red",
                style="bright_white",
                expand=False,
            )
            console.print(panel)
            console.print()  # blank line
            console.print()

            if success:
                passed += 1
            completed += 1
            progress.advance(task)

    total_time = time.time() - start_all
    console.rule("🔎  Summary", style="cyan")
    summary = Table(show_edge=False, header_style="bold")
    summary.add_column("Metric", style="bold")
    summary.add_column("Value", justify="right")
    summary.add_row("Total Flows", str(total))
    summary.add_row("Passed", f"[green]{passed}[/green]")
    summary.add_row("Failed", f"[red]{total - passed}[/red]")
    summary.add_row("Total Time", f"{total_time:.2f}s")
    console.print(summary)
    console.rule()

    if passed != total:
        sys.exit(1)


@cli.command("generate-flows")
@click.option("--url", help="URL to fetch OpenAPI spec from")
@click.option(
    "--path", type=click.Path(exists=True), help="Path to local OpenAPI JSON/YAML file"
)
@click.option(
    "--out",
    type=click.Path(),
    default="default.generated.yaml",
    help="Output file for test flows",
)
@click.pass_context
def generate_flows(ctx, url, path, out):
    """Generate test flows for each endpoint in the OpenAPI spec."""
    if not url and not path:
        raise click.UsageError("Either --url or --path must be provided")

    if url:
        print(f"Fetching OpenAPI spec from {url}...")
        response = requests.get(url)
        response.raise_for_status()
        openapi_spec = response.json()
    else:
        print(f"Loading OpenAPI spec from {path}...")
        with open(path, "r") as f:
            if path.endswith(".json"):
                openapi_spec = json.load(f)
            else:
                openapi_spec = yaml.safe_load(f)

    agent = FlowGeneratorAgent()
    flows = agent.generate_flows_for_spec(openapi_spec)
    print(f"Writing generated flows to {out}...")
    with open(out, "w") as f:
        yaml.dump(flows, f, indent=2)

    print("✅ Done.")


if __name__ == "__main__":
    cli()
