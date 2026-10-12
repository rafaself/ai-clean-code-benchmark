"""Stage a fresh, neutral source/dependency snapshot. Never starts an agent or a service."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

p = argparse.ArgumentParser()
p.add_argument('--variant', choices=['A','B'], required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[3]
manifest = json.loads((root/'experiments/srp/config/execution-manifest.json').read_text())
source = root/'subjects/hoppscotch'
if a.output.exists():
    raise SystemExit('Output must be a new disposable directory; nothing overwritten')
archive = root/manifest['local_cache']['dependencies']['path']
if hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() != manifest['local_cache']['dependencies']['sha256']:
    raise SystemExit('Dependency snapshot hash mismatch')
a.output.mkdir(parents=True)
subprocess.run(['git','init','-b','master'],cwd=a.output,check=True,stdout=subprocess.DEVNULL)
raw = subprocess.check_output(['git','archive',manifest['upstream_commit']],cwd=source)
with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
    tar.extractall(a.output,filter='data')
if a.variant == 'B':
    subprocess.run(['git','apply',str(root/'experiments/srp/preparation/variant-b.patch')],cwd=a.output,check=True)
with tarfile.open(archive) as tar:
    tar.extractall(a.output,filter='data')
(a.output/'AGENTS.md').write_bytes((root/'experiments/srp/config/AGENTS.md').read_bytes())
subprocess.run(['git','add','.'],cwd=a.output,check=True)
subprocess.run(['git','-c','user.name=Benchmark','-c','user.email=benchmark@example.invalid','commit','-m','Prepared maintenance workspace'],cwd=a.output,check=True,stdout=subprocess.DEVNULL,
               env={**__import__('os').environ,'GIT_AUTHOR_DATE':'2026-10-12T00:00:00Z','GIT_COMMITTER_DATE':'2026-10-12T00:00:00Z'})
print('Staged',a.variant,'with one neutral commit and no upstream history; no agent launched')
