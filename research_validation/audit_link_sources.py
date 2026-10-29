"""Locate both ends of descriptor links in source PDFs; not a semantic validation."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research_validation'

SOURCES = {
 'BİTLİS': ('https://www.beu.edu.tr/akademik/fakulteler/spor-bilimleri-fakultesi/haberler', 'Haber indeksinde 2 Mayıs 2025 tarihli BESYO dönüşüm başlığı bulundu; haberin tam metni alınamadı.', 'limited'),
 'GÜMÜŞHANE': ('https://spor.gumushane.edu.tr/sayfa/tarihce', 'Tarihçe, yüksekokulun Eylül 2024 tarihinde fakülteye dönüşmesini açıklıyor.', 'transformation'),
 'ESENYURT': ('https://www.esenyurt.edu.tr/icerik/1758-spor-bilimleri-fakultesi-tarihce', 'Tarihçe, Temmuz 2025 tarihinde yüksekokulun kapatılması ve fakültenin açılmasını açıklıyor.', 'transformation'),
 'GELİŞİM': ('https://sporbilimleri.gelisim.edu.tr/tr/akademik-bolum-engellilerde-egzersiz-ve-spor-bilimleri-haber-igu-besyo-spor-bilimleri-fakultesi-oldu', '2 Ağustos 2024 tarihli duyuru yüksekokulun fakülteye dönüşmesini açıklıyor.', 'transformation'),
 'KİLİS': ('https://sporbilimleri.kilis.edu.tr/tr/page/1232', 'Tarihçe, Temmuz 2025 tarihinde yüksekokulun kapatılmasını ve fakültenin kurulmasını birlikte açıklıyor.', 'transformation'),
 'MARDİN': ('https://obs.artuklu.edu.tr/oibs/bologna/progAbout.aspx?curSunit=6126&lang=tr', 'Program bilgi paketi, Mayıs 2025 tarihinde yüksekokulun kapatılarak yerine fakültenin kurulmasını açıklıyor. Üniversitenin tanıtım kitapçığı ile gün bilgisi farklı olduğundan yalnızca ay kullanıldı.', 'transformation'),
 'VAN': ('https://bilgipaketi.yyu.edu.tr/DereceProgramlari/Detay/1/61478/9644/932001', 'Program bilgi paketi, Ağustos 2024 tarihinde yüksekokulun kapatılmasını, fakültenin kurulmasını ve programlarla öğrencilerin aktarılmasını açıklıyor.', 'transformation'),
 'ZONGULDAK': ('https://w3.beun.edu.tr/haberler/spor-bilimleri-fakultesi-20252026-yili-akademik-kurul-toplantisi-gerceklestirilirdi.html', 'Üniversite haberi Temmuz 2025 tarihinde fakültenin kuruluşunu bildiriyor; eski ve yeni kodların eşdeğerliğini açıklamıyor.', 'limited'),
}

def main():
    links = [x for x in json.loads((OUT/'panel_links.json').read_text(encoding='utf-8')) if x['method']=='descriptor_fallback']
    indices, hashes = {}, {}
    for year in (2024,2025):
        path = ROOT/'src'/f'{year}_ilk.pdf'
        hashes[str(year)] = hashlib.sha256(path.read_bytes()).hexdigest()
        index = {}
        for page_no,page in enumerate(PdfReader(path).pages,1):
            for line in page.extract_text(extraction_mode='layout').splitlines():
                match = re.match(r'^\s*([1-4]\d{8})(?!\d)',line)
                if match:
                    index.setdefault(match[1],[]).append({'page':page_no,'raw_row':line.strip(),'columns':re.split(r'\s{2,}',line.strip())})
        indices[year]=index
    records=[]
    for link in links:
        old=indices[link['previous_year']].get(link['previous_code'],[])
        new=indices[link['current_year']].get(link['current_code'],[])
        assert len(old)==len(new)==1, link
        key=next(k for k in SOURCES if k in link['university'])
        url,note,level=SOURCES[key]
        records.append({**link,'old_pdf':old[0], 'new_pdf':new[0], 'institutional_source':url,'source_note':note,'evidence_level':level,'explicit_code_crosswalk_found':False})
    result={'review_date':'2026-10-12','scope':'Source row presence and contextual institutional evidence; no independent human adjudication or official code crosswalk.', 'pdf_sha256':hashes,'summary':{'links':len(records),'pdf_endpoints_located':len(records)*2,'universities':len(SOURCES),'institutional_transformation_links':sum(x['evidence_level']=='transformation' for x in records),'limited_context_links':sum(x['evidence_level']=='limited' for x in records),'explicit_code_crosswalks_found':0},'records':records}
    (OUT/'link_source_evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Kod değişiklikleri için kaynak incelemesi','', 'İnceleme tarihi: 12 Ekim 2026. Bu kayıt, otomatik eşleştirmelerin resmî olarak onaylandığı anlamına gelmez. İki ÖSYM PDF’sindeki 48 kodun her biri tek bir satırda bulundu. Ham kaynak satırları, sayfa numaraları ve dosya özetleri eşlik eden JSON kaydındadır. Kurumsal kaynak incelemesi yapay zekâ asistanıyla yürütüldü; bağımsız uzman değerlendirmesi yapılmadı.','', 'Altı üniversiteye ait 20 bağlantı için birim dönüşümünü açıklayan kurumsal metin bulundu. Diğer iki üniversitenin dört bağlantısı için daha sınırlı bağlamsal kanıt kaydedildi. İncelenen kaynaklarda 24 kod çiftinin hiçbirini doğrudan eski kod → yeni kod biçiminde onaylayan bir çapraz liste bulunmadı. Bu, böyle bir listenin hiç bulunmadığı iddiası değildir.','', '| Panel | Üniversite ve program | 2024 kodu / PDF sayfası | 2025 kodu / PDF sayfası | Kanıt |','|---|---|---|---|---|']
    for x in records:
        detail=' / '.join(filter(None,[x['university'],x['programme_type'],x['language'],x['fee']]))
        label='Birim dönüşümü' if x['evidence_level']=='transformation' else 'Sınırlı bağlam'
        lines.append(f"| {x['panel']} | {detail} | {x['previous_code']} / {x['old_pdf']['page']} | {x['current_code']} / {x['new_pdf']['page']} | {label} |")
    lines+=['','## Kurumsal kaynaklar','']
    for key,(url,note,level) in SOURCES.items():
        lines += [f'- [{key}]({url}): {note}']
    lines+=['','## Yorumlama sınırı','', 'Kaynak satırında aynı üniversite, benzer program ve farklı birim adı görülmesi ile kurumsal dönüşüm duyurusu birlikte eşleştirmenin makul olduğunu destekler. Ancak programın müfredatı, akreditasyonu, bütün hakları veya istatistiksel karşılaştırılabilirliği hakkında eşdeğerlik kanıtı oluşturmaz. Tarihsel puanlar yıllar arasında eşdeğer ölçek kabul edilmemelidir. Eşleştirme algoritması ve veri değiştirilmedi.','', 'Kaynak PDF’ler: [2024 ilk yerleştirme](https://dokuman.osym.gov.tr/pdfdokuman/2024/OZYES/YERLESTIRME/minmax_ozyd11102024.pdf) ve [2025 ilk yerleştirme](https://dokuman.osym.gov.tr/pdfdokuman/2025/OZYES/YERLESTIRME/minmax-ozyyd19092025.pdf).','']
    (OUT/'kod_degisikligi_kanit_raporu.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(result['summary'],ensure_ascii=False))

if __name__=='__main__':
    main()
