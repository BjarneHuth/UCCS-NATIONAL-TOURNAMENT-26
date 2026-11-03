"""Read published regional snapshot; never pretend this is an official NCAA feed."""
import re
import requests
from bs4 import BeautifulSoup
URL='https://www.inkblotsports.com/d2stats/2627/mso/sr4.html'

def fetch_snapshot():
    r=requests.get(URL,timeout=25,headers={'User-Agent':'Mozilla/5.0 UCCS research simulator'})
    r.raise_for_status()
    soup=BeautifulSoup(r.text,'html.parser')
    text=soup.get_text(' ',strip=True)
    m=re.search(r'Data through\s+(November\s+\d+)',text,re.I)
    if not m:raise ValueError('Could not verify Inkblot snapshot date; no changes applied')
    date_label=m.group(1)
    if not re.search(r'November\s+([2-9]|[12]\d|30)\b',date_label):
        raise ValueError(f'Inkblot snapshot is stale ({date_label}); no changes applied')
    out={}
    for tr in soup.select('tr'):
        cells=tr.find_all(['td','th'],recursive=False)
        if len(cells)<5:continue
        a=cells[0].get_text(' ',strip=True)
        # The source uses a three-digit team ID in the first column, followed by name.
        idmatch=re.search(r'\b(\d{3})\b',a)
        if not idmatch:continue
        try:val=float(cells[3].get_text(' ',strip=True).replace(',',''))
        except ValueError:continue
        if not 20<=val<=100:continue
        name=re.sub(r'^\s*\d{3}\s*','',a).strip()
        out[name]=val
    if len(out)<40:raise ValueError(f'Only {len(out)} regional NPI rows parsed; no changes applied')
    return date_label,out
