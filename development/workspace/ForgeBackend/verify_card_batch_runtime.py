"""Exercise research fixture isolation and existing rules using the real backend.

Run only after the batch runner releases its dedicated runtime.
"""
import json
import os
import subprocess
import time
from engine_test_client import Engine
from runtime_paths import ROOT, JAVA_HOME
from headless_resources import java_options, process_flags


def run():
    results=[]
    cases=[
        ('oversized-initial-graveyard','card-family',dict(fixtureHand=['Revitalize'],fixtureLands=['Plains']*3,fixtureGraveyard=['Plains']*41),'Initial zone fixture exceeds its research bound'),
        ('unmapped-initial-graveyard','card-family',dict(fixtureHand=['Revitalize'],fixtureLands=['Plains']*3,fixtureGraveyard=['Not a source mapped card']),'Unmapped initial research card'),
        ('nonresearch-scenario-zone-override','starter',dict(fixtureGraveyard=['Plains']),'Initial zone fixtures require an explicit research-only card-family scenario'),
        ('noncreature-in-battlefield-override','card-family',dict(fixtureHand=['Revitalize'],fixtureLands=['Plains']*3,fixtureBattlefield=['Divination']),'Initial research battlefield override supports creatures only')]
    for label,scenario,settings,expected in cases:
        start=time.monotonic()
        try:
            e=Engine(scenario,**settings)
        except RuntimeError as error:
            assert expected in str(error),(label,str(error))
            assert time.monotonic()-start<30,'Invalid fixture did not exit promptly'
            results.append(dict(case=label,passed=True,expectedError=expected,seconds=round(time.monotonic()-start,3)))
        else:
            e.close();raise AssertionError(label+' unexpectedly started')
    # The actual executable must reject fixture use under production metadata,
    # even if a caller bypasses the Python runner's research-policy check.
    scratch=ROOT.parent/'production-manifest-negative';(scratch/'native-lab').mkdir(parents=True,exist_ok=False)
    runtime=scratch/'forge-runtime';runtime.mkdir()
    ipc=scratch/'ipc';ipc.mkdir();(ipc/'scenario.json').write_text(json.dumps(dict(scenario='card-family',fixtureHand=['Revitalize'],fixtureLands=['Plains']*2)))
    manifest=json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text(encoding='utf8'));manifest['researchOnly']=False
    (scratch/'native-lab/bridge-card-manifest.json').write_text(json.dumps(manifest),encoding='utf8')
    cp=os.pathsep.join(map(str,[ROOT/'build/ForgeBackend/classes',ROOT/'forge-runtime/forge.jar',ROOT/'forge-runtime/gson.jar']))
    reply=subprocess.run([str(JAVA_HOME/'bin/java.exe'),*java_options(),'-cp',cp,'ForgeLandEngine',str(runtime),str(ipc)],capture_output=True,text=True,encoding='utf8',creationflags=process_flags(),timeout=15)
    (scratch/'engine.log').write_text(reply.stdout+reply.stderr,encoding='utf8')
    assert reply.returncode!=0 and 'Card-family fixtures require an explicit research-only manifest' in reply.stderr
    results.append(dict(case='production-manifest-rejects-research-scenario',passed=True,evidence=str(scratch)))
    e=Engine('card-family',fixtureHand=['Revitalize'],fixtureLands=['Plains']*2)
    try:
        identity=next(c['forgeId'] for c in e.state['hand'] if c['name']=='Revitalize')
        assert e.send('cast_spell',identity)['accepted']
        e.pass_or_decision()
        assert e.state['life']==23 and len(e.state['hand'])==1 and not e.state['fidelityGap']
        results.append(dict(case='valid-case-after-rejected-fixtures',passed=True,evidence=str(e.ipc)))
    finally:
        e.close()
    out=ROOT.parent/'fixture-boundaries.json'
    out.write_text(json.dumps(dict(checks=len(results),cases=results),indent=2),encoding='utf8')
    print(json.dumps(dict(checks=len(results),report=str(out))),flush=True)


if __name__=='__main__':
    from run_background_validation import lower_resources
    lower_resources()
    locks=ROOT/'research/background-runs';locks.mkdir(parents=True,exist_ok=True)
    with (locks/'validation.lock').open('a+b') as lease:
        lease.seek(0);lease.write(b'1');lease.flush();lease.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(lease.fileno(),msvcrt.LK_NBLCK,1)
        run()
