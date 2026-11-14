"""Execute clean notebook copies with the current Python environment."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Save executed copies here; source notebooks stay unchanged.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        if args.output.resolve() == root:
            parser.error('Choose another output directory to preserve clean source notebooks.')
    with tempfile.TemporaryDirectory(prefix='zakaria-kernel-') as temporary:
        kernel_dir = Path(temporary) / 'zakaria-verification'
        kernel_dir.mkdir()
        (kernel_dir / 'kernel.json').write_text(json.dumps({
            'argv': [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}'],
            'display_name': 'Zakaria verification', 'language': 'python',
            'env': {'MPLBACKEND': 'Agg'},
        }))
        specs = KernelSpecManager(kernel_dirs=[temporary])
        for path in sorted(root.glob('*.ipynb')):
            notebook = nbformat.read(path, as_version=4)
            manager = KernelManager(kernel_name='zakaria-verification', kernel_spec_manager=specs)
            client = NotebookClient(notebook, timeout=180, kernel_name='zakaria-verification',
                                    resources={'metadata': {'path': str(root)}})
            client.km = manager
            try:
                client.execute()
                if args.output:
                    nbformat.write(notebook, args.output / path.name)
                print(f'PASS {path.name}', flush=True)
            finally:
                if manager.has_kernel:
                    manager.shutdown_kernel(now=True)


if __name__ == '__main__':
    main()
