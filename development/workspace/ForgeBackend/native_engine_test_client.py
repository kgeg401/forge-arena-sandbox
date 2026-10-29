"""One persistent shipped Arena parser/adapter session for a headless Forge game.

Only the native handler submits valid gameplay actions. Independent malformed
backend-input checks remain in engine_test_client/verify_shared_choices.
"""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from engine_test_client import Engine
from headless_resources import process_flags
from runtime_paths import ROOT


class NativeEngine(Engine):
    def __init__(self,scenario='card-family',*,worker,managed,fixture,**settings):
        if (ROOT/'native-lab/MTGA.exe').exists() or json.loads((ROOT/'native-lab/bridge-card-manifest.json').read_text(encoding="utf-8-sig")).get('researchOnly') is not True:
            raise ValueError('Persistent native tests require an isolated research runtime')
        super().__init__(scenario,**settings)
        self.native_folder=self.ipc/'native-worker'
        self.native_log=(self.ipc/'native-worker.log').open('w',encoding='utf8')
        self.native_process=None
        try:
            self.native_process=subprocess.Popen(['dotnet',str(worker),str(managed),str(ROOT/'native-lab'),str(self.ipc),str(fixture)],stdout=self.native_log,stderr=subprocess.STDOUT,creationflags=process_flags())
            self.native_status=self.native_wait(self.native_folder/'ready.json',20)
            self.state=self.native_status['state']
        except BaseException:
            self.close();raise

    def native_wait(self,path,seconds=25):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            try:return json.loads(path.read_text(encoding='utf8'))
            except (FileNotFoundError,PermissionError,json.JSONDecodeError):pass
            if self.native_process and self.native_process.poll() is not None:
                raise RuntimeError('Native worker exited: '+(self.ipc/'native-worker.log').read_text(encoding='utf8')[-4000:])
            if self.process.poll() is not None:raise RuntimeError('Forge rules owner exited: '+(self.ipc/'engine.log').read_text(encoding='utf8',errors='replace')[-4000:])
            time.sleep(.02)
        raise TimeoutError(str(path))

    def native_call(self,op,forgeId=0,**fields):
        status=self.native_status
        request=dict(id=uuid.uuid4().hex,worker=status['worker'],session=self.session,nativeStateId=status['nativeStateId'],nativeMessageId=status['nativeMessageId'],op=op,forgeId=forgeId);request.update(fields)
        path=self.native_folder/'requests'/(request['id']+'.json');temporary=path.with_suffix('.pending');temporary.write_text(json.dumps(request),encoding='utf8');temporary.replace(path)
        reply=self.native_wait(self.native_folder/'responses'/path.name)
        if reply.get('worker')==status['worker'] and reply.get('session')==self.session and 'state' in reply:
            self.native_status=reply;self.state=reply['state']
        return reply

    def begin(self,op,forgeId=0,**fields):
        reply=self.native_call(op,forgeId,**fields)
        if not reply.get('accepted'):raise RuntimeError('Native request rejected: '+str(reply.get('reason') or reply.get('gap')))
        if not reply.get('forgeRequestId'):raise RuntimeError('Native handler did not create a Forge request')
        return reply['forgeRequestId']

    def send(self,op,forgeId=0,**fields):
        reply=self.native_call(op,forgeId,**fields)
        if not reply.get('accepted'):return dict(id=reply['id'],accepted=False,reason=reply.get('reason') or reply.get('gap'),state=self.state,rejectionLayer='native-worker')
        return self.finish(reply['forgeRequestId'])

    def close(self):
        try:
            if getattr(self,'native_process',None):
                self.native_folder.mkdir(exist_ok=True);(self.native_folder/'stop.request').write_text('Bounded headless native test complete')
                try:self.native_process.wait(timeout=5)
                except subprocess.TimeoutExpired:self.native_process.terminate();self.native_process.wait(timeout=5)
        finally:
            if hasattr(self,'native_log'):self.native_log.close()
            super().close()
