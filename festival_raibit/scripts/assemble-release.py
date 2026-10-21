"""Create a deterministic transfer ZIP from already verified files in a draft release."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

TOKEN = os.environ['GITHUB_TOKEN']
REPO = os.environ['REPOSITORY']
RELEASE_ID = os.environ['RELEASE_ID']
assert RELEASE_ID.isdigit()
VERSION = json.loads((Path(__file__).resolve().parent.parent/'package.json').read_text())['version']
EXPECTED = [f'raibitScoreboard-Windows-{VERSION}.exe', f'raibitScoreboard-Windows-Setup-{VERSION}.exe',
            f'raibitScoreboard-Mac-AppleSilicon-{VERSION}.dmg',f'raibitScoreboard-Mac-Intel-{VERSION}.dmg',
            f'raibit-final-settings-{VERSION}.json','READ_ME_KO.md','VERIFIED.json','SHA256SUMS.txt']
HEADERS = {'Authorization':'Bearer '+TOKEN,'Accept':'application/vnd.github+json','User-Agent':'raibit-transfer-assembly'}
BASE = 'https://api.github.com/repos/'+REPO
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):
        return None
def api(suffix):
    with urllib.request.urlopen(urllib.request.Request(BASE+suffix,headers=HEADERS),timeout=60) as response:
        return json.load(response)
def digest(file):
    with file.open('rb') as source:
        return hashlib.file_digest(source,'sha256').hexdigest()
def download(asset,file):
    headers = dict(HEADERS,Accept='application/octet-stream')
    request=urllib.request.Request(BASE+'/releases/assets/'+str(asset['id']),headers=headers)
    try:
        response=urllib.request.build_opener(NoRedirect).open(request,timeout=60)
    except urllib.error.HTTPError as error:
        if error.code!=302:
            raise
        location=error.headers['Location']
        host=urllib.parse.urlparse(location)
        assert host.scheme=='https' and any((host.hostname or '').endswith(domain) for domain in ['.githubusercontent.com','.blob.core.windows.net'])
        response=urllib.request.urlopen(location,timeout=120)
    with response, file.open('wb') as target:
        while block:=response.read(1024*1024):
            target.write(block)
    assert file.stat().st_size==asset['size']
    assert asset['digest']=='sha256:'+digest(file)
    print('Downloaded and verified '+file.name,flush=True)

release=None
for attempt in range(90):
    release=api('/releases/'+RELEASE_ID)
    assert release['draft'] and release['tag_name']=='festival-v'+VERSION
    assets={a['name']:a for a in release['assets'] if a['state']=='uploaded'}
    if all(name in assets for name in EXPECTED):
        break
    if attempt%6==0:
        print('Waiting for verified individual files: '+', '.join(name for name in EXPECTED if name not in assets),flush=True)
    time.sleep(10)
else:
    raise RuntimeError('Individual release files did not finish uploading')

folder=Path(tempfile.mkdtemp(prefix='raibit-transfer-'))
for name in EXPECTED:
    download(assets[name],folder/name)
for line in (folder/'SHA256SUMS.txt').read_text().splitlines():
    checksum,name=line.split(maxsplit=1)
    assert Path(name).name==name and name in EXPECTED
    assert digest(folder/name)==checksum
settings=json.loads((folder/f'raibit-final-settings-{VERSION}.json').read_text())['settings']
assert (settings['score']['ref'],settings['score']['top'],settings['soundVolume'])==(35,3000,34)
verified=json.loads((folder/'VERIFIED.json').read_text())
assert verified['version']==VERSION and len(verified['mac'])==2 and verified['unitTestsPassed']==57
assert all(item['packagedAppSmokeTest'] for item in verified['mac'])

bundle=folder/f'raibitScoreboard-AllPlatforms-{VERSION}.zip'
files=sorted((folder/name for name in EXPECTED if name!='SHA256SUMS.txt'),key=lambda p:p.name)
with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as output:
    for file in files+[folder/'SHA256SUMS.txt']:
        info=zipfile.ZipInfo(f'raibitScoreboard-{VERSION}/'+file.name,(2026,10,21,0,0,0))
        info.create_system=3
        info.external_attr=0o100644<<16
        info.compress_type=zipfile.ZIP_STORED
        output.writestr(info,file.read_bytes())
with zipfile.ZipFile(bundle) as content:
    assert content.testzip() is None
checksum_file=folder/'SHA256-AllPlatforms.txt'
checksum_file.write_text(digest(bundle)+'  '+bundle.name+'\n')
for file in [bundle,checksum_file]:
    checksum=digest(file)
    current=api('/releases/'+RELEASE_ID)
    old=next((a for a in current['assets'] if a['name']==file.name),None)
    if old:
        if old['state']=='uploaded' and old.get('digest')=='sha256:'+checksum:
            continue
        request=urllib.request.Request(BASE+'/releases/assets/'+str(old['id']),headers=HEADERS,method='DELETE')
        urllib.request.urlopen(request,timeout=60).close()
    url='https://uploads.github.com/repos/'+REPO+'/releases/'+RELEASE_ID+'/assets?name='+urllib.parse.quote(file.name)
    headers=dict(HEADERS,**{'Content-Type':'application/zip' if file.suffix=='.zip' else 'text/plain','Content-Length':str(file.stat().st_size)})
    with file.open('rb') as source:
        request=urllib.request.Request(url,data=source,headers=headers,method='POST')
        with urllib.request.urlopen(request,timeout=180) as response:
            asset=json.load(response)
    assert asset['digest']=='sha256:'+checksum and asset['size']==file.stat().st_size
    print('Uploaded and verified '+file.name+' sha256='+checksum,flush=True)
print('Transfer ZIP assembled. Release remains draft until final review.',flush=True)
