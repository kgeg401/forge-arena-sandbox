"""Aggregate executed evidence without turning plans or narrow tests into support.

Every imported run is tied to its authored suite, actual checks, journal and
build/source hashes. Casting coverage, native assets and native controls remain
separate. This tool never writes an admission policy or infers complete rules.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def source_copy(path,digest,archives):
    if path.is_file() and sha(path)==digest:return str(path)
    # Archives preserve repository-relative paths, not a basename-only match.
    if 'ForgeBackend' in path.parts:
        relative=Path(*path.parts[path.parts.index('ForgeBackend'):])
        for root in archives:
            candidate=root/relative
            if candidate.is_file() and sha(candidate)==digest:return str(candidate)
    raise ValueError('Pinned source/input unavailable or changed: '+str(path))


def load_run(path,archives):
    report=read(path)
    if report.get('researchOnly') is not True or report.get('admittedCards')!=0:raise ValueError('Only non-admitting research runs allowed')
    archives=list(archives)+([Path(report['sourceArchive'])] if report.get('sourceArchive') else [])
    identities=report['identities']
    required={'ForgeLandEngine.java','ForgeLandEngine.class','card_batch_case.py','run_card_batches.py','runtime_paths.py','engine_test_client.py','forge.jar','gson.jar'}
    if not required<={Path(p).name for p in identities}:raise ValueError('Missing source/build dependency identities')
    resolved={p:source_copy(Path(p),digest,archives) for p,digest in identities.items()}
    suites=[]
    for original,actual in resolved.items():
        if Path(original).suffix!='.json':continue
        data=read(Path(actual))
        if isinstance(data,dict) and isinstance(data.get('cards'),dict) and isinstance(data.get('cases'),list):suites.append((original,data))
    if len(suites)!=1:raise ValueError('Run needs one pinned suite')
    suite_path,suite=suites[0];definitions={c['id']:c for c in suite['cases']}
    if len(definitions)!=len(suite['cases']):raise ValueError('Duplicate authored case IDs')
    seen=set();rows=[];artifacts={str(path.resolve()):sha(path)}
    for row in report['cases']:
        key=row['id']
        if key in seen or key not in definitions or row['card']!=definitions[key]['card']:raise ValueError('Duplicate, unknown or mislabeled result: '+key)
        seen.add(key);case=definitions[key]
        if not set(case['covers'])<=set(suite['cards'][case['card']]):raise ValueError('Undeclared coverage')
        evidence=Path(row['evidence']) if row.get('evidence') else None
        branch=dict(id=key,card=row['card'],status=row['status'],declaredBranches=case['covers'],execution=report.get('execution','cold'),
                    report=str(path),scope=case.get('scope',suite.get('scope',report['scope'])))
        if row['status']=='passed':
            if evidence is None:raise ValueError('Passing result has no game evidence')
            checks=read(evidence/'checks.json');fixture=read(evidence/'scenario.json')
            if fixture!=dict(scenario='card-family',randomSeed=case.get('seed',7274),**case['fixture']):raise ValueError('Executed fixture differs from authored suite: '+key)
            if not checks or row['checks']!=len(checks) or not all(c.get('passed') is True for c in checks):raise ValueError('Passing result has missing/failed/miscounted assertions: '+key)
            journal=evidence/'engine-journal.jsonl';records=[json.loads(l) for l in journal.read_text(encoding='utf8').splitlines() if l]
            requests=[r for r in records if 'request' in r and 'response' in r]
            if not requests:raise ValueError('No actual input/response journal: '+key)
            final=requests[-1]['response']['state']
            if final.get('fidelityGap') or final.get('researchControls',{}).get('strictHumanCallbacks') is not True:raise ValueError('Passing evidence lacks strict choice guard or has a fidelity gap: '+key)
            for name in ('scenario.json','checks.json','engine-journal.jsonl'):
                artifact=evidence/name;artifacts[str(artifact)]=sha(artifact)
            branch.update(assertions=len(checks),journalRecords=len(records),journalSha256=sha(journal),evidence=str(evidence))
        else:branch.update(category=row.get('category'),error=row.get('error'),fidelityGap=row.get('fidelityGap'))
        rows.append(branch)
    expected_status='passed' if len(seen)==len(definitions) and all(r['status']=='passed' for r in rows) else 'needs-attention'
    if report['status']!=expected_status:raise ValueError('Report status disagrees with actual case results')
    if report['summary']['completed']!=len(rows) or report['summary']['totalCases']!=len(definitions) or report['summary']['assertions']!=sum(r.get('checks',0) for r in report['cases']):raise ValueError('Summary totals disagree with case records')
    return dict(path=str(path),sha256=sha(path),status=expected_status,cases=rows,suite=str(suite_path),sourceCopies=resolved,artifacts=artifacts)


def load_matches(path):
    """Verify sealed input-only full games, without closing interaction gates."""
    report=read(path)
    if report.get('schema')!=2 or report.get('researchOnly') is not True or report.get('newAdmissions')!=0 or report.get('passed') is not True or report.get('missingSeatCoverage'):
        raise ValueError('Complete-match evidence needs a passed, non-admitting schema-2 seal')
    identities=report['identities'];copies=report['sourceCopies']
    required={'ForgeLandEngine.java','ForgeLandEngine.class','forge.jar','gson.jar','verify_catalogue_full_matches.py','engine_test_client.py','preparation.json'}
    if not required<={Path(p).name for p in identities}:raise ValueError('Missing full-match source/build identities')
    for original,digest in identities.items():
        source=Path(original)
        if source.is_file() and sha(source)==digest:continue
        if original not in copies or sha(Path(copies[original]))!=digest:raise ValueError('Changed complete-match dependency: '+original)
    inputs=read(path.parent/'inputs.json')
    if inputs.get('schema')!=2 or inputs['identities']!=identities or inputs['sourceCopies']!=copies:raise ValueError('Full-match input seal differs')
    # Resolve the exact proposal input; no unknown card can acquire match credit.
    proposals=[]
    for original,digest in identities.items():
        if Path(original).suffix!='.json':continue
        actual=Path(original) if Path(original).is_file() and sha(Path(original))==digest else Path(copies[original])
        value=read(actual)
        if isinstance(value,dict) and isinstance(value.get('proposals'),list):proposals.append(value)
    if not proposals or any(p['provenance']!=proposals[0]['provenance'] for p in proposals):raise ValueError('Compatible source proposal inputs required')
    specs={}
    for proposal_file in proposals:
        for p in proposal_file['proposals']:
            if p['name'] in specs:raise ValueError('Duplicate full-match source proposal')
            specs[p['name']]=p
    rows=[];totals=Counter();seeds=set();games=set();artifacts={str(path.resolve()):sha(path),str(path.parent/'inputs.json'):sha(path.parent/'inputs.json')}
    declared_names=set(report['requiredCards'])
    if len(declared_names)!=len(report['requiredCards']) or not declared_names or declared_names!=set(report['resolved']) or not declared_names<=specs.keys():raise ValueError('Unknown, incomplete or duplicate required-resolution coverage')
    if not 1<=len(report['matches'])<=12:raise ValueError('Outside bounded full-game count')
    for game in report['matches']:
        evidence=Path(game['evidence']).resolve()
        if game['seed'] in seeds or evidence in games:raise ValueError('Duplicate complete game')
        seeds.add(game['seed']);games.add(evidence)
        expected_artifacts={str(evidence/n) for n in ('scenario.json','checks.json','engine-journal.jsonl')}
        if set(game['artifacts'])!=expected_artifacts:raise ValueError('Missing game artifacts')
        for filename,digest in game['artifacts'].items():
            if sha(Path(filename))!=digest:raise ValueError('Changed full-game artifact')
            artifacts[filename]=digest
        scenario=read(evidence/'scenario.json');checks=read(evidence/'checks.json')
        if set(scenario)!={'scenario','randomSeed','localDeck','opponentDeck','startingPlayerPolicy'} or scenario['scenario']!='custom-duel' or scenario['randomSeed']!=game['seed'] or scenario['startingPlayerPolicy']!='local-first':raise ValueError('Not the declared normally shuffled game')
        for key in ('localDeck','opponentDeck'):
            deck=scenario[key]
            if identities.get(deck['source'])!=deck['sha256']:raise ValueError('Played deck has no matching input seal')
        if not checks or game['checks']!=len(checks) or not all(c.get('passed') is True for c in checks):raise ValueError('Missing, failed or miscounted full-game checks')
        records=[json.loads(line) for line in (evidence/'engine-journal.jsonl').read_text(encoding='utf8').splitlines() if line]
        exchanges=[r for r in records if 'request' in r and 'response' in r]
        if not exchanges:raise ValueError('No executed full-game inputs')
        states=[r['response']['state'] for r in exchanges];final=states[-1];objects={}
        if not final['gameOver'] or final.get('fidelityGap') or final.get('researchControls',{}).get('strictHumanCallbacks') is not True or final['winnerSeat'] not in (0,1,2) or final['winnerSeat']!=game['winner'] or final['lossReason']!=game['reason'] or final['turn']!=game['turn'] or any(final[k] for k in ('legalLands','legalCasts','legalMana','canPass')):raise ValueError('Invalid or mislabeled terminal game')
        allowed={'pass_priority','play_land','cast_spell','select_attackers','submit_attackers','select_blockers','submit_blockers','select_targets','submit_targets','submit_assign_damage','submit_order_cards','submit_mulligan','submit_mulligan_bottom','submit_starting_player','submit_discard'}
        for exchange in exchanges:
            request=exchange['request']
            if request['op'] not in allowed or request['session']!=final['session'] or request['seat']!=1 or exchange['response'].get('accepted') is not True:raise ValueError('Unexpected or rejected input in full game')
        for state in states:
            if state.get('fidelityGap') or state.get('researchControls',{}).get('strictHumanCallbacks') is not True or any('name' in c for c in state.get('hidden',[])):raise ValueError('Full game left strict control or exposed hidden identities')
            for zone in ('hand','battlefield','graveyard','exile','command','stack'):
                for card in state.get(zone,[]):objects[card['forgeId']]=card
        resolved=[];fizzled=[]
        for event in final['researchTrace']:
            if event['kind']!='spell-resolved' or event['sourceForgeId'] not in objects:continue
            card=objects[event['sourceForgeId']]
            if card['name'] not in declared_names:continue
            if event['hasFizzled'] is True:
                fizzled.append(dict(name=card['name'],seat=card['owner'],forgeId=card['forgeId']));continue
            if event['hasFizzled'] is not False:raise ValueError('Invalid fizzle status')
            resolved.append(dict(name=card['name'],seat=card['owner'],forgeId=card['forgeId']))
        if resolved!=game['resolved']:raise ValueError('Claimed resolutions differ from actual event trace')
        if fizzled!=game.get('fizzled',[]):raise ValueError('Claimed fizzles differ from actual event trace')
        for card in resolved:
            totals[(card['name'],card['seat'])]+=1
            rows.append(dict(**card,seed=game['seed'],evidence=str(evidence),report=str(path),scope='Actually resolved during this strict input-only complete shuffled game; not complete interaction coverage.'))
    expected={n:{str(seat):totals[(n,seat)] for seat in (1,2) if totals[(n,seat)]} for n in declared_names}
    if not rows or expected!=report['resolved'] or any(not totals[(n,s)] for n in declared_names for s in (1,2)):raise ValueError('Aggregate resolution/seat totals differ')
    return dict(path=str(path),sha256=sha(path),matches=len(games),gameEvidence=sorted(str(p) for p in games),rows=rows,artifacts=artifacts,proposalProvenance=proposals[0]['provenance'])


def build(a):
    if a.output.exists():raise ValueError('Preserve old evidence ledgers; choose a fresh output')
    catalogue=read(a.catalogue);baseline=read(a.baseline_policy)
    if baseline.get('researchOnly') or catalogue['provenance']['policySha256']!=sha(a.baseline_policy):raise ValueError('Catalogue baseline mismatch')
    proposals=read(a.proposals)
    if proposals['provenance']!=catalogue['provenance']:raise ValueError('Proposal catalogue provenance mismatch')
    rows={c['name']:dict(name=c['name'],baselineAdmission=c['admission'],construction=c['construction'],minimumRequirements=c['requirements'],
        sourceQualifiedProposal=None,engineCases=[],nativeAssets=[],nativeControls=[],completeMatches=[],
        admissionDecision='unchanged-existing-bounded' if c['name'] in baseline['verifiedNames'] else 'not-admitted',
        remainingReview='All required capabilities need explicit gate review; passing named branches never closes untested interactions.') for c in catalogue['cards']}
    for proposal in proposals['proposals']:
        row=rows[proposal['name']]
        row['sourceQualifiedProposal']=dict(template=proposal['template'],printing=proposal['printing'],remainingGates=proposal['remainingGates'])
    sources=[];artifacts={str(p.resolve()):sha(p) for p in (a.catalogue,a.proposals,a.baseline_policy)};digests=set()
    for path in getattr(a,'additional_proposals',[]):
        extra=read(path);qualifier=Path(source_copy(Path(extra['qualifierSource']),extra['qualifierSha256'],a.source_archive))
        if extra.get('schema')!=1 or extra.get('newAdmissions')!=0 or extra.get('executedCases')!=0 or extra['provenance']!=proposals['provenance']:raise ValueError('Additional source proposal provenance differs')
        artifacts[str(path.resolve())]=sha(path);artifacts[str(qualifier)]=sha(qualifier)
        for proposal in extra['proposals']:
            row=rows[proposal['name']]
            if row['sourceQualifiedProposal'] or proposal['sourceScriptSha256']!=next(c['sourceScriptSha256'] for c in catalogue['cards'] if c['name']==proposal['name']) or proposal['printing'] not in next(c['arenaGrpIds'] for c in catalogue['cards'] if c['name']==proposal['name']):raise ValueError('Duplicate or mismatched additional qualification')
            row['sourceQualifiedProposal']=dict(template=proposal['template'],printing=proposal['printing'],remainingGates=proposal['remainingGates'],report=str(path),qualifierSha256=extra['qualifierSha256'])
    for path in a.run:
        digest=sha(path)
        if digest in digests:raise ValueError('Duplicate run would inflate coverage')
        digests.add(digest);run=load_run(path,a.source_archive);sources.append({k:v for k,v in run.items() if k not in ('cases','artifacts')});artifacts.update(run['artifacts'])
        for case in run['cases']:
            if case['card'] not in rows:raise ValueError('Run contains non-catalogue card')
            rows[case['card']]['engineCases'].append(case)
    for path in a.native_assets:
        data=read(path);artifacts[str(path.resolve())]=sha(path)
        if data['failures'] or data['passed']!=data['cards'] or len(data['cardsChecked'])!=data['cards']:raise ValueError('Native asset report incomplete')
        for card in data['cardsChecked']:
            if card.get('passed') is not True or card['name'] not in rows:raise ValueError('Failed/unknown native asset')
            rows[card['name']]['nativeAssets'].append(dict(report=str(path),printing=card['grpId'],expectedArt=card['expectedArt'],scope=data['scope']))
    for path in a.native_controls:
        data=read(path);artifacts[str(path.resolve())]=sha(path)
        if not isinstance(data.get('cards'),list) or not data['cards'] or data.get('passed',True) is not True or data['checks']!=len(data['results']) or not all(c.get('passed') is True for c in data['results']):raise ValueError('Native control report incomplete')
        for name in data['cards']:
            if name not in rows:raise ValueError('Unknown native control card')
            rows[name]['nativeControls'].append(dict(report=str(path),scope=data['scope']))
    matches=[];seen_games=set()
    for path in getattr(a,'complete_matches',[]):
        digest=sha(path)
        if digest in digests:raise ValueError('Duplicate match report would inflate coverage')
        digests.add(digest);match=load_matches(path)
        if match['proposalProvenance']!=proposals['provenance']:raise ValueError('Full-game proposals differ from catalogue provenance')
        evidence=set(match['gameEvidence'])
        if seen_games&evidence:raise ValueError('Same game would be counted in multiple reports')
        seen_games.update(evidence);artifacts.update(match['artifacts']);matches.append({k:v for k,v in match.items() if k not in ('rows','artifacts')})
        for row in match['rows']:
            if row['name'] not in rows:raise ValueError('Non-catalogue match card')
            rows[row['name']]['completeMatches'].append(row)
    counts=Counter()
    for row in rows.values():
        for stage,key in [('sourceQualified','sourceQualifiedProposal'),('engineExercised','engineCases'),('nativeAssetTested','nativeAssets'),('nativeControlTested','nativeControls'),('fullMatchObserved','completeMatches')]:
            if row[key]:counts[stage]+=1
        passed=[c for c in row['engineCases'] if c['status']=='passed']
        if passed:counts['engineTested']+=1
        row['passingDeclaredBranches']=sorted({b for c in passed for b in c['declaredBranches']})
        row['executionModes']=sorted({c['execution'] for c in passed})
        row['newAdmission']=False
    summary=dict(arenaNames=len(rows),existingBoundedAdmissions=len(baseline['verifiedNames']),newAdmissions=0,**counts,
        executedCases=sum(len(r['engineCases']) for r in rows.values()),uniqueCardCases=len({(r['name'],c['id']) for r in rows.values() for c in r['engineCases']}),
        assertions=sum(c.get('assertions',0) for r in rows.values() for c in r['engineCases']),
        completeGames=sum(m['matches'] for m in matches),fullMatchGatesClosedByThisTool=0)
    result=dict(schema=1,summary=summary,runs=sources,matches=matches,artifacts=artifacts,cards=list(rows.values()),
        scope='Evidence inventory only. No automatic capability closure, support/admission promotion, ownership/release/format assertion, or complete interaction claim.')
    a.output.mkdir(parents=True);(a.output/'card-evidence-ledger.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf8')
    lines=['# Catalogue evidence checkpoint','',f"{summary['arenaNames']:,} Arena names; {summary['engineTested']} names with executed branches; {summary['newAdmissions']} new admissions.",'',
        'These stages describe different evidence. A cast does not prove combat, a rendered model does not prove a working card, and none of these totals automatically grants support.','',
        '| Stage | Card names |','| --- | ---: |']
    lines += ['| '+label+' | '+str(summary.get(key,0))+' |' for key,label in [('sourceQualified','Source-qualified proposal'),('engineTested','Executed engine scenarios'),('nativeAssetTested','Original native model/art'),('nativeControlTested','Original native controls'),('fullMatchObserved','Actual resolutions in complete games'),('existingBoundedAdmissions','Existing bounded admission')]]
    lines += ['','Every card retains its minimum requirements, actual branch records, source hashes and remaining review. Complete-match observations are verified against sealed game inputs, checks and event journals; they do not close untested interactions.']
    (a.output/'SUMMARY.md').write_text('\n'.join(lines)+'\n',encoding='utf8');print(json.dumps(dict(output=str(a.output),**summary)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('catalogue','proposals','baseline-policy','output'):p.add_argument('--'+key,type=Path,required=True)
    for key in ('run','native-assets','native-controls','source-archive','complete-matches','additional-proposals'):p.add_argument('--'+key,type=Path,action='append',default=[])
    build(p.parse_args())
