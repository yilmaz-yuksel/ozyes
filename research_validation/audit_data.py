"""Reproducible read-only audit of the local source snapshot and existing code.

Does not call parse.main or execute dataset export operations.
The independent numeric extractor uses pypdf text layout, not pdfplumber tables.
"""
from pathlib import Path
import ast
import contextlib
import copy
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import platform
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'dataset'))
import parse as production
from osym_ozet import OSYM

GROUPS = ['ge', 'gk', 'me', 'mk', 'ee', 'ek']
EGROUPS = ['ge', 'gk', 'ee', 'ek']
FIELDS = ['kontenjan', 'yerlesen', 'en_kucuk_puan', 'en_buyuk_puan']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def numeric(token):
    if token in ('--','-'):
        return None
    return Decimal(token.replace('.', '').replace(',', '.'))

def eq(a,b):
    if a is None or b is None:
        return a is None and b is None
    return Decimal(str(a)) == Decimal(str(b))

def independent_numeric(path, groups):
    records, duplicates = {}, []
    for pi,page in enumerate(PdfReader(path).pages,1):
        text = page.extract_text(extraction_mode='layout')
        for line in text.splitlines():
            m=re.match(r'^\s*([1-4]\d{8})(?!\d)',line)
            if not m:
                continue
            code=m.group(1)
            tokens=re.findall(r'--|\d+(?:[.,]\d+)*',line[m.end():])
            n=len(groups)*4
            if len(tokens)<n:
                raise ValueError(f'Independent extraction: {path.name} p{pi} {code}: only {len(tokens)} values')
            vals=[numeric(t) for t in tokens[-n:]]
            if code in records:
                duplicates.append(code)
            records[code]={'page':pi,'groups':{g:vals[i*4:i*4+4] for i,g in enumerate(groups)}}
    if duplicates:
        raise ValueError(f'Independent extraction duplicates {path}: {duplicates}')
    return records

def norm(v):
    if pd.isna(v):
        return None
    return v.item() if hasattr(v,'item') else v

report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Local files only. Automated differential extraction; no independent human double-entry audit.',
        'environment':{'python':sys.version,'platform':platform.platform(),
                       'packages':{n:importlib.metadata.version(n) for n in ['pdfplumber','pypdf','pandas','openpyxl']}},
        'files':{},'sources':[],'numeric_differences':[]}
audit_inputs=[ROOT/'data.json',ROOT/'parse.py',ROOT/'app.js',ROOT/'dataset/build_dataset.py',ROOT/'dataset/lookups.py',ROOT/'dataset/osym_ozet.py']
audit_inputs += sorted((ROOT/'src').glob('20*_*.pdf'))+sorted((ROOT/'src_sayisal').glob('20*_*.pdf'))
report['files']={str(p.relative_to(ROOT)):sha(p) for p in audit_inputs}
DATA=json.loads((ROOT/'data.json').read_text(encoding='utf-8'))
raw_sources={}
numeric_comparisons=0
for path in sorted((ROOT/'src').glob('20*_*.pdf')):
    year,roundname=path.stem.split('_')
    groups=GROUPS if roundname=='ilk' else EGROUPS
    raw=production.read_pdf(path)
    raw_sources[(int(year),roundname)]=raw
    independent=independent_numeric(path,groups)
    original={r['kod']:r for r in DATA[year] if roundname=='ilk' or r['x']}
    codes={r['kod'] for r in raw}
    log=io.StringIO()
    with contextlib.redirect_stdout(log):
        passed=production.check(path.name,raw,path)
    row={'file':str(path.relative_to(ROOT)),'rows':len(raw),'pages':len(PdfReader(path).pages),
         'production_checks_pass':passed,'check_log':log.getvalue().strip(),
         'independent_rows':len(independent),'independent_code_set_match':set(independent)==codes,
         'json_code_set_match':set(original)==codes,'duplicate_codes':len(raw)-len(codes),
         'numeric_cells':len(raw)*len(groups)*4,'active_groups':0,
         'orphan_supplementary_codes':sorted(codes-set(r['kod'] for r in DATA[year])) if roundname=='ek' else [],
         'missing_placed_in_active_groups':0,'placed_over_quota':0,'zero_quota_positive_placed':0,
         'missing_scores_with_placed':0,'null_score_fields':0,'boundary_score_groups':0}
    for r in raw:
        code=r['kod']
        for g in groups:
            vals=r[g]
            k,n,mn,mx=vals
            active=(k or 0)>0 or (n or 0)>0
            row['active_groups']+=int(active)
            row['missing_placed_in_active_groups']+=int(active and n is None)
            row['placed_over_quota']+=int(k is not None and n is not None and n>k)
            row['zero_quota_positive_placed']+=int(k==0 and (n or 0)>0)
            row['missing_scores_with_placed']+=int((n or 0)>0 and (mn is None or mx is None))
            row['null_score_fields']+=int(mn is None)+int(mx is None)
            row['boundary_score_groups']+=int(mn in (100,500) or mx in (100,500))
            for j,v in enumerate(vals):
                iv=independent[code]['groups'][g][j]
                numeric_comparisons+=1
                if not eq(v,iv):
                    report['numeric_differences'].append({'file':path.name,'code':code,'group':g,'field':FIELDS[j],'pdfplumber':v,'pypdf':str(iv)})
                if code in original:
                    block=original[code] if roundname=='ilk' else original[code]['x']
                    if not eq(v,block[g][j]):
                        report['numeric_differences'].append({'file':path.name,'code':code,'group':g,'field':FIELDS[j],'parser':v,'json':block[g][j]})
    report['sources'].append(row)
    print(path.name,len(raw),'codes; numeric audit complete',flush=True)

# Reproduce the exact existing parse data transformations without writing data.json.
reconstructed={}; faculties={}
for year in sorted(map(int,DATA)):
    rows=[production.enrich(copy.deepcopy(r),faculties) for r in raw_sources[(year,'ilk')]]
    for r in rows:
        faculties[r['kod']]=r['fak']; r['x']=None
    index={r['kod']:r for r in rows}
    for e in raw_sources.get((year,'ek'),[]):
        if e['kod'] in index:
            index[e['kod']]['x']={g:e[g] for g in EGROUPS if g in e}
    reconstructed[str(year)]=rows
report['json_reproduction_exact']=reconstructed==DATA
report['numeric_comparisons_per_path']=numeric_comparisons

# Execute the original dataset model prefix. Export-only pyreadstat import is omitted.
# The truncation point and original source hash are reported explicitly.
source=(ROOT/'dataset/build_dataset.py').read_text(encoding='utf-8')
prefix=source.split('# ---------------------------------------------------------------- SPSS ve CSV')[0]
tree=ast.parse(prefix)
tree.body=[node for node in tree.body if not (isinstance(node,ast.Import) and any(a.name=='pyreadstat' for a in node.names))]
ns={'__file__':str(ROOT/'dataset/build_dataset.py'),'__name__':'dataset_audit_model'}
exec(compile(tree,str(ROOT/'dataset/build_dataset.py'),'exec'),ns)
df=ns['df']
report['dataset']={'rows':len(df),'columns':len(df.columns),'panels':len(ns['panels']),
                   'universities':df.universite.nunique(),'programme_years':sum(map(len,DATA.values())),
                   'code_change_panels':sum(ns['kod_degisti_panel'].values()),
                   'model_execution':'Original prefix before SPSS/CSV export; unused pyreadstat import omitted.',
                   'exports_tested':False,'reason_exports_not_tested':'pyreadstat is not installed in bundled runtime; source exports were not executed.',
                   'duplicate_observation_keys':int(df.duplicated(['yil','yerlestirme','program_kodu','kontenjan_turu','cinsiyet']).sum()),
                   'duplicate_panel_year_keys':int(df[['yil','panel_id','program_kodu']].drop_duplicates().duplicated(['yil','panel_id']).sum())}

# Validate all derived numeric fields with independent Decimal-based expected values.
derived_diffs=[]; tested=0
record_lookup={(r.yil,r.yerlestirme,r.panel_id,r.kontenjan_turu,r.cinsiyet):r for r in df.itertuples(index=False)}
def difference(a,b,digits=5):
    if a is None or b is None:
        return None
    return float(round(Decimal(str(a))-Decimal(str(b)),digits))
for r in df.itertuples(index=False):
    k,n,mn,mx=map(norm,(r.kontenjan,r.yerlesen,r.en_kucuk_puan,r.en_buyuk_puan))
    first=record_lookup.get((r.yil,1,r.panel_id,r.kontenjan_turu,r.cinsiyet)) if r.yerlestirme==2 else None
    prev=record_lookup.get((r.yil-1,r.yerlestirme,r.panel_id,r.kontenjan_turu,r.cinsiyet))
    first_min=norm(first.en_kucuk_puan) if first else None
    prev_min=norm(prev.en_kucuk_puan) if prev else None
    expected={'doluluk_orani':float(round(Decimal(n)/Decimal(k),4)) if k and k>0 else None,
              'bos_kontenjan':max(k-n,0) if k is not None else None,
              'kontenjan_doldu':int(n>=k) if k and k>0 else None,
              'puan_araligi':difference(mx,mn),'ilk_en_kucuk_puan':first_min,
              'ek_ilk_farki':difference(mn,first_min),'onceki_yil_en_kucuk_puan':prev_min,
              'en_kucuk_puan_degisim':difference(mn,prev_min),
              'uc_puan':int(mn in (100,500) or mx in (100,500))}
    for col,want in expected.items():
        tested+=1; got=norm(getattr(r,col))
        if not (got==want or (got is not None and want is not None and abs(got-want)<1e-9)):
            derived_diffs.append({'year':r.yil,'round':r.yerlestirme,'code':r.program_kodu,'column':col,'actual':got,'expected':want})
report['derived_checks']={'cells':tested,'differences':derived_diffs}

# Summaries independently read with pypdf; transcribed reference dictionary is also checked.
report['aggregate_checks']=[]
for path in sorted((ROOT/'src_sayisal').glob('20*_*.pdf')):
    year,roundname=path.stem.split('_');year=int(year);yer=1 if roundname=='ilk' else 2
    text='\n'.join(p.extract_text(extraction_mode='layout') for p in PdfReader(path).pages)
    for typ,label in [(1,'Devlet'),(2,'Vakıf')]:
        candidates=[line for line in text.splitlines() if re.match(r'^\s*'+label+r'\b',line)]
        if len(candidates)!=1:
            raise ValueError(f'Summary line ambiguous {path} {label}')
        numbers=re.findall(r'\d[\d.]*',candidates[0])
        expected=[int(s.replace('.','')) for s in numbers[-4:]]
        sub=df[(df.yil==year)&(df.yerlestirme==yer)&(df.uni_turu==typ)]
        actual=[int(sub.program_sayac.sum()),int(sub.kontenjan.sum()),int(sub.yerlesen.sum()),int(sub.kontenjan.sum()-sub.yerlesen.sum())]
        report['aggregate_checks'].append({'year':year,'round':roundname,'university_type':label,'pdf_reference':expected,'transcribed_reference':list(OSYM[(year,yer,typ)]),'actual':actual,'diff':[a-b for a,b in zip(actual,expected)],'group_vacancies':int(sub.bos_kontenjan.sum())})

panel_links=[]; descriptor_changes=[]
for key,prev in ns['link'].items():
    a,b=ns['progs'][key],ns['progs'][prev]
    row={'current_year':key[0],'current_code':key[1],'previous_year':prev[0],'previous_code':prev[1],
         'university':a['uni'],'programme_type':a['ptur'],'language':a['dil'],'fee':a['burs'],
         'faculty_current':a['fak'],'faculty_previous':b['fak'],
         'panel':ns['panel_id'][key],'method':'same_code' if key[1]==prev[1] else 'descriptor_fallback'}
    panel_links.append(row)
    if a['k2']!=b['k2']:
        descriptor_changes.append(row)
report['panel_checks']={'links':len(panel_links),'fallback_links':sum(r['method']=='descriptor_fallback' for r in panel_links),
                        'gap_links':sum(r['current_year']-r['previous_year']>1 for r in panel_links),
                        'same_code_changed_descriptors':descriptor_changes,
                        'institutional_continuity_verified':False}
save('panel_links.json',panel_links)
save('dataset_records.json',json.loads(df.to_json(orient='records',force_ascii=False)))
report['input_files_unchanged']=all(sha(ROOT/path)==h for path,h in report['files'].items())
save('data_audit.json',report)
print(json.dumps({'sources':len(report['sources']),'numeric_cells_per_path':numeric_comparisons,'numeric_differences':len(report['numeric_differences']),
                  'json_exact':report['json_reproduction_exact'],'dataset':report['dataset'],'derived_cells':tested,'derived_differences':len(derived_diffs),
                  'aggregate_cells':len(report['aggregate_checks'])*4,'aggregate_differences':sum(v!=0 for r in report['aggregate_checks'] for v in r['diff']),
                  'inputs_unchanged':report['input_files_unchanged']},ensure_ascii=False,indent=2))
