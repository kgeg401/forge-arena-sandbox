"""Conservative resource bounds for developer rules tests, never the game."""
import os
import subprocess


def java_options():
    heap = int(os.environ.get('FORGE_ARENA_TEST_HEAP_MB', '1024'))
    threads = int(os.environ.get('FORGE_ARENA_TEST_THREADS', '2'))
    if not 256 <= heap <= 2048 or not 1 <= threads <= 4:
        raise ValueError('Headless test bounds: 256-2048 MiB heap and 1-4 Java processors')
    return [f'-Xmx{heap}m', f'-XX:ActiveProcessorCount={threads}', '-Djava.awt.headless=false', '-Dfile.encoding=UTF-8']


def process_flags():
    return (subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name == 'nt' else 0


def run_owned(command,*,timeout,**options):
    """A bounded test subprocess owns its Windows descendants until completion.

    Closing this existing kill-on-close job cannot target user games or other
    jobs. It also closes on successful completion to retire leaked helpers.
    """
    from run_background_validation import ChildJob
    job=ChildJob();process=None
    try:
        process=subprocess.Popen(command,creationflags=process_flags(),**options)
        job.attach(process)
        return subprocess.CompletedProcess(command,process.wait(timeout=timeout))
    finally:
        job.close()
        if process is not None and process.poll() is None:
            process.terminate();process.wait(timeout=5)
