import os, io, csv, sys, requests, numpy as np
from PIL import Image
from rembg import remove, new_session

SHEET='https://docs.google.com/spreadsheets/d/e/2PACX-1vT-eb1DbbZOxOCyBB8pkFrsVRQ7Iaicq9eI2pTVMl8BbIyRxnpkANfydeKHSnWtJ6kYSfx3d5gNijba/pub?gid=0&single=true&output=csv'
FEED='https://scottsfavs.com/feed.csv'
IMG='https://scottsfavs.com/img/'
UPLOAD=os.environ['UPLOAD_URL']; TOKEN=os.environ['UPLOAD_TOKEN']
session=new_session('u2netp')

def rows(url):
    t=requests.get(url,timeout=30).text
    return list(csv.reader(io.StringIO(t)))

def make_cutout(img_bytes):
    src=Image.open(io.BytesIO(img_bytes)).convert('RGB')
    out=remove(src, session=session).convert('RGBA')
    a=np.asarray(out).astype(np.float32); al=a[...,3]/255.0
    m=(al>0.01)&(al<0.99)                       # decontaminate edge pixels (unpremultiply vs white)
    for c in range(3):
        ch=a[...,c]; ch[m]=np.clip((ch[m]-(1-al[m])*255)/np.maximum(al[m],1e-3),0,255); a[...,c]=ch
    res=Image.fromarray(a.astype('uint8'),'RGBA')
    bb=res.getbbox()
    if bb: res=res.crop(bb)
    w,h=res.size; s=600/max(w,h)
    if s<1: res=res.resize((max(1,int(w*s)),max(1,int(h*s))),Image.LANCZOS)
    buf=io.BytesIO(); res.save(buf,'PNG'); return buf.getvalue()

# map asin -> raw image url from the live feed
feed=rows(FEED); fh=[c.strip() for c in feed[0]]
ai=fh.index('ASIN'); ii=fh.index('image_url')
imgmap={}
for r in feed[1:]:
    if ai<len(r) and r[ai].strip(): imgmap[r[ai].strip()]=(r[ii].strip() if ii<len(r) else '')

# which ASINs are missing a cutout?
missing=[]
for asin,url in imgmap.items():
    try:
        if requests.head(IMG+asin+'.png',timeout=15).status_code==200: continue
    except Exception: pass
    if url.startswith('http') and '/img/' not in url:   # url is a raw amazon image, not already a cutout
        missing.append((asin,url))

print(f"{len(imgmap)} products, {len(missing)} missing cutouts: {[a for a,_ in missing]}")
done=0
for asin,url in missing:
    try:
        png=make_cutout(requests.get(url,timeout=30).content)
        r=requests.post(UPLOAD,data={'token':TOKEN,'asin':asin},files={'png':(asin+'.png',png,'image/png')},timeout=60)
        print(f"  {asin}: {len(png)//1024}KB -> {r.status_code} {r.text[:40]}")
        if r.status_code==200: done+=1
    except Exception as e:
        print(f"  {asin}: ERROR {e}")
print(f"done: {done}/{len(missing)} uploaded")
