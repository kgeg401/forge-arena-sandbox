"""Render an evidence-backed edit manifest; preserve every source take."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess, json, sys

manifest=Path(sys.argv[1]).resolve(); spec=json.loads(manifest.read_text()); root=manifest.parent
work=root/(spec['name']+'-edit'); work.mkdir(exist_ok=True)
font=ImageFont.truetype(r'C:\Windows\Fonts\segoeuib.ttf',30)
small=ImageFont.truetype(r'C:\Windows\Fonts\segoeui.ttf',24)
for i, segment in enumerate(spec['segments']):
    im=Image.new('RGBA',(1280,720)); d=ImageDraw.Draw(im)
    d.rectangle((0,0,1280,106),fill=(7,12,20,228));d.rectangle((0,103,1280,106),fill=(230,154,64,255))
    d.text((24,10),f"{i+1:02d}  |  {segment['title']}",font=font,fill='white')
    d.text((24,53),segment['caption'],font=small,fill=(220,226,232,255))
    overlay=work/f'caption-{i}.png'; im.save(overlay)
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(segment['start']),'-t',str(segment['duration']),'-i',str(root/segment['clip']),'-loop','1','-i',str(overlay),'-filter_complex','[0:v]scale=1280:720,setsar=1,fps=30[base];[base][1:v]overlay=0:0:shortest=1[v]','-map','[v]','-map','0:a?','-t',str(segment['duration']),'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-ar','48000','-ac','2',str(work/f'segment-{i}.mp4')]
    subprocess.run(cmd,check=True);print(f'Rendered segment {i+1}',flush=True)
listing=work/'concat.txt';listing.write_text('\n'.join("file '"+str(work/f'segment-{i}.mp4').replace('\\','/')+"'" for i in range(len(spec['segments']))))
master=root/(spec['name']+'.mp4')
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(master)],check=True)
outputs=[master]
if master.stat().st_size>=9_000_000:
    duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(master)]))
    bitrate=int(8_400_000*8/duration-64_000)
    chat=root/(spec['name']+'-chat.mp4')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(master),'-c:v','libx264','-preset','fast','-b:v',str(bitrate),'-maxrate',str(bitrate),'-bufsize',str(bitrate*2),'-pix_fmt','yuv420p','-c:a','aac','-b:a','64k','-movflags','+faststart',str(chat)],check=True)
    assert chat.stat().st_size<9_000_000;outputs.append(chat)
for p in outputs:
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)]))
    subprocess.run(['ffmpeg','-hide_banner','-v','error','-i',str(p),'-f','null','-'],check=True)
    (root/(p.stem+'-validation.json')).write_text(json.dumps({'file':str(p),'bytes':p.stat().st_size,'decode':'passed','probe':info},indent=2))
    print(p,p.stat().st_size,info['format']['duration'],flush=True)
