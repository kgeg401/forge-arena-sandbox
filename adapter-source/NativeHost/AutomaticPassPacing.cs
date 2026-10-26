using System;
using System.Diagnostics;

namespace ForgeArenaSandbox;

/// <summary>Wait for native readiness, never add a dwell to every rules step.</summary>
internal sealed class AutomaticPassPacing
{
    private readonly Func<double> _seconds;
    private readonly Stopwatch _clock = Stopwatch.StartNew();
    private uint _state, _request;
    private bool _attempted, _submitted;
    private double _retryAt;

    internal AutomaticPassPacing(Func<double>? seconds = null)
    {
        _seconds = seconds ?? (() => _clock.Elapsed.TotalSeconds);
    }

    internal bool TrySubmit(uint state, uint request, Func<bool> submit)
    {
        if (!_attempted || state != _state || request != _request)
        {
            _state = state; _request = request; _submitted = false;
            _attempted = false;
        }
        double now = _seconds();
        if (_submitted || (_attempted && now < _retryAt)) return false;
        _attempted = true;
        // A workflow may still be applying after the state has been presented.
        // Retry that request without delaying a newly presented request.
        _retryAt = now + .05;
        _submitted = submit();
        return _submitted;
    }
}
