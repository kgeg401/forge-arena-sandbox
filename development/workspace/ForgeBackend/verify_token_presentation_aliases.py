"""Guard token-face aliases against stale projections and wrong native faces."""
import copy
from token_presentation_aliases import add_token_presentation_aliases

canonical = 'token:incubator_c_0_0_a_phyrexian:Backside'
alias = 'token:phyrexian:Backside'
base = {'cards': {canonical: {'grpId': 84617, 'bindingBasis': 'qualified linked face', 'abilityIds': [], 'types': ['Artifact', 'Creature']}}}
projection = {'incubator_c_0_0_a_phyrexian:Backside': {'parentTokenScript': 'incubator_c_0_0_a_phyrexian', 'presentationImageKey': 't:phyrexian|EOC|15$alt', 'presentationState': 'Backside'}}
m = copy.deepcopy(base)
assert add_token_presentation_aliases(m, projection) == {alias: canonical}
assert m['cards'][canonical] == base['cards'][canonical]
assert m['cards'][alias]['grpId'] == 84617 and not m['cards'][alias]['abilityIds']
m['cards'][alias]['types'].append('Invalid')
assert m['cards'][canonical]['types'] == ['Artifact', 'Creature'], 'Alias must not mutate canonical data'
for broken in [
    {'incubator_c_0_0_a_phyrexian:Backside': {'parentTokenScript': 'incubator_c_0_0_a_phyrexian'}},
]:
    try: add_token_presentation_aliases(copy.deepcopy(base), broken)
    except ValueError: pass
    else: raise AssertionError('Old projections must require a fresh active-face read')
m = copy.deepcopy(base);m['cards'][alias] = {'grpId': 999}
try: add_token_presentation_aliases(m, projection)
except ValueError: pass
else: raise AssertionError('A conflicting native face must fail')
print('PASS: linked face, canonical preservation, independent data, stale projection and conflicting identity guards')
