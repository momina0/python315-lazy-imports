"""Import and use each library in a fresh process, with lazy imports off and forced on
(-X lazy_imports=all). No network: clients are created, requests are mocked or only prepared.

usage: python bench/compat.py   (run with the Python 3.15 interpreter)
"""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"}

SMOKE = {
    "numpy": "import numpy as np\nassert int(np.arange(10).sum()) == 45",
    "pandas": "import pandas as pd\ndf = pd.DataFrame({'k': ['a', 'b', 'a'], 'v': [1, 2, 3]})\nassert df.groupby('k')['v'].sum().to_dict() == {'a': 4, 'b': 2}",
    "pydantic": "from pydantic import BaseModel\nclass M(BaseModel):\n    x: int\nassert M.model_validate({'x': '3'}).x == 3",
    "sqlalchemy": "from sqlalchemy import create_engine, text\ne = create_engine('sqlite://')\nwith e.connect() as c:\n    assert c.execute(text('select 1')).scalar() == 1",
    "fastapi": "from fastapi import FastAPI\nfrom fastapi.testclient import TestClient\napp = FastAPI()\n@app.get('/')\ndef root():\n    return {'ok': True}\nassert TestClient(app).get('/').json() == {'ok': True}",
    "httpx": "import httpx\nt = httpx.MockTransport(lambda r: httpx.Response(200, json={'ok': 1}))\nassert httpx.Client(transport=t).get('https://x.test').json() == {'ok': 1}",
    "requests": "import requests\nassert requests.Request('GET', 'https://x.test', params={'a': 1}).prepare().url == 'https://x.test/?a=1'",
    "boto3": "import boto3\nc = boto3.client('s3', region_name='us-east-1', aws_access_key_id='x', aws_secret_access_key='x')\nassert type(c).__name__ == 'S3'",
    "openai": "from openai import OpenAI\nassert OpenAI(api_key='sk-test').api_key == 'sk-test'",
    "rich": "from rich.console import Console\nfrom rich.table import Table\nt = Table('a')\nt.add_row('1')\nc = Console(record=True, width=40)\nc.print(t)\nassert '1' in c.export_text()",
    "typer": "import typer\nfrom typer.testing import CliRunner\napp = typer.Typer()\n@app.command()\ndef hi(name: str):\n    print(f'hi {name}')\nassert 'hi bob' in CliRunner().invoke(app, ['bob']).output",
    "click": "import click\nfrom click.testing import CliRunner\n@click.command()\n@click.argument('n')\ndef hi(n):\n    click.echo(f'hi {n}')\nassert 'hi bob' in CliRunner().invoke(hi, ['bob']).output",
    "jinja2": "from jinja2 import Template\nassert Template('hi {{ n }}').render(n='bob') == 'hi bob'",
    "uvicorn": "import uvicorn\nc = uvicorn.Config(app='x:y', port=0)\nassert c.port == 0 and c.host == '127.0.0.1'",
}


def run(code, mode):
    proc = subprocess.run([sys.executable, "-X", f"lazy_imports={mode}", "-c", code], env=ENV, capture_output=True, cwd=ROOT)
    if proc.returncode == 0:
        return "ok"
    lines = [l for l in proc.stderr.decode(errors="replace").splitlines() if l.strip()]
    errors = [l for l in lines if l.split(":")[0].endswith("Error") or l.split(":")[0].endswith("Exception")]
    return (errors or lines)[-1].strip()[:200]


rows = []
for name, code in SMOKE.items():
    from importlib.metadata import version

    row = {"library": name, "version": version(name), "normal": run(textwrap.dedent(code), "normal"), "lazy_all": run(textwrap.dedent(code), "all")}
    rows.append(row)
    print(json.dumps(row), flush=True)

(ROOT / "results").mkdir(exist_ok=True)
(ROOT / "results" / "compat.json").write_text(json.dumps({"python": sys.version.split()[0], "rows": rows}, indent=2))
