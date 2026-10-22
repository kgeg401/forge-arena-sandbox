using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
using ForgeArenaSandbox;
using GreClient.Rules;
using Wizards.Arena.TcpConnection;
using Wotc.Mtgo.Gre.External.Messaging;
using Wotc.Mtga.Cards.Database;
using ClientStateUpdate = GreClient.Rules.GameStateUpdate;

internal static class Program
{
    private static int Main(string[] args)
    {
        if (args.Length != 3) throw new ArgumentException("Usage: ParserProbe <managed-dir> <fixtures-json or native-wire.jsonl> <report-json>");
        var managed = Path.GetFullPath(args[0]);
        AssemblyLoadContext.Default.Resolving += (_, name) =>
        {
            var path = Path.Combine(managed, name.Name + ".dll");
            return File.Exists(path) ? AssemblyLoadContext.Default.LoadFromAssemblyPath(path) : null;
        };
        return args[1].EndsWith(".jsonl",StringComparison.OrdinalIgnoreCase)?WireSequenceProbe.Run(args[1],args[2]):Run(args[1], args[2]);
    }

    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    private static int Run(string fixturePath, string reportPath)
    {
        var checks = new List<string>();
        var states = new List<object>();
        var changes = new List<string>();
        var life = new List<int>();
        var commands = new List<ClientToGREMessage>();
        var local = new LocalGreConnection();
        // This build dereferences the original cdb argument later in its constructor.
        // Pass the shipped null provider explicitly instead of passing a null argument.
        using var gre = new GreInterface(NullCardDatabaseAdapter.Default, null, null, true, null);
        local.MessageReceived += gre.OnMessageReceived;
        local.LocalCommand += command => commands.Add(command);
        local.Connect(null!);
        local.ConnectToGRE(LocalGreConnection.LocalUri, local.MatchId);
        using var fixtures = JsonDocument.Parse(File.ReadAllText(fixturePath));
        foreach (var element in fixtures.RootElement.GetProperty("messages").EnumerateArray())
        {
            var msg = GREToClientMessage.Parser.ParseJson(element.GetRawText());
            local.Enqueue(msg);
            local.ProcessMessages();
            gre.ProcessQueues();
            foreach (var update in gre.RetrieveClientUpdates())
                if (update is ClientStateUpdate u)
                {
                    states.Add(new { id = u.NewState.Id, players = u.NewState.Players.Select(p => new { seat = p.InstanceId, life = p.LifeTotal }).ToArray(), zones = u.NewState.Zones.Count });
                    changes.AddRange(u.Changes.Select(x => x.GetType().Name));
                    life.Add(u.NewState.GetPlayerById(1).LifeTotal);
                    if (u.NewState.Players.Count != 2) throw new Exception("Two player state was not preserved.");
                    if (u.Interaction is MulliganRequest request)
                    {
                        request.KeepHand();
                        local.SendMessage(gre.DequeueOutgoingMessage() ?? throw new Exception("Keep hand generated no response."));
                    }
                }
        }
        if (states.Count != 2) throw new Exception("Expected full and diff client updates.");
        if (!life.SequenceEqual(new[] { 20, 17 })) throw new Exception("Native parser life values did not match supplied state.");
        if (!changes.Contains("UpdatePlayerLifeTotal")) throw new Exception("No native life-total event was generated: " + JsonSerializer.Serialize(new { states, changes }));
        checks.Add("Installed Arena parser processed a local full state and subsequent diff");
        checks.Add("Installed Arena parser emitted a native life-total presentation event");
        var choice = commands.Single();
        if (choice.Type != ClientMessageType.MulliganResp || choice.GameStateId != 2 || choice.RespId != 3 || choice.MulliganResp.Decision != MulliganOption.AcceptHand)
            throw new Exception("Arena choice response did not preserve decision and request correlation: " + choice);
        checks.Add("Native keep-hand choice generated a local MulliganResp with matching state and response ID; seat routing remains connection-scoped");
        ClientToGREMessage? outgoing = null;
        local.LocalCommand += command => outgoing = command;
        gre.ConcedeGame();
        var response = gre.DequeueOutgoingMessage() ?? throw new Exception("Arena did not generate a command.");
        local.SendMessage(response);
        if (outgoing == null || ReferenceEquals(outgoing, response)) throw new Exception("Outgoing transport did not deliver a cloned command.");
        checks.Add("Arena generated a command and the local transport received it without sockets");
        var disconnected = new LocalGreConnection();
        try { disconnected.SendMessage(response); throw new Exception("Disconnected command was accepted."); }
        catch (InvalidOperationException) { checks.Add("Disconnected commands rejected"); }
        local.Close(TcpConnectionCloseType.NormalClosure, "Probe complete");
        checks.AddRange(TransportChecks.Run());
        var report = new { scope = "Headless installed Arena parser and local transport only", passed = true, checks, states, nativeEvents = changes.Distinct().ToArray(), outgoingType = outgoing.Type.ToString(), choice = new { type = choice.Type.ToString(), state = choice.GameStateId, responseId = choice.RespId, seat = choice.SystemSeatId, decision = choice.MulliganResp.Decision.ToString() }, limitations = new[] { "Synthetic protocol fixture; not a legal game or reference-match replay", "No Unity scene or rendered board was launched", "No Forge rules engine is connected", "Null card database; card art and animation playback not tested", "Startup/account/content dependencies unresolved", "Headless .NET 8 result does not establish Unity Mono runtime compatibility" } };
        File.WriteAllText(reportPath, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine(JsonSerializer.Serialize(report));
        return 0;
    }
}
