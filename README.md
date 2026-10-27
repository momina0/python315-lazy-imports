# Python 3.15 lazy imports on a real FastAPI service and CLI

Python 3.15 (released Oct 9, 2026) ships [PEP 810](https://peps.python.org/pep-0810/) explicit lazy imports. You can write `lazy import pandas as pd`, and pandas only loads the first time `pd` is used. There's also a global switch, `-X lazy_imports=all` (or `PYTHON_LAZY_IMPORTS`), that makes every module-level import lazy without touching code.

I wanted two answers: how much it helps on the kind of code I actually write, and whether the global switch is safe to turn on.

**Setup:** Python 3.15.2 (via `uv`), Windows 11, AMD Ryzen 7 5700U. FastAPI 0.162, Pydantic 2.14, SQLAlchemy 2.1, pandas 3.1, numpy 2.5, boto3 1.43, openai 3.39, requests 2.34, Typer 0.27, Rich 15; full pins in [`requirements.txt`](requirements.txt). Every measurement is a fresh process, with 2 warm-up runs and then 10 timed runs. Raw numbers are in [`results/`](results).

## The test apps

- [`apps/cli.py`](apps/cli.py): a Typer CLI with four commands, each needing a different heavy library (pandas, boto3, openai, requests), all imported at the top as usual.
- [`apps/api.py`](apps/api.py): a FastAPI service with SQLAlchemy, Pydantic and endpoints that use pandas, boto3, openai and httpx. Again, everything is imported at the top.
- [`apps/cli_lazy.py`](apps/cli_lazy.py) and [`apps/api_lazy.py`](apps/api_lazy.py): the same files with `lazy` added to the 4 heavy, rarely used imports. That's the whole diff. FastAPI, Pydantic, SQLAlchemy, Typer and Rich stay eager.

## Result 1: marking 4 imports `lazy` cut startup by half or more

| Scenario | Modules loaded, normal → `lazy` | Fastest run, normal → `lazy` | Median, normal → `lazy` |
|---|---|---|---|
| `cli --help` | 1,720 → 330 | 5.2 s → 1.1 s | 5.5 s → 1.2 s |
| `cli fetch` (needs requests) | 1,624 → 364 | 5.1 s → 2.6 s | 10.0 s → 2.6 s |
| `cli report` (needs pandas) | 1,624 → 687 | 4.8 s → 3.4 s | 5.3 s → 5.3 s |
| API boot | 1,888 → 570 | 6.3 s → 2.7 s | 10.0 s → 2.8 s |
| API boot + `GET /health` | 1,896 → 625 | 6.5 s → 3.1 s | 10.6 s → 6.0 s |
| API boot + `GET /report` (needs pandas) | 1,896 → 1,059 | 6.3 s → 4.6 s | 7.0 s → 4.9 s |

"Modules loaded" is the most reliable column: it's counted from `-X importtime`, so it comes out the same on every run. The timings are noisy on this machine. Python startup on this Windows laptop is slow in general, and normal-mode runs jumped between roughly 5 s and 10 s with nothing changing, so read the medians loosely. On Linux the absolute numbers would be much smaller, but the module counts would be the same.

What the table shows:
- Commands and endpoints that don't need the heavy libraries get most of the benefit: `--help`, `/health`, booting the service.
- A command that does need pandas still pays for pandas, just later. `cli report` and `GET /report` gain much less. For an API, lazy imports move cost from boot to the first request that needs the library, so the first `/report` after a deploy is the slow one.

## Result 2: the global switch broke 3 of 14 libraries, and the API couldn't start

[`bench/compat.py`](bench/compat.py) imports and actually uses each library in a fresh process, once normally and once with `-X lazy_imports=all`:

| Library | Normal | `-X lazy_imports=all` |
|---|---|---|
| numpy, pydantic, fastapi, httpx, requests, boto3, rich, typer, click, jinja2, uvicorn | ok | ok |
| **pandas** 3.1.0 | ok | `ImportError: numpy._core.multiarray failed to import` |
| **SQLAlchemy** 2.1.6 | ok | `InvalidRequestError: No such event 'connect' for target <...Pool>` |
| **openai** 3.39.0 | ok | `AttributeError: 'lazy_import' object has no attribute '__module__'` |

My reading of the errors:
- **SQLAlchemy** registers its event hooks as a side effect of importing modules. With every import lazy, those modules never run, so the hooks don't exist when `create_engine` looks for them. `create_engine` runs at import time in `api.py`, so the API failed before serving a single request.
- **pandas** fails inside its compiled extension's call into numpy's C API during import.
- **openai** sets `__module__` on objects it re-exports. Under the global switch, some of those names are still unloaded lazy placeholders, and those can't have attributes set.

All three work fine when the imports in *my* files are marked `lazy`, because the libraries' own internal imports stay normal. `api_lazy.py` lazily imports openai and pandas and serves every endpoint.

I couldn't find existing reports of these three, so treat them as what I hit with these versions, not confirmed upstream bugs.

## One more thing to know before turning it on

With the global switch, a **missing package no longer fails at startup**:

```
$ python -X lazy_imports=all -c "import does_not_exist; print('started fine')"
started fine
```

The `ModuleNotFoundError` only appears when the code first touches that name. For a web service, that means a deploy with a missing dependency can pass its health check and fail later on one endpoint. The same applies to anything you mark `lazy`, so keep a check in CI that imports those dependencies directly, e.g. `python -c "import pandas, boto3, openai, httpx"`.

(The 3.16 docs list a `-X lazy_imports=none` mode that turns every `lazy` keyword off. It doesn't exist in 3.15.2: `Fatal Python error: ... invalid value; expected 'all' or 'normal'`.)

## Takeaways

- Put `lazy` on the few heavy imports that most code paths don't use (pandas, cloud SDKs, LLM clients). In these apps that was 4 words per file, and it cut the modules loaded at startup by 67-81% on paths that do not need them.
- Don't flip `-X lazy_imports=all` on an existing app and assume it works. Here it broke pandas, SQLAlchemy and openai.
- Expect the first request that needs a lazily imported library to be slower than it used to be.
- `lazy` is only allowed at module level. Inside a function it's a `SyntaxError` (`lazy import not allowed inside functions`).

## Run it yourself

```bash
uv python install 3.15
uv venv --python 3.15 .venv
uv pip install -r requirements.txt
.venv/Scripts/python bench/startup.py 10    # ~20 min on my laptop
.venv/Scripts/python bench/compat.py
.venv/Scripts/python bench/summary.py
```

On macOS or Linux, use `.venv/bin/python` instead.
