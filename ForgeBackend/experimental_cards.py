"""Explicit local experimental admission; never changes verified card claims."""
from pathlib import Path
import hashlib
import json


def load_experimental(path=None):
    path=Path(path) if path else Path(__file__).with_name('experimental-admission.json')
    if not path.exists():return dict(cards={},blockedCards={},enabled=False)
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    if value.get('schema')!=1 or value.get('enabled') is not True:
        raise ValueError('Experimental card configuration must explicitly enable schema 1')
    from runtime_paths import DB,FORGE_SCRIPTS,SUPPORT_POLICY
    for label,source in [('sourceDatabaseSha256',DB),('sourceForgeScriptsSha256',FORGE_SCRIPTS),('policySha256',SUPPORT_POLICY)]:
        if hashlib.sha256(source.read_bytes()).hexdigest()!=value.get(label):
            raise ValueError('Experimental identities no longer match '+label)
    if not isinstance(value.get('cards'),dict) or not isinstance(value.get('blockedCards'),dict):
        raise ValueError('Invalid experimental card inventory')
    verified=set(json.loads(SUPPORT_POLICY.read_text())['verifiedNames'])
    if verified & value['cards'].keys():raise ValueError('Experimental inventory cannot overwrite verified cards')
    for name,card in value['cards'].items():
        if card.get('experimental') is not True or card.get('verified') is not False or card.get('token') is not False or card.get('admitted') is not True:
            raise ValueError('Experimental admission must retain its unverified status: '+name)
        if type(card.get('grpId')) is not int or card['grpId']<=0 or not card.get('forgeScriptSha256'):
            raise ValueError('Experimental card lacks native/source identity: '+name)
        if not isinstance(card.get('colorIdentity'),list) or not set(card['colorIdentity'])<=set('WUBRG'):
            raise ValueError('Invalid experimental color identity: '+name)
        if card.get('commanderAdmitted') and ('Legendary' not in card.get('supertypes',[]) or not {'Creature','Planeswalker'} & set(card.get('types',[]))):
            raise ValueError('Experimental Brawl commander requires an original legendary creature or planeswalker: '+name)
    return value


def apply_human_choices(manifest,overlay):
    """Apply presentation-only bindings to the same pinned experimental runtime.

    This enables original human payment/choice paths, not verified admissions.
    The private overlay is generated locally from both owned installations.
    """
    if not isinstance(overlay,dict) or overlay.get('schema')!=1 or overlay.get('enabled') is not True:
        raise ValueError('Human choice bindings must explicitly enable schema 1')
    for key in ('sourceDatabaseSha256','sourceForgeScriptsSha256'):
        if overlay.get(key)!=manifest.get(key):raise ValueError('Human choice bindings no longer match '+key)
    overrides=overlay.get('cardOverrides');objects=overlay.get('presentationObjects')
    if not isinstance(overrides,dict) or not isinstance(objects,dict):raise ValueError('Missing human choice binding inventory')
    allowed={'abilityBindings','modalBinding','targetPromptId','genericChoiceBinding'}
    for name,value in overrides.items():
        original=manifest['cards'].get(name)
        if not original or original.get('grpId')!=value.get('grpId') or original.get('forgeScriptSha256')!=value.get('forgeScriptSha256'):
            raise ValueError('Human choice binding identity drift: '+name)
        if not isinstance(value.get('fields'),dict) or not set(value['fields'])<=allowed:
            raise ValueError('Human choice bindings cannot change card admission or characteristics: '+name)
    def has_source_card(name,seen=None):
        if name in manifest['cards']:return True
        seen=set() if seen is None else seen
        if name in seen:return False
        seen.add(name);face=objects.get(name)
        return bool(isinstance(face,dict) and face.get('facePresentation') is True and has_source_card(face.get('parentName'),seen))
    for name,value in objects.items():
        if name in manifest['cards'] or value.get('admitted') is not False or not any(value.get(k) is True for k in ('token','facePresentation','emblemPresentation')):
            raise ValueError('Only additional presentation objects may be supplied: '+name)
        if type(value.get('grpId')) is not int or value['grpId']<=0:raise ValueError('Missing original presentation identity: '+name)
        # A transforming planeswalker's emblem can name its back face, which
        # is added in this same overlay. Require an acyclic face chain ending
        # at an existing card, and validate it before making any mutations.
        if (value.get('facePresentation') or value.get('emblemPresentation')) and not has_source_card(value.get('parentName')):
            raise ValueError('Presentation object lacks its original source card: '+name)
    for key in ('keywordAbilityIds','typeEnumIds','cardNameIds'):
        if not isinstance(overlay.get(key),dict):raise ValueError('Missing owned human choice dictionary: '+key)
    for name,value in overrides.items():manifest['cards'][name].update(value['fields'])
    manifest['cards'].update(objects)
    for key in ('keywordAbilityIds','typeEnumIds','cardNameIds'):manifest[key]=overlay[key]
    manifest['humanChoiceBindingProvenance']=overlay.get('provenance',{})
    manifest['fullHumanChoices']=True
    return manifest


def merge_manifest(manifest,experimental=None):
    experimental=experimental if experimental is not None else load_experimental()
    if not experimental.get('enabled'):return manifest
    if set(manifest['cards']) & set(experimental['cards']):
        raise ValueError('Experimental cards cannot overwrite existing native mappings')
    manifest['cards'].update(experimental['cards'])
    manifest['experimentalAdmission']=True
    manifest['experimentalNames']=sorted(experimental['cards'])
    manifest['experimentalStatus']='User-enabled unverified cards; runtime fidelity gaps still stop unsupported behavior'
    manifest['experimentalBlockedCards']=experimental['blockedCards']
    if 'humanChoices' in experimental:apply_human_choices(manifest,experimental['humanChoices'])
    return manifest
