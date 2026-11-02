import json, itertools, collections, io, csv
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title='UCCS | Tournament Control Center',page_icon='⚽',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>
.stApp{background:#101114;color:#f6f2e9}.block-container{padding-top:1.3rem;max-width:1500px}
h1,h2,h3{color:#f4cb64!important}div[data-testid="stMetric"]{background:#1c1d20;border:1px solid #6c5525;padding:16px;border-radius:12px}
div[data-testid="stMetricLabel"]{color:#d3bd85!important}.stButton>button[kind="primary"]{background:#d9ae45;color:#151515;border:none}
section[data-testid="stSidebar"]{background:#1c1b19}div[data-testid="stTabs"] button{font-weight:700}
</style>''',unsafe_allow_html=True)
DATA=json.loads((Path(__file__).parent/'data.json').read_text())
TEAMS=DATA['TEAM_DATA']; GAMES=DATA['GAMES']; CONF=['CCAA','GNAC','LSC','PWC','RMAC']
NPI_BASE={r[0]:float(r[3]) for r in TEAMS}; CONF_OF={r[0]:r[1] for r in TEAMS}
GAME_BY_ID={g['id']:g for g in GAMES}; DEFAULT={g['id']:g['winner'] for g in GAMES}
if 'winners' not in st.session_state:st.session_state.winners=DEFAULT.copy()
if 'npi' not in st.session_state:st.session_state.npi=NPI_BASE.copy()
if 'mode' not in st.session_state:st.session_state.mode='Published snapshot (fixed NPI)'

# Resolve dependencies in topological game order, clearing invalid downstream selections.
def resolved_games(winners):
 resolved={}; cleaned={}; rows=[]
 for g in GAMES:
  a=resolved.get(g['a'],g['a'] if g['a'] not in GAME_BY_ID else None)
  b=resolved.get(g['b'],g['b'] if g['b'] not in GAME_BY_ID else None)
  w=winners.get(g['id'])
  if not a or not b or w not in (a,b):w=None
  cleaned[g['id']]=w;resolved[g['id']]=w
  rows.append((g,a,b,w))
 return cleaned,rows

st.session_state.winners,_=resolved_games(st.session_state.winners)

def field_for(champions,npi):
 aq=[champions[c] for c in CONF]
 remaining=sorted((t for t in npi if t not in aq),key=lambda t:(-npi[t],t))
 return aq,remaining[:5],remaining[5] if len(remaining)>5 else None

@st.cache_data(show_spinner=False)
def simulate(winners_tuple,npi_tuple):
 known=dict(winners_tuple);npi=dict(npi_tuple)
 pending=[g for g in GAMES if not known.get(g['id'])]
 total=2**len(pending)
 counts=collections.Counter(); fields=collections.Counter(); champion_stats={c:collections.Counter() for c in CONF}
 sample=None
 for bits in itertools.product((0,1),repeat=len(pending)):
  outcomes={};i=0
  for g in GAMES:
   a=outcomes.get(g['a'],g['a']);b=outcomes.get(g['b'],g['b'])
   w=known.get(g['id'])
   if not w:
    w=(a,b)[bits[i]];i+=1
   outcomes[g['id']]=w
  champions={c:next(outcomes[g['id']] for g in GAMES if g['conf']==c and g['round']=='Final') for c in CONF}
  aq,at,first_out=field_for(champions,npi)
  selected=tuple(aq+at);in_field='UCCS' in selected
  counts['in' if in_field else 'out']+=1
  fields[tuple(sorted(selected))]+=1
  for c in CONF:
   champion_stats[c][(champions[c],in_field)]+=1
  if sample is None:sample=(champions,aq,at,first_out)
 return total,counts,fields,champion_stats,sample

st.sidebar.title('⚽ UCCS CONTROL CENTER')
st.sidebar.caption('2026 NCAA Division II Men’s Soccer · Super Region 4')
st.sidebar.warning('Model baseline: Nov 1, 2026. Fixed NPI unless you supply updated ratings. Not official NCAA selection odds.')
st.sidebar.divider()
st.sidebar.subheader('Save / restore your picks')
state={'winners':st.session_state.winners,'npi':st.session_state.npi}
st.sidebar.download_button('⬇ Download saved scenario',json.dumps(state,indent=2),file_name='uccs_scenario.json',mime='application/json',use_container_width=True)
upload=st.sidebar.file_uploader('Restore saved scenario (.json)',type='json')
if upload and st.sidebar.button('Load saved scenario'):
 try:
  obj=json.load(upload);st.session_state.winners={**DEFAULT,**{k:v for k,v in obj.get('winners',{}).items() if k in DEFAULT}}
  st.session_state.npi={**NPI_BASE,**{k:float(v) for k,v in obj.get('npi',{}).items() if k in NPI_BASE}}
  st.rerun()
 except Exception as e:st.sidebar.error(f'Could not load: {e}')
if st.sidebar.button('Reset to baseline',use_container_width=True):
 st.session_state.winners=DEFAULT.copy();st.session_state.npi=NPI_BASE.copy();st.rerun()

st.title('NCAA Tournament Control Center')
st.caption('UCCS Men’s Soccer  •  Five conference brackets  •  10-team projected field  •  Scenario explorer')

cleaned,rows=resolved_games(st.session_state.winners)
st.session_state.winners=cleaned
pending=sum(w is None for _,_,_,w in rows)
npi=st.session_state.npi
npi_order=sorted(npi,key=lambda t:(-npi[t],t)); rank=npi_order.index('UCCS')+1
with st.spinner('Calculating possible tournament fields…'):
 total,counts,fields,champ_stats,sample=simulate(tuple(sorted(cleaned.items())),tuple(sorted(npi.items())))
prob=counts['in']/total if total else 0
c1,c2,c3,c4=st.columns(4)
c1.metric('UCCS NPI',f"{npi['UCCS']:.3f}",f"{npi['UCCS']-NPI_BASE['UCCS']:+.3f} vs baseline")
c2.metric('Regional rank',f'#{rank}')
c3.metric('Scenarios with UCCS',f'{prob:.1%}',help='Fraction of enumerated outcomes, NOT a real-world probability')
c4.metric('Unresolved games',pending)
st.progress(prob,text=f'UCCS qualifies in {counts["in"]:,} of {total:,} equally weighted modeled outcomes')

tab1,tab2,tab3,tab4,tab5=st.tabs(['🏆 Projected Field','🎮 Games & Brackets','📊 Rankings & Contenders','🧭 Rooting Guide','⚙️ Data & Accuracy'])
with tab1:
 st.subheader('Projected 10-team NCAA field')
 if pending:st.info(f'{pending} games are undecided. The field below is ONE illustrative completion (first branch), not a definitive selection. See the most frequent fields below.')
 else:st.success('All modeled tournament games have winners. This is the single field under the current NPI values.')
 champs,aq,at,first_out=sample
 a,b=st.columns(2)
 with a:
  st.markdown('#### 🏆 Five automatic bids')
  st.dataframe(pd.DataFrame([{'Conference':c,'Champion':champs[c],'NPI':round(npi[champs[c]],3)} for c in CONF]),hide_index=True,use_container_width=True)
 with b:
  st.markdown('#### 🎟️ Five at-large bids')
  st.dataframe(pd.DataFrame([{'Team':t,'NPI':round(npi[t],3),'Regional rank':npi_order.index(t)+1} for t in at]),hide_index=True,use_container_width=True)
 st.write('**UCCS:**', 'IN — at-large' if 'UCCS' in at else ('IN — automatic' if 'UCCS' in aq else 'OUT of this illustrative field'))
 if first_out:st.caption(f'First team out in this illustrative field: {first_out} (NPI {npi[first_out]:.3f})')
 st.markdown('#### Most frequent projected fields')
 top=[]
 for f,n in fields.most_common(12):top.append({'Scenarios':n,'Share':f'{n/total:.1%}','UCCS in field':'Yes' if 'UCCS' in f else 'No','Teams':', '.join(f)})
 st.dataframe(pd.DataFrame(top),hide_index=True,use_container_width=True)
with tab2:
 st.subheader('Select game winners — advancement updates immediately')
 st.caption('Choose a winner for each matchup. The next round unlocks automatically. Changing an earlier winner clears incompatible later results.')
 for conf in CONF:
  with st.expander(f'{conf} Tournament',expanded=(conf=='RMAC')):
   for g,a,b,w in [x for x in rows if x[0]['conf']==conf]:
    label=f"{g['round']} · {g['id']}"
    if not a or not b:
     st.caption(f'{label} — awaiting earlier-round winner')
     continue
    options=['— Undecided —',a,b]
    selected=st.selectbox(f'{label}  |  {a} vs {b}',options,index=(options.index(w) if w in options else 0),key='pick_'+g['id'])
    new=None if selected==options[0] else selected
    if new!=st.session_state.winners.get(g['id']):
     st.session_state.winners[g['id']]=new
     st.session_state.winners,_=resolved_games(st.session_state.winners)
     # Clear widget states for later rounds to prevent stale selections.
     for gg in GAMES:
      if gg['id']!=g['id']:st.session_state.pop('pick_'+gg['id'],None)
     st.rerun()
 st.caption('Each selection immediately updates the top metrics and projected field. Results are local to this browser session unless downloaded from the sidebar.')
with tab3:
 st.subheader('Top 20 + remaining automatic-bid contenders')
 contenders=set(npi_order[:20]); eliminated=set()
 for g,a,b,w in rows:
  if w:eliminated.update(t for t in (a,b) if t and t!=w)
 for g,a,b,w in rows:
  if g['round']=='Final' and w:contenders.add(w)
  elif w is None:
   if a:contenders.add(a)
   if b:contenders.add(b)
 ranking=[{'Rank':i+1,'Team':t,'Conference':CONF_OF.get(t,'—'),'NPI':round(npi[t],3),'Top 20':i<20,'AQ pathway':'Possible' if t in contenders and t not in eliminated else 'Not confirmed'} for i,t in enumerate(npi_order) if t in contenders]
 st.dataframe(pd.DataFrame(ranking),hide_index=True,use_container_width=True,height=650)
 st.caption('All 51 regional teams remain eligible for at-large selection in the model; the table focuses on top 20 and bracket contenders.')
with tab4:
 st.subheader('Conference champion rooting guide')
 st.caption('Fixed-NPI scenario shares conditional on each conference champion; not statistical game-winning probabilities.')
 for conf in CONF:
  grouped=collections.defaultdict(lambda:[0,0])
  for (champ,yes),ct in champ_stats[conf].items():grouped[champ][0]+=ct;grouped[champ][1]+=ct if yes else 0
  df=pd.DataFrame([{'Champion':t,'UCCS scenario share':round(x[1]/x[0]*100,1),'Matching scenarios':x[0]} for t,x in grouped.items()]).sort_values('UCCS scenario share',ascending=False)
  st.markdown(f'**{conf}**');st.dataframe(df,hide_index=True,use_container_width=True)
with tab5:
 st.subheader('Ratings and data integrity')
 st.warning('The nationwide historical dataset is not included. Entering a tournament winner does NOT yet recalculate official NPI or indirect opponent effects. The standings here use fixed or manually updated ratings.')
 st.markdown('#### Edit current NPI values')
 edits=pd.DataFrame([{'Team':t,'Conference':CONF_OF[t],'NPI':npi[t]} for t in npi_order])
 edited=st.data_editor(edits,hide_index=True,use_container_width=True,disabled=['Team','Conference'],column_config={'NPI':st.column_config.NumberColumn('NPI',min_value=0,max_value=100,format='%.3f')},key='npi_editor')
 if st.button('Apply NPI updates',type='primary'):
  st.session_state.npi={r['Team']:float(r['NPI']) for _,r in edited.iterrows()};st.rerun()
 st.markdown('#### Data source / validation status')
 st.write('Baseline: 51 regional teams and 19 modeled conference tournament games from the earlier Colab project (Nov 1, 2026 snapshot).')
 st.write('Nationwide game-by-game import: **not connected**. NCAA formula reproduction: **not validated**. This site must not be presented as official NCAA rankings.')
 st.download_button('Download regional NPI table',edits.to_csv(index=False),file_name='regional_npi.csv',mime='text/csv')
