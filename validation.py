"""Conservative preflight: fail closed on missing or incompatible historical data."""
from collections import Counter
from dynamic_engine import estimate

def audit_history(history, baseline, import_audit=None):
    issues=[]
    if not history:
        return {'ok':False,'issues':['No historical games imported.'],'counts':{},'differences':{}}
    failures=(import_audit or {}).get('failed_dates',[])
    if failures: issues.append(f'{len(failures)} scoreboard dates failed to import.')
    counts=Counter(t for r in history for t in (r.get('a'),r.get('b')))
    missing=[t for t in baseline if counts[t]<12]
    if missing: issues.append(f'{len(missing)} of {len(baseline)} regional teams have fewer than 12 historical games: '+', '.join(sorted(missing)[:12]))
    bad=[r for r in history if r.get('winner') not in (r.get('a'),r.get('b'),'TIE') or r.get('venue') not in ('N','H')]
    if bad: issues.append(f'{len(bad)} games have malformed results or venues.')
    differences={}
    if not missing and not bad:
        try:
            calculated,_=estimate(history,baseline)
            differences={t:round(calculated[t]-float(baseline[t]),3) for t in baseline}
            large={t:d for t,d in differences.items() if abs(d)>3.0}
            if large:
                worst=sorted(large.items(),key=lambda x:-abs(x[1]))[:6]
                issues.append(f'Baseline validation failed: {len(large)} regional teams differ by more than 3.0 NPI points from the published snapshot. Largest: '+', '.join(f'{t} ({d:+.2f})' for t,d in worst))
        except Exception as exc: issues.append(f'Baseline validation failed to run: {exc}')
    # This engine is an approximation, not the official NCAA formula. Never certify it.
    issues.append('The experimental formula is not independently validated against the NCAA methodology; dynamic selection projections remain disabled.')
    return {'ok':False,'issues':issues,'counts':dict(counts),'differences':differences}
