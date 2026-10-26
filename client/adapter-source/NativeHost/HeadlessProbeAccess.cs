using System.Runtime.CompilerServices;

// This friend contains no Unity entry point and runs only against private
// research manifests. It exercises the same adapter used by the native host.
[assembly:InternalsVisibleTo("ForgeBridgeProbe")]
[assembly:InternalsVisibleTo("HeadlessBridgeWorker")]
[assembly:InternalsVisibleTo("TurnFlowProbe")]
