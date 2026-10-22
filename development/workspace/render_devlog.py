from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import subprocess,json
root=Path(r'D:\GAMES\CodexAssets\ForgeArenaSandbox\devlogs\2026-10-20-mana');work=root/'edit';work.mkdir(exist_ok=True)
segments=[
 ('native-mana-take1.mp4',5,17,'Forge x Arena: land play and mana','Native card clicks; Forge validates and resolves each action.'),
 ('native-second-turn.mp4',0,12,'New turn, new land play','Plains untapped; a drawn card and a renewed land allowance.'),
 ('native-second-turn.mp4',12,8,'Second land on the battlefield','Forge allows the next land; Arena groups the matching Plains.'),
 ('native-final.mp4',23,10,'Cast, stack, resolve','Savannah Lions spends white mana and resolves through Forge.'),
 ('native-final.mp4',33,7,'Arena presents the result','The native client displays the resolved 2/1 creature.'),
 ('native-final.mp4',40,5,'Still a limited playable test','Combat, general card support and game sound are unfinished.')]
(root/'devlog-edit.json').write_text(json.dumps({'segments':segments,'audio':'Captured game-process audio retained; native sound initialization incomplete.','originals':'All original MKV, raw audio and muxed MP4 takes retained.'},indent=2))
font=ImageFont.truetype(r'C:\Windows\Fonts\segoeuib.ttf',30);small=ImageFont.truetype(r'C:\Windows\Fonts\segoeui.ttf',24)
for i,(clip,start,duration,title,caption) in enumerate(segments):
 im=Image.new('RGBA',(1280,720));d=ImageDraw.Draw(im);d.rectangle((0,0,1280,106),fill=(7,12,20,228));d.rectangle((0,103,1280,106),fill=(230,154,64,255))
 d.text((24,10),f'{i+1:02d}  |  {title}',font=font,fill='white');d.text((24,53),caption,font=small,fill=(220,226,232,255))
 overlay=work/f'caption-{i}.png';im.save(overlay);out=work/f'segment-{i}.mp4'
 command=['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(start),'-t',str(duration),'-i',str(root/clip),'-loop','1','-i',str(overlay),'-filter_complex','[0:v]scale=1280:720,setsar=1,fps=30[base];[base][1:v]overlay=0:0:shortest=1[v]','-map','[v]','-map','0:a?','-t',str(duration),'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-ar','48000','-ac','2',str(out)]
 subprocess.run(command,check=True);print(f'Rendered segment {i+1}',flush=True)
listing=work/'concat.txt';listing.write_text('\n'.join("file '"+str(work/f'segment-{i}.mp4').replace('\\','/')+"'" for i in range(len(segments))))
master=root/'Forge-Arena-Devlog-01-Mana-Turns-Casting.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(master)],check=True)
chat=root/'Forge-Arena-Devlog-01-chat.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(master),'-c:v','libx264','-preset','fast','-b:v','780k','-maxrate','900k','-bufsize','1800k','-pix_fmt','yuv420p','-c:a','aac','-b:a','64k','-movflags','+faststart',str(chat)],check=True)
for p in [master,chat]:
 info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)]));subprocess.run(['ffmpeg','-hide_banner','-v','error','-i',str(p),'-f','null','-'],check=True)
 (root/(p.stem+'-validation.json')).write_text(json.dumps({'file':str(p),'bytes':p.stat().st_size,'decode':'passed','probe':info},indent=2));print(p,p.stat().st_size,info['format']['duration'],flush=True)
assert chat.stat().st_size<9_000_000
