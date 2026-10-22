"""Bounded normally shuffled pump match through original native controls.

Explicit test policies: keep, all legal attacks, no blocks, lowest-ID legal
friendly pump target (otherwise legal enemy), original automatic damage and
original default graveyard order. No Forge requests or intermediate injection.
"""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import re
import shutil
import time
import native_ui_client as native
from native_client_ui import capture
from runtime_paths import ROOT


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seconds', type=int, default=600)
    p.add_argument('--resume', action='store_true', help='Continue observing the same live match without repeating accepted inputs')
    p.add_argument('--expected-native-pid',type=int,required=True)
    p.add_argument('--proposals',type=Path,required=True)
    p.add_argument('--verified-policy',type=Path,help='Explicit installed production policy; otherwise research-only validation')
    p.add_argument('--additional-proposals',type=Path,action='append',default=[])
    p.add_argument('--require-burn',action='store_true',help='Also require an observed local fixed creature-damage spell')
    a = p.parse_args()
    if (a.additional_proposals or a.require_burn) and not a.verified_policy:
        raise ValueError('Additional burn integration requires an explicit installed production policy')
    if (a.output.exists() and not a.resume) or not 30 <= a.seconds <= 900:
        raise ValueError('Select a new output folder and a bounded 30–900 second run')
    a.output.mkdir(parents=True, exist_ok=a.resume)
    lab = ROOT/'native-lab'
    launch=json.loads((lab/'launch-receipt.json').read_text());manifest=json.loads((lab/'bridge-card-manifest.json').read_text())
    if launch['pid']!=a.expected_native_pid or not launch.get('appContainer') or launch.get('capabilityCount')!=0:raise ValueError('Expected independent zero-network native process')
    if a.verified_policy:
        import hashlib
        policy=json.loads(a.verified_policy.read_text(encoding='utf-8-sig'))
        if policy.get('researchOnly') or manifest.get('researchOnly') or manifest['policySha256']!=hashlib.sha256(a.verified_policy.read_bytes()).hexdigest():raise ValueError('Installed production policy differs')
        if {n for n,c in manifest['cards'].items() if c.get('admitted')}!=set(policy['verifiedNames']):raise ValueError('Installed admission differs from verified policy')
        if Path(launch['executable']).resolve()!=lab/'MTGA.exe':raise ValueError('Wrong configured installed client')
    elif not manifest.get('researchOnly'):raise ValueError('Research manifest required without explicit production policy')
    proposals=json.loads(a.proposals.read_text(encoding='utf8'));specs={v['name']:v for v in proposals['proposals']}
    for path in a.additional_proposals:
        extra=json.loads(path.read_text(encoding='utf8'))
        if extra['provenance']!=proposals['provenance'] or any(p['name'] in specs or p['template']!='fixed-creature-damage-v1' for p in extra['proposals']):raise ValueError('Only compatible, explicit fixed creature-damage proposals may be added')
        specs.update({p['name']:p for p in extra['proposals']})
    checks = []
    actions = 0
    stale_observations = 0
    deferred_snapshots = 0
    seen_native_damage = False

    def state():
        return json.loads((lab/'forge-ipc/state.json').read_text())

    def check(label, passed):
        checks.append(dict(check=label, passed=bool(passed)))
        assert passed, label

    s = state()
    session = s['session']
    if a.resume:
        initial = json.loads((a.output/'initial-state.json').read_text())
        check('Resume keeps the exact live session', initial['session'] == session)
        actions = len(re.findall(r'"requestId"\s*:', (a.output/'native-actions.log').read_text()))
        initial_turn = initial['turn']
        seen_native_damage = any('assignDamageResp' in line for line in (lab/'forge-ipc/native-wire.jsonl').read_text().splitlines())
    else:
        initial_turn = s['turn']
        (a.output/'initial-state.json').write_text(json.dumps(s, indent=2))
    check('Actual normally shuffled custom match', s['scenario'] == 'custom-duel' and not any(k.startswith('fixture') for k in json.loads((lab/'forge-ipc/scenario.json').read_text())))
    deck_names={c['name'] for c in s['localDeck']['cards']};tested=deck_names&specs.keys()
    check('Starting deck includes source-qualified supported target families',bool(tested) and all(specs[n]['template'] in ('fixed-target-pump-v1','fixed-creature-damage-v1') and manifest['cards'][n]['grpId']==specs[n]['printing'] for n in tested))
    known={}
    def observe_cards(value):
        for zone in ('hand','battlefield','graveyard','exile','command','stack'):
            for card in value.get(zone,[]):known[card['forgeId']]=card
    observe_cards(s)
    if not a.resume:
        capture(a.output/'opening.png')
    deadline = time.monotonic()+a.seconds
    with (a.output/'native-actions.log').open('a' if a.resume else 'w', encoding='utf8') as log, redirect_stdout(log):
        while time.monotonic() < deadline:
            s = state()
            check('Same native match session, no fidelity gap', s['session'] == session and not s['fidelityGap'])
            if s['gameOver']:
                break
            try:
                observed = native.inspect()
                # Normal clients automatically yield empty priority windows.
                # Read Forge after observing the native screen, then require
                # agreement before choosing an operation from that snapshot.
                s = state()
                if s['gameOver']:
                    break
                kind = (s.get('decision') or {}).get('kind')
                observe_cards(s)
                expected = {'attackers':'DeclareAttackersWorkflow', 'blockers':'DeclareBlockersWorkflow', 'assign_damage':'AssignDamageWorkflow','targets':'SelectTargetsWorkflow','order_cards':'OrderWorkflow'}
                if (kind in expected and observed['workflow'] != expected[kind]) or (not kind and observed['workflow'] != 'ActionsAvailableWorkflow'):
                    deferred_snapshots += 1
                    time.sleep(.1)
                    continue
                buttons = [b for b in observed['buttons'] if b['enabled']]
                primary = [b for b in buttons if b['tag'] == 'Primary']
                advance = [b for b in buttons if b['text'] in ('Pass', 'Resolve')]
                if kind == 'starting_player':
                    native.action('play', observed=observed)
                elif kind == 'mulligan':
                    native.action('keep', observed=observed)
                elif kind == 'attackers':
                    if any(b['text'] == 'All Attack' for b in buttons):
                        native.action('button', 'All Attack', observed=observed)
                    elif len(primary) == 1:
                        native.action('button', primary[0]['text'], observed=observed)
                    elif any(b['text'] == 'No Attacks' for b in buttons):
                        native.action('button', 'No Attacks', observed=observed)
                    else:
                        raise AssertionError(observed)
                elif kind == 'blockers':
                    no_blocks = [b for b in buttons if b['text'] == 'No Blocks']
                    if len(no_blocks) != 1:
                        raise AssertionError(observed)
                    native.action('button', 'No Blocks', observed=observed)
                elif kind == 'assign_damage':
                    capture(a.output/'damage-assignment.png')
                    done = [b for b in observed['uiButtons'] if b['enabled'] and b['key'] == 'DuelScene/KeywordSelection/KeywordSelection_Done']
                    check('Real original damage allocation browser', observed['workflow'] == 'AssignDamageWorkflow' and len(done) == 1)
                    native.action('ui', done[0]['key'], observed=observed)
                    seen_native_damage = True
                elif kind == 'targets':
                    decision=s['decision'];source=known.get(decision['sourceForgeId'],{})
                    check('Real target decision belongs to a qualified creature-target family',source.get('name') in tested and decision['minTargets']==decision['maxTargets']==1)
                    selected=decision['assignments']
                    if not selected:
                        options=decision['options'];visible={c['forgeId']:c for c in s['battlefield']}
                        check('Every legal target is a visible battlefield creature',bool(options) and all(v['forgeId'] in visible for v in options))
                        preferred=1 if specs[source['name']]['template']=='fixed-target-pump-v1' else 2
                        target=min(options,key=lambda v:(visible[v['forgeId']]['owner']!=preferred,v['forgeId']))
                        native.card(target['forgeId'])
                    else:
                        submit=[b for b in buttons if b['text'].startswith('Submit')]
                        check('One original target confirmation',len(submit)==1);native.action('button',submit[0]['text'],observed=observed)
                elif kind == 'order_cards':
                    done=[b for b in buttons if b['text'].casefold() in ('done','submit')]
                    if len(done)==1:native.action('button',done[0]['text'],observed=observed)
                    else:
                        done=[b for b in observed['uiButtons'] if b['enabled'] and (b.get('key') or '').casefold().endswith(('_done','/done'))]
                        check('Original default graveyard order is explicitly confirmed',len(done)==1);native.action('ui',done[0]['key'],observed=observed)
                elif kind in ('discard', 'mulligan_bottom'):
                    decision = s['decision']
                    selected = {v['forgeId'] for v in decision['assignments']}
                    if len(selected) < decision['count']:
                        identity = next(v['forgeId'] for v in decision['options'] if v['forgeId'] not in selected)
                        native.card(identity)
                    elif len(primary) == 1:
                        native.action('button', primary[0]['text'], observed=observed)
                    else:
                        raise AssertionError(observed)
                elif kind:
                    raise AssertionError('No native choice adapter in this QA driver: '+kind)
                elif s['legalLands']:
                    native.card(s['legalLands'][0])
                elif s['legalCasts']:
                    native.card(s['legalCasts'][0])
                elif observed['workflow'] == 'ActionsAvailableWorkflow' and len(primary) == 1:
                    native.action('button', primary[0]['text'], observed=observed)
                elif len(advance) == 1:
                    native.action('button', advance[0]['text'], observed=observed)
                else:
                    raise AssertionError(observed)
            except native.StaleObservation:
                stale_observations += 1
                continue  # QA rejected before publication; no accepted input is resent.
            actions += 1
            (a.output/'progress.json').write_text(json.dumps(dict(session=session, actions=actions, turn=s['turn'], phase=s['phase']), indent=2))
            if actions % 20 == 0:
                print(json.dumps(dict(actions=actions, turn=s['turn'], phase=s['phase'], life=[s['life'], s['opponentLife']])), flush=True)
    s = state()
    if not s['gameOver']:
        capture(a.output/'bounded-checkpoint.png')
        (a.output/'incomplete-checkpoint.json').write_text(json.dumps(dict(session=session, actions=actions, turn=s['turn'], phase=s['phase'], life=[s['life'], s['opponentLife']],
            status='bounded-timeout', scope='Original match remains live; no accepted action was resent and no completed-game claim.'), indent=2))
    check('Normal native match reaches a real game outcome before deadline', s['gameOver'])
    check('Many original gameplay controls exercised', actions >= 30)
    check('No gameplay actions remain after outcome', not any(s[k] for k in ('legalLands', 'legalCasts', 'legalMana', 'canPass')))
    observe_cards(s);resolutions=[]
    for event in s.get('researchTrace',[]):
        card=known.get(event.get('sourceForgeId'),{})
        if event['kind']=='spell-resolved' and card.get('name') in tested:
            check('Actually observed qualified pump resolves without fizzle',event['hasFizzled'] is False)
            resolutions.append(dict(name=card['name'],owner=card['owner'],forgeId=card['forgeId']))
    burns=[]
    if a.verified_policy:
        from verify_observed_pump_journal import observed_pumps,observed_burns
        resolutions=observed_pumps(lab/'forge-ipc',specs)
        burns=observed_burns(lab/'forge-ipc',specs)
    if a.require_burn:check('At least one real local burn has matching original native damage',any(v['owner']==1 for v in burns))
    check('At least one real local pump resolves during the native game',any(v['owner']==1 for v in resolutions))
    capture(a.output/'outcome.png')
    for name in ('state.json', 'native-wire.jsonl', 'engine-journal.jsonl', 'scenario.json'):
        shutil.copy2(lab/'forge-ipc'/name, a.output/name)
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cards=sorted({v['name'] for v in resolutions+burns}),resolutions=resolutions,burnResolutions=burns,checks=len(checks), results=checks, actions=actions,
        sawNativeDamageBrowser=seen_native_damage, rejectedStaleObservations=stale_observations, deferredSnapshots=deferred_snapshots, seed=s.get('randomSeed'), initialTurn=initial_turn, turn=s['turn'], winner=s['winnerSeat'], life=[s['life'], s['opponentLife']],
        scope='Normally shuffled independent Forge match through original native controls, including explicit source-qualified pump targets. QA chooses no blocks and original automatic allocation/order. Actual resolutions only; exact deltas and expiration have separate targeted checks. Not optimal play, physical mouse input or complete animation parity.'), indent=2))
    print(json.dumps(dict(checks=len(checks), actions=actions, turn=s['turn'], winner=s['winnerSeat'], report=str(a.output/'report.json'))))


if __name__ == '__main__':
    main()
