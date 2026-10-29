"""Audit whether group-level over-quota placements are explained by ÖSYM quota transfer rules.

Rules (ÖSYM ÖZYES kılavuzları, 2024-2026):
  * Initial placement: unfilled national-athlete (millî sporcu) seats are transferred to the
    general quota of the same program and sex.
  * Supplementary placement: unfilled disabled-candidate (engelli aday) seats are transferred
    to the general quota of the same program and sex.

Test: for every program x sex x round, general-group excess (placed - quota, if positive)
must not exceed the donor group's vacancy (quota - placed, if positive).
Also reports vacancies after transfer and the 2026 initial-placement decomposition.
Standard library only; run from any directory.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data.json'
OUT = ROOT / 'research_validation/quota_transfer_audit.json'


def pair(arr):
    return (arr[0] or 0, arr[1] or 0) if arr else (0, 0)


def pos(v):
    return v if v > 0 else 0


def audit_round(programs, rnd):
    groups = ('g', 'm', 'e') if rnd == 'ilk' else ('g', 'e')
    donor = 'm' if rnd == 'ilk' else 'e'
    s = Counter()
    by_group = {f'{g}{x}': Counter() for g in groups for x in 'ek'}
    violations = []
    for p in programs:
        src = p if rnd == 'ilk' else p.get('x')
        if not src:
            continue
        s['programs'] += 1
        for sex in 'ek':
            for g in groups:
                q, pl = pair(src.get(g + sex))
                b = by_group[g + sex]
                b['quota'] += q
                b['placed'] += pl
                b['vacancy'] += pos(q - pl)
                b['excess'] += pos(pl - q)
                b['excess_rows'] += int(pl > q)
                s['quota'] += q
                s['placed'] += pl
                s['positive_group_vacancy'] += pos(q - pl)
                s['group_excess'] += pos(pl - q)
            gq, gp = pair(src['g' + sex])
            dq, dp = pair(src.get(donor + sex))
            exc, dvac = pos(gp - gq), pos(dq - dp)
            pooled = pos(gq + dq - gp - dp)
            others = sum(pos(q - pl) for q, pl in (pair(src.get(g + sex)) for g in groups if g not in ('g', donor)))
            s['vacancy_after_transfer'] += pooled + others
            if exc:
                s['general_excess_rows'] += 1
                s['general_excess_total'] += exc
                s['covered_rows'] += int(exc <= dvac)
                s['exactly_equal_rows'] += int(exc == dvac)
                s['general_quota_zero_rows'] += int(gq == 0)
                if exc > dvac:
                    violations.append({'code': p['kod'], 'sex': sex, 'general': [gq, gp], 'donor': [dq, dp]})
    s['net_vacancy'] = s['quota'] - s['placed']
    non_general_excess = sum(b['excess_rows'] for k, b in by_group.items() if not k.startswith('g'))
    return {'round': rnd, 'donor_group': donor, 'summary': dict(s),
            'non_general_excess_rows': non_general_excess,
            'violations': violations, 'by_group': {k: dict(v) for k, v in by_group.items()}}


def main():
    data = json.loads(RAW.read_text(encoding='utf-8'))
    results = []
    for year in sorted(data):
        for rnd in ('ilk', 'ek'):
            r = audit_round(data[year], rnd)
            if r['summary'].get('programs'):
                r['year'] = int(year)
                results.append(r)
    for r in results:
        s = r['summary']
        assert not r['violations'], (r['year'], r['round'], r['violations'][:3])
        assert r['non_general_excess_rows'] == 0
        assert s['covered_rows'] == s['general_excess_rows']
        assert s['vacancy_after_transfer'] == s['net_vacancy']
        assert s['positive_group_vacancy'] - s['group_excess'] == s['net_vacancy']
    total = Counter()
    for r in results:
        for k in ('general_excess_rows', 'covered_rows', 'exactly_equal_rows', 'general_quota_zero_rows'):
            total[k] += r['summary'].get(k, 0)
    out = {'input_sha256': hashlib.sha256(RAW.read_bytes()).hexdigest(),
           'rule_sources': ['ÖSYM 2024 ÖZYES tercih işlemleri', 'ÖSYM 2024 ÖZYES ek yerleştirme tercih işlemleri',
                            'ÖSYM 2025 ÖZYES tercih kılavuzu', 'ÖSYM 2025 ÖZYES ek yerleştirme tercih kılavuzu',
                            'ÖSYM 2026 ÖZYES kılavuzu'],
           'totals': dict(total), 'periods': results}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for r in results:
        s = r['summary']
        print(r['year'], r['round'], {k: s.get(k, 0) for k in (
            'quota', 'placed', 'positive_group_vacancy', 'general_excess_rows', 'general_excess_total',
            'covered_rows', 'exactly_equal_rows', 'general_quota_zero_rows', 'vacancy_after_transfer', 'net_vacancy')})
    print('TOTAL', dict(total))


if __name__ == '__main__':
    main()
