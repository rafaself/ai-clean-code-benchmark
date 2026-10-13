"""Score preserved external reports against the frozen test identities; never launches a session."""
from collections import Counter
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

def read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None

def score(session, identities):
    meta = read(session / 'session.json') or {}
    task = meta.get('task')
    termination = read(session / 'termination.json') or {}
    grading = read(session / 'grading/status.json') or {}
    oracle = read(session / 'grading/reports/oracle.json')
    unit = read(session / 'grading/reports/unit.json')
    expected = {name for name in identities['oracle_cases'] if name.startswith(('RG ', str(task) + ' '))}
    executed = [a for s in (oracle or {}).get('testResults', []) for a in s.get('assertionResults', []) if a['status'] not in ('pending', 'todo', 'skipped')]
    actual = {a['fullName']: a['status'] for a in executed}
    oracle_ok = bool(oracle) and bool(expected) and len(executed) == len(actual) and set(actual) == expected and all(v == 'passed' for v in actual.values()) and oracle.get('success') is True
    required = Counter((x['file'], x['name']) for x in identities['required_unit_tests'])
    passed, failed_original = Counter(), []
    for suite in (unit or {}).get('testResults', []):
        file = suite['name'].removeprefix('/workspace/')
        for case in suite.get('assertionResults', []):
            key = (file, case['fullName'])
            if case['status'] == 'passed':
                passed[key] += 1
            elif key in required:
                failed_original.append({'file': file, 'name': case['fullName'], 'status': case['status']})
    original_tests_ok = bool(unit) and unit.get('success') is True and all(passed[k] >= v for k, v in required.items()) and unit.get('numFailedTests') == 0 and unit.get('numPendingTests') == 0
    checks = grading.get('checks', {})
    build_ok = checks.get('build', {}).get('exit_code') == 0 and checks.get('build', {}).get('timed_out') is False
    integrity = grading.get('verification', {}).get('passed') is True and checks.get('post_build_verification', {}).get('passed') is True
    agent_ok = termination.get('code') == 0 and termination.get('container_exit_code') == 0 and termination.get('timed_out') is False and termination.get('container_oom_killed') is False
    failed_rg = [name for name in sorted(expected) if name.startswith('RG ') and actual.get(name) == 'failed'] if oracle else None
    return {'session': meta.get('session'), 'task': task, 'variant': meta.get('variant'), 'repetition': meta.get('repetition'), 'position': meta.get('position'),
            'correct_completion': grading.get('status') == 'graded' and agent_ok and oracle_ok and original_tests_ok and build_ok and integrity,
            'agent_termination_ok': agent_ok, 'oracle_complete_and_passed': oracle_ok, 'required_original_tests_passed': original_tests_ok,
            'build_passed': build_ok, 'protected_integrity_passed': integrity,
            'regression_scenarios_failed': failed_rg, 'regression_count': len(failed_rg) if failed_rg is not None else None,
            'original_tests_not_passing': failed_original if unit else None,
            'regression_incidence': bool(failed_rg or failed_original) if oracle and unit else None,
            'oracle_statuses': actual, 'expected_oracle_cases': len(expected),
            'elapsed_seconds': termination.get('elapsed_seconds'), 'timed_out': termination.get('timed_out'),
            'telemetry': grading.get('telemetry') or {}, 'grading_status': grading.get('status'),
            'classification': 'attempt retained; infrastructure exclusion requires a separate written review'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('session', type=Path)
    args = parser.parse_args()
    identities = read(ROOT / 'experiments/srp/preparation/required-test-identities.json')
    if not identities:
        raise SystemExit('Frozen test identity list unavailable')
    print(json.dumps(score(args.session, identities), indent=2))
