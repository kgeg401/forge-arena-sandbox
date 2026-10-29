import pathlib,json,subprocess,time,uuid
from runtime_paths import ROOT,JAVA_HOME
from headless_resources import java_options,process_flags
JAVA=str(JAVA_HOME/'bin/java.exe')
class Engine:
 def __init__(self,scenario="starter",**settings):
  self.ipc=ROOT/"research"/("combat-check-"+time.strftime("%Y%m%d-%H%M%S")+"-"+uuid.uuid4().hex[:6]);self.ipc.mkdir();(self.ipc/"scenario.json").write_text(json.dumps({"scenario":scenario,**settings}));self.log=(self.ipc/"engine.log").open("w")
  cp=";".join(str(ROOT/p) for p in ["build/ForgeBackend/classes","forge-runtime/forge.jar","forge-runtime/gson.jar"])
  self.process=subprocess.Popen([JAVA,*java_options(),"-cp",cp,"ForgeLandEngine",str(ROOT/"forge-runtime"),str(self.ipc)],cwd=ROOT/"forge-runtime",stdout=self.log,stderr=subprocess.STDOUT,creationflags=process_flags())
  try:self.state=self.wait_json(self.ipc/"state.json",45)
  except Exception:
   self.process.terminate();self.process.wait(timeout=5);self.log.close();raise
  self.session=self.state["session"];self.checks=[]
 def wait_json(self,path,seconds=5):
  limit=time.monotonic()+seconds;last_error=None
  while time.monotonic()<limit:
   try:return json.loads(path.read_text(encoding="utf-8-sig"))
   except (FileNotFoundError,PermissionError,json.JSONDecodeError) as error:last_error=error
   if self.process.poll() is not None:raise RuntimeError((self.ipc/"engine.log").read_text(encoding="utf-8-sig")[-5000:])
   time.sleep(.025)
  raise TimeoutError(str(path)+'; last read: '+repr(last_error))
 def begin(self,op,forgeId=0,**fields):
  r={"id":uuid.uuid4().hex,"session":self.session,"seat":1,"op":op,"forgeId":forgeId,**fields};p=self.ipc/"requests"/(r["id"]+".json");t=p.with_suffix(".tmp");t.write_text(json.dumps(r));t.rename(p);return r["id"]
 def finish(self,id,seconds=5):
  r=self.wait_json(self.ipc/"responses"/(id+".json"),seconds);self.state=r["state"];return r
 def send(self,op,forgeId=0,**fields):return self.finish(self.begin(op,forgeId,**fields))
 def pass_or_decision(self):
  id=self.begin("pass_priority");end=time.monotonic()+5
  while time.monotonic()<end:
   if self.process.poll() is not None:raise RuntimeError((self.ipc/"engine.log").read_text(encoding="utf-8-sig")[-3000:])
   response=self.ipc/"responses"/(id+".json")
   if response.exists():r=self.finish(id);assert r["accepted"],r;return r,None
   p=self.ipc/"decision.json"
   if p.exists():
    try:d=json.loads(p.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError,PermissionError,json.JSONDecodeError):d=None
    if d and d["parentRequestId"]==id:self.state=d["state"];return None,d
   time.sleep(.025)
  raise TimeoutError("pass did not finish or expose a controller decision")
 def check(self,label,condition,detail=None):
  self.checks.append({"check":label,"passed":bool(condition)})
  assert condition,(label,detail or self.state)
 def close(self):
  (self.ipc/"checks.json").write_text(json.dumps(self.checks,indent=2));(self.ipc/"stop.request").write_text("bounded test complete")
  try:self.process.wait(timeout=5)
  except subprocess.TimeoutExpired:
   self.process.terminate();self.process.wait(timeout=5)
  self.log.close()
