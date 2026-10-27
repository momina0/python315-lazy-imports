"""Same CLI as cli.py, with the heavy imports marked `lazy` (Python 3.15, PEP 810)."""
import json

lazy import boto3
lazy import pandas as pd
lazy import requests
import typer
lazy from openai import OpenAI
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()


@app.command()
def report(rows: int = 5):
    """Summarise some data with pandas."""
    df = pd.DataFrame({"team": ["a", "b"] * rows, "value": range(rows * 2)})
    table = Table("team", "total")
    for team, total in df.groupby("team")["value"].sum().items():
        table.add_row(team, str(total))
    console.print(table)


@app.command()
def upload(path: str):
    """Upload a file to S3."""
    s3 = boto3.client("s3", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x")
    console.print(f"would upload {path} with {type(s3).__name__}")


@app.command()
def ask(question: str):
    """Ask an LLM."""
    client = OpenAI(api_key="sk-test")
    console.print(f"would ask {question!r} with {type(client).__name__}")


@app.command()
def fetch(url: str):
    """Build an HTTP request."""
    req = requests.Request("GET", url).prepare()
    console.print(json.dumps({"method": req.method, "url": req.url}))


if __name__ == "__main__":
    app()
