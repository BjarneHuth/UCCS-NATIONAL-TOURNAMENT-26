import json, itertools, collections, io, csv, html
from datetime import date, timedelta
from dynamic_engine import fetch_season, anchored_scenario
from validation import audit_history
from projection import estimate_projection
from inkblot import fetch_snapshot
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title='UCCS | Tournament Control Center',page_icon='⚽',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>
/* UCCS Mountain Lions — official black and CU gold #CFB87C */
:root { --uccs-gold:#CFB87C; --uccs-black:#000000; --uccs-charcoal:#242629; --uccs-surface:#303338; --uccs-white:#FAFAF8; }
html, body, [data-testid="stAppViewContainer"], .stApp { background:#101113 !important; color:#FAFAF8 !important; font-family:Helvetica,Arial,sans-serif; }
[data-testid="stHeader"] { background:#101113 !important; }
.block-container { padding-top:1.5rem; max-width:1500px; }
h1,h2,h3 { color:#CFB87C !important; font-weight:800 !important; letter-spacing:-.025em; }
p,li,label,[data-testid="stMarkdownContainer"] { color:#FAFAF8; }
[data-testid="stSidebar"] { background:#202226 !important; border-right:2px solid #CFB87C !important; }
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 { color:#CFB87C !important; }
[data-testid="stMetric"] { background:#282B30 !important; border:1px solid #8C7C55 !important; border-left:4px solid #CFB87C !important; border-radius:10px; padding:14px 18px; }
[data-testid="stMetricLabel"] * { color:#E4D6B8 !important; }
[data-testid="stMetricValue"] * { color:#FFFFFF !important; }
/* Buttons are visibly lighter than surrounding surfaces */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
 background:#CFB87C !important; color:#101113 !important; border:2px solid #E8D6A8 !important;
 border-radius:8px !important; font-weight:750 !important; box-shadow:0 2px 0 rgba(0,0,0,.35) !important;
 min-height:2.75rem; transition:background-color .15s ease,transform .15s ease;
}
.stButton > button *, .stDownloadButton > button *, [data-testid="stFormSubmitButton"] button * {color:#101113 !important;}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] button:hover { background:#E9D7A9 !important; border-color:#FFFFFF !important; transform:translateY(-1px); }
.stButton > button:focus-visible, .stDownloadButton > button:focus-visible { outline:3px solid #FFFFFF !important; outline-offset:3px !important; }
.stButton > button:disabled, .stDownloadButton > button:disabled { background:#565A5C !important; border-color:#858789 !important; color:#F5F5F5 !important; opacity:.8 !important; }
.stButton > button:disabled *, .stDownloadButton > button:disabled * { color:#F5F5F5 !important; }
/* Selected tabs: gold fill, unselected tabs: dark cards with visible outlines */
[data-testid="stTabs"] [role="tablist"] { gap:8px; border-bottom:1px solid #565A5C; padding-bottom:8px; }
[data-testid="stTabs"] button[role="tab"] { background:#303338 !important; color:#F6F3ED !important; border:1px solid #77746B !important; border-radius:8px !important; font-weight:700 !important; padding:10px 16px !important; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { background:#CFB87C !important; color:#101113 !important; border-color:#F0E2BF !important; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] * { color:#101113 !important; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"], [data-testid="stTabs"] [data-baseweb="tab-border"] { background:transparent !important; }
/* Controls: clearly outlined and lighter than page background */
[data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="textarea"] > div,
[data-testid="stNumberInput"] input, [data-testid="stTextInput"] input, [data-testid="stFileUploader"] section {
 background:#303338 !important; color:#FFFFFF !important; border:1px solid #9A8B68 !important; border-radius:7px !important;
}
[data-baseweb="select"] *, [data-baseweb="input"] input, [data-baseweb="textarea"] textarea { color:#FFFFFF !important; }
[data-baseweb="popover"] [role="listbox"], [role="listbox"] { background:#303338 !important; color:#FFFFFF !important; }
[role="option"] { background:#303338 !important; color:#FFFFFF !important; }
[role="option"]:hover { background:#565A5C !important; }
[data-testid="stExpander"] { background:#25272B !important; border:1px solid #686D70 !important; border-radius:8px !important; }
[data-testid="stDataFrame"], [data-testid="stTable"] { border:1px solid #77746B; border-radius:7px; }
[data-testid="stAlert"] { border-left:4px solid #CFB87C; }
a { color:#E9D7A9 !important; }
[data-testid="stProgress"] [role="progressbar"] > div { background:#CFB87C !important; }
@media(max-width:700px){ [data-testid="stTabs"] button[role="tab"] { padding:8px !important; font-size:.8rem !important; } }
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
if 'venue_overrides' not in st.session_state:st.session_state.venue_overrides={}
if 'snapshot_date' not in st.session_state:st.session_state.snapshot_date=DATA.get('snapshot_date','November 5, 2026')
if 'records' not in st.session_state:st.session_state.records={r[0]:r[2] for r in TEAMS}
# Previously saved sessions can contain outdated baselines. Refresh on deployment.
if st.session_state.get('data_version') != DATA.get('data_version', DATA.get('snapshot_date')):
 st.session_state.npi=NPI_BASE.copy()
 st.session_state.records={r[0]:r[2] for r in TEAMS}
 st.session_state.snapshot_date=DATA.get('snapshot_date','November 5, 2026')
 st.session_state.winners=DEFAULT.copy()
 st.session_state.data_version=DATA.get('data_version', DATA.get('snapshot_date'))

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

st.session_state.winners,_=resolved_games({**st.session_state.winners,**{g['id']:g['winner'] for g in GAMES if g.get('locked')}})

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
st.sidebar.caption(f'Ratings updated: {st.session_state.snapshot_date}')
st.sidebar.divider()
st.sidebar.subheader('Your scenario')
state={'winners':st.session_state.winners,'npi':st.session_state.npi}
st.sidebar.download_button('⬇ Download saved scenario',json.dumps(state,indent=2),file_name='uccs_scenario.json',mime='application/json',use_container_width=True)
upload=st.sidebar.file_uploader('Restore saved scenario (.json)',type='json')
if upload and st.sidebar.button('Load saved scenario'):
 try:
  obj=json.load(upload);st.session_state.winners={**DEFAULT,**{k:v for k,v in obj.get('winners',{}).items() if k in DEFAULT and not GAME_BY_ID[k].get('locked')}}
  st.session_state.npi={**NPI_BASE,**{k:float(v) for k,v in obj.get('npi',{}).items() if k in NPI_BASE}}
  st.rerun()
 except Exception as e:st.sidebar.error(f'Could not load: {e}')
if st.sidebar.button('Reset to baseline',use_container_width=True):
 st.session_state.winners=DEFAULT.copy();st.session_state.npi=NPI_BASE.copy();st.session_state.snapshot_date=DATA.get('snapshot_date','November 5, 2026');st.rerun()

# Build actual entered hypothetical games in topological order. A selected match is one game, not every possible branch.
def selected_games(rows):
 return [{'a':a,'b':b,'winner':w,'venue':st.session_state.venue_overrides.get(g['id'],'N'),'date':'2026-11-04','id':g['id']} for g,a,b,w in rows if w and a and b and DEFAULT.get(g['id']) is None]

@st.cache_data(show_spinner=False,max_entries=8)
def scenario_ratings(history_json,scenario_json,baseline_json):
 return anchored_scenario(json.loads(history_json),json.loads(scenario_json),json.loads(baseline_json))

st.title('UCCS Tournament Simulator')
st.caption('Pick winners, see updated NPI estimates, and explore the projected national tournament field.')
cleaned,rows=resolved_games(st.session_state.winners)
st.session_state.winners=cleaned
pending=sum(w is None for _,_,_,w in rows)
npi=st.session_state.npi.copy()
scenario=selected_games(rows)
coverage={}
validation=audit_history(st.session_state.history,st.session_state.npi,st.session_state.import_audit)
# Dynamic scenario estimates use the published baseline, not an unvalidated
# reconstruction of all historical games. This makes every selected result count.
# It remains an approximation, not an NCAA-certified NPI calculation.
coverage = {}
if st.session_state.mode == 'Experimental dynamic NPI':
 records = st.session_state.records
 npi, coverage, estimate_info = estimate_projection(st.session_state.npi, records, scenario, st.session_state.history)



else:
 st.info('Published snapshot mode: picks change conference champions but not NPI ratings.')
npi_order=sorted(npi,key=lambda t:(-npi[t],t)); rank=npi_order.index('UCCS')+1
# Instant deterministic completion for the visible projected field.
# Full combinatorial enumeration runs only on explicit request.
def preview_field(known,ratings):
 outcomes={}
 for g in GAMES:
  a=outcomes.get(g['a'],g['a']); b=outcomes.get(g['b'],g['b'])
  outcomes[g['id']]=known.get(g['id']) or (a if ratings.get(a,0)>=ratings.get(b,0) else b)
 champions={c:next(outcomes[g['id']] for g in GAMES if g['conf']==c and g['round']=='Final') for c in CONF}
 aq,at,first_out=field_for(champions,ratings)
 return champions,aq,at,first_out
sample=preview_field(cleaned,npi)
prob=None
c1,c2,c3=st.columns(3)
c1.metric('UCCS NPI',f"{npi['UCCS']:.3f}",f"{npi['UCCS']-NPI_BASE['UCCS']:+.3f} vs baseline")
c2.metric('Regional rank',f'#{rank}')
c3.metric('Unresolved games',pending)

tab2,tab1,tab_bracket,tab3,tab5=st.tabs(['⚽ Pick Winners','🏆 Projected Field','🏟️ National Bracket','📊 Rankings','⚙️ Settings & Data'])
with tab1:
 st.subheader('Illustrative 10-team field — '+('dynamic estimated NPI' if st.session_state.mode=='Experimental dynamic NPI' else 'fixed NPI snapshot'))
 if pending:st.info(f'{pending} games are undecided. The field below is ONE illustrative completion (first branch), not a definitive selection. The preview selects higher-rated teams in unresolved games.')
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
 st.markdown('#### Scenario analysis')
 st.caption('Optional: analyze all remaining possible bracket outcomes. The page does not run this automatically.')
 if st.button('Calculate scenarios',key='calculate_scenarios'):
  with st.spinner('Analyzing remaining bracket combinations…'):
   total,counts,fields,champ_stats,_=simulate(tuple(sorted(cleaned.items())),tuple(sorted(npi.items())))
  st.metric('UCCS appears in modeled outcomes',f'{counts["in"]/total:.1%}')
  top=[{'Scenarios':n,'Share':f'{n/total:.1%}','UCCS in field':'Yes' if 'UCCS' in f else 'No','Teams':', '.join(f)} for f,n in fields.most_common(12)]
  st.dataframe(pd.DataFrame(top),hide_index=True,use_container_width=True)

with tab_bracket:
 st.subheader('Super Region 4 · National Tournament Bracket')
 st.caption('Projected bracket based on your conference tournament picks and the resulting 10-team field. No separate bracket picks needed.')
 projected_teams=sorted(set(sample[1]+sample[2]),key=lambda t:(-npi[t],t))
 if len(projected_teams)!=10:
  st.error('Cannot draw a 10-team bracket until the projected field contains exactly 10 distinct teams.')
 else:
  seeds={i+1:t for i,t in enumerate(projected_teams)}
  def line(team, seed=None):
   if team is None:
    return '<div class="team pending"><span class="seed">—</span><span class="name">To be determined</span></div>'
   if isinstance(team,int):
    seed=team
    team=seeds[team]
   prefix=f'#{seed}' if seed is not None else ''
   return f'<div class="team"><span class="seed">{prefix}</span><span class="name">{html.escape(str(team))}</span></div>'
  def game(label,team1,team2,host=None):
   host_text=f' · Hosted by #{host} {html.escape(seeds[host])}' if host else ''
   return f'<div class="match"><div class="match-header">{html.escape(label)}{host_text}</div>{line(team1)}{line(team2)}</div>'
  # Future NCAA tournament results are not predicted. Bracket progression remains
  # labeled by the relevant section until those games are played.
  def card(x,y,markup):
   return f'<div class="slot" style="left:{x}px;top:{y}px">{markup}</div>'
  r1_89=game('FIRST ROUND',8,9,1)
  r1_710=game('FIRST ROUND',7,10,2)
  r2_1=game('SECOND ROUND',1,'Winner #8 / #9',1)
  r2_4=game('SECOND ROUND',4,5,4)
  r2_2=game('SECOND ROUND',2,'Winner #7 / #10',2)
  r2_3=game('SECOND ROUND',3,6,3)
  semi_1=game('REGIONAL SEMIFINAL','Winner #1 section','Winner #4 section')
  semi_2=game('REGIONAL SEMIFINAL','Winner #2 section','Winner #3 section')
  final=game('REGIONAL FINAL','Semifinal 1 winner','Semifinal 2 winner')
  markup=''.join([
   card(12,70,r1_89),card(12,690,r1_710),
   card(340,70,r2_1),card(340,290,r2_4),
   card(340,690,r2_2),card(340,910,r2_3),
   card(670,180,semi_1),card(670,800,semi_2),
   card(1000,490,final)
  ])
  # Each line joins a completed matchup to the next round, in the style of
  # a traditional NCAA tournament bracket.
  connections=[(302,143,328,143),(630,143,650,143),(650,143,650,253),(650,253,658,253),
               (630,363,650,363),(650,363,650,253),
               (302,763,328,763),(630,763,650,763),(650,763,650,873),(650,873,658,873),
               (630,983,650,983),(650,983,650,873),
               (960,253,980,253),(980,253,980,563),(980,563,988,563),
               (960,873,980,873),(980,873,980,563)]
  svg=''.join(f'<path d="M{x1} {y1} L{x2} {y2}"/>' for x1,y1,x2,y2 in connections)
  bracket_html=f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#141518;color:#f9f8f5;font-family:Arial,Helvetica,sans-serif}}
.legend{{font-size:13px;color:#c9c4b8;padding:12px 14px 0}}.viewport{{width:100%;overflow-x:auto;padding:8px 0 20px}}
.board{{width:1320px;height:1085px;position:relative;background:#1a1b1e;border:1px solid #55524a;border-radius:12px;margin:0 8px}}
.slot{{position:absolute;width:290px;z-index:1}}.match{{background:#282a2e;border:1px solid #a38e60;border-radius:8px;overflow:hidden;box-shadow:0 4px 12px #0005}}
.match-header{{height:31px;display:flex;align-items:center;padding:0 10px;background:#cfb87c;color:#161616;font-size:10px;font-weight:800;letter-spacing:.055em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.team{{height:56px;display:flex;align-items:center;gap:10px;border-top:1px solid #47484b;padding:0 10px;font-size:14px}}
.team .seed{{min-width:30px;color:#cfb87c;font-weight:bold}}.team .name{{white-space:normal;line-height:1.25}}.team.pending{{color:#a9a9a9;font-style:italic}}
svg{{position:absolute;inset:0;pointer-events:none}}path{{fill:none;stroke:#cfb87c;stroke-width:2.5}}
.round-label{{position:absolute;top:15px;font-size:12px;font-weight:800;letter-spacing:.07em;color:#cfb87c}}
</style></head><body><div class="legend">Seeds #1–#6 receive byes · Scroll horizontally on smaller screens</div>
<div class="viewport"><div class="board">
<div class="round-label" style="left:12px">FIRST ROUND</div><div class="round-label" style="left:340px">SECOND ROUND</div>
<div class="round-label" style="left:670px">REGIONAL SEMIFINALS</div><div class="round-label" style="left:1000px">REGIONAL FINAL</div>
<svg width="1320" height="1085">{svg}</svg>{markup}
</div></div></body></html>"""
  components.html(bracket_html,height=1160,scrolling=False)
  st.caption('The bracket shows matchups and advancement paths only. Teams update when your conference tournament selections or NPI rankings change. Future national tournament winners are not assumed.')

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
    if g.get('locked'):
     st.markdown(f'**{label}:** {a} vs {b} — **{w} advances** 🔒')
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
 st.caption('The November 5 screenshot provides updated ratings for the top 23. Lower-ranked teams retain the previous saved ratings until refreshed.')
with tab5:
 st.subheader('Settings & Data')
 st.radio('NPI mode',['Experimental dynamic NPI','Published snapshot (fixed NPI)'],key='mode',horizontal=True)
 st.caption('Dynamic NPIs are estimates, not official NCAA ratings. Published baseline: November 5 (top 23 from supplied screenshot).')
 st.markdown('#### Set game venue (relative to first-listed team)')
 for g,a,b,w in rows:
  if w and a and b and DEFAULT.get(g['id']) is None:
   current=st.session_state.venue_overrides.get(g['id'],'N')
   choice=st.selectbox(f'{g["conf"]}: {a} vs {b}', ['N','H','A'], index=['N','H','A'].index(current), format_func=lambda v: {'N':'Neutral','H':f'{a} home','A':f'{b} home'}[v], key='venue_'+g['id'])
   st.session_state.venue_overrides[g['id']]=choice
 st.markdown('#### Refresh published NPI baseline')
 st.caption('Read the latest published Super Region 4 table directly from Inkblot. Updates all 47 listed teams together and leaves others unchanged; no invented ratings.')
 if st.button('Refresh NPIs from Inkblot'):
  try:
   snapshot_date, updated = fetch_snapshot()
   overlap=set(st.session_state.npi)&set(updated)
   if len(overlap)<40:raise ValueError(f'Only {len(overlap)} known teams matched; refusing partial update')
   st.session_state.npi.update({t:updated[t] for t in overlap})
   st.session_state.snapshot_date=snapshot_date
   st.session_state.records={**st.session_state.records,**{r[0]:r[2] for r in TEAMS}}
   st.success(f'Updated {len(overlap)} regional NPIs from Inkblot ({snapshot_date}).')
   st.rerun()
  except Exception as exc:st.error(f'Inkblot refresh failed safely: {exc}')
 st.markdown('#### Import completed 2026 games automatically')
 st.caption('Imports completed games through yesterday, not just November 1. A tied score remains a draw for NPI; shootout advancement is stored separately in the bracket.')
 if st.button('Fetch completed 2026 NCAA Division II soccer games',type='primary'):
  with st.spinner('Downloading daily scoreboard results; this may take several minutes…'):
   try:
    history,audit=fetch_season(end=date.today()-timedelta(days=1))
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
 with st.expander('Advanced: Historical-data validation report'):
  if st.session_state.history:
   st.write('**Dynamic estimate: ACTIVE (not NCAA-validated)**')
   for issue in validation['issues']:st.error(issue)
   if validation['differences']:
    st.dataframe(pd.DataFrame([{'Team':t,'Published baseline':st.session_state.npi[t],'Experimental reconstruction':round(st.session_state.npi[t]+d,3),'Difference':d,'Imported games':validation['counts'].get(t,0)} for t,d in sorted(validation['differences'].items(),key=lambda x:-abs(x[1]))]),hide_index=True,use_container_width=True)
 st.markdown('#### NPI movement from selected games — live estimates')
 if st.session_state.mode=='Experimental dynamic NPI':
  tracked=['Fort Lewis','CSU Pueblo','Regis (CO)','UCCS']
  st.markdown('**Scenario impact — key RMAC teams**')
  st.dataframe(pd.DataFrame([{'Team':t,'Baseline':round(st.session_state.npi[t],3),'Scenario estimate':round(npi[t],3),'Change':round(npi[t]-st.session_state.npi[t],4)} for t in tracked if t in npi]),hide_index=True,use_container_width=True)
  st.caption('These are baseline-anchored scenario estimates, not official NCAA NPI. Without historical games, indirect effects are unavailable.')
 if st.session_state.mode=='Experimental dynamic NPI':
  movers=sorted([{'Team':t,'Baseline NPI':round(st.session_state.npi[t],3),'Scenario estimate':round(npi[t],3),'Change':round(npi[t]-st.session_state.npi[t],3),'Imported games':coverage.get(t,0)} for t in npi],key=lambda x:abs(x['Change']),reverse=True)
  st.dataframe(pd.DataFrame(movers[:30]),hide_index=True,use_container_width=True)
  st.caption('Changes are illustrative sensitivity estimates anchored to published NPI, not NCAA-validated results.')
 st.markdown('#### Edit current NPI values')
 edits=pd.DataFrame([{'Team':t,'Conference':CONF_OF[t],'NPI':npi[t]} for t in npi_order])
 edited=st.data_editor(edits,hide_index=True,use_container_width=True,disabled=['Team','Conference'],column_config={'NPI':st.column_config.NumberColumn('NPI',min_value=0,max_value=100,format='%.3f')},key='npi_editor')
 if st.button('Apply NPI updates',type='primary'):
  st.session_state.npi={r['Team']:float(r['NPI']) for _,r in edited.iterrows()};st.rerun()

 st.download_button('Download regional NPI table',edits.to_csv(index=False),file_name='regional_npi.csv',mime='text/csv')
