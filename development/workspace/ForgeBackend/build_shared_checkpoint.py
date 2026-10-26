"""Summarize executed shared-interface evidence without promoting card admission.

Failed campaigns are retained; explicit corrected reports are listed alongside
them. Counts require actual per-game checks and native completion receipts.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=a.evidence_root.resolve();repo=Path(__file__).resolve().parents[1];checks=[];artifacts={};missing=[];native={}
    def check(label,value):checks.append(dict(check=label,passed=bool(value)))
    def load(relative):
        path=root/relative
        if not path.is_file():missing.append(str(path));return None
        artifacts[str(path)]=sha(path);return read(path)
    def game(evidence,expected=None,allow_empty=False):
        folder=Path(evidence).resolve()
        check('Evidence is inside the private checkpoint root',folder.is_relative_to(root))
        actual=load(str(folder/'checks.json'))
        if actual is None:return 0
        check('Every authored per-game assertion passed',all(c.get('passed') is True for c in actual) and (bool(actual) or allow_empty))
        if expected is not None:check('Reported assertion count matches saved per-game checks',len(actual)==expected)
        completion=load(str(folder/'native-worker/completed.json'))
        if completion is not None:
            native[str(folder)]=completion
            check('Native session processed actual rules updates',completion['updates']>0)
        return len(actual)
    suites=[]
    paths=[('shared','final-r22-decisions/shared/report.json'),('matrix','final-matrix-consolidated.json')]
    paths += [(key,'final-r22-decisions/'+key+'/report.json') for key in ('attachments','colors','discard','keywords','characteristics','ability_choices')]
    paths.append(('exile_order','exile-order-r23-corrected/report.json'))
    paths.append(('protection-attachments','cross-family-protection-attachments-r23-corrected/report.json'))
    for name,path in paths:
        data=load(path)
        if data is None:continue
        for field in ('nativeBinarySha256','nativeBinaries','pinnedArtifacts'):
            for value,digest in (data.get(field) or {}).items():
                target=Path(value)
                if not target.is_absolute():
                    if target.parent!=Path('.'):raise ValueError('Unresolved relative native artifact path')
                    target=Path(read(root/'choices-r23-copy/runtime-config.json')['arenaInstall'])/'MTGA_Data/Managed'/target
                check(name+' pinned artifact remains unchanged: '+target.name,target.is_file() and sha(target)==digest)
        for provenance in data.get('provenance',[]):
            target=Path(provenance['path']);check(name+' consolidated provenance remains unchanged',target.is_file() and sha(target)==provenance['sha256'])
        check(name+' suite passed',data.get('passed') is True);rows=data.get('cases',[]);total=0;seen=set()
        for row in rows:
            key=row.get('id');check(name+' case identity is unique',key not in seen);seen.add(key)
            check(name+' authored scenario passed',row.get('passed') is True)
            total+=game(row['evidence'],row.get('checks'))
        suites.append(dict(suite=name,scenarios=len(rows),checks=total,report=str(root/path)))
    decisions=load('final-r22-decisions/report.json')
    if decisions:check('Decision campaign has only explicitly corrected startup/exile oracle failures',{r['id'] for r in decisions['results'] if r['exitCode']!=0}=={'contracts','exile_order'} and len(decisions['results'])==decisions['plannedJobs'] and not decisions['timedOut'] and not decisions['artifactDrift'])
    baselines=[]
    for group in ('normal','emry'):
        data=load('final-r22-'+group+'/report.json')
        if data is None:continue
        expected_failures={'opening'} if group=='normal' else {'emry_target_invalidation','paradox_engine'}
        failed={r['id'] for r in data['results'] if r['exitCode']!=0}
        check(group+' campaign has only the retained diagnosed failures',failed==expected_failures and len(data['results'])==data['plannedJobs'] and not data['timedOut'] and not data['artifactDrift'])
        corrections={'opening':'opening-r23-corrected','emry_target_invalidation':'emry-invalidation-r23-corrected','paradox_engine':'paradox-r23-corrected'}
        for job in data['results']:
            if job['id']=='terminal-direct':continue
            relative=(corrections[job['id']] if job['id'] in failed else 'final-r22-'+group+'/'+job['id'])+'/report.json'
            report=load(relative)
            if report is None:continue
            check(group+' '+job['id']+' selected regression passed',report.get('passed') is True)
            total=0
            for session in report.get('sessions',[]):
                check('Rules and native test processes exited',session['javaExited'] and session['nativeExited'])
                total+=game(session['evidence'],len(session['checks']),allow_empty=job['id']=='emry_commander_bounce' and not session['checks'])
            baselines.append(dict(group=group,id=job['id'],report=str(root/relative),checks=total,corrected=job['id'] in failed))
    for path in ('parallel-first-start-r23/report.json','owned-timeout-cleanup/report.json','profile-preparation-boundaries/report.json','final-r22-decisions/research_payment_boundary/report.json','final-r22-decisions/unsupported_choice/report.json'):
        data=load(path)
        if data is not None:check(path+' passed',data.get('passed') is True)
    parallel=load('parallel-first-start-r23/report.json')
    if parallel:
        for row in parallel['results']:
            data=load(str(Path(row['report'])))
            if data is not None:game(data['evidence'],len(data['checks']))
    initial=load('checkpoint.json');installed={}
    if initial:
        install=Path(initial['installedRoot']);active=read(install/'active-version.json');manifest=install/'versions'/active['version']/'release-manifest.json'
        installed=dict(version=active['version'],releaseManifestSha256=sha(manifest),path=str(install))
        check('Installed version and release manifest are unchanged',installed['version']==initial['installedVersion'] and installed['releaseManifestSha256']==initial['installedManifestSha256'])
    policy=repo/'ForgeBackend/bridge_support.json';admission=read(policy)
    check('Production policy matches the starting policy hash',sha(policy)=='5752392f087eede8e69c546fe2fc31dfc1b2243235c5c61bfcb34a86207d67b5')
    check('Production admitted names remain 370',len(admission['verifiedNames'])==370)
    preparations={}
    for epoch in ('r22','r23'):
        prep=load('choices-'+epoch+'-copy/preparation.json')
        if prep is None:continue
        rt=Path(prep['config']).parent/'runtime';classes=rt/'build/ForgeBackend/classes'
        check(epoch+' prepared Java source matches the checkout',sha(repo/'ForgeBackend/ForgeLandEngine.java')==prep['sourceSha256'])
        check(epoch+' actual compiled classes match the preparation receipt',all(sha(classes/name)==digest for name,digest in {**prep['classes'],**prep['workerClasses']}.items()))
        check(epoch+' actual Forge libraries match the preparation receipt',sha(rt/'forge-runtime/forge.jar')==prep['forgeJarSha256'] and sha(rt/'forge-runtime/gson.jar')==prep['gsonJarSha256'])
        check(epoch+' is a non-admitting private runtime',prep['researchOnly'] and prep['productionAdmissions']==0 and not (rt/'native-lab/MTGA.exe').exists())
        preparations[epoch]=dict(sourceSha256=prep['sourceSha256'],preparationSha256=sha(Path(prep['config']).parent/'preparation.json'))
    audit=load('shared-interface-catalogue-audit-expanded.json')
    inheritance=load('additional-inheritance-audit.json')
    result=dict(schema=1,passed=not missing and all(c['passed'] for c in checks),generatedUtc=datetime.now(timezone.utc).isoformat(),
                scope=__doc__,checkpointDeadlineUtc='2026-10-23T01:29:13Z',headlessOnly=True,published=False,renderedAcceptancePending=True,
                productionAdmissionsAdded=0,productionAdmittedNames=len(admission['verifiedNames']),productionPolicySha256=sha(policy),installed=installed,
                authoredInterfaceScenarios=sum(s['scenarios'] for s in suites),authoredInterfaceChecks=sum(s['checks'] for s in suites),suites=suites,baselineRegressions=baselines,
                nativeSessions=len(native),nativeUpdates=sum(n['updates'] for n in native.values()),nativeWorkerRequests=sum(n['requests'] for n in native.values()),
                preparations=preparations,staticCatalogue=dict(arenaNames=audit['arenaNames'],uniqueScriptCandidates=audit['uniquelyMappedNames'],namesMentioningAuditedFamilies=audit['namesMentioningTheseInterfaces'],exactModalBindings=audit['exactNativeModalBindingNames'],notGameplayEvidence=True) if audit else None,
                retainedCorrections=[dict(failed='final-r22-decisions/contracts.log',corrected='parallel-first-start-r23/report.json',cause='Concurrent fresh Forge profile initialization; directories now prepared before parallel startup'),dict(failed='final-r22-normal/opening/report.json',corrected='opening-r23-corrected/report.json',cause='Same first-start profile race'),dict(failed='final-r22-emry/emry_target_invalidation/report.json',corrected='emry-invalidation-r23-corrected/report.json',cause='Oracle must explicitly answer the added exile-order prompt before checking resolution'),dict(failed='final-r22-emry/paradox_engine/report.json',corrected='paradox-r23-corrected/report.json',cause='Old test supplied obsolete defenderId instead of targetSeat; rules oracles retained')],
                additionalControllerInheritanceAudit=inheritance,completeHumanControllerParity=False,
                remainingGaps=['Rendered original UI/input/assets/animation acceptance','Additional inherited human-controller entry points and identity flags beyond the named choice guard','Competing replacement/reducer choices and optional/targeted/simultaneous trigger ordering','Broader payment choices including X, hybrid, snow and alternate costs','Type/card-name choices, copy/face/token semantics and Arena digital rules','Mixed-mechanic/card-specific evidence and release admission'],
                missingReports=missing,checks=checks,artifacts=artifacts,localCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
    result['retainedCorrections'].extend([
        dict(failed='final-r22-matrix/matrix/report.json',corrected='final-matrix-consolidated.json',cause='One first-start directory race; identical authored input rerun, pinned source/native binaries checked before consolidation'),
        dict(failed='final-r22-decisions/exile_order/report.json',corrected='exile-order-r23-corrected/report.json',cause='The bot owns ordering of its own graveyard. Local permutations remain exact; bot cases assert identity conservation without unauthorized human input'),
        dict(failed='cross-family-protection-attachments-r23/report.json',corrected='cross-family-protection-attachments-r23-corrected/report.json',cause='Authored fixture now answers the real Aura endpoint selection and uses the source Bird subtype; protection/SBA/native-model assertions retained'),
        dict(failed='final-r20-normal/duel-161803/report.json',corrected='final-r22-normal/duel-161803/report.json',cause='Test bot now makes actual London mulligan decisions; casting and outcome assertions retained'),
        dict(failed='final-r21-emry/emry_mechanics/report.json',corrected='final-r22-emry/emry_mechanics/report.json',cause='Native driver rejects coerced integer identities before invoking original typed handlers')])
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:result[k] for k in ('passed','authoredInterfaceScenarios','authoredInterfaceChecks','nativeSessions','nativeUpdates','productionAdmissionsAdded','missingReports')}));raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
