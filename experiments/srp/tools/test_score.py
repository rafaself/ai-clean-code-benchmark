"""Scoring integrity fixtures; these are not measured benchmark outcomes."""
import json
from pathlib import Path
import tempfile
import unittest
from score import score

class ScoringIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'grading/reports').mkdir(parents=True)
        self.ids = {'oracle_cases':['RG fixture regression','T01 fixture acceptance'], 'required_unit_tests':[{'file':'src/fixture.spec.ts','name':'required fixture'}]}
        self.put('session.json',{'session':'fixture','task':'T01'})
        self.put('termination.json',{'code':0,'container_exit_code':0,'timed_out':False,'container_oom_killed':False})
        self.put('grading/status.json',{'status':'graded','verification':{'passed':True},'checks':{'build':{'exit_code':0,'timed_out':False},'post_build_verification':{'passed':True}}})
        self.put('grading/reports/oracle.json',{'success':True,'testResults':[{'assertionResults':[{'fullName':n,'status':'passed'} for n in self.ids['oracle_cases']]}]})
        self.put('grading/reports/unit.json',{'success':True,'numFailedTests':0,'numPendingTests':0,'testResults':[{'name':'/workspace/src/fixture.spec.ts','assertionResults':[{'fullName':'required fixture','status':'passed'},{'fullName':'new relevant fixture','status':'passed'}]}]})
    def tearDown(self): self.temp.cleanup()
    def put(self, name, data): (self.root/name).write_text(json.dumps(data))
    def test_required_identities_and_extra_passing_test(self): self.assertTrue(score(self.root,self.ids)['correct_completion'])
    def test_missing_required_test_despite_reported_success(self):
        p=self.root/'grading/reports/unit.json';d=json.loads(p.read_text());d['testResults'][0]['assertionResults'].pop(0);self.put(str(p.relative_to(self.root)),d)
        self.assertFalse(score(self.root,self.ids)['correct_completion'])
    def test_duplicate_oracle_identity_is_not_complete(self):
        p=self.root/'grading/reports/oracle.json';d=json.loads(p.read_text());d['testResults'][0]['assertionResults'].append({'fullName':'RG fixture regression','status':'passed'});self.put(str(p.relative_to(self.root)),d)
        self.assertFalse(score(self.root,self.ids)['correct_completion'])
    def test_timeout_cannot_be_upgraded_by_passing_tests(self):
        self.put('termination.json',{'code':0,'container_exit_code':0,'timed_out':True,'container_oom_killed':False})
        self.assertFalse(score(self.root,self.ids)['correct_completion'])
    def test_integrity_rejection_retains_observed_usage(self):
        self.put('grading/status.json',{'status':'integrity_failure','reason':'protected_source_changed_before_grading'})
        (self.root/'control').mkdir()
        (self.root/'control/events.jsonl').write_text(json.dumps({'type':'turn.started'})+'\n'+json.dumps({'type':'turn.completed','usage':{'input_tokens':7,'cached_input_tokens':3,'output_tokens':2}})+'\n')
        result=score(self.root,self.ids)
        self.assertFalse(result['correct_completion'])
        self.assertEqual(result['telemetry']['reported_total_tokens'],9)

    def test_build_integrity_required(self):
        p=self.root/'grading/status.json';d=json.loads(p.read_text());d['checks']['post_build_verification']['passed']=False;self.put(str(p.relative_to(self.root)),d)
        self.assertFalse(score(self.root,self.ids)['correct_completion'])
if __name__=='__main__':unittest.main()
