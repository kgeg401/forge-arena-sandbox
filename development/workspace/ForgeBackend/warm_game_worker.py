"""Research-only sequential worker with fresh bridge classloaders per game.

The cold Engine remains the reference. Sharing Forge's database is experimental
until a capability family passes cold/warm, order and failure isolation checks.
"""
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid
from engine_test_client import Engine
from headless_resources import java_options, process_flags
from run_background_validation import ChildJob
from runtime_paths import ROOT, JAVA_HOME


def atomic(path, data):
    tmp=path.with_suffix('.pending')
    tmp.write_text(json.dumps(data,indent=2),encoding='utf8');tmp.replace(path)


class Worker:
    def __init__(self, folder, maximum):
        self.folder=folder;folder.mkdir(parents=True,exist_ok=False)
        self.log=(folder/'worker.log').open('w',encoding='utf8')
        self.job=ChildJob();self.lock=threading.Lock();self.retired=False;self.poisoned=False
        cp=os.pathsep.join(str(ROOT/p) for p in ('build/ForgeBackend/classes','forge-runtime/forge.jar','forge-runtime/gson.jar'))
        try:
            self.process=subprocess.Popen([str(JAVA_HOME/'bin/java.exe'),*java_options(),'-cp',cp,'ResearchGameWorker',
                str(ROOT/'forge-runtime'),str(folder),str(ROOT/'build/ForgeBackend/classes'),str(maximum)],
                cwd=ROOT/'forge-runtime',stdout=self.log,stderr=subprocess.STDOUT,creationflags=process_flags())
            self.job.attach(self.process)
            self.ready=self.wait(folder/'ready.json',45)
        except BaseException:
            self.close();raise

    def wait(self, path, seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            try:return json.loads(path.read_text(encoding='utf8'))
            except (FileNotFoundError,PermissionError,json.JSONDecodeError):pass
            if self.process.poll() is not None:
                raise RuntimeError('Research worker exited: '+(self.folder/'worker.log').read_text(encoding='utf8')[-5000:])
            time.sleep(.02)
        raise TimeoutError(str(path))

    def poison(self):
        with self.lock:
            self.poisoned=True
            self.job.close()

    def close(self):
        if hasattr(self,'process'):
            (self.folder/'stop.request').write_text('Bounded research worker complete',encoding='utf8')
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.poison()
            self.process.wait(timeout=5)
        self.job.close();self.log.close()


class WarmEngine(Engine):
    def __init__(self, worker, scenario, **settings):
        if scenario!='card-family':raise ValueError('Warm engine supports research card-family only')
        self.worker=worker;self.process=worker.process;self.closed=False
        self.id=uuid.uuid4().hex;self.ipc=worker.folder/'jobs'/self.id;self.ipc.mkdir(parents=True,exist_ok=False)
        worker.active_ipc=self.ipc
        atomic(self.ipc/'scenario.json',dict(scenario=scenario,**settings))
        request=worker.folder/'job.request.json'
        if request.exists():raise RuntimeError('An earlier worker job is still pending')
        atomic(request,dict(id=self.id,worker=worker.ready['worker']))
        try:self.state=self.wait_json(self.ipc/'state.json',45)
        except BaseException:
            worker.poison();raise
        self.session=self.state['session'];self.checks=[]

    def close(self):
        if self.closed:return
        self.closed=True
        atomic(self.ipc/'checks.json',self.checks)
        (self.ipc/'stop.request').write_text('Research case complete',encoding='utf8')
        try:
            self.completion=self.worker.wait(self.ipc/'completed.json',8)
            if getattr(self,'_case_failed',False):
                # Stopping a deliberately failed case during a pending choice
                # can be caught by the engine and return normally. Preserve
                # the primary assertion and retire on every failed case,
                # regardless of Java's completion envelope.
                self.worker.poison();return
            if self.completion['status']!='completed' or self.completion['session']!=self.session:
                raise RuntimeError('Worker did not complete the expected session')
            self.worker.retired=not self.completion['reusable']
        except BaseException:
            self.worker.poison();raise


class WarmPool:
    def __init__(self, folder, maximum=25):
        self.folder=folder;self.maximum=maximum;self.worker=None;self.generations=[];self.last_engine=None;self.engine_serial=0
        folder.mkdir(parents=True,exist_ok=False)

    def __enter__(self):return self
    def __exit__(self,*_):self.close()

    def ensure_worker(self):
        if self.worker and (self.worker.retired or self.worker.poisoned or self.worker.process.poll() is not None):
            self.worker.close();self.worker=None
        if self.worker is None:
            self.worker=Worker(self.folder/('worker-'+str(len(self.generations)+1)),self.maximum)
            self.generations.append(dict(path=str(self.worker.folder),**self.worker.ready))
            atomic(self.folder/'generations.json',self.generations)
        return self.worker

    def engine(self,scenario,**settings):
        self.ensure_worker()
        return self.engine_existing(self.worker,scenario,**settings)

    def engine_existing(self,worker,scenario,**settings):
        if worker is not self.worker or worker.retired or worker.poisoned or worker.process.poll() is not None:
            raise RuntimeError('Research worker was lost before case submission; restart on the next case')
        engine=WarmEngine(self.worker,scenario,**settings);self.last_engine=engine;self.engine_serial+=1;return engine

    def execute(self,case,timeout,schema=1):
        if schema==2:
            from card_batch_scenario import execute
        else:
            from card_batch_case import execute
        # Initialization is separately bounded by Worker.wait(ready,45). Start
        # the case watchdog only after the worker exists, so it can always
        # terminate the exact owned process rather than racing construction.
        try:current=self.ensure_worker()
        except Exception as error:return dict(status='failed',category='infrastructure',error='Worker startup: '+repr(error),checks=0)
        current.active_ipc=None
        expired=threading.Event()
        def abort():
            expired.set()
            current.poison()
        timer=threading.Timer(timeout,abort);timer.daemon=True
        start=self.engine_serial;timer.start()
        try:
            try:result=execute(case,engine_factory=lambda scenario,**settings:self.engine_existing(current,scenario,**settings))
            except Exception as error:
                result=dict(status='failed',category='infrastructure',error=repr(error),checks=0)
            if expired.is_set():result.update(status='failed',category='timeout',error='Bounded warm-case timeout; owned worker stopped')
            if self.engine_serial>start:
                e=self.last_engine
                result['evidence']=str(e.ipc)
                result['worker']=dict(pid=e.process.pid,token=e.worker.ready['worker'],completion=getattr(e,'completion',None))
            elif current.active_ipc:
                result['evidence']=str(current.active_ipc)
            return result
        finally:
            timer.cancel();timer.join()

    def close(self):
        if self.worker:self.worker.close();self.worker=None
