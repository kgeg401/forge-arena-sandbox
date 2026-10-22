"""Hold Windows non-delete-sharing read handles while Forge advances."""
from engine_test_client import Engine
import ctypes,json,threading,time
from ctypes import wintypes

k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
k.CreateFileW.restype=wintypes.HANDLE
k.CloseHandle.argtypes=[wintypes.HANDLE]

def hold_read(path,seconds=.4):
    handle=k.CreateFileW(str(path),0x80000000,1,None,3,0,None)
    if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    timer=threading.Timer(seconds,lambda:k.CloseHandle(handle));timer.start();return timer

e=Engine('opening-duel',randomSeed=1)
try:
    d=e.state['decision'];timer=hold_read(e.ipc/'decision.json');begin=time.monotonic()
    r=e.send('submit_starting_player',decisionToken=d['token'],assignments=[{'startingSeat':1}]);timer.join()
    e.check('decision retirement survives a conflicting Windows reader',r['accepted'] and e.state['decision']['kind']=='mulligan' and time.monotonic()-begin>=.3)
    d=e.state['decision'];timer=hold_read(e.ipc/'state.json');begin=time.monotonic()
    r=e.send('submit_mulligan',decisionToken=d['token'],assignments=[{'keep':False}]);assert r['accepted'],r
    e.send('snapshot');timer.join()
    e.check('atomic state replacement survives a conflicting reader',e.process.poll() is None and e.state['mulligans']==1 and time.monotonic()-begin>=.3)
    d=e.state['decision'];r=e.send('submit_mulligan',decisionToken=d['token'],assignments=[{'keep':True}]);assert r['accepted'],r
    d=e.state['decision'];r=e.send('submit_mulligan_bottom',decisionToken=d['token'],assignments=d['options'][:1]);assert r['accepted'],r
    e.check('normal startup still reaches kept six after both conflicts',e.state['stage']=='Play' and len(e.state['hand'])==6)
    e.send('concede');e.check('same engine remains responsive through terminal state',e.state['gameOver'])
    print(json.dumps({'evidence':str(e.ipc),'checks':len(e.checks)},indent=2))
finally:e.close()
