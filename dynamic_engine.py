"""Experimental, baseline-anchored opponent network model; NOT official NCAA NPI."""
from collections import defaultdict, Counter
from datetime import date, timedelta
import requests

ALIASES={'Colorado Springs':'UCCS','UC-Colo. Springs':'UCCS','UC Colorado Springs':'UCCS','S. Dakota Mines':'South Dakota Mines','South Dakota School of Mines':'South Dakota Mines','Fort Lewis College':'Fort Lewis','CSU-Pueblo':'CSU Pueblo','Cal St. Pueblo':'CSU Pueblo','Cal St. L.A.':'Cal State Los Angeles'}
def name(s):
 s=' '.join(str(s or '').split());return ALIASES.get(s,s)
def parse_day(payload,day):
 if not isinstance(payload,dict) or not isinstance(payload.get('games'),list):raise ValueError('Unexpected scoreboard response')
 out=[]; skipped=0
 for item in payload['games']:
  g=item.get('game',item)
  if not isinstance(g,dict):continue
  state=str(g.get('gameState') or g.get('state') or g.get('status') or '').lower()
  if not any(x in state for x in ('final','complete','closed')):continue
  def team(side):
   x=g.get(side) or {}; names=x.get('names') or {}
   n=(names.get('short') or names.get('full')) if isinstance(names,dict) else None
   n=n or x.get('nameShort') or x.get('name') or x.get('displayName')
   try:score=int(x.get('score'))
   except (ValueError,TypeError):score=None
   return name(n),score
  away,sa=team('away');home,sh=team('home')
  if not away or not home or sa is None or sh is None or away==home:skipped+=1;continue
  neutral=bool(g.get('neutralSite') or g.get('isNeutral') or g.get('neutral'))
  out.append({'date':day.isoformat(),'id':str(g.get('gameID') or g.get('id') or ''),'a':away,'b':home,'winner':away if sa>sh else home if sh>sa else 'TIE','venue':'N' if neutral else 'B','score_a':sa,'score_b':sh,'neutral_confirmed':neutral})
 return out,skipped

def fetch_season(start=date(2026,8,1),end=None):
 end=min(end or date.today(),date(2026,12,31))
 if end<start:return [],{'failed_dates':[],'skipped':0,'days':0}
 allrows=[];failed=[];skipped=0;day=start;days=0
 sess=requests.Session()
 while day<=end:
  url=f'https://ncaa-api.henrygd.me/scoreboard/soccer-men/d2/{day:%Y/%m/%d}/all-conf'
  try:
   response=sess.get(url,timeout=12,headers={'User-Agent':'UCCS-NPI-Research/1.0'});response.raise_for_status()
   rows,n=parse_day(response.json(),day);allrows+=rows;skipped+=n
  except Exception as exc:failed.append(f'{day.isoformat()}: {str(exc)[:90]}')
  days+=1;day+=timedelta(days=1)
 unique={}
 for row in allrows:
  k=row['id'] or (row['date'],tuple(sorted((row['a'],row['b']))))
  unique[k]=row
 return list(unique.values()),{'failed_dates':failed,'skipped':skipped,'days':days}

def estimate(rows,baseline,iterations=100):
 """Simplified iterative opponent rating. NOT NCAA NPI. Handles ties/venue and trimmed wins approximately."""
 played=defaultdict(list)
 for r in rows:
  a,b,w,v=r['a'],r['b'],r['winner'],r['venue']
  if not a or not b or a==b:continue
  played[a].append((b,1 if w==a else .5 if w=='TIE' else 0,'H' if v=='A' else 'A' if v=='B' else 'N'))
  played[b].append((a,1 if w==b else .5 if w=='TIE' else 0,'H' if v=='B' else 'A' if v=='A' else 'N'))
 vals={t:float(v) for t,v in baseline.items()}
 for t in played:vals.setdefault(t,50.)
 for _ in range(iterations):
  updated={}
  for t,games in played.items():
   wins=[];others=[]
   for opp,result,loc in games:
    strength=vals.get(opp,50.)
    factor=(.9 if loc=='H' else 1.1 if loc=='A' else 1.) if result==1 else 1.
    value=.75*strength+25*result*factor+max(0,strength-53.5)*.6*(1 if result==1 else .5 if result==.5 else 0)
    (wins if result==1 else others).append(value)
   wins.sort(reverse=True)
   while len(wins)>10 and (sum(others+wins[:-1])/len(others+wins[:-1])>sum(others+wins)/len(others+wins)):
    wins.pop()
   updated[t]=sum(others+wins)/len(others+wins)
  diff=0
  for t,value in updated.items():
   nxt=.65*vals[t]+.35*value;diff=max(diff,abs(nxt-vals[t]));vals[t]=nxt
  if diff<.0001:break
 return vals,Counter(t for r in rows for t in (r['a'],r['b']))

def anchored_scenario(history,scenario,baseline):
 """Apply *changes* in estimated network NPI to baseline NPI; don't replace published baseline with raw model estimates."""
 original,coverage=estimate(history,baseline)
 new,_=estimate(history+scenario,baseline)
 ratings={t:round(v+new.get(t,original.get(t,v))-original.get(t,v),4) for t,v in baseline.items()}
 return ratings,coverage
