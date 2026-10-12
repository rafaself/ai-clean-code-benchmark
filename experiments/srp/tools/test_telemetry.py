import unittest
from telemetry import summarize
class TelemetryTest(unittest.TestCase):
    def test_deduplicates_actions_and_turn_usage(self):
        item={'id':'fixture-action','type':'command_execution'}
        usage={'input_tokens':7,'cached_input_tokens':3,'output_tokens':2}
        events=[{'type':'turn.started','turn_id':'fixture-turn'},{'type':'item.started','item':item},{'type':'item.completed','item':item},{'type':'turn.completed','turn_id':'fixture-turn','usage':usage},{'type':'turn.completed','turn_id':'fixture-turn','usage':usage}]
        result=summarize(events)
        self.assertEqual(result['observed_tool_action_items'],1)
        self.assertEqual(result['reported_total_tokens'],9)
        self.assertEqual(result['cached_input_tokens'],3)
    def test_missing_usage_is_not_zero(self):
        result=summarize([{'type':'turn.started'},{'type':'turn.completed'}])
        self.assertIsNone(result['reported_total_tokens'])
        self.assertFalse(result['usage_complete'])
    def test_incomplete_turn_cannot_claim_complete_usage(self):
        result=summarize([{'type':'turn.started','turn_id':'one'},{'type':'turn.completed','turn_id':'one','usage':{'input_tokens':7,'output_tokens':2}},{'type':'turn.started','turn_id':'two'}])
        # Interrupted sessions must be classified externally; observed usage is partial.
        self.assertEqual(result['reported_total_tokens'],9)
        self.assertFalse(result['usage_complete'])
if __name__ == '__main__': unittest.main()
