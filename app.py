import json, itertools, collections, io, csv
from datetime import date
from dynamic_engine import fetch_season, anchored_scenario
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
if 'mode' not in st.session_state:st.session_state.mode='Experimental dynamic NPI'
if 'history' not in st.session_state:st.session_state.history=[]
if 'import_audit' not in st.session_state:st.session_state.import_audit={}
if 'import_attempted' not in st.session_state:st.session_state.import_attempted=False

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

# Build actual entered hypothetical games in topological order. A selected match is one game, not every possible branch.
def selected_games(rows):
 return [{'a':a,'b':b,'winner':w,'venue':'N','date':'2026-11-02','id':g['id']} for g,a,b,w in rows if w and a and b and DEFAULT.get(g['id']) is None]

@st.cache_data(show_spinner=False,max_entries=8)
def scenario_ratings(history_json,scenario_json,baseline_json):
 return anchored_scenario(json.loads(history_json),json.loads(scenario_json),json.loads(baseline_json))

st.title('NCAA Tournament Control Center')
st.caption('UCCS Men’s Soccer  •  Five conference brackets  •  10-team projected field  •  Scenario explorer')
st.warning('NPI mode: '+st.session_state.mode+'. Dynamic ratings are experimental and NOT validated NCAA ratings.' if st.session_state.mode=='Experimental dynamic NPI' else 'Fixed published-snapshot NPI: game picks do not change ratings. Enable experimental dynamic mode under Data & Accuracy.')

cleaned,rows=resolved_games(st.session_state.winners)
st.session_state.winners=cleaned
pending=sum(w is None for _,_,_,w in rows)
npi=st.session_state.npi.copy()
scenario=selected_games(rows)
coverage={}
if st.session_state.mode=='Experimental dynamic NPI' and st.session_state.history:
 with st.spinner('Recalculating opponent network for the entered results…'):
  npi,coverage=scenario_ratings(json.dumps(st.session_state.history,sort_keys=True),json.dumps(scenario,sort_keys=True),json.dumps(st.session_state.npi,sort_keys=True))
if st.session_state.mode=='Experimental dynamic NPI' and not st.session_state.history:
 st.error('DYNAMIC NPI NOT ACTIVE: no historical game database has been loaded. The numbers below are unchanged baseline ratings, NOT recalculated ratings. Go to Data & Accuracy and import completed games. If the import fails, the site cannot calculate scenario NPI.')
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
if st.session_state.mode=='Experimental dynamic NPI' and st.session_state.history:
 st.info(f'EXPERIMENTAL DYNAMIC RATINGS ACTIVE · {len(st.session_state.history):,} historical games · {len(scenario)} entered hypothetical games · {len(st.session_state.import_audit.get("failed_dates",[]))} failed import dates. Changes are estimates, not NCAA-validated NPI.')
else:
 st.error('FIXED BASELINE DISPLAYED — the game editor cannot change NPI until a complete historical dataset is imported and dynamic mode is active.')

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
 st.warning('Dynamic ratings are EXPERIMENTAL, not official NCAA NPI. The importer uses an unofficial NCAA scoreboard service. Venue classification, Division II eligibility, name matching, game coverage and formula have NOT been fully verified.')
 st.radio('NPI calculation mode',['Published snapshot (fixed NPI)','Experimental dynamic NPI'],key='mode',help='Dynamic mode estimates network effects and anchors the change to your baseline NPI. It is not official.')
 st.markdown('#### Import completed 2026 games automatically')
 st.caption('Import is required for scenario-dependent ratings. Importing is per Streamlit session; refreshing or restarting the app may require a new import.')
 if st.button('Fetch completed 2026 NCAA Division II soccer games',type='primary'):
  with st.spinner('Downloading daily scoreboard results; this may take several minutes…'):
   try:
    history,audit=fetch_season(end=min(date.today(),date(2026,12,31)))
    st.session_state.import_attempted=True
    if not history:st.error('No games imported. The source may be unavailable. NPI recalculation is unavailable.')
    else:
     st.session_state.history=history;st.session_state.import_audit=audit
     st.success(f'Imported {len(history):,} distinct games from {audit["days"]} dates. {len(audit["failed_dates"])} dates failed.');st.rerun()
   except Exception as exc:st.error(f'Import failed: {exc}')
 if st.session_state.history:
  hist=st.session_state.history;aud=st.session_state.import_audit
  participants=set(t for r in hist for t in (r['a'],r['b']))
  matches=set(NPI_BASE)&participants
  st.write(f'Imported games: **{len(hist):,}** · Regional team-name matches: **{len(matches)}/51** · Failed dates: **{len(aud.get("failed_dates",[]))}**')
  if aud.get('failed_dates'):st.error('Some dates failed to load. Results are incomplete and ratings should not be trusted.');st.write(aud['failed_dates'][:20])
  missing=set(NPI_BASE)-matches
  if missing:st.warning('Unmatched regional teams: '+', '.join(sorted(missing)))
  if coverage:
   thin=[t for t in NPI_BASE if coverage.get(t,0)<10]
   if thin:st.warning(f'{len(thin)} regional teams have fewer than 10 imported games. Results may be distorted.')
  st.download_button('Download imported historical games',pd.DataFrame(hist).to_csv(index=False),file_name='ncaa_2026_imported_games.csv',mime='text/csv')
 st.markdown('#### NPI movement from selected games')
 if st.session_state.mode=='Experimental dynamic NPI' and st.session_state.history:
  tracked=['Fort Lewis','CSU Pueblo','Regis (CO)','UCCS']
  st.markdown('**Scenario impact — key RMAC teams**')
  st.dataframe(pd.DataFrame([{'Team':t,'Baseline':round(st.session_state.npi[t],3),'Scenario estimate':round(npi[t],3),'Change':round(npi[t]-st.session_state.npi[t],4)} for t in tracked if t in npi]),hide_index=True,use_container_width=True)
  st.caption('These are simplified opponent-network estimates, not official NCAA NPI. A zero change may indicate missing or unmatched historical data.')
 if st.session_state.mode=='Experimental dynamic NPI' and st.session_state.history:
  movers=sorted([{'Team':t,'Baseline NPI':round(st.session_state.npi[t],3),'Scenario estimate':round(npi[t],3),'Change':round(npi[t]-st.session_state.npi[t],3),'Imported games':coverage.get(t,0)} for t in npi],key=lambda x:abs(x['Change']),reverse=True)
  st.dataframe(pd.DataFrame(movers[:30]),hide_index=True,use_container_width=True)
  st.caption('Changes are differences between two simplified network-model runs, anchored to the entered baseline. The official NCAA formula and coverage have not been validated.')
 st.markdown('#### Edit current NPI values')
 edits=pd.DataFrame([{'Team':t,'Conference':CONF_OF[t],'NPI':npi[t]} for t in npi_order])
 edited=st.data_editor(edits,hide_index=True,use_container_width=True,disabled=['Team','Conference'],column_config={'NPI':st.column_config.NumberColumn('NPI',min_value=0,max_value=100,format='%.3f')},key='npi_editor')
 if st.button('Apply NPI updates',type='primary'):
  st.session_state.npi={r['Team']:float(r['NPI']) for _,r in edited.iterrows()};st.rerun()
 st.markdown('#### Data source / validation status')
 st.write('Baseline: 51 regional teams and 19 modeled conference tournament games from the earlier Colab project (Nov 1, 2026 snapshot).')
 st.write('Nationwide scoreboard importer: **available, unofficial and subject to coverage audit**. NCAA formula reproduction: **not validated**. This site must not be presented as official NCAA rankings.')
 st.download_button('Download regional NPI table',edits.to_csv(index=False),file_name='regional_npi.csv',mime='text/csv')
