"""Set a bounded CPU pair before importing a known research test driver."""
import argparse
import ctypes
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import runpy
import sys


def affinity(mask):
    if os.name!='nt':raise ValueError('This affinity wrapper currently supports Windows only')
    if mask<=0 or mask.bit_count()!=2:raise ValueError('Select exactly two logical processors')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p;process=kernel.GetCurrentProcess()
    kernel.GetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    current=ctypes.c_size_t();system=ctypes.c_size_t()
    if not kernel.GetProcessAffinityMask(process,ctypes.byref(current),ctypes.byref(system)):raise ctypes.WinError(ctypes.get_last_error())
    if mask & ~current.value:raise ValueError('Requested CPU pair is outside this process allocation')
    if not kernel.SetProcessAffinityMask(process,mask):raise ctypes.WinError(ctypes.get_last_error())
    return dict(previousMask=current.value,systemMask=system.value,selectedMask=mask,logicalProcessors=2)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cpu-mask',type=lambda v:int(v,0),required=True);p.add_argument('--receipt',type=Path)
    p.add_argument('script',type=Path);p.add_argument('arguments',nargs=argparse.REMAINDER)
    a=p.parse_args();script=a.script.resolve();here=Path(__file__).resolve().parent
    if script.parent!=here or script.name not in ('run_card_batches.py','run_background_validation.py','verify_catalogue_full_matches.py'):raise ValueError('Select a known local research driver')
    receipt=dict(pid=os.getpid(),utc=datetime.now(timezone.utc).isoformat(),script=str(script),affinity=affinity(a.cpu_mask))
    if a.receipt:
        with a.receipt.open('x',encoding='utf8') as f:json.dump(receipt,f,indent=2)
    sys.argv=[str(script),*a.arguments];runpy.run_path(str(script),run_name='__main__')


if __name__=='__main__':main()
