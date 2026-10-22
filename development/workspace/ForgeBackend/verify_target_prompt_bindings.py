"""Check actual owned prompt bindings, including rejecting wrong IDs/text/types."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
from build_card_coverage import checked_target_prompt


def run(a):
    db=sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True);bindings={};checks=[]
    for p in a.policy:bindings.update(json.loads(p.read_text(encoding='utf8')).get('targetPromptBindings',{}))
    if not bindings:raise ValueError('Expected actual source-bound target prompts')
    for name,binding in bindings.items():
        assert checked_target_prompt(db,name,binding)==binding['promptId'];checks.append(dict(check=name+' actual owned prompt',passed=True))
    first=next(iter(bindings.values()))
    for label,change in [('wrong text',lambda b:b.update(expectedText='Wrong target restriction.')),('wrong ID',lambda b:b.update(promptId=99999999)),('boolean ID',lambda b:b.update(promptId=True)),('negative ID',lambda b:b.update(promptId=-1)),('unexpected binding field',lambda b:b.update(fallback=1010))]:
        binding=deepcopy(first);change(binding)
        try:checked_target_prompt(db,'negative-check',binding)
        except ValueError:checks.append(dict(check=label+' rejected',passed=True))
        else:raise AssertionError(label)
    db.close();a.output.mkdir(parents=True,exist_ok=False);(a.output/'report.json').write_text(json.dumps(dict(passed=True,checks=len(checks),results=checks),indent=2));print(json.dumps(dict(checks=len(checks))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',type=Path,required=True);p.add_argument('--policy',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True);run(p.parse_args())
