from engine_test_client import Engine
import json
engine=Engine("attack-open")
try:
 d=None
 for i in range(12):
  r,d=engine.pass_or_decision()
  if d:break
 engine.check("real Forge declaration callback exposes a native-facing decision",d is not None,d)
 decision=d["state"]["decision"];token=decision["token"];attacker=decision["options"][0]["forgeId"]
 r=engine.send("select_attackers",decisionToken="stale",assignments=[{"forgeId":attacker,"targetSeat":2}]);engine.check("stale decision token rejected",not r["accepted"])
 r=engine.send("select_attackers",decisionToken=token,assignments=[{"forgeId":999999,"targetSeat":2}]);engine.check("unoffered attacker rejected",not r["accepted"])
 r=engine.send("select_attackers",decisionToken=token,assignments=[{"forgeId":attacker,"targetSeat":1}]);engine.check("illegal defender rejected",not r["accepted"])
 r=engine.send("select_attackers",decisionToken=token,assignments=[{"forgeId":attacker,"targetSeat":2}]);engine.check("legal attacker selection accepted without tapping before submit",r["accepted"] and not next(c for c in r["state"]["battlefield"] if c["forgeId"]==attacker)["tapped"])
 r=engine.send("submit_attackers",decisionToken=token);engine.check("submitted attacker goes through Forge validation and taps",r["accepted"] and next(c for c in r["state"]["battlefield"] if c["forgeId"]==attacker)["tapped"])
 for i in range(12):
  r,d=engine.pass_or_decision();engine.check("no unexpected controller decision",d is None,d)
  if engine.state["opponentLife"]<20:break
 engine.check("Forge deals exactly two unblocked combat damage",engine.state["opponentLife"]==18)
 print(json.dumps({"evidence":str(engine.ipc),"checks":len(engine.checks),"state":engine.state},indent=2))
finally:engine.close()
