"""Conservative resource bounds for developer rules tests, never the game."""
import os
import subprocess


def java_options():
    heap = int(os.environ.get('FORGE_ARENA_TEST_HEAP_MB', '1024'))
    threads = int(os.environ.get('FORGE_ARENA_TEST_THREADS', '2'))
    if not 256 <= heap <= 2048 or not 1 <= threads <= 4:
        raise ValueError('Headless test bounds: 256-2048 MiB heap and 1-4 Java processors')
    return [f'-Xmx{heap}m', f'-XX:ActiveProcessorCount={threads}', '-Djava.awt.headless=false']


def process_flags():
    return (subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name == 'nt' else 0
