"""Parse Codex events; observed action-item counts are a lower bound because code-mode wrapper calls are omitted."""
import json

ACTION_TYPES = {'command_execution', 'file_change', 'mcp_tool_call', 'web_search'}


def summarize(events):
    actions = set()
    completed = set()
    started = set()
    usage_by_turn = {}
    turn = 0
    active_turn = None
    for event in events:
        kind = event.get('type')
        if kind == 'turn.started':
            turn += 1
            active_turn = event.get('turn_id', f'observed-{turn}')
            started.add(active_turn)
        item = event.get('item', {})
        if item.get('type') in ACTION_TYPES and item.get('id') is not None:
            actions.add((active_turn, item['id']))
        if kind == 'turn.completed':
            identity = event.get('turn_id', active_turn)
            if identity is None:
                continue
            completed.add(identity)
            if isinstance(event.get('usage'), dict):
                usage_by_turn.setdefault(identity, event['usage'])

    usage = list(usage_by_turn.values())

    def total(key):
        values = [record.get(key) for record in usage]
        return sum(values) if values and all(isinstance(v, int) and v >= 0 for v in values) else None

    input_tokens, output_tokens = total('input_tokens'), total('output_tokens')
    return {
        'observed_tool_action_items': len(actions),
        'exact_internal_tool_calls': None,
        'input_tokens': input_tokens,
        'cached_input_tokens': total('cached_input_tokens'),
        'output_tokens': output_tokens,
        'reasoning_output_tokens': total('reasoning_output_tokens'),
        'reported_total_tokens': input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None,
        'usage_records': len(usage),
        'usage_complete': bool(started) and started == completed == set(usage_by_turn),
    }

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('trace')
    a = p.parse_args()
    with open(a.trace) as handle:
        print(json.dumps(summarize(json.loads(line) for line in handle if line.strip()), indent=2))
