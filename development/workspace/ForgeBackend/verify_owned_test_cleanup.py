"""Verify bounded Windows test ownership without touching any existing process."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from headless_resources import process_flags,run_owned


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if os.name!='nt':p.error('This proof exercises Windows job ownership')
    a.output.mkdir(parents=True,exist_ok=False);pid_file=a.output/'owned-descendant.pid';checks=[]
    control=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],creationflags=process_flags())
    code="import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);Path(sys.argv[1]).write_text(str(p.pid));time.sleep(30)"
    try:
        try:run_owned([sys.executable,'-c',code,str(pid_file)],timeout=2,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:checks.append(dict(check='Bounded owned parent times out',passed=True))
        else:raise AssertionError('Owned parent unexpectedly completed before deadline')
        child=int(pid_file.read_text());kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        def running():
            handle=kernel.OpenProcess(0x1000,False,child)
            if not handle:return False
            try:
                value=wintypes.DWORD();return bool(kernel.GetExitCodeProcess(handle,ctypes.byref(value))) and value.value==259
            finally:kernel.CloseHandle(handle)
        deadline=time.monotonic()+3
        while running() and time.monotonic()<deadline:time.sleep(.02)
        checks.append(dict(check='Owned descendant is stopped when the test job closes',passed=not running()))
        checks.append(dict(check='Independent control process survives the other test job timeout',passed=control.poll() is None))
        result=dict(passed=all(c['passed'] for c in checks),checks=checks,scope=__doc__)
        (a.output/'report.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));raise SystemExit(0 if result['passed'] else 1)
    finally:
        if control.poll() is None:control.terminate()
        control.wait(timeout=5)


if __name__=='__main__':main()
