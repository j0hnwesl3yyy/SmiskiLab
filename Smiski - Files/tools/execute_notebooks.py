"""Execute notebooks in-process (no Jupyter kernel / sockets) and store outputs.

Use this when a kernel cannot start (e.g. a sandbox that forbids local sockets).
In normal Jupyter, just "Run All" - the notebooks are plain code.

    python tools/execute_notebooks.py notebooks/01_resale_premium.ipynb [...]
"""
from __future__ import annotations

import ast
import base64
import contextlib
import io
import os
import sys
import time
import traceback
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import nbformat  # noqa: E402


def _repr_output(value) -> dict:
    data = {"text/plain": repr(value)}
    if hasattr(value, "_repr_html_"):
        try:
            data["text/html"] = value._repr_html_()
        except Exception:
            pass
    return data


def run_cell(src: str, ns: dict) -> list:
    outs, buf = [], io.StringIO()
    tree = ast.parse(src)
    last = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last = ast.Expression(tree.body.pop().value)
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(compile(tree, "<cell>", "exec"), ns)
            value = eval(compile(last, "<cell>", "eval"), ns) if last is not None else None
    except Exception:
        text = buf.getvalue()
        if text:
            outs.append(nbformat.v4.new_output("stream", name="stdout", text=text))
        tb = traceback.format_exc()
        outs.append(nbformat.v4.new_output("error", ename="Error", evalue=tb.splitlines()[-1], traceback=tb.splitlines()))
        raise RuntimeError(tb)
    text = buf.getvalue()
    if text:
        outs.append(nbformat.v4.new_output("stream", name="stdout", text=text))
    for num in plt.get_fignums():
        f = io.BytesIO()
        plt.figure(num).savefig(f, format="png", dpi=110, bbox_inches="tight")
        outs.append(nbformat.v4.new_output("display_data", data={"image/png": base64.b64encode(f.getvalue()).decode()}))
    plt.close("all")
    if value is not None:
        outs.append(nbformat.v4.new_output("execute_result", data=_repr_output(value), execution_count=None))
    return outs


def execute(path: Path) -> None:
    nb = nbformat.read(path, as_version=4)
    os.chdir(path.parent)                        # notebooks assume cwd == notebooks/
    ns: dict = {"__name__": "__main__"}
    t0, n = time.time(), 0
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        n += 1
        cell.execution_count = n
        cell.outputs = run_cell(cell.source, ns)
        for o in cell.outputs:
            if o.output_type == "execute_result":
                o.execution_count = n
    nbformat.write(nb, path)
    print(f"{path.name}: {n} code cells in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    for p in [Path(a).resolve() for a in sys.argv[1:]]:   # resolve first: execute() changes the cwd
        execute(p)
