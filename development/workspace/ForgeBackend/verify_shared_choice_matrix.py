"""Exhaustive bounded choice permutations with independent object-order oracles.

The matrix seeds only initial libraries and human decisions. No observed Forge
intermediate state is fed into the expected outcomes. This is shared-interface
coverage, not a declaration that unrelated cards/interactions are verified.
"""
from itertools import permutations
import sys
import verify_shared_choices as verifier


def matrix():
    rows=[]
    for variant,library,n in [('distinct',['Forest','Mountain','Plains','Island'],2),('duplicate',['Forest','Forest','Plains','Island'],2),('short',['Forest'],1)]:
        for order in permutations(range(n)):
            for cut in range(n+1):
                top=list(order[:cut]);bottom=list(order[cut:]);groups=['top' if i in top else 'bottom' for i in range(n)]
                final=top+list(range(n,len(library)))+bottom;draw=final.pop(0)
                rows.append(dict(id=f'matrix-scry-{variant}-{cut}-'+''.join(map(str,order)),card='Preordain',library=library,
                                 plans=[dict(type='partition',groups=groups,order=list(order),names=library[:n])],draw=[library[draw]],libraryAfter=final,grave=[]))
    for card,n in [('Anticipate',3),('Impulse',4),('Strategic Planning',3)]:
        for variant,library in [('distinct',['Forest','Mountain','Plains','Island','Swamp'][:n+1]),('duplicate',['Forest']*n+['Island']),('short',['Forest','Mountain'])]:
            size=min(n,len(library));untouched=list(range(size,len(library)))
            for chosen in range(size):
                remaining=[i for i in range(size) if i!=chosen]
                for order in permutations(remaining):
                    plans=[dict(type='entities',choose=[chosen+1],count=size,minimum=1,maximum=1,names=library[:size])]
                    if len(remaining)>1:
                        plans.append(dict(type='order',choose=[remaining.index(i)+1 for i in order],count=len(remaining),minimum=len(remaining),maximum=len(remaining)))
                    to_grave=card=='Strategic Planning'
                    rows.append(dict(id='matrix-'+card.lower().replace(' ','-')+'-'+variant+'-'+str(chosen)+'-'+''.join(map(str,order)),card=card,library=library,lands=['Island']*2,
                                     plans=plans,draw=[library[chosen]],libraryAfter=untouched if to_grave else untouched+list(order),grave=[library[i] for i in remaining] if to_grave else [],
                                     drawnOriginalIndices=[chosen],graveyardOriginalIndices=list(order) if to_grave else []))
    return rows


if __name__=='__main__':
    verifier.CASES=matrix()
    if '--describe' in sys.argv:
        import json
        print(json.dumps(verifier.CASES,indent=2))
    else:verifier.main()
