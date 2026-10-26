"""Bounded input-driven helpers. Never change an engine state or seed a zone."""
from pathlib import Path
import json
from deck_import import read_deck,parse_deck,parse_brawl
from engine_test_client import Engine

EMRY='Emry, Lurker of the Loch'
BOMB='Aether Spellbomb'
ORNITHOPTER='Ornithopter'
TAP=136098
BOUNCE=86974
DRAW=4921

class EmryGame:
    def __init__(self,seed=113,brawl=False,deck_override=None):
        root=Path(__file__).resolve().parents[1]
        deck=deck_override or read_deck(root/('decks/Brawl-Emry-Foundation.txt' if brawl else 'decks/Emry-Mechanics-Practice.txt'),'arena-brawl' if brawl else 'practice')
        other=parse_brawl('Commander\n1 Isamaru, Hound of Konda\n\nDeck\n98 Plains\n1 Yoked Ox\n','Vanilla Brawl opponent') if brawl else parse_deck('24 Plains\n36 Yoked Ox\n','Vanilla opponent')
        self.e=Engine('brawl-duel' if brawl else 'custom-duel',localDeck=deck,opponentDeck=other,randomSeed=seed,startingPlayerPolicy='local-first');self.timeline=[]
        self.answer('mulligan',[{'keep':True}]);self.to_main(1)
    @property
    def s(self):return self.e.state
    def check(self,label,ok,detail=None):self.e.check(label,ok,detail)
    def send(self,op,card=0,**fields):
        r=self.e.send(op,card,**fields);self.check('Accepted '+op+' #'+str(len(self.timeline)),r['accepted'],r['reason'])
        self.timeline.append(dict(op=op,card=card,fields=fields,turn=self.s['turn'],phase=self.s['phase'],decision=(self.s.get('decision') or {}).get('kind')))
        self.check('No silent fidelity gap',not self.s['fidelityGap']);return r
    def reject(self,label,op,card=0,**fields):
        before=self.s;r=self.e.send(op,card,**fields);self.check(label,not r['accepted'],r['reason'])
        self.check(label+' preserves the current phase',self.s['turn']==before['turn'] and self.s['phase']==before['phase']);return r
    def answer(self,kind,values=None):
        d=self.s['decision'];self.check('Expected '+kind+' decision',d['kind']==kind,d);fields={'decisionToken':d['token']}
        if values is not None:fields['assignments']=values
        return self.send('submit_'+kind,**fields)
    def step(self):
        d=self.s.get('decision')
        if d:
            kind=d['kind']
            if kind in ('attackers','blockers'):self.answer(kind)
            elif kind=='discard':
                hand={c['forgeId']:c for c in self.s['hand']};options=sorted(d['options'],key=lambda o:(hand[o['forgeId']]['name']!='Island',hand[o['forgeId']]['name']!=EMRY));self.answer(kind,options[:d['count']])
            elif self.shared_observation():pass
            else:raise AssertionError('Unscripted human decision '+kind)
        else:self.e.pass_or_decision();self.check('Priority progression has no gap',not self.s['fidelityGap'])
    def shared_observation(self):
        d=self.s.get('decision') or {};spec=d.get('choice',{})
        if d.get('kind')!='choice':return False
        if spec.get('type')=='look':
            self.check('Look acknowledgement cannot select or move an object',spec['min']==spec['max']==0)
            self.send('submit_choice',decisionToken=d['token'],assignments=[]);return True
        if spec.get('type')=='order' and spec.get('destination') in ('Graveyard','Exile'):
            # Explicit authored test input: keep Forge's offered insertion order.
            # The general choice suite separately checks reverse/permuted orders.
            self.check(spec['destination']+' order includes every offered original object exactly once',spec['min']==spec['max']==len(spec['options']) and len({o['forgeId'] for o in spec['options']})==len(spec['options']))
            self.send('submit_choice',decisionToken=d['token'],assignments=[{'choiceId':o['choiceId']} for o in spec['options']]);return True
        return False
    def to_main(self,min_turn):
        for _ in range(140):
            if self.s['gameOver']:raise AssertionError('Game ended before requested main phase')
            if self.s['turn']>=min_turn and self.s['activeSeat']==1 and self.s['phase']=='MAIN1' and not self.s.get('decision') and not self.s['stack'] and not self.s['stackAbilities']:return
            self.step()
        raise AssertionError('Main phase bound exceeded')
    def next_main(self):self.to_main(self.s['turn']+1)
    def cards(self,zone,name=None,owner=1):return [c for c in self.s[zone] if c['owner']==owner and (name is None or c['name']==name)]
    def one(self,zone,name):
        cards=self.cards(zone,name);assert cards,(zone,name);return cards[0]
    def land(self):
        assert self.s['legalLands'],'No real legal land play';self.send('play_land',self.s['legalLands'][0])
    def lands(self,count):
        while len(self.cards('battlefield','Island'))<count:
            if self.s['legalLands']:self.land()
            if len(self.cards('battlefield','Island'))<count:self.next_main()
    def ensure_hand(self,name):
        for _ in range(25):
            if self.cards('hand',name):return self.one('hand',name)
            if self.s['legalLands']:self.land()
            self.next_main()
        raise AssertionError('Required shuffled card was not drawn within the input bound: '+name)
    def optional_land(self):
        if self.s['legalLands']:self.land()
    def resolve(self):
        for _ in range(40):
            if not self.s['stack'] and not self.s['stackAbilities'] and not self.s.get('decision'):return
            if self.s.get('decision'):
                if self.shared_observation():continue
                raise AssertionError('Choose the target explicitly before resolving')
            self.step()
        raise AssertionError('Stack resolution bound exceeded')
    def cast(self,card,resolve=True):
        self.send('cast_spell',card['forgeId'])
        if resolve:self.resolve()
    def cost(self,card):return next(o['manaCost'] for o in self.s['castOffers'] if o['forgeId']==card['forgeId'])
    def tapped_lands(self):return sum(c['tapped'] for c in self.cards('battlefield','Island'))
    def activation(self,source,ability,target=None,resolve=True):
        self.send('activate_ability',source['forgeId'],abilityId=ability)
        if target is not None:
            d=self.s['decision'];assert d['kind']=='targets';self.send('select_targets',decisionToken=d['token'],assignments=[{'forgeId':target['forgeId']}]);self.answer('targets')
        if resolve:self.resolve()
    def close(self):
        (self.e.ipc/'emry-input-timeline.json').write_text(json.dumps(self.timeline,indent=2));self.e.close()
