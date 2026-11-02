"""Review one native first-strike/instant/regular-strike capture, not global animation parity."""
from native_strike_timeline import utc_ticks

def review(timeline,wire,source,target,spell):
    starts=[v for v in timeline if v['kind']=='start' and v['type']=='CombatFrame']
    ends=[v for v in timeline if v['kind']=='complete' and v['type']=='CombatFrame']
    assert len(starts)==len(ends)==2,'Two complete original strike clips are required'
    ended={v['instance']:v for v in ends}
    assert len(ended)==2 and {v['instance'] for v in starts}==ended.keys(),'Clip identities must complete exactly once'
    assert all(utc_ticks(v['utc'])<utc_ticks(ended[v['instance']]['utc']) for v in starts),'Both clips must run forward'
    hits=[[(v['target'],v['amount']) for v in row['impacts'] if v['source']==source] for row in starts]
    assert hits==[[(target,1)],[(target,4)]],'The real instant must change only the later hit'
    # Human actions are outgoing GRE responses. internal-rules contains only
    # automatic passes and is not an authoritative record of a clicked spell.
    casts=[v for v in wire if v['direction']=='outgoing' and v['message'].get('type')=='ClientMessageType_PerformActionResp'
           and any(a.get('actionType')=='ActionType_Cast' and a.get('instanceId')==spell for a in v['message'].get('performActionResp',{}).get('actions',[]))]
    assert len(casts)==1,'Exactly one original user spell-cast response is required'
    first_end=utc_ticks(ended[starts[0]['instance']]['utc']);cast=utc_ticks(casts[0]['utc']);second=utc_ticks(starts[1]['utc'])
    assert first_end<=cast<second,'The actual original spell cast must be after completed first and before started regular strike'
    return dict(passed=True,combatFrames=starts,cast=casts[0],firstCompletionUtc=ended[starts[0]['instance']]['utc'],scope=__doc__)

if __name__=='__main__':
    import copy
    stamp=lambda n:f'2026-11-02T11:00:0{n}.0000000Z'
    rows=[dict(kind='start',type='CombatFrame',instance=1,utc=stamp(0),impacts=[dict(source=100,target=200,amount=1)]),
          dict(kind='complete',type='CombatFrame',instance=1,utc=stamp(1)),
          dict(kind='start',type='CombatFrame',instance=2,utc=stamp(3),impacts=[dict(source=100,target=200,amount=4)]),
          dict(kind='complete',type='CombatFrame',instance=2,utc=stamp(4))]
    wire=[dict(direction='outgoing',utc=stamp(2),message=dict(type='ClientMessageType_PerformActionResp',performActionResp=dict(actions=[dict(actionType='ActionType_Cast',instanceId=300)])))]
    assert review(rows,wire,100,200,300)['passed']
    cases=[]
    a=copy.deepcopy(wire);a[0]['utc']=stamp(0);cases.append((rows,a,'cast before first completion'))
    a=copy.deepcopy(wire);a[0]['utc']=stamp(4);cases.append((rows,a,'cast after second strike'))
    a=copy.deepcopy(wire);a[0]['direction']='internal-rules';cases.append((rows,a,'automatic pass cannot prove user casting'))
    cases.append((rows,wire+wire,'duplicate cast'))
    a=copy.deepcopy(wire);a[0]['message']['performActionResp']['actions'][0]['instanceId']=301;cases.append((rows,a,'different spell'))
    a=copy.deepcopy(rows);a[2]['impacts'][0]['amount']=1;cases.append((a,wire,'unchanged second damage'))
    cases.append((rows[:-1],wire,'unfinished second clip'))
    a=copy.deepcopy(rows);a[-1]['instance']=1;cases.append((a,wire,'mismatched completion'))
    for r,w,label in cases:
        try:review(r,w,100,200,300)
        except AssertionError:pass
        else:raise AssertionError('Invalid capture accepted: '+label)
    print('One positive and eight negative first-strike response timeline checks passed')
