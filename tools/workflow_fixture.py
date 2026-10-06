"""Create an authored Notebook/Quarto workflow in a new test directory."""

import argparse
from pathlib import Path

from paperdelta.demo import create_demo
from paperdelta.storage import Project, json_text

RUNNER = """import argparse,sys
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
parser=argparse.ArgumentParser()
parser.add_argument('--only',choices=['metrics','figure'])
args=parser.parse_args()
path=Path('analysis.ipynb')
original=nbformat.read(path,as_version=4)
chosen=[cell for cell in original.cells if not args.only or cell.id==args.only]
work=nbformat.v4.new_notebook(cells=chosen,metadata=original.metadata)
manager=KernelManager(kernel_name='python3')
manager.kernel_spec.argv=[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}']
try:
    NotebookClient(work,km=manager,timeout=60,resources={'metadata':{'path':str(Path.cwd())}}).execute()
finally:
    if manager.has_kernel:
        manager.shutdown_kernel(now=True)
completed={cell.id:cell for cell in work.cells}
original.cells=[completed.get(cell.id,cell) for cell in original.cells]
nbformat.write(original,path)
with Path('.paperdelta/example-executions.log').open('a',encoding='utf-8') as log:
    log.write((args.only or 'all')+'\\n')
"""

METRICS = """from pathlib import Path
import csv,io
from decimal import Decimal
raw=Path('observations.csv').read_bytes()
rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
mean=sum(Decimal(row['accuracy']) for row in rows if row['model']=='Ours')/3
Path('results/metrics.csv').write_bytes(raw)
print('Ours accuracy (%):',mean*100)
"""

FIGURE = """from pathlib import Path
import csv,io
from decimal import Decimal
rows=list(csv.DictReader(io.StringIO(Path('results/metrics.csv').read_text('utf-8'))))
score=sum(Decimal(row['accuracy']) for row in rows if row['model']=='Ours')/3*100
svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="500" height="150">'
     f'<rect width="500" height="150" fill="white"/>'
     f'<text x="20" y="35" font-family="sans-serif" font-size="20">Ours: {score:.1f}%</text>'
     f'<rect x="20" y="65" width="{score*5}" height="35" fill="#147d92"/></svg>')
Path('results/figure.svg').write_text(svg,encoding='utf-8',newline='\\n')
print('Figure accuracy (%):',score)
"""


def create_fixture(output, *, saved=False):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Use a new fixture directory")
    create_demo(Project(output.parent), output.name, "baseline", "quarto")
    store = Project(output)
    store.write("observations.csv", store.read("results/metrics.csv"))
    cells = []
    for index, (name, code) in enumerate((("metrics", METRICS), ("figure", FIGURE)), 1):
        cells.append(
            {
                "cell_type": "code",
                "id": name,
                "metadata": {},
                "source": code,
                "execution_count": index if saved else None,
                "outputs": [
                    {
                        "output_type": "stream",
                        "name": "stdout",
                        "text": "Authored saved-state fixture: 84.1\n",
                    }
                ]
                if saved
                else [],
            }
        )
    store.write(
        "analysis.ipynb",
        json_text(
            {
                "nbformat": 4,
                "nbformat_minor": 5,
                "metadata": {
                    "kernelspec": {
                        "name": "python3",
                        "display_name": "Python 3",
                        "language": "python",
                    }
                },
                "cells": cells,
            }
        ).encode(),
    )
    store.write("run_notebook.py", RUNNER.encode())
    store.write(
        "paper.qmd",
        store.read("paper.qmd") + b"\n![Authored accuracy figure](results/figure.svg)\n",
    )
    if saved:
        store.write(
            "results/figure.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg" width="500" height="150">'
            b'<text x="10" y="30">84.1%</text></svg>',
        )
        store.write("rendered.html", b"<p>Authored saved export: 84.1%</p>")
    return store


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--saved", action="store_true")
    args = parser.parse_args()
    create_fixture(args.out, saved=args.saved)
