"""Actual private action-worker composition for observation-boundary controls.

This fixture never claims native PACKAGE construction: its authorized callback
runs one real owned Python child and finishes with a typed controlled failure.
The callback's actual current receiver context and capability are still required.
"""

ACTOR = r'''
import json, os, sys, time
from pathlib import Path
from types import SimpleNamespace
from literate_ai.action_worker import main
from literate_ai.adapters.action_dispatch_wire import ActionWireError
from literate_ai.adapters.action_dispatch_wire import record_identity
from literate_ai.adapters.action_retained_unit_package_worker import (
    ConfiguredRetainedUnitPackageWorker,
)
from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.worker_telemetry_owner import open_worker_telemetry_publisher
from literate_ai.adapters.worker_telemetry_relay import start_worker_telemetry_relay
from literate_ai.contracts import ContentIdentity
from literate_ai.contracts.execution_dispatch import ExecutionWorker

settings = Path(sys.argv[1])
registered = settings.read_bytes()
v = json.loads(registered)
os.environ['LITAI_STATE_DIR'] = v['state']
if '--observe-telemetry' in sys.argv[2:]:
    # The selected private wrapper routes observations before constructing any
    # lifecycle adapter, publisher, CAS or workspace owner.
    raise SystemExit(main(['--cas',v['cas'],'--workspace',v['workspace'],
        '--telemetry-configuration',v['telemetry'],*sys.argv[2:]]))
def current():
    if (settings.read_bytes() != registered
            or Path(v['authority']).read_bytes() != b'approved'):
        raise ValueError('fixture private authority changed')
def execute(context):
    context.require_current()
    operation = context.request.identity.digest
    control = Path(v['control'])
    instance = os.environ.get('TELEMETRY_ACTOR_INSTANCE','0')
    started, release = control / (operation+'-'+instance), control / 'release'
    if v.get('protected_parent'):
        from literate_ai.adapters import retained_receiver_attempt as attempts
        from literate_ai.adapters import worker_telemetry_reservation as observations
        fault = v.get('observer_startup_fault')
        def unavailable_event():
            failed = control / ('allocation-failed-'+instance)
            failed.write_bytes(b'actualstdlibboundary')
            raise OSError('controlled synchronization allocation unavailable')
        # Only substitute the external stdlib synchronization-allocation boundary,
        # inside a real action-worker/canonical parent flow. No native proof is made.
        if fault in ('context','legacy'):
            attempts.threading = SimpleNamespace(Event=unavailable_event)
        elif fault == 'observer':
            observations.threading = SimpleNamespace(Event=unavailable_event)
        native_mode = v.get('native_parent')
        with attempts.reserve_retained_receiver_attempt(
            settings,context.request,record_identity(registered),context.deadline,
            preflight=current,
            observation_publisher=None
                if fault=='legacy' or native_mode=='none' else publisher,
        ) as parent:
            parent.require_current()
            if native_mode:
                import errno
                from literate_ai.adapters import freebsd_owned_attempt as owned
                actual_os,actual_process=owned.os,owned.subprocess
                actual_selectors=owned.selectors
                observed_pipe=[]
                class NativeIo:
                    def __getattr__(self,name):return getattr(actual_os,name)
                    def pipe(self):
                        pair=actual_os.pipe()
                        self.calls=getattr(self,'calls',0)+1
                        if self.calls==2:observed_pipe.extend(pair)
                        return pair
                    def read(self,fd,size):
                        if observed_pipe and fd==observed_pipe[0]:
                            if native_mode=='read-error':
                                (control/'read-error').write_bytes(b'actual-pipe-read')
                                raise OSError(errno.EIO,'controlled pipe I/O error')
                        return actual_os.read(fd,size)
                class SlowSelector:
                    def __init__(self):self.actual=actual_selectors.DefaultSelector()
                    def __getattr__(self,name):return getattr(self.actual,name)
                    def select(self,timeout):
                        ready=self.actual.select(timeout)
                        if native_mode=='full' and observed_pipe:
                            retained=[v for v in ready if v[0].fd!=observed_pipe[0]]
                            if ready and not retained:time.sleep(min(timeout,.05))
                            return retained
                        return ready
                class NativeProcess:
                    def __getattr__(self,name):return getattr(actual_process,name)
                    def Popen(self,*args,**kwargs):
                        # Mutate only the actual external observation pipe at the
                        # process-launch boundary; never fabricate a native frame.
                        if observed_pipe and native_mode=='corrupt':
                            actual_os.write(observed_pipe[1],b'not-a-native-frame\n')
                        if observed_pipe and native_mode=='full':
                            for _ in range(4096):
                                try:actual_os.write(observed_pipe[1],b'x'*512)
                                except BlockingIOError:
                                    (control/'pipe-full').write_bytes(b'actual-EAGAIN')
                                    break
                            else:raise RuntimeError('observation pipe was not bounded')
                        return actual_process.Popen(*args,**kwargs)
                owned.os=NativeIo()
                owned.subprocess=NativeProcess()
                owned.selectors=SimpleNamespace(
                    DefaultSelector=SlowSelector,EVENT_READ=actual_selectors.EVENT_READ
                )
                child_code="""import json,os,pathlib,sys,time
from literate_ai.adapters.freebsd_owned_attempt import OwnedFreeBsdChild
native=OwnedFreeBsdChild();native.require_current()
pathlib.Path(sys.argv[1]).write_text(json.dumps({'actor':os.getppid(),'child':os.getpid()}))
end=time.monotonic()+40
while not pathlib.Path(sys.argv[2]).is_file():
 native.require_current()
 if time.monotonic()>=end:raise RuntimeError('native fixture barrier expired')
 time.sleep(.02)
print('native-telemetry-result')
"""
                if v.get('native_resources'):
                    child_code=r"""import json,os,pathlib,subprocess,sys,time
from literate_ai.adapters.freebsd_owned_attempt import OwnedFreeBsdChild
native=OwnedFreeBsdChild();native.require_current()
control=pathlib.Path(sys.argv[1]).parent
memory_code=(
 'import pathlib,sys,time\n'
 'block=bytearray(160*1024*1024)\n'
 'for i in range(0,len(block),4096):block[i]=1\n'
 'until=time.process_time()+1.5\n'
 'while time.process_time()<until:sum(range(20000))\n'
 "pathlib.Path(sys.argv[1]).write_bytes(b'actual-resident-child')\n"
 'until=time.monotonic()+30\n'
 'while not pathlib.Path(sys.argv[2]).is_file():\n'
 " if time.monotonic()>=until:raise RuntimeError('memory-child-control-expired')\n"
 ' time.sleep(.02)\n'
)
child=subprocess.Popen([sys.executable,'-B','-c',memory_code,
 str(control/'resource-child-ready'),str(control/'release-resource-child')])
pathlib.Path(sys.argv[1]).write_text(json.dumps({'actor':os.getppid(),'child':os.getpid()}))
end=time.monotonic()+40
reaped=False
while not pathlib.Path(sys.argv[2]).is_file():
 native.require_current()
 if child.poll() is not None and not reaped:
  if child.wait()!=0:raise RuntimeError('actual resource child failed')
  (control/'resource-child-reaped').write_bytes(b'actual-wait-completed')
  reaped=True
 if time.monotonic()>=end:raise RuntimeError('native fixture barrier expired')
 # Keep parent CPU small so a lost reaped-child counter cannot be masked.
 sum(range(5000))
 time.sleep(.02)
if not reaped:
 if child.wait(timeout=5)!=0:raise RuntimeError('actual resource child failed')
print('native-telemetry-result')
"""
                feed=None
                if native_mode!='none':
                    feed=publisher.native_feed_for_actual_parent(parent)
                proof=None
                try:
                    result=owned.run_owned_freebsd_attempt(
                        [sys.executable,'-B','-c',child_code,str(started),
                         str(control/'release-native')],
                        cwd=Path(v['workspace']),staging_root=Path(v['workspace']),
                        environment=dict(os.environ),expires_at=context.deadline.expires_at,
                        admission_guard=parent.require_current,
                        cancelled=lambda:(control/'cancel-native').is_file(),
                        stdout_limit_bytes=4096,stderr_limit_bytes=4096,
                        observation_feed=feed,
                    )
                    proof={'returncode':result.returncode,'stdout':result.stdout.decode(),
                           'guardian_pid':result.guardian_pid,
                           'response':json.loads(result.recovery_frame)}
                except owned.FreeBsdOwnedAttemptError as error:
                    proof={'error':error.reason,'guardian_pid':error.guardian_pid,
                           'cleanup_verified':error.cleanup_verified,
                           'quarantine_required':error.quarantine_required}
                    if not error.cleanup_verified:raise
                finally:
                    owned.os,owned.subprocess=actual_os,actual_process
                    owned.selectors=actual_selectors
                (control/('native-result-'+instance)).write_text(json.dumps(proof))
                # Keep the ORIGINAL protected parent alive after real native
                # cleanup. A query must not reconstruct its ended native runner.
                end=time.monotonic()+15
                while not release.is_file():
                    parent.require_current()
                    if time.monotonic()>=end:raise RuntimeError('parent hold expired')
                    time.sleep(.02)
                parent.release_after_native_empty()
                raise ActionWireError(
                    'fixture.telemetry_parent_finished','controlled native fixture end'
                )
            started.write_text(json.dumps({'actor':os.getpid(),'parent_reserved':True}))
            end=time.monotonic()+40
            while not release.is_file():
                parent.require_current()
                context.deadline.remaining()
                if time.monotonic()>=end:
                    raise RuntimeError('fixture parent barrier expired')
                time.sleep(.02)
            context.require_current()
            # No native attempt was launched; retain the real reservation marker
            # on this controlled failure. Never invent a native empty proof.
            raise ActionWireError(
                'fixture.telemetry_parent_finished','controlled pre-native end'
            )
    code = """import json,os,pathlib,sys,time
pathlib.Path(sys.argv[1]).write_text(json.dumps({'actor':os.getppid(),'child':os.getpid()}))
end=time.monotonic()+40
while not pathlib.Path(sys.argv[2]).is_file():
 if time.monotonic()>=end:raise RuntimeError('fixture barrier expired')
 time.sleep(.02)
print('telemetry-private-stdout')
"""
    result = run_bounded_process(
        [sys.executable,'-B','-c',code,str(started),str(release),'telemetry-private-argv'],
        cwd=Path(v['workspace']),environment=dict(os.environ,TELEMETRY_PRIVATE_SECRET='telemetry-private-environment'),
        timeout_seconds=min(45,context.deadline.remaining()),stdout_limit_bytes=4096,stderr_limit_bytes=4096,
        error_prefix='fixture.telemetry-child',terminate_descendants=True,trace=False,
    )
    if result.returncode:raise RuntimeError('fixture owned child refused')
    context.require_current()
    raise ActionWireError(
        'fixture.telemetry_finished','controlled fixture end; no native PACKAGE result'
    )
i = ContentIdentity.parse_uri(v['identity'])
worker = ConfiguredRetainedUnitPackageWorker(
    ExecutionWorker.from_dict(v['worker']),ContentIdentity.parse_uri(v['catalog_identity']),
    i,i,i,v['input'].encode(),execute,current,poll_guard=current,
)
publisher = relay = None
if '--describe' not in sys.argv[2:]:
    if v.get('startup_race')=='initialization' and os.environ.get(
        'TELEMETRY_ACTOR_INSTANCE','0'
    )=='0':
        from literate_ai.adapters import worker_telemetry_namespace as namespace
        actual_namespace_os=namespace.os
        class PausedMarkerIo:
            paused=False
            def __getattr__(self,name):return getattr(actual_namespace_os,name)
            def pwrite(self,fd,raw,offset):
                if (not self.paused
                        and b'private-worker-telemetry-owner-slot@1' in raw):
                    self.paused=True
                    control=Path(v['control'])
                    (control/'init-marker-held').write_bytes(b'actual-pwrite-boundary')
                    end=time.monotonic()+15
                    while not (control/'finish-marker').is_file():
                        if time.monotonic()>=end:
                            raise OSError('fixture publication barrier expired')
                        time.sleep(.01)
                return actual_namespace_os.pwrite(fd,raw,offset)
        namespace.os=PausedMarkerIo()
    publisher = open_worker_telemetry_publisher(Path(v['telemetry']))
    relay = start_worker_telemetry_relay(publisher)
try:
    status = main(['--cas',v['cas'],'--workspace',v['workspace'],*sys.argv[2:]],
                  package_worker=worker,
                  telemetry_publisher=None if v.get('protected_parent') else publisher)
finally:
    if relay is not None:relay.close()
    if publisher is not None:publisher.close()
raise SystemExit(status)
'''

# Real native crypto is delegated unchanged. Only its completion is held at an
# external dependency boundary to schedule a genuine competing receiver.
GATED_QUERY = r"""
import sys,time
from pathlib import Path
from types import SimpleNamespace
from literate_ai.security.evidence import ed25519
actual_backend = ed25519.Ed25519PrivateKey
control = Path(sys.argv[1])
class GatedKey:
    def __init__(self,key):self.key=key
    def public_key(self):return self.key.public_key()
    def sign(self,message):
        signature=self.key.sign(message)
        if b'literate-ai/authenticated-worker-telemetry-response@2' in message:
            (control/'response-signed').write_bytes(b'genuine-native-signature-produced')
            end=time.monotonic()+15
            while not (control/'release-signature').is_file():
                if time.monotonic()>=end:
                    raise RuntimeError('fixture crypto barrier expired')
                time.sleep(.01)
        return signature
def load(raw):return GatedKey(actual_backend.from_private_bytes(raw))
ed25519.Ed25519PrivateKey=SimpleNamespace(from_private_bytes=load)
from literate_ai.worker_telemetry_receiver import main
raise SystemExit(main(['--configuration',sys.argv[2]]))
"""
