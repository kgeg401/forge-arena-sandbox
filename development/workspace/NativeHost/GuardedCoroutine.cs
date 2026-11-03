using System;
using System.Collections;
using System.Collections.Generic;

namespace ForgeArenaSandbox;

internal static class GuardedCoroutine
{
    public static IEnumerator Run(IEnumerator routine,Action<Exception> failed)
    {
        var stack=new Stack<IEnumerator>();stack.Push(routine);
        try
        {
            while(stack.Count>0)
            {
                object? current=null;bool moved=false;Exception? error=null;
                try{moved=stack.Peek().MoveNext();if(moved)current=stack.Peek().Current;}
                catch(Exception ex){error=ex;}
                if(error!=null){failed(error);yield break;}
                if(!moved){(stack.Pop() as IDisposable)?.Dispose();continue;}
                if(current is IEnumerator nested){stack.Push(nested);continue;}
                yield return current;
            }
        }
        finally{while(stack.Count>0)(stack.Pop() as IDisposable)?.Dispose();}
    }
}
