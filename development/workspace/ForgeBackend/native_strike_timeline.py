"""Review original-renderer strike clips and raw native auto-pass ordering.

This specific sequence is a three-power double striker against one 0/4 blocker,
with trample actually granted by Charge Through.
The seven-digit UTC fraction is retained as 100 ns ticks. No timestamps are
smoothed, and synthetic checks do not count as native animation evidence.
"""
import calendar,datetime,re

def utc_ticks(value):
 match=re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,7}))?(?:Z|\+00:00)',value)
 if not match:raise ValueError('Expected exact UTC timestamp with at most seven fractional digits')
 base=datetime.datetime.strptime(match[1],'%Y-%m-%dT%H:%M:%S')
 return calendar.timegm(base.timetuple())*10000000+int((match[2] or '').ljust(7,'0'))

def review(timeline,wire,source,target):
 starts=[v for v in timeline if v['kind']=='start' and v['type']=='CombatFrame'];ends=[v for v in timeline if v['kind']=='complete' and v['type']=='CombatFrame']
 assert len(starts)==len(ends)==2,'Expected two complete original combat clips'
 by_id={v['instance']:v for v in ends};assert len(by_id)==2 and {v['instance'] for v in starts}==by_id.keys(),'Clip identities must match exactly once'
 assert all(v['seconds']<by_id[v['instance']]['seconds'] for v in starts),'Both original clips must run forward'
 assert starts[1]['seconds']>by_id[starts[0]['instance']]['seconds'],'The second strike began before the first animation completed'
 hits=[[(v['target'],v['amount']) for v in row['impacts'] if v['source']==source] for row in starts]
 assert hits==[[(target,3)],[(target,1),(2,2)]],'Original clips must contain the actual first hit and later trample split'
 passes=[v for v in wire if v['direction']=='internal-rules' and v['request']['nativeStateId']==starts[0]['state']]
 assert passes,'No rules handoff from the first original clip was captured'
 completion=utc_ticks(by_id[starts[0]['instance']]['utc']);assert all(utc_ticks(v['utc'])>=completion for v in passes),'Automatic rules pass preceded the first clip completion'
 return dict(passed=True,combatFrames=starts,firstCompletionUtc=by_id[starts[0]['instance']]['utc'],nextPassUtc=passes[0]['utc'],nextPassDelayTicks=utc_ticks(passes[0]['utc'])-completion,scope=__doc__)

if __name__=='__main__':
 import copy,json
 base='2026-11-02T09:24:42';assert utc_ticks(base+'.1234567Z')-utc_ticks(base+'.1234566Z')==1
 assert utc_ticks(base+'Z')==utc_ticks(base+'.0000000+00:00')
 for invalid in (base+'.12345678Z',base+'+01:00','2026-02-30T00:00:00Z',base):
  try:utc_ticks(invalid)
  except ValueError:pass
  else:raise AssertionError('Invalid timestamp accepted')
 rows=[dict(kind='start',type='CombatFrame',instance=1,seconds=1,state=10,utc=base+'.1000000Z',impacts=[dict(source=100,target=200,amount=3)]),dict(kind='complete',type='CombatFrame',instance=1,seconds=2,state=10,utc=base+'.2000000Z'),dict(kind='start',type='CombatFrame',instance=2,seconds=3,state=12,utc=base+'.3000000Z',impacts=[dict(source=100,target=200,amount=1),dict(source=100,target=2,amount=2)]),dict(kind='complete',type='CombatFrame',instance=2,seconds=4,state=12,utc=base+'.4000000Z')]
 wire=[dict(direction='internal-rules',utc=base+'.2000001Z',request=dict(nativeStateId=10))];assert review(rows,wire,100,200)['nextPassDelayTicks']==1
 for mutation in ('early-pass','overlap','missing-hit','missing-completion'):
  r=copy.deepcopy(rows);w=copy.deepcopy(wire)
  if mutation=='early-pass':w[0]['utc']=base+'.1999999Z'
  elif mutation=='overlap':r[2]['seconds']=1.5
  elif mutation=='missing-hit':r[2]['impacts'].pop()
  else:r.pop()
  try:review(r,w,100,200)
  except AssertionError:pass
  else:raise AssertionError('Invalid native evidence accepted: '+mutation)
 print(json.dumps(dict(passed=True,checks=11,scope='Synthetic reader/negative checks only; no native animation claim')))
