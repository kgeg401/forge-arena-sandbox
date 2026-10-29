"""Real Forge rejection/recovery through the owned Arena blocker handlers.

Prepared initial combat only: a Boggart Brute attacks two Yoked Oxen. No
intermediate life, damage, priority or combat state is supplied to the engine.
The literal menace requirement and three damage are independent expectations.
No Unity window, installed profile or production admission is changed.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import traceback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("config", "worker", "managed", "fixture", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    a = parser.parse_args()
    os.environ["FORGE_ARENA_CONFIG"] = str(a.config)
    from native_engine_test_client import NativeEngine

    a.output.mkdir(parents=True, exist_ok=False)
    reports = []
    for case in ("correct-rejected-menace-block", "decline-block-after-rejection", "concede-after-rejected-block"):
        e = None
        try:
            e = NativeEngine("defend", worker=a.worker, managed=a.managed, fixture=a.fixture,
                             fixtureAttacker="Boggart Brute", fixtureBlockers=["Yoked Ox", "Yoked Ox"])
            for _ in range(20):
                if (e.state.get("decision") or {}).get("kind") == "blockers":
                    break
                response, decision = e.pass_or_decision()
                if decision:
                    assert decision["state"]["decision"]["kind"] == "blockers"
            d = e.state["decision"]
            assert d["kind"] == "blockers" and len(d["options"]) == 2
            token = d["token"]
            attacker = next(c["forgeId"] for c in e.state["battlefield"] if c["name"] == "Boggart Brute")
            blockers = [o["forgeId"] for o in d["options"]]
            initial = copy.deepcopy(e.state)
            journal = e.ipc / "engine-journal.jsonl"
            requests_before = journal.read_bytes()
            invalids = [
                ("stale decision", dict(decisionToken="stale", assignments=[])),
                ("duplicate blocker", dict(decisionToken=token, assignments=[
                    dict(forgeId=blockers[0], attackerIds=[attacker]),
                    dict(forgeId=blockers[0], attackerIds=[])])),
                ("duplicate attacker", dict(decisionToken=token, assignments=[
                    dict(forgeId=blockers[0], attackerIds=[attacker, attacker])])),
                ("fractional blocker", dict(decisionToken=token, assignments=[
                    dict(forgeId=blockers[0] + .5, attackerIds=[attacker])])),
                ("late unoffered blocker", dict(decisionToken=token, assignments=[
                    dict(forgeId=blockers[0], attackerIds=[attacker]),
                    dict(forgeId=999999, attackerIds=[attacker])])),
            ]
            for label, fields in invalids:
                reply = e.native_call("select_blockers", **fields)
                assert not reply["accepted"], label
                assert e.state == initial, label + " changed actual rules state"
                assert journal.read_bytes() == requests_before, label + " reached the rules owner"
            selection = dict(forgeId=blockers[0], attackerIds=[attacker])
            reply = e.send("select_blockers", decisionToken=token, assignments=[selection])
            assert reply["accepted"]
            reply = e.send("submit_blockers", decisionToken=token)
            assert not reply["accepted"], "Forge must reject a single blocker against menace"
            assert e.state["decision"]["token"] == token
            assert e.state["life"] == initial["life"] == 20
            assert e.state["battlefield"] == initial["battlefield"], "Rejected declaration changed actual combat"
            assert e.native_status["interaction"] == "DeclareBlockersRequest", "No fresh native retry request"
            retry_state = e.native_status["nativeStateId"]

            if case == "concede-after-rejected-block":
                reply = e.send("concede")
                assert reply["accepted"] and e.state["gameOver"]
                assert e.state.get("decision") is None and not e.state["canPass"]
                assert e.state["life"] == 20, "Concession invented combat damage"
                reports.append(dict(case=case, passed=True, invalidInputsRejectedBeforeRules=len(invalids),
                                    concessionReleasedDecision=True, evidence=str(e.ipc)))
                print(json.dumps(reports[-1]), flush=True)
                continue

            if case == "correct-rejected-menace-block":
                assignments = [dict(forgeId=b, attackerIds=[attacker]) for b in blockers]
            else:
                assignments = [dict(forgeId=b, attackerIds=[]) for b in blockers]
            reply = e.send("select_blockers", decisionToken=token, assignments=assignments)
            assert reply["accepted"], "Original blocker handler could not correct a rejected declaration"
            assert e.native_status["nativeStateId"] > retry_state
            reply = e.send("submit_blockers", decisionToken=token)
            assert reply["accepted"], "Corrected complete declaration did not release the rules callback"
            for _ in range(20):
                if e.state["phase"] == "MAIN2":
                    break
                response, decision = e.pass_or_decision()
                assert decision is None, "Unexpected decision after corrected combat"
            assert e.state["phase"] == "MAIN2", "Combat did not return to actionable main phase"
            expected_life = 20 if case == "correct-rejected-menace-block" else 17
            assert e.state["life"] == expected_life
            assert not e.state["fidelityGap"] and not e.native_status["gap"]
            ox_damage = sum(c["damage"] for c in e.state["battlefield"] if c["name"] == "Yoked Ox")
            assert ox_damage == (3 if case == "correct-rejected-menace-block" else 0)
            reports.append(dict(case=case, passed=True, life=expected_life, blockerDamage=ox_damage,
                                invalidInputsRejectedBeforeRules=len(invalids),
                                recoveredOriginalNativeHandler=True, evidence=str(e.ipc)))
        except Exception as error:
            reports.append(dict(case=case, passed=False, error=repr(error), traceback=traceback.format_exc(),
                                evidence=str(e.ipc) if e else None))
        finally:
            if e:
                e.close()
        print(json.dumps(reports[-1]), flush=True)
    report = dict(passed=all(r["passed"] for r in reports), cases=reports, scope=__doc__)
    (a.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
