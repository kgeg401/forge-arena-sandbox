"""Reduce retained REA metadata to a reusable, build-bound host entry map."""
import json
from pathlib import Path

root = Path(r"D:\GAMES\CodexAssets\ForgeArenaSandbox\research")
document = json.loads((root / "core-members.json").read_text(encoding="utf-8"))
data = document["result"]
selected = {
    ("Matchmaking", "InitializeMatchManager"),
    ("MatchManager", "Initialize"),
    ("MatchManager", "OnMessageReceived"),
    ("MatchManager", "Update"),
    ("MatchSceneManager", "MatchStateChanged"),
    ("MatchSceneManager", "OnSceneLoaded"),
    ("MatchSceneManager", "Load"),
    ("GameManager", "Init"),
    ("GameManager", "Update"),
    ("GreClient.Rules.GreInterfaceFactory", "Create"),
}
methods = []
for method in data["methods"]:
    if (method["declaring_type"], method["name"]) not in selected:
        continue
    token = method["token"]
    methods.append({"name": method["declaring_type"] + "." + method["name"], "token": token,
                    "rva": method["rva"], "signature": method["signature"],
                    "rawCilSha256": method["body"]["il_sha256"],
                    "callers": [e for e in data["call_edges"] if e["target_token"] == token and e["target_kind"] == "method-def"],
                    "calls": [e for e in data["call_edges"] if e["caller_token"] == token]})
output = {"evidence_id": document["evidence_id"], "artifact": data["artifact"], "identity_scope": data["identity_scope"],
          "scope": "Static candidates only; not runtime hook verification", "methods": methods}
(root / "native-host-hook-map.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
print(f"Saved {len(methods)} source-bound method entries")
