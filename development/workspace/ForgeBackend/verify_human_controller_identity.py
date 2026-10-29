"""Human/bot identity and original native opening controls in real Forge games.

Checks actual controller and cached PlayerView identity, not a name or a
presentation label. Initial state comes from normal shuffled deck startup.
"""
import argparse
import json
import os
from pathlib import Path
import traceback


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("config", "worker", "managed", "fixture", "output"):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    os.environ["FORGE_ARENA_CONFIG"] = str(a.config)
    from native_engine_test_client import NativeEngine
    from native_test_policy import execute

    a.output.mkdir(parents=True, exist_ok=False)
    cases = []
    for name, seats in (("opening-duel", 2), ("commander-pod", 4)):
        e = None
        trace = []
        identities = []
        try:
            settings = dict(randomSeed=7274, startingPlayerPolicy="local-first")
            if seats == 4:
                deck = dict(name="Identity regression", format="commander-40", experimental=True,
                            commander=dict(name="Isamaru, Hound of Konda", count=1),
                            cards=[dict(name="Plains", count=99)])
                settings.update(localDeck=deck, opponentDecks=[deck] * 3)
            e = NativeEngine(name, worker=a.worker, managed=a.managed, fixture=a.fixture, **settings)

            def check_identity(label):
                actual = e.state["researchControls"]["controllerIdentities"]
                identities.append(dict(stage=label, identities=actual))
                assert len(actual) == seats
                for entry in actual:
                    expected = entry["seat"] != 1
                    assert entry["controllerIsAI"] is expected and entry["playerIsAI"] is expected, (
                        "The human seat must be human in both the controller and cached PlayerView", entry)

            check_identity("opening-hand")
            assert e.state["decision"]["kind"] == "mulligan"
            execute(e, trace, "submit_mulligan", decisionToken=e.state["decision"]["token"],
                    assignments=[dict(keep=True)])
            for _ in range(32):
                if e.state["phase"] == "MAIN1" and e.state["activeSeat"] == 1:
                    break
                execute(e, trace, "pass_priority")
            assert e.state["phase"] == "MAIN1" and e.state["legalLands"]
            check_identity("first-main")
            execute(e, trace, "play_land", e.state["legalLands"][0])
            assert e.state["landsPlayed"] == 1 and not e.state["fidelityGap"]
            check_identity("land-played")
            cases.append(dict(case=name, passed=True, identities=identities, evidence=str(e.ipc)))
        except Exception as error:
            cases.append(dict(case=name, passed=False, identities=identities, error=repr(error),
                              traceback=traceback.format_exc(), evidence=str(e.ipc) if e else None))
        finally:
            if e:
                e.close()
        print(json.dumps(cases[-1]), flush=True)
    result = dict(passed=all(c["passed"] for c in cases), cases=cases, scope=__doc__)
    (a.output / "report.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
