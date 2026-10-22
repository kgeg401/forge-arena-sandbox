using System;
using System.Collections.Generic;
using ForgeArenaSandbox;
using Wizards.Arena.TcpConnection;
using Wotc.Mtgo.Gre.External.Messaging;

internal static class TransportChecks
{
    public static IEnumerable<string> Run()
    {
        var c = new LocalGreConnection(capacity: 1);
        c.Connect(null!);
        Reject(() => c.ConnectToGRE("https://remote.invalid", c.MatchId));
        c.ConnectToGRE(LocalGreConnection.LocalUri, c.MatchId);
        var msg = new GREToClientMessage { MsgId = 12 };
        c.Enqueue(msg);
        msg.MsgId = 99;
        Reject(() => c.Enqueue(msg));
        uint delivered = 0;
        c.MessageReceived += m => delivered = m.MsgId;
        c.ProcessMessages();
        if (delivered != 12) throw new Exception("Incoming message was not isolated from producer mutation.");
        Reject(() => c.SendMessage(new ClientToGREMessage()));
        c.Enqueue(msg);
        c.Close(TcpConnectionCloseType.NormalClosure, "test close clears queue");
        c.Connect(null!);
        c.ConnectToGRE(LocalGreConnection.LocalUri, c.MatchId);
        delivered = 0;
        c.ProcessMessages();
        if (delivered != 0) throw new Exception("Message leaked across close/reconnect.");
        return new[] { "Nonlocal join rejected", "Queue overflow rejected without silent drop", "Incoming messages cloned", "Missing backend rejected", "Close/reconnect discarded old queued messages" };
    }

    private static void Reject(System.Action action)
    {
        try { action(); }
        catch (InvalidOperationException) { return; }
        throw new Exception("Expected transport rejection did not occur.");
    }
}
