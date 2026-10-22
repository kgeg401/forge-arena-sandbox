using System;
using ForgeArenaSandbox;

// Own-code boundary check; never loads or starts the Arena executable.
if(args.Length==1 && args[0]=="token")
{
    bool isolated=IsolationToken.HasZeroCapabilities();Console.WriteLine(isolated?"zero-capability":"ordinary-token");return isolated?1:0;
}
if(args.Length==1 && args[0]=="require-token")
{
    if(!IsolationToken.HasZeroCapabilities())Environment.Exit(78);
    return 0;
}
if(args.Length==2 && args[0]=="validate")
{
    try{Console.WriteLine(LabBoundary.Validate(args[1],true));return 0;}
    catch(Exception e){Console.WriteLine(e.Message);return 2;}
}
return 3;
