"""Verify the frozen artifacts and a staged subject without invoking Codex or modifying files."""
from pathlib import Path
import argparse
import hashlib
import json

p = argparse.ArgumentParser()
p.add_argument('--subject', type=Path, help='Optional monorepo snapshot to check protected original inputs')
a = p.parse_args()
root = Path(__file__).resolve().parents[3]
manifest = json.loads((root / 'experiments/srp/config/execution-manifest.json').read_text())
errors = []
for name, expected in manifest['artifact_sha256'].items():
    path = root / name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        errors.append('Changed or missing artifact: ' + name)
if a.subject:
    for name, expected in manifest['protected_subject_sha256'].items():
        path = a.subject / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append('Changed or missing protected subject input: ' + name)
    agents = a.subject / 'AGENTS.md'
    if not agents.is_file() or hashlib.sha256(agents.read_bytes()).hexdigest() != manifest['common_instruction_sha256']:
        errors.append('Staged root AGENTS.md does not match frozen common instructions')
if errors:
    raise SystemExit('\n'.join(errors))
print('PASS: frozen artifacts' + (' and protected subject inputs/instructions' if a.subject else '') + '; no model calls performed')
