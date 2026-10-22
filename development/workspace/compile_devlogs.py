"""Combine verified numbered dev logs without trimming any footage or audio."""
from pathlib import Path
import hashlib
import argparse
import json
import re
import subprocess

parser=argparse.ArgumentParser()
parser.add_argument('stem',nargs='?')
parser.add_argument('--from-chapter',type=int,default=1)
args=parser.parse_args()

root = Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\devlogs')
out = root / '2026-10-21-combat'
sources = sorted((p for p in root.glob('**/Forge-Arena-Devlog-*.mp4')
                  if re.match(r'Forge-Arena-Devlog-\d\d-', p.name) and not p.stem.endswith('-chat')),
                 key=lambda p: p.name)
numbers = [int(re.search(r'Devlog-(\d\d)-', p.name)[1]) for p in sources]
assert numbers == list(range(1, len(sources) + 1)), sources
assert 1 <= args.from_chapter <= len(sources)
sources=[p for p in sources if int(re.search(r'Devlog-(\d\d)-',p.name)[1])>=args.from_chapter]
assert sources

def run(args):
    subprocess.run(args, check=True)

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-show_chapters', '-of', 'json', str(path)]))

metadata = [';FFMETADATA1', 'title=Forge x Arena - development log',
            'comment=Local Forge sandbox in original Arena presentation. Earlier seeded slices progress to normal shuffled matches; each chapter states its scope.']
chapters = []
elapsed = 0
for p in sources:
    duration = float(probe(p)['format']['duration'])
    title = p.stem.removeprefix('Forge-Arena-Devlog-').replace('-', ' ')
    end = elapsed + duration
    metadata += ['[CHAPTER]', 'TIMEBASE=1/1000', f'START={round(elapsed*1000)}', f'END={round(end*1000)}', f'title={title}']
    chapters.append({'source': str(p), 'start': elapsed, 'duration': duration, 'title': title})
    elapsed = end
listing = out / 'combined-sources.txt'
listing.write_text('\n'.join("file '" + str(p).replace('\\', '/') + "'" for p in sources))
meta = out / 'combined-chapters.ffmeta'
meta.write_text('\n'.join(metadata))
stem = args.stem or f'Forge-Arena-Devlog-Combined-2026-10-21-{len(sources)}Chapters'
assert Path(stem).name == stem and not stem.endswith('.mp4')
master = out / (stem + '.mp4')
assert not master.exists(), 'Preserve the earlier video; choose a new output name.'
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(listing), '-i', str(meta), '-map_metadata', '1', '-map_chapters', '1', '-c', 'copy', '-movflags', '+faststart', str(master)])
print('Combined original-quality master', master.stat().st_size, flush=True)

# Keep every source second and its audio in a separate small attachment.
# The original-quality master and individual clips remain available locally.
chat = out / (master.stem + '-chat.mp4')
duration = float(probe(master)['format']['duration'])
audio_bitrate = 32_000 if duration < 1000 else 24_000
bitrate = int(8_350_000 * 8 / duration - audio_bitrate - 4_000)
assert bitrate > 12_000, 'Compilation is too long for one useful chat attachment.'
width, height, fps = (640,360,12) if bitrate >= 40_000 else (480,270,10) if bitrate >= 22_000 else (384,216,8)
common = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(master),
          '-vf', f'scale={width}:{height}:flags=lanczos,fps={fps}', '-c:v', 'libx264', '-preset', 'slow',
          '-b:v', str(bitrate), '-maxrate', str(bitrate*3), '-bufsize', str(bitrate*6),
          '-pix_fmt', 'yuv420p', '-passlogfile', str(out / 'combined-chat-pass')]
run(common + ['-pass', '1', '-an', '-f', 'null', 'NUL'])
run(common + ['-pass', '2', '-c:a', 'aac', '-b:a', str(audio_bitrate), '-ar', '48000', '-ac', '2',
              '-movflags', '+faststart', str(chat)])
assert chat.stat().st_size < 9_000_000
for p in (master, chat):
    info = probe(p)
    actual = float(info['format']['duration'])
    assert abs(actual - elapsed) < .5, (actual, elapsed)
    assert len(info['chapters']) == len(sources)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    assert video['codec_name'] == 'h264' and video['pix_fmt'] == 'yuv420p'
    assert next(s for s in info['streams'] if s['codec_type'] == 'audio')['codec_name'] == 'aac'
    run(['ffmpeg', '-hide_banner', '-v', 'error', '-i', str(p), '-f', 'null', '-'])
    with p.open('rb') as f:
        header = f.read(2_000_000)
    assert 0 <= header.find(b'moov') < header.find(b'mdat'), 'faststart box ordering'
    with p.open('rb') as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    report = {'file': str(p), 'bytes': p.stat().st_size, 'decode': 'passed', 'sha256': digest,
              'sourceDuration': elapsed, 'probe': info, 'chapters': chapters,
              'note': 'Chat copy reduces resolution/frame rate/bitrate; full duration and audio are retained.' if p == chat else 'Original-quality source streams concatenated; originals retained.'}
    (out / (p.stem + '-validation.json')).write_text(json.dumps(report, indent=2))
    print(p, p.stat().st_size, actual, flush=True)
