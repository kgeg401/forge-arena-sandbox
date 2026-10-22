using System;
using System.Collections.Generic;
using Core.Shared.Code.DebugTools;
using GreClient.Network;
using Wizards.Arena.TcpConnection;
using Wotc.Mtgo.Gre.External.Messaging;

namespace ForgeArenaSandbox;

/// <summary>
/// In-process sandbox transport. Implements the installed Arena interface;
/// does not create sockets, authenticate, evaluate rules, or start a Unity scene.
/// Enqueue may run on a worker; ProcessMessages belongs to the client update thread.
/// </summary>
public sealed class LocalGreConnection : IGREConnection
{
    public const string LocalUri = "sandbox://local";
    private readonly object _sync = new object();
    private readonly Queue<GREToClientMessage> _incoming = new Queue<GREToClientMessage>();
    private readonly int _capacity;
    private bool _dispatching;

    public LocalGreConnection(string matchId = "sandbox-1", int capacity = 256)
    {
        if (string.IsNullOrWhiteSpace(matchId)) throw new ArgumentException("A local match ID is required.", nameof(matchId));
        if (capacity < 1) throw new ArgumentOutOfRangeException(nameof(capacity));
        MatchId = matchId;
        _capacity = capacity;
    }

    public string MatchId { get; }
    public string McFabricUri => LocalUri;
    public MatchDoorConnectionState MatchDoorState { get; private set; }
    public IConnectionHistory History => null!;
    public event Action<MatchDoorConnectionState, MatchDoorConnectionState>? MatchConnectionStateChanged;
    public event Action<GREToClientMessage>? MessageReceived;
    public event Action<ClientToGREMessage>? LocalCommand;
#pragma warning disable CS0067 // Required by Arena's interface; no remote service exists here.
    public event Action<string, string, string>? ServerExceptionReceived;
    public event System.Action? MatchCompleted;
    public event Action<(string reason, string details)>? MatchFailed;
    public event Action<string>? ConnectionLost;
    public event Action<string>? ConnectionFailed;
#pragma warning restore CS0067

    public void Connect(ConnectionConfig greConnectionConfig)
    {
        if (MatchDoorState != MatchDoorConnectionState.None && MatchDoorState != MatchDoorConnectionState.Disconnected)
            throw new InvalidOperationException("Local connection is already open.");
        ChangeState(MatchDoorConnectionState.ConnectedToMatchDoor);
    }

    public void CreateMatch(ClientToMatchServiceMessage createMatchMsg)
    {
        if (MatchDoorState != MatchDoorConnectionState.ConnectedToMatchDoor)
            throw new InvalidOperationException("Connect the local transport before creating a match.");
        ChangeState(MatchDoorConnectionState.ConnectedToMatchDoor_MatchCreated);
    }

    public void ConnectToGRE(string mcFabricUri, string matchId)
    {
        if (mcFabricUri != LocalUri || matchId != MatchId)
            throw new InvalidOperationException("Only this local sandbox match may be joined.");
        if (MatchDoorState != MatchDoorConnectionState.ConnectedToMatchDoor &&
            MatchDoorState != MatchDoorConnectionState.ConnectedToMatchDoor_MatchCreated)
            throw new InvalidOperationException("Connect the local transport before joining.");
        ChangeState(MatchDoorConnectionState.Playing);
    }

    public void Enqueue(GREToClientMessage message)
    {
        if (message == null) throw new ArgumentNullException(nameof(message));
        lock (_sync)
        {
            RequirePlaying();
            if (_incoming.Count >= _capacity) throw new InvalidOperationException("Local incoming queue is full; no message was dropped.");
            _incoming.Enqueue(message.Clone());
        }
    }

    public void ProcessMessages()
    {
        if (_dispatching) throw new InvalidOperationException("Recursive local message dispatch is unsupported.");
        _dispatching = true;
        try
        {
            // One per update keeps processing bounded and lets Arena's own queues advance.
            GREToClientMessage? message = null;
            lock (_sync)
                if (MatchDoorState == MatchDoorConnectionState.Playing && _incoming.Count > 0)
                    message = _incoming.Dequeue();
            if (message != null) MessageReceived?.Invoke(message);
        }
        finally { _dispatching = false; }
    }

    public void SendMessage(ClientToGREMessage msg)
    {
        if (msg == null) throw new ArgumentNullException(nameof(msg));
        RequirePlaying();
        var receiver = LocalCommand ?? throw new InvalidOperationException("No local rules backend is attached; command was not accepted.");
        receiver(msg.Clone());
    }

    public void Close(TcpConnectionCloseType status, string reason)
    {
        lock (_sync) _incoming.Clear();
        ChangeState(MatchDoorConnectionState.Disconnected);
    }

    private void RequirePlaying()
    {
        if (MatchDoorState != MatchDoorConnectionState.Playing)
            throw new InvalidOperationException("The local match is not connected.");
    }

    private void ChangeState(MatchDoorConnectionState next)
    {
        var old = MatchDoorState;
        MatchDoorState = next;
        if (old != next) MatchConnectionStateChanged?.Invoke(old, next);
    }
}
