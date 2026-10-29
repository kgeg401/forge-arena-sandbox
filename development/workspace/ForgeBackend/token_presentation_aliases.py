"""Bind active token image/state keys to already qualified native faces."""
import copy


def add_token_presentation_aliases(manifest, tokens):
    added = {}
    for script, source in tokens.items():
        canonical = 'token:' + script
        if canonical not in manifest['cards'] or source.get('missing'):
            continue
        image = source.get('presentationImageKey')
        if not image:
            if source.get('parentTokenScript'):
                raise ValueError('Re-project token faces with active image keys: ' + script)
            continue
        if not image.startswith('t:'):
            continue
        state = source.get('presentationState', 'Backside' if source.get('parentTokenScript') else 'Original')
        alias = 'token:' + image[2:].split('|', 1)[0] + (':Backside' if state == 'Backside' else '')
        if alias == canonical:
            continue
        definition = manifest['cards'][canonical]
        existing = manifest['cards'].get(alias)
        if existing and existing['grpId'] != definition['grpId']:
            raise ValueError('Ambiguous active token face: ' + alias)
        bound = copy.deepcopy(definition)
        bound['presentationAliasOf'] = canonical
        bound['presentationImageKey'] = image
        bound['bindingBasis'] += '; exact pinned active Forge token image and state'
        manifest['cards'][alias] = bound
        added[alias] = canonical
    return added
