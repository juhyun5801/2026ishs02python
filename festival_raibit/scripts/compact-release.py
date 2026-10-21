"""Append a smaller transfer ZIP; preserve the existing release and original downloads."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPO=os.environ['REPOSITORY']
TOKEN=os.environ['GITHUB_TOKEN']
VERSION='2.1.16'
BASE='https://api.github.com/repos/'+REPO
HEADERS={'Authorization':'Bearer '+TOKEN,'Accept':'application/vnd.github+json','User-Agent':'raibit-compact-download'}
def api(path,data=None,method=None):
    body=None if data is None else json.dumps(data).encode()
    request=urllib.request.Request(BASE+path,data=body,headers=dict(HEADERS,**{'Content-Type':'application/json'}),method=method)
    with urllib.request.urlopen(request,timeout=60) as response:
        content=response.read()
        return json.loads(content) if content else None
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):
        return None
def fetch(path,file):
    accept='application/octet-stream' if path.startswith('/releases/assets/') else 'application/vnd.github+json'
    request=urllib.request.Request(BASE+path,headers=dict(HEADERS,Accept=accept))
    try:
        response=urllib.request.build_opener(NoRedirect).open(request,timeout=90)
    except urllib.error.HTTPError as error:
        if error.code!=302:
            raise
        location=error.headers['Location']
        host=urllib.parse.urlparse(location)
        assert host.scheme=='https' and any((host.hostname or '').endswith(domain) for domain in ['.githubusercontent.com','.blob.core.windows.net'])
        response=urllib.request.urlopen(location,timeout=120)
    with response,file.open('wb') as target:
        shutil.copyfileobj(response,target)
def sha(file):
    with file.open('rb') as source:
        return hashlib.file_digest(source,'sha256').hexdigest()

release=api('/releases/tags/festival-v'+VERSION)
assert not release['draft']
assets={a['name']:a for a in release['assets']}
folder=Path(tempfile.mkdtemp(prefix='raibit-compact-'))
payload=folder/'payload'
payload.mkdir()
for name in [f'raibitScoreboard-Windows-{VERSION}.exe',f'raibit-final-settings-{VERSION}.json']:
    asset=assets[name]
    fetch('/releases/assets/'+str(asset['id']),payload/name)
    assert asset['digest']=='sha256:'+sha(payload/name)
run=api('/actions/runs/39593049632')
assert run['conclusion']=='success'
artifacts=api('/actions/runs/39593049632/artifacts')['artifacts']
for arch,label,expected in [
    ('arm64','AppleSilicon','02bd8cd0e05dd80574f3337e832b12768df94bd58fd9283cc5710bb49ebb2ca8'),
    ('x64','Intel','a964b7e75b44c9748494e574b1b854f5124f8fc8fc557dc94a4b837923594a42')]:
    artifact=next(a for a in artifacts if a['name']=='raibitScoreboard-mac-'+arch and not a['expired'])
    archive=folder/(arch+'.zip')
    fetch('/actions/artifacts/'+str(artifact['id'])+'/zip',archive)
    if artifact.get('digest'):
        assert artifact['digest']=='sha256:'+sha(archive)
    target=payload/f'raibitScoreboard-Mac-{label}-{VERSION}.zip'
    with zipfile.ZipFile(archive) as content:
        member=next(n for n in content.namelist() if n.endswith(f'raibitScoreboard-{VERSION}-{arch}-mac.zip'))
        target.write_bytes(content.read(member))
    assert sha(target)==expected
    with zipfile.ZipFile(target) as content:
        assert content.testzip() is None
        assert stat.S_IMODE(content.getinfo('raibitScoreboard.app/Contents/MacOS/raibitScoreboard').external_attr>>16)&0o111
    print('Verified original Mac app ZIP: '+label,flush=True)
shutil.copyfile(Path(__file__).resolve().parent.parent/'COMPACT_RELEASE.txt',payload/'READ_ME_COMPACT_KO.txt')
files=sorted(payload.iterdir(),key=lambda p:p.name)
(payload/'SHA256-COMPACT.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in files),encoding='utf-8')
bundle=folder/f'raibitScoreboard-Compact-{VERSION}.zip'
with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as content:
    for file in sorted(payload.iterdir(),key=lambda p:p.name):
        info=zipfile.ZipInfo(f'raibitScoreboard-Compact-{VERSION}/'+file.name,(2026,10,21,0,0,0))
        info.create_system=3
        info.external_attr=0o100644<<16
        content.writestr(info,file.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
with zipfile.ZipFile(bundle) as content:
    assert content.testzip() is None
    for member in content.infolist():
        assert hashlib.sha256(content.read(member)).hexdigest()==sha(payload/Path(member.filename).name)
assert bundle.stat().st_size<286000000
checksum=folder/'SHA256-COMPACT-ZIP.txt'
checksum.write_text(sha(bundle)+'  '+bundle.name+'\n')
for file in [bundle,checksum]:
    old=next((a for a in api('/releases/'+str(release['id']))['assets'] if a['name']==file.name),None)
    if old:
        if old['state']=='uploaded' and old.get('digest')=='sha256:'+sha(file):
            continue
        assert old['state']!='uploaded','Refuse to overwrite an existing public file'
        api('/releases/assets/'+str(old['id']),method='DELETE')
    url='https://uploads.github.com/repos/'+REPO+'/releases/'+str(release['id'])+'/assets?name='+urllib.parse.quote(file.name)
    headers=dict(HEADERS,**{'Content-Type':'application/zip' if file.suffix=='.zip' else 'text/plain','Content-Length':str(file.stat().st_size)})
    with file.open('rb') as source:
        with urllib.request.urlopen(urllib.request.Request(url,data=source,headers=headers,method='POST'),timeout=180) as response:
            asset=json.load(response)
    assert asset['digest']=='sha256:'+sha(file)
    print(json.dumps({'file':file.name,'bytes':asset['size'],'sha256':sha(file),'url':asset['browser_download_url']}),flush=True)
body=api('/releases/'+str(release['id']))['body']
if bundle.name not in body:
    link='https://github.com/'+REPO+'/releases/download/festival-v'+VERSION+'/'+bundle.name
    intro=f'**더 작은 통합본: [{bundle.stat().st_size/1000000:.0f} MB 경량 ZIP]({link})** — 기존 389 MB보다 약 27% 작습니다. Windows 설치 없는 실행 파일과 Mac 원본 앱 ZIP을 포함합니다. 게임·점수·소리는 같습니다.\n\n'
    api('/releases/'+str(release['id']),{'body':intro+body},method='PATCH')
