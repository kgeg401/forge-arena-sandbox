"""Check the beta's player docs, local links and GitHub issue forms."""
from pathlib import Path
import json,re,xml.etree.ElementTree as ET
from urllib.parse import unquote
R=Path(__file__).resolve().parents[1];C=R/'client';D=R/'docs';checks=[]
def check(label,ok):
 if not ok:raise AssertionError(label)
 checks.append(label)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
info=read(C/'release-info.json');starter=read(C/'starter-content.json');extra=read(C/'ForgeBackend/experimental-admission.json');policy=read(C/'ForgeBackend/bridge_support.json')
check('Beta update/display version',info['version']=='0.2.0-beta.1' and info['displayVersion']=='Beta 1')
check('Actual card counts',len(policy['verifiedNames'])==370 and len(extra['cards'])==1590 and not set(policy['verifiedNames'])&extra['cards'].keys())
check('Actual shared starter content',len(starter['decks'])==32 and len(starter['cards'])==907 and sum(starter['cards'].values())==1338)
current=['README.md','CONTRIBUTING.md']+['docs/'+n for n in ['README.md','BETA.md','KNOWN-ISSUES.md','REPORTING-BUGS.md','FAQ.md','GAME-MODES.md','MULTIPLAYER.md','STARTER-CONTENT.md','STACK-RESOLUTION.md','LOOP-REPEAT.md','ARCHITECTURE.md','ARENA-COMPATIBILITY.md','LIBRARY-HEIST.md','FIVE-MECHANICS.md','CAST-HIGHLIGHTS.md','DEVELOPMENT.md']]
for rel in current:
 p=R/rel;s=p.read_text(encoding='utf8')
 links=re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)',s)+re.findall(r'(?:href|src)="([^"]+)"',s)
 for link in links:
  if re.match(r'^(?:https?://|mailto:|#)',link):continue
  dest=(p.parent/unquote(link.split('#',1)[0])).resolve();check('Local link: '+rel+' -> '+link,R.resolve() in dest.parents and dest.exists())
 for phrase in ['1,421 are enabled','**26 saved decks**','**521 collection','Stop** prevents','Multiplayer is unfinished.']:
  check('No stale current claim: '+rel+' '+phrase,phrase not in s)
readme=(R/'README.md').read_text(encoding='utf8')
check('Pinned beta download',readme.count('/releases/tag/v0.2.0-beta.1')==2 and '/releases/tag/v0.2.0-alpha.' not in readme)
check('Documented lifetime/coverage limits','durable match saves' in (D/'KNOWN-ISSUES.md').read_text().lower() or 'not durable' in (D/'KNOWN-ISSUES.md').read_text().lower())
for f in (D/'images').glob('*.svg'):ET.parse(f);check('Well-formed SVG: '+f.name,True)
check('Hero and download image identify the beta',all('ALPHA' not in (D/'images'/name).read_text().upper() for name in ['hero.svg','download-windows.svg']))
# YAML parsing is exercised locally with the installed parser; CI also checks
# every form's required fields without adding a package dependency.
forms=list((R/'.github/ISSUE_TEMPLATE').glob('*.yml'))
for f in forms:
 s=f.read_text(encoding='utf8')
 if f.name=='config.yml':check('Issue chooser keeps help links','KNOWN-ISSUES.md' in s and 'REPORTING-BUGS.md' in s);continue
 check('Named issue form: '+f.name,bool(re.search(r'^name: .+',s,re.M)) and bool(re.search(r'^description: .+',s,re.M)) and '\nbody:' in s)
 ids=re.findall(r'^\s+id: (\S+)',s,re.M);check('Unique field IDs: '+f.name,len(ids)==len(set(ids)) and bool(ids))
check('Bug categories present',{'bug_report.yml','card_interaction.yml','multiplayer.yml','performance.yml','feature_request.yml'}<={f.name for f in forms})
print(json.dumps(dict(passed=True,checks=len(checks),playerDocuments=len(current),issueForms=len(forms)-1,version=info['version']),indent=2))
