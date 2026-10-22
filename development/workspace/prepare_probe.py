"""Prepare a synthetic empty-board test from a retained native schema example.

Reads saved evidence only. Never starts Arena or opens a connection.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(r"D:\GAMES\CodexAssets\ForgeArenaSandbox")
MANAGED = Path(r"D:\GAMES\MTGA\MTGA_Data\Managed")
SOURCE = Path(r"D:\GAMES\CodexAssets\ArenaObserver\sessions\20261017-122858-822080\events.jsonl")


def prepare():
    with SOURCE.open(encoding="utf-8") as stream:
        for line in stream:
            event = json.loads(line)
            if event.get("kind") != "server_labelled_gre":
                continue
            messages = event["payload"]["greToClientEvent"]["greToClientMessages"]
            full = next((m for m in messages if m.get("gameStateMessage", {}).get("type") == "GameStateType_Full"), None)
            if full:
                break
        else:
            raise RuntimeError("No full-state schema example found")

    full = copy.deepcopy(full)
    full["systemSeatIds"] = [1]
    full["msgId"] = 1
    full["gameStateId"] = 1
    state = full["gameStateMessage"]
    state["gameStateId"] = 1
    state["gameInfo"]["matchID"] = "sandbox-1"
    state["pendingMessageCount"] = 0
    for key in ("timers", "diffDeletedInstanceIds", "annotations", "persistentAnnotations", "gameObjects"):
        state.pop(key, None)
    for zone in state["zones"]:
        zone.pop("objectInstanceIds", None)
    for player in state["players"]:
        player["lifeTotal"] = 20
        player["startingLifeTotal"] = 20
        player.pop("timerIds", None)
    changed = copy.deepcopy(state["players"][0])
    changed["lifeTotal"] = 17
    diff = {"type": "GREMessageType_GameStateMessage", "systemSeatIds": [1], "msgId": 2, "gameStateId": 2,
            "gameStateMessage": {"type": "GameStateType_Diff", "gameStateId": 2, "prevGameStateId": 1,
                                 "players": [changed], "pendingMessageCount": 1,
                                 "annotations": [{"id": 1, "affectorId": 1, "affectedIds": [1],
                                                  "type": ["AnnotationType_ModifiedLife"],
                                                  "details": [{"key": "life", "type": "KeyValuePairValueType_int32", "valueInt32": [-3]}]}]}}
    mulligan = {"type": "GREMessageType_MulliganReq", "systemSeatIds": [1], "msgId": 3, "gameStateId": 2,
                "prompt": {"promptId": 34, "parameters": [{"parameterName": "NumberOfCards", "type": "ParameterType_Number", "numberValue": 7}]},
                "mulliganReq": {"mulliganType": "MulliganType_London"}}
    destination = ROOT / "fixtures" / "empty-board-and-life-diff.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({"provenance": {"kind": "synthetic protocol test, not a legal game or native match replay", "schemaSource": str(SOURCE), "sourceSequence": event.get("sequence"), "edits": "Empty zones, no objects/timers, local match ID, life totals 20 then 17; life annotation and mulligan choice exercise client translation only"}, "messages": [full, diff, mulligan]}, indent=2), encoding="utf-8")
    files = ["Core.dll", "SharedClientCore.dll", "Wizards.MDN.GreProtobuf.dll", "Wizards.Arena.TcpConnection.dll", "Google.Protobuf.dll", "Wizards.Arena.Client.Logging.dll"]
    identity = {"scope": "Installed assemblies used as static evidence or parser dependencies", "files": [{"path": str(MANAGED / name), "sha256": hashlib.sha256((MANAGED / name).read_bytes()).hexdigest()} for name in files]}
    manifest = ROOT / "research" / "build-identity.json"
    if manifest.exists():
        existing = json.loads(manifest.read_text(encoding="utf-8"))
        known = {x["path"]: x["sha256"] for x in existing["files"]}
        for entry in identity["files"]:
            if entry["path"] in known and known[entry["path"]] != entry["sha256"]:
                raise RuntimeError("Arena build changed; review evidence before regenerating fixtures")
    manifest.write_text(json.dumps(identity, indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    prepare()
