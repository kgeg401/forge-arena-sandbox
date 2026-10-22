"""Explain support without ever granting admission from an audit or name match."""
from pathlib import Path
import hashlib
import json
import re
from arena_catalog import clean_name
from runtime_paths import ROOT, SUPPORT_POLICY, FORGE_SCRIPTS

SECTIONS = ('Commander', 'Deck', 'Sideboard', 'Companion')
ENTRY = re.compile(r'([1-9][0-9]{0,2})[xX]?\s+(.+?)(?:\s+\([A-Za-z0-9]+\)\s+[0-9]+[A-Za-z]?)?')
FRIENDLY_ISSUES = {
    'mapping.no_script':'No matching rules implementation has been identified.',
    'mapping.ambiguous':'The matching rules implementation still needs to be identified.',
    'engine.construction_failed':'The installed rules engine could not load this card.',
    'engine.construction_diagnostic':'The rules engine reported problems loading this card.',
    'engine.identity_mismatch':'The rules engine loaded a different card face than expected.',
    'engine.not_audited':'This card has not been checked against the installed rules engine.',
    'bridge.mana_colors':'This card needs mana sources or colors that are not supported yet.',
    'bridge.mana_sources':'This card produces mana in a way that is not supported yet.',
    'bridge.cost_form':'This card has casting or additional costs that are not supported yet.',
    'bridge.card_type':'This card type is not fully supported yet.',
    'bridge.faces':'Changing between this card\'s faces is not supported yet.',
    'bridge.keywords':'One or more of this card\'s keywords are not fully supported yet.',
    'bridge.combat_assignment':'Combat damage choices for this creature still need verification.',
    'bridge.legendary_choice':'Choosing between legendary permanents still needs verification.',
    'bridge.damage_events':'This card\'s damage effects are not fully supported yet.',
    'bridge.counter_events':'Countering spells with this card is not fully supported yet.',
    'bridge.activated':'This card\'s activated abilities are not fully supported yet.',
    'bridge.triggers':'This card\'s triggered abilities are not fully supported yet.',
    'bridge.replacements':'This card changes how an event happens in a way that is not supported yet.',
    'bridge.static':'This card\'s ongoing effects are not fully supported yet.',
    'bridge.targets':'Choosing targets for this card is not fully supported yet.',
    'bridge.player_targets':'Choosing a player as this card\'s target is not fully supported yet.',
    'bridge.tokens':'This card creates tokens that are not supported yet.',
    'bridge.counters':'This card uses counters that are not fully supported yet.',
    'bridge.choices':'This card needs a choice the sandbox cannot yet ask you to make.',
    'bridge.effects':'One or more of this card\'s effects are not supported yet.',
    'bridge.extra_zones':'This card uses a game zone that is not fully supported yet.',
    'bridge.zone_choices':'Searching, choosing or rearranging cards for this effect is not supported yet.',
    'bridge.digital':'This digital or rebalanced version still needs its own verification.',
    'verification.rules_text':'This card\'s rules still need verification.',
    'verification.native_assets':'This card\'s appearance still needs verification.',
    'verification.sequence':'This card still needs gameplay and interaction checks.',
}


def identity(name):
    return re.sub(r'\s*/{2,3}\s*', ' // ', clean_name(name)).casefold()


def load_index(path=None, policy_path=SUPPORT_POLICY, forge_scripts=FORGE_SCRIPTS, forge_jar=ROOT/'forge-runtime/forge.jar'):
    paths = [Path(path)] if path else [Path(__file__).with_name('card-support-index.json'), ROOT/'native-lab/card-support-index.json']
    for candidate in paths:
        if not candidate.is_file():
            continue
        data = json.loads(candidate.read_text(encoding='utf-8'))
        if data.get('schema') != 1 or data.get('provenance', {}).get('policySha256') != hashlib.sha256(Path(policy_path).read_bytes()).hexdigest():
            raise ValueError('Card support report belongs to a different admission policy; rebuild it before use.')
        for key,source in (('sourceForgeScriptsSha256',forge_scripts),('forgeJarSha256',forge_jar)):
            if not Path(source).is_file() or data['provenance'].get(key)!=hashlib.sha256(Path(source).read_bytes()).hexdigest():
                raise ValueError('Card support report belongs to a different Forge engine/script distribution; rebuild it before use.')
        if len({identity(c['name']) for c in data['cards']}) != len(data['cards']):
            raise ValueError('Ambiguous names in card support report')
        return data
    return None


def explain(name, index=None, policy_path=SUPPORT_POLICY, section='Deck'):
    policy = json.loads(Path(policy_path).read_text())
    admitted = {identity(n): n for n in policy['verifiedNames']}
    commanders = {identity(n): n for n in policy.get('brawlCommanders', {})}
    key = identity(name)
    allowed = commanders if section == 'Commander' else admitted
    # The policy is the sole authority. Report entries cannot grant permission.
    if key in allowed:
        return dict(name=allowed[key], status='verified-bounded-slice', matchAdmitted=True,
                    reasons=['Verified for the currently supported sandbox features only.'])
    card = next((c for c in (index or {}).get('cards', []) if identity(c['name']) == key), None)
    if not card:
        return dict(name=name, status='not-indexed' if index else 'unverified', matchAdmitted=False,
                    reasons=['Not in this installed Arena catalogue; it may be a linked face or an unknown name.'] if index else ['This card has not been verified for sandbox play.'])
    reasons = [index['issues'][b] for b in card['blockers']]
    if key in commanders:
        reasons.insert(0, 'Verified as a commander only; not admitted to the main deck.')
    status=card['status'] if card['status']!='verified-bounded-slice' else 'unverified'
    return dict(name=card['name'], status=status, matchAdmitted=False,
                construction=card['construction'], reasons=reasons,
                blockerCodes=card['blockers'], arenaGrpIds=card['arenaGrpIds'])


def unsupported_message(names):
    try:
        index = load_index()
    except (OSError, ValueError, KeyError, TypeError):
        index = None  # Missing/stale diagnostics never relax production admission.
    details = []
    for name in dict.fromkeys(names):
        row = explain(name, index)
        reasons = row['reasons']
        details.append(name + ': ' + '; '.join(reasons[:3]))
    return 'This deck contains cards not verified for the sandbox:\n' + '\n'.join(details)


def inspect_deck(text, index, policy_path=SUPPORT_POLICY):
    rows = []
    errors = []
    section = 'Deck'
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line in SECTIONS:
            section = line
            continue
        match = ENTRY.fullmatch(line)
        if not match:
            errors.append(dict(line=number, text=line, reason='Expected a card count and name.'))
            continue
        row = explain(match[2], index, policy_path, section)
        row.update(line=number, section=section, count=int(match[1]))
        rows.append(row)
    blocked = [r for r in rows if not r['matchAdmitted']]
    return dict(schema=1, cards=rows, parseErrors=errors,
                totalCopies=sum(r['count'] for r in rows), unsupportedCopies=sum(r['count'] for r in blocked),
                unsupportedNames=list(dict.fromkeys(r['name'] for r in blocked)),
                admissionBlocked=bool(blocked or errors),
                scope='Card-support preflight only. Does not check deck size, singleton, color identity, release status, account ownership or format legality. No match was started.')
