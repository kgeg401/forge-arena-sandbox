"""Native UI callbacks only; inspect every action; no engine input files written."""
import json,subprocess,sys,time
from pathlib import Path
from runtime_paths import ROOT
LAB=ROOT/'native-lab';QA=Path(__file__).with_name('native_ui_qa.py')

class StaleObservation(RuntimeError):
 """The QA guard rejected before publishing an action; re-observe safely."""
def read(name):return json.loads((LAB/name).read_text(encoding='utf-8-sig'))
def inspect(primary=False):
 end=time.monotonic()+8
 while time.monotonic()<end:
  r=subprocess.run([sys.executable,'-B',str(QA),'inspect',*(['--primary'] if primary else [])],capture_output=True,text=True,timeout=5)
  if r.returncode==0:return json.loads(r.stdout)
  if 'not stable' not in r.stderr:raise RuntimeError(r.stderr[-2500:])
  time.sleep(.2)
 raise RuntimeError('Native state did not settle')
def mapping():
 objects={};nf={}
 for line in (LAB/'forge-ipc/native-wire.jsonl').read_text().splitlines():
  r=json.loads(line)
  if r['direction']!='incoming':continue
  s=r['message'].get('gameStateMessage',{})
  for a in s.get('annotations',[]):
   if 'AnnotationType_ObjectIdChanged' in a.get('type',[]):
    d={d['key']:d for d in a['details']};old=d['orig_id']['valueInt32'][0];new=d['new_id']['valueInt32'][0]
    nf[new]=nf.get(old,old-1000 if 1000<old<10000 else None)
  for c in s.get('gameObjects',[]):
   i=c['instanceId'];objects[i]=c
   if 1000<i<10000:nf[i]=i-1000
  for i in s.get('diffDeletedInstanceIds',[]):objects.pop(i,None)
 return objects,nf
def action(*args,observed=None,wait_for_change=True):
 p=observed or inspect();r=subprocess.run([sys.executable,'-B',str(QA),*map(str,args),'--expected-state',str(p['state'])],capture_output=True,text=True,timeout=8)
 if r.returncode:
  if any(message in r.stderr for message in ('Native QA observation changed before publication; inspect again','Native state not stable; observe again')):
   raise StaleObservation(r.stderr[-2500:])
  raise RuntimeError(r.stderr[-2500:])
 print(r.stdout.strip(),flush=True)
 # Some original controls perform only a local selection (for example choosing
 # a blocker before choosing its attacker). QA has already received a matching
 # callback receipt. Observe again without claiming a Forge state change or
 # resending that accepted local interaction.
 if not wait_for_change:return inspect()
 end=time.monotonic()+8
 while time.monotonic()<end:
  n=inspect()
  if (n['state'],n['workflow'],n['buttons'],n['uiButtons'],n.get('damageAssignments'),n.get('damageControls'),[(v['id'],v['holder']) for v in n['clickable']])!=(p['state'],p['workflow'],p['buttons'],p['uiButtons'],p.get('damageAssignments'),p.get('damageControls'),[(v['id'],v['holder']) for v in p['clickable']]):return n
  time.sleep(.15)
 raise RuntimeError('No native state/workflow change; no retry sent')
def card(forge_id,wait_for_change=True):
 objects,nf=mapping()
 for primary in (False,True):
  p=inspect(primary);ids=[v['id'] for v in p['clickable'] if nf.get(v['id'])==forge_id and v.get('visible')]
  if len(ids)==1:return action('click',ids[0],*(['--primary'] if primary else []),observed=p,wait_for_change=wait_for_change)
  if len(ids)>1:raise RuntimeError('Ambiguous native card view; inspect before choosing')
 raise RuntimeError('No original clickable native view for Forge '+str(forge_id))
if __name__=='__main__':
 if sys.argv[1]=='inspect':print(json.dumps(inspect(),indent=2))
 elif sys.argv[1]=='card':card(int(sys.argv[2]))
 elif sys.argv[1]=='action':action(*sys.argv[2:])
