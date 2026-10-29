// Execute existing pure app logic in Node. This is not a browser/DOM or usability test.
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');
const root = path.resolve(__dirname, '..');
const raw = JSON.parse(fs.readFileSync(path.join(root, 'data.json'), 'utf8'));
const source = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
const prefix = source.slice(0, source.indexOf('/* ---------- Çizim'));
const chain = source.slice(source.indexOf('function chainOf('), source.indexOf('function detailTable('));
if (!prefix || !chain || !source.includes('/* ---------- Çizim')) throw Error('Source boundaries changed');
const context = vm.createContext({console});
vm.runInContext(prefix.replace('__DATA__',JSON.stringify(raw))+'\n'+chain+'\n'+
  'globalThis.api={DATA,YEARS,S,DEFAULTS,unitsFor,listFor,normalize,parseBox,matchBox,chainOf,prevOf,nextOf};',context);
const api=context.api;
const report={timestamp_utc:new Date().toISOString(),node:process.version,
  app_sha256:crypto.createHash('sha256').update(source).digest('hex'),
  scope:'Existing data-preparation/filter/aggregation/sort/history functions; no DOM, browser compatibility, latency or user study.',
  aggregation_cells:0,aggregation_numeric_fields:0,absent_group_checks:0,
  filter_scenarios:0,nonempty_filter_scenarios:0,filtered_value_checks:0,
  sort_scenarios:0,sort_scenarios_with_distinct_values:0,sort_scenarios_with_null_and_value:0,
  history_records:0,sentinel_cases:[],failures:[]};
function check(ok, type, detail) { if(!ok) report.failures.push({type,...detail}); }
function eq(a,b){ return JSON.stringify(a)===JSON.stringify(b); }
function values(records,g,round){
  const parts=records.map(r=>round==='ilk'?r[g]:r.x?.[g]).filter(Boolean);
  if(!parts.length)return null;
  return [0,1,2,3].map(i=>{
    const a=parts.map(v=>v[i]).filter(n=>n!=null);
    if(!a.length)return null;
    return i<2?a.reduce((s,n)=>s+n,0):i===2?Math.min(...a):Math.max(...a);
  });
}
const groups=['ge','gk','me','mk','ee','ek'];
const rounds=['ilk','ek'];
function reset(patch){Object.assign(api.S,api.DEFAULTS,patch);}
function sourceGroups(year,combined,patch={}){
  const map=new Map();
  for(const r of raw[year]){
    if(patch.uni&&r.uni!==patch.uni)continue;
    if(patch.prog&&r.ptur!==patch.prog)continue;
    if(patch.tur&&r.tur!==patch.tur)continue;
    if(patch.burs&&r.burs!==(patch.burs==='__none'?'':patch.burs))continue;
    const id=combined?[r.uni,r.ptur,r.dil].join('|'):r.kod;
    if(!map.has(id))map.set(id,[]);
    map.get(id).push(r);
  }
  return map;
}
for(const year of Object.keys(raw))for(const combined of [false,true]){
  const ref=sourceGroups(year,combined);
  for(const u of api.unitsFor(+year,combined))for(const round of rounds)for(const g of groups){
    const want=values(ref.get(u.id),g,round);
    const got=u.g[round][g];
    report.aggregation_cells+=want?4:1;
    if(want)report.aggregation_numeric_fields+=4;else report.absent_group_checks++;
    check(eq(got,want),'aggregation',{year,combined,id:u.id,round,group:g,got,want});
  }
}
function runFilter(year,round,g,combined,patch){
  reset({year:+year,yer:round,kont:g[0],cins:g[1],combine:combined,...patch});
  const ref=sourceGroups(year,combined,patch);
  const expected=[];
  for(const [id,records]of ref){
    const v=values(records,g,round);
    if(!v||!((v[0]||0)>0||(v[1]||0)>0))continue;
    if(patch.unfilled===false&&(v[1]||0)<(v[0]||0))continue;
    if(patch.onlyOk&&patch.score!=null&&!(v[2]!=null&&patch.score>=v[2]))continue;
    expected.push(id);
  }
  const actual=Array.from(api.listFor(+year,round),u=>u.id);
  report.filter_scenarios++;
  if(actual.length)report.nonempty_filter_scenarios++;
  check(eq(actual.slice().sort(),expected.sort()),'filter',{year,round,group:g,combined,patch,actual_count:actual.length,expected_count:expected.length});
  for(const u of api.listFor(+year,round)){
    const want=values(ref.get(u.id),g,round);
    report.filtered_value_checks+=4;
    check(eq(u.g[round][g],want),'filtered_values',{year,round,group:g,combined,patch,id:u.id});
  }
  const keys=['min','max','k','y','fill','span',...(round==='ek'?['ilkmin']:[])];
  for(const key of keys)for(const dir of [-1,1]){
    reset({year:+year,yer:round,kont:g[0],cins:g[1],combine:combined,...patch,sort:key,dir});
    const list=api.listFor(+year,round);
    const vals=Array.from(list,u=>{
      const v=values(ref.get(u.id),g,round);
      const f=values(ref.get(u.id),g,'ilk');
      return {min:v[2],max:v[3],k:v[0],y:v[1],fill:v[0]?(v[1]||0)/v[0]:null,span:v[2]!=null&&v[3]!=null?v[3]-v[2]:null,ilkmin:f?.[2]??null}[key];
    });
    let last=null,missing=false,good=true;
    for(const v of vals){if(v==null){missing=true;continue;}if(missing)good=false;if(last!=null&&dir*(v-last)<-1e-9)good=false;last=v;}
    report.sort_scenarios++;
    if(new Set(vals.filter(v=>v!=null)).size>1)report.sort_scenarios_with_distinct_values++;
    if(vals.some(v=>v==null)&&vals.some(v=>v!=null))report.sort_scenarios_with_null_and_value++;
    check(good,'sort',{year,round,group:g,combined,patch,key,dir});
  }
}
for(const year of Object.keys(raw))for(const round of rounds){
  if(round==='ek'&&!raw[year].some(r=>r.x))continue;
  for(const g of (round==='ilk'?groups:['ge','gk','ee','ek']))for(const combined of [false,true]){
    const patches=[{}, {unfilled:false}, {score:350,onlyOk:true}, {uni:raw[year][0].uni},
      {prog:'Antrenörlük Eğitimi'}, {tur:'VAKIF'}, {burs:'Burslu'}, {burs:'__none'},
      {uni:'DOES NOT EXIST'}, {tur:'VAKIF',burs:'%50 İndirimli',unfilled:false}];
    for(const patch of patches)runFilter(year,round,g,combined,patch);
  }
}
const sentinels=[
  ['Turkish case folding',()=>api.matchBox('ışık üniversitesi',api.parseBox('IŞIK ÜNİVERSİTESİ'))===true],
  ['AND search rejects missing word',()=>api.matchBox('ankara üniversitesi',api.parseBox('ankara rekreasyon'))===false],
  ['Negative token excludes record',()=>api.matchBox('ankara rekreasyon',api.parseBox('ankara -rekreasyon'))===false],
  ['Blank query',()=>api.parseBox('   ')===null],
  ['Unavailable supplementary normalization',()=>{reset({year:2026,yer:'ek'});api.normalize();return api.S.yer==='ilk';}],
  ['National athlete supplementary normalization',()=>{reset({year:2025,yer:'ek',kont:'m'});api.normalize();return api.S.kont==='g';}],
  ['Initial placement sort normalization',()=>{reset({year:2025,yer:'ilk',sort:'ilkmin'});api.normalize();return api.S.sort==='min';}],
  ['Two search boxes use OR',()=>{reset({year:2025,combine:false,q1:'ankara',q2:'istanbul'});const actual=Array.from(api.listFor(2025,'ilk'),u=>u.id).sort();reset({year:2025,combine:false,q1:'ankara'});const a=Array.from(api.listFor(2025,'ilk'),u=>u.id);reset({year:2025,combine:false,q1:'istanbul'});const b=Array.from(api.listFor(2025,'ilk'),u=>u.id);return eq(actual,[...new Set([...a,...b])].sort());}]
];
for(const [name,fn]of sentinels){let passed=false;try{passed=fn();}catch(e){report.failures.push({type:'sentinel_error',name,error:String(e)});}report.sentinel_cases.push({name,passed});check(passed,'sentinel',{name});}
const records=JSON.parse(fs.readFileSync(path.join(__dirname,'dataset_records.json'),'utf8'));
const byPanel=new Map(),panelFor=new Map();
for(const r of records){if(!byPanel.has(r.panel_id))byPanel.set(r.panel_id,new Set());byPanel.get(r.panel_id).add(r.yil+'|'+r.program_kodu);panelFor.set(r.yil+'|'+r.program_kodu,r.panel_id);}
for(const [year,rows]of Object.entries(api.DATA))for(const r of rows){
  const want=Array.from(byPanel.get(panelFor.get(year+'|'+r.kod))).sort();
  const got=Object.values(api.chainOf(r)).map(v=>v.year+'|'+v.kod).sort();
  report.history_records++;
  check(eq(got,want),'history_vs_dataset',{year,code:r.kod,got,want});
}
fs.writeFileSync(path.join(__dirname,'app_audit.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify({...report,failures:report.failures.slice(0,10),failure_count:report.failures.length},null,2));
