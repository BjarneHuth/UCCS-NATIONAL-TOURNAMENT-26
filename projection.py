"""Baseline-anchored scenario sensitivity estimator; NOT the NCAA NPI algorithm.
No full historical-game reconstruction is claimed. Historical games, if available,
are used only to estimate indirect opponent-strength sensitivity.
"""
from collections import defaultdict
import re


def record_games(record):
    parts = re.findall(r'\d+', str(record))
    return sum(map(int, parts[:3])) if len(parts) >= 3 else 0


def estimate_projection(baseline, team_records, scenario, history=None):
    base = {k: float(v) for k, v in baseline.items()}
    counts = {k: max(1, record_games(team_records.get(k, ''))) for k in base}
    if not scenario:
        return base.copy(), {}, {'mode': 'baseline', 'history_games': len(history or [])}
    # A scenario's games are new games. Never silently count already-played
    # tournament games twice. The caller controls the snapshot cutoff.
    opponent_edges = defaultdict(list)
    for g in history or []:
        a, b = g.get('a'), g.get('b')
        if a in base and b in base and a != b:
            opponent_edges[a].append(b)
            opponent_edges[b].append(a)
    ratings = base.copy()
    for iteration in range(7):
        direct = defaultdict(float)
        game_counts = defaultdict(int)
        for g in scenario:
            a, b, winner = g['a'], g['b'], g['winner']
            if a not in base or b not in base or winner not in (a, b, 'TIE') or a == b:
                continue
            venue = g.get('venue', 'N')
            for team, opp in ((a, b), (b, a)):
                outcome = 1 if winner == team else .5 if winner == 'TIE' else 0
                loc = 'N' if venue == 'N' else ('H' if (team == a) == (venue == 'H') else 'A')
                # Illustrative game value, not a claim of official NCAA weights.
                value = .75 * ratings[opp] + 25 * outcome
                if outcome == 1:
                    value += max(0, ratings[opp] - 53.5) * .6
                weight = 0.9 if (loc == 'H' and outcome == 1) or (loc == 'A' and outcome == 0) else 1.1 if (loc == 'A' and outcome == 1) or (loc == 'H' and outcome == 0) else 1.0
                direct[team] += weight * (value - base[team])
                game_counts[team] += 1
        new = base.copy()
        for team in base:
            # Conservative baseline anchoring: approximate full-season game count.
            d = direct[team] / (counts[team] + game_counts[team])
            # Indirect effect only where historical opponent linkage is known.
            edges = opponent_edges[team]
            indirect = .75 * sum(ratings[opp] - base[opp] for opp in edges) / (counts[team] + game_counts[team]) if edges else 0.0
            new[team] = base[team] + d + indirect
        if max(abs(new[t] - ratings[t]) for t in base) < 0.00001:
            ratings = new
            break
        ratings = new
    return {t: round(v, 4) for t, v in ratings.items()}, {t: len(opponent_edges[t]) for t in base}, {'mode': 'estimated', 'history_games': len(history or []), 'scenario_games': len(scenario)}
