"""Verify test resource limits and cleanup using only disposable Python children."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
from headless_resources import java_options, process_flags
from run_background_validation import ChildJob

checks=[]
def check(label,ok):
    assert ok,label
    checks.append(label)

with patch.dict(os.environ,{'FORGE_ARENA_TEST_HEAP_MB':'1024','FORGE_ARENA_TEST_THREADS':'2'}):
    options=java_options()
    check('Test JVM has an explicit 1 GiB heap and two processors','-Xmx1024m' in options and '-XX:ActiveProcessorCount=2' in options)
for name,value in [('FORGE_ARENA_TEST_HEAP_MB','8192'),('FORGE_ARENA_TEST_THREADS','32')]:
    with patch.dict(os.environ,{name:value}):
        try:java_options()
        except ValueError:check('Unbounded setting is rejected '+name,True)
        else:raise AssertionError('Invalid resource setting accepted')
if os.name=='nt':
    check('Child processes are hidden and below normal priority',process_flags()&subprocess.CREATE_NO_WINDOW and process_flags()&subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    with tempfile.TemporaryDirectory(prefix='arena-background-job-') as folder:
        marker=Path(folder)/'child-pid.txt'
        code='import subprocess,sys,time,pathlib\np=subprocess.Popen([sys.executable,"-c","import time; time.sleep(120)"],creationflags='+str(subprocess.CREATE_NO_WINDOW)+')\npathlib.Path(sys.argv[1]).write_text(str(p.pid))\ntime.sleep(120)'
        job=ChildJob();parent=None;handle=None
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_bool,ctypes.c_uint32];kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        try:
            parent=subprocess.Popen([sys.executable,'-c',code,str(marker)],creationflags=process_flags())
            job.attach(parent)
            end=time.monotonic()+10
            while not marker.exists() and time.monotonic()<end:time.sleep(.05)
            check('Disposable driver spawned a child inside its test job',marker.exists())
            handle=kernel.OpenProcess(0x100000,False,int(marker.read_text()))
            check('Disposable descendant is running before cleanup',bool(handle) and kernel.WaitForSingleObject(handle,0)==258)
            job.close();parent.wait(timeout=5)
            check('Closing the test job terminates its driver',parent.returncode is not None)
            check('Closing the test job also terminates its descendant',kernel.WaitForSingleObject(handle,5000)==0)
        finally:
            job.close()
            if parent is not None and parent.poll() is None:parent.kill();parent.wait(timeout=5)
            if handle:kernel.CloseHandle(handle)
print(json.dumps(dict(checks=len(checks),passed=checks),indent=2))
