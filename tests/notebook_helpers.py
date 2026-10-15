"""Load the self-contained compatibility cell without running Kaggle setup."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / 'wan2gp-kaggle.ipynb'


def compatibility_cell():
    notebook = json.loads(NOTEBOOK.read_text())
    return next(''.join(cell['source']) for cell in notebook['cells']
                if cell['cell_type'] == 'code'
                and 'def configure_ffmpeg_passthrough(' in ''.join(cell['source']))


def load_configure():
    tree = ast.parse(compatibility_cell())
    tree.body = [node for node in tree.body if isinstance(
        node, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
    namespace = {}
    exec(compile(tree, str(NOTEBOOK), 'exec'), namespace)
    return namespace['configure_ffmpeg_passthrough']
