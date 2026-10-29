"""ÖSYM 'Yerleştirme Sonuçlarına İlişkin Sayısal Bilgiler' tablolarından elle aktarılan değerler.

Kaynak dosyalar: src_sayisal/<yıl>_ilk.pdf, src_sayisal/<yıl>_ek.pdf
Anahtar: (yıl, yerleştirme kodu 1=ilk 2=ek, üniversite türü kodu 1=devlet 2=vakıf)
Değer : (program sayısı, kontenjan, yerleşen, boş kontenjan)
TERCIH: (yıl, yerleştirme) -> tercih yapan aday sayısı (tabloda tür ayrımı olmadan tek değer)
"""

OSYM = {
    (2024, 1, 1): (244, 11065, 10005, 1060), (2024, 1, 2): (107, 2655, 2259, 396),
    (2024, 2, 1): (239, 1663, 1318, 345),    (2024, 2, 2): (67, 802, 608, 194),
    (2025, 1, 1): (195, 8050, 7417, 633),    (2025, 1, 2): (86, 2048, 1675, 373),
    (2025, 2, 1): (194, 1340, 845, 495),     (2025, 2, 2): (64, 760, 368, 392),
    (2026, 1, 1): (271, 10175, 9359, 816),   (2026, 1, 2): (113, 2944, 2051, 893),
}

TERCIH = {
    (2024, 1): 34231, (2024, 2): 12566,
    (2025, 1): 20547, (2025, 2): 6070,
    (2026, 1): 19113,
}

KAYNAK = {
    (2024, 1): "2024 ÖZYES Yerleştirme Sonuçlarına İlişkin Sayısal Bilgiler",
    (2024, 2): "2024 YKS Spor Bilimleri İçin Özel Yetenek Sınavı Ek Yerleştirme Sonuçlarına İlişkin Sayısal Bilgiler",
    (2025, 1): "2025 ÖZYES Yerleştirme Sonuçlarına İlişkin Sayısal Bilgiler",
    (2025, 2): "2025 ÖZYES Ek Yerleştirme Sonuçlarına İlişkin Sayısal Bilgiler",
    (2026, 1): "2026 YKS Spor Bilimleri İçin Özel Yetenek Sınavı Yerleştirme Sonuçlarına İlişkin Sayısal Bilgiler",
}
