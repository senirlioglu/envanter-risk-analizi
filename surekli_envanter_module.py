# ==================== SÜREKLİ ENVANTER MODÜLÜ v3 ====================
# Haftalık envanter analizi: Et-Tavuk, Ekmek, Meyve/Sebze
# Yeni mantık: Envanter Sayısı bazlı kümülatif takip
# Supabase: surekli_envanter_detay tablosu

import pandas as pd
import numpy as np
from datetime import datetime
import json
import os

# ==================== JSON'DAN VERİ YÜKLEME ====================

def load_json_data(filename):
    """JSON dosyasından veri yükle"""
    paths = [
        os.path.join(os.path.dirname(__file__), filename),
        os.path.join('/mount/src/envanter-risk-analizi', filename),
        filename
    ]
    for path in paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            continue
    return {}

# Verileri yükle
SM_BS_MAGAZA = load_json_data('sm_bs_magaza.json')
SEGMENT_URUN = load_json_data('segment_urun.json')

# ==================== SABİTLER ====================

HARIC_NITELIKLER = ['Geçici Delist', 'Bölgesel', 'Delist']
SEGMENT_MAPPING = {
    'L': ['L', 'LA', 'LAB', 'LABC', 'LABCD'],
    'A': ['A', 'LA', 'LAB', 'LABC', 'LABCD'],
    'B': ['B', 'LAB', 'LABC', 'LABCD'],
    'C': ['C', 'LABC', 'LABCD'],
    'D': ['D', 'LABCD']
}

# Kategori tespiti için keyword'ler
KATEGORI_KEYWORDS = {
    'Et-Tavuk': ['ET VE ET ÜRÜNLERİ', 'TAVUK', 'PİLİÇ', 'KIYMA', 'KÖFTE', 'SUCUK', 'SALAM'],
    'Ekmek': ['UN VE UNLU MAMULLER', 'EKMEK', 'LAVAŞ', 'BAZLAMA', 'PİDE', 'SIMIT'],
    'Meyve/Sebze': ['MEYVE', 'SEBZE', 'YAŞ MEYVE', 'YAŞ SEBZE']
}

# Risk puan ağırlıkları (toplam 97) - ESKİ KRİTERLER
RISK_WEIGHTS = {
    'bolge_sapma': 20,
    'satir_iptali': 12,
    'kronik_acik': 10,
    'aile_analizi': 5,
    'kronik_fire': 8,
    'fire_manipulasyon': 8,
    'sayilmayan_urun': 8,
    'anormal_miktar': 10,
    'tekrar_miktar': 8,
    'yuvarlak_sayi': 8
}

# ==================== YARDIMCI FONKSİYONLAR ====================

def get_magaza_bilgi(magaza_kodu):
    """Mağaza SM/BS bilgisini döner"""
    magaza_kodu = str(magaza_kodu)
    if magaza_kodu in SM_BS_MAGAZA:
        return SM_BS_MAGAZA[magaza_kodu]
    return {'sm': 'BİLİNMİYOR', 'bs': 'BİLİNMİYOR'}

def get_sm_list():
    """Tüm SM listesini döner"""
    return list(set(v['sm'] for v in SM_BS_MAGAZA.values()))

def get_bs_list():
    """Tüm BS listesini döner"""
    return list(set(v['bs'] for v in SM_BS_MAGAZA.values()))

def get_magazalar_by_sm(sm):
    """Bir SM'e bağlı mağazaları döner"""
    return [k for k, v in SM_BS_MAGAZA.items() if v['sm'] == sm]

def get_magazalar_by_bs(bs):
    """Bir BS'e bağlı mağazaları döner"""
    return [k for k, v in SM_BS_MAGAZA.items() if v['bs'] == bs]

def get_magaza_adi_col(df):
    """DataFrame'deki mağaza adı kolonunu bul"""
    if 'Mağaza Adı' in df.columns:
        return 'Mağaza Adı'
    elif 'Mağaza Tanım' in df.columns:
        return 'Mağaza Tanım'
    return None

def detect_kategori(row):
    """Satırdan kategori tespit et"""
    text = ' '.join([
        str(row.get('Ürün Grubu Tanımı', '')),
        str(row.get('Mal Grubu Tanımı', '')),
        str(row.get('Malzeme Tanımı', ''))
    ]).upper()
    
    for kategori, keywords in KATEGORI_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return kategori
    return 'Diğer'

# ==================== ENVANTER TİPİ TESPİTİ ====================

def detect_envanter_type(df):
    """Dosyanın sürekli mi parçalı mı olduğunu tespit et"""
    cols_lower = [c.lower() for c in df.columns]
    
    # Sürekli envanter belirteçleri
    surekli_indicators = ['envanter sayisi', 'envanter sayısı', 'depolama koşulu']
    for ind in surekli_indicators:
        if any(ind in c for c in cols_lower):
            return 'surekli'
    
    # Depolama koşulu değerleri kontrolü
    if 'Depolama Koşulu Grubu' in df.columns or 'Depolama Koşulu' in df.columns:
        return 'surekli'
    
    return 'parcali'

# ==================== SUPABASE KAYIT FONKSİYONLARI ====================

def prepare_detay_kayitlar(df):
    """
    DataFrame'den Supabase'e kaydedilecek detay kayıtlarını hazırla
    Her satır = 1 ürün kaydı
    """
    records = []
    magaza_adi_col = get_magaza_adi_col(df)
    
    # Envanter dönemi
    if 'Envanter Dönemi' in df.columns:
        envanter_donemi = str(df['Envanter Dönemi'].iloc[0])
    else:
        envanter_donemi = datetime.now().strftime('%Y%m')
    
    for _, row in df.iterrows():
        magaza_kodu = str(row.get('Mağaza Kodu', ''))
        if not magaza_kodu:
            continue
            
        magaza_bilgi = get_magaza_bilgi(magaza_kodu)
        kategori = detect_kategori(row)
        
        # Envanter sayısı
        env_sayisi = int(row.get('Envanter Sayisi', 1) or 1)
        
        record = {
            'magaza_kodu': magaza_kodu,
            'magaza_adi': str(row.get(magaza_adi_col, '')) if magaza_adi_col else '',
            'sm': magaza_bilgi['sm'],
            'bs': magaza_bilgi['bs'],
            'malzeme_kodu': str(row.get('Malzeme Kodu', '')),
            'malzeme_tanimi': str(row.get('Malzeme Tanımı', ''))[:100],
            'kategori': kategori,
            'envanter_donemi': envanter_donemi,
            'envanter_sayisi': env_sayisi,
            'fark_miktari': float(row.get('Fark Miktarı', 0) or 0),
            'fark_tutari': float(row.get('Fark Tutarı', 0) or 0),
            'fire_miktari': float(row.get('Fire Miktarı', 0) or 0),
            'fire_tutari': float(row.get('Fire Tutarı', 0) or 0),
            'iptal_satir_tutari': float(row.get('İptal Satır Tutarı', 0) or 0),
            'sayim_miktari': float(row.get('Sayım Miktarı', 0) or 0),
            'satis_hasilati': float(row.get('Satış Hasılatı', 0) or 0),
        }
        records.append(record)
    
    return records

def save_detay_to_supabase(supabase_client, records):
    """Detay kayıtlarını Supabase'e kaydet (upsert)"""
    if not records:
        return 0, 0
    
    inserted = 0
    skipped = 0
    
    # Batch upsert
    try:
        result = supabase_client.table('surekli_envanter_detay').upsert(
            records,
            on_conflict='magaza_kodu,malzeme_kodu,envanter_donemi,envanter_sayisi'
        ).execute()
        inserted = len(result.data) if result.data else 0
    except Exception as e:
        print(f"Supabase hata: {e}")
        # Tek tek dene
        for rec in records:
            try:
                supabase_client.table('surekli_envanter_detay').upsert(
                    rec,
                    on_conflict='magaza_kodu,malzeme_kodu,envanter_donemi,envanter_sayisi'
                ).execute()
                inserted += 1
            except:
                skipped += 1
    
    return inserted, skipped

def get_onceki_envanter(supabase_client, magaza_kodu, malzeme_kodu, envanter_donemi, envanter_sayisi):
    """Bir önceki envanter sayısındaki kaydı getir"""
    if envanter_sayisi <= 1:
        return None
    
    try:
        result = supabase_client.table('surekli_envanter_detay').select('*').eq(
            'magaza_kodu', magaza_kodu
        ).eq(
            'malzeme_kodu', malzeme_kodu
        ).eq(
            'envanter_donemi', envanter_donemi
        ).eq(
            'envanter_sayisi', envanter_sayisi - 1
        ).execute()
        
        if result.data:
            return result.data[0]
    except:
        pass
    return None

def get_magaza_onceki_kayitlar(supabase_client, magaza_kodu, envanter_donemi):
    """Mağazanın bu dönemdeki tüm önceki kayıtlarını getir"""
    try:
        result = supabase_client.table('surekli_envanter_detay').select('*').eq(
            'magaza_kodu', magaza_kodu
        ).eq(
            'envanter_donemi', envanter_donemi
        ).execute()
        
        if result.data:
            return pd.DataFrame(result.data)
    except:
        pass
    return pd.DataFrame()

# ==================== ANALİZ FONKSİYONLARI ====================

def analiz_fire_yazmama(df, df_onceki=None):
    """
    Fire yazmadan açık verenleri tespit et
    Envanter sayısı artmış + Fark artmış + Fire artmamış = 🚨
    """
    sonuclar = []
    
    if df_onceki is None or df_onceki.empty:
        # Önceki veri yok, sadece mevcut durumu raporla
        return sonuclar
    
    magaza_adi_col = get_magaza_adi_col(df)
    
    for _, row in df.iterrows():
        malzeme_kodu = str(row.get('Malzeme Kodu', ''))
        env_sayisi = int(row.get('Envanter Sayisi', 1) or 1)
        
        if env_sayisi <= 1:
            continue
        
        # Önceki kaydı bul
        onceki = df_onceki[
            (df_onceki['malzeme_kodu'] == malzeme_kodu) & 
            (df_onceki['envanter_sayisi'] == env_sayisi - 1)
        ]
        
        if onceki.empty:
            continue
        
        onceki = onceki.iloc[0]
        
        # Değişimleri hesapla
        fark_simdi = float(row.get('Fark Tutarı', 0) or 0)
        fark_onceki = float(onceki.get('fark_tutari', 0) or 0)
        fire_simdi = float(row.get('Fire Tutarı', 0) or 0)
        fire_onceki = float(onceki.get('fire_tutari', 0) or 0)
        
        fark_degisim = fark_simdi - fark_onceki  # Negatif = daha fazla açık
        fire_degisim = fire_simdi - fire_onceki  # Negatif = daha fazla fire
        
        # Fire yazmama: Fark arttı (daha negatif) ama fire artmadı
        if fark_degisim < -50 and fire_degisim >= -10:  # 50 TL'den fazla yeni açık, 10 TL'den az fire
            sonuclar.append({
                'Mağaza Kodu': row.get('Mağaza Kodu', ''),
                'Mağaza Adı': row.get(magaza_adi_col, '') if magaza_adi_col else '',
                'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                'Env.Sayısı': f"{env_sayisi-1} → {env_sayisi}",
                'Fark Değişim': f"{fark_degisim:,.0f} TL",
                'Fire Değişim': f"{fire_degisim:,.0f} TL",
                'Durum': '🚨 Fire yazmadan açık!'
            })
    
    return sonuclar

def analiz_kronik_acik(df, df_onceki=None):
    """Her sayımda açık artan ürünleri tespit et"""
    sonuclar = []
    
    if df_onceki is None or df_onceki.empty:
        return sonuclar
    
    magaza_adi_col = get_magaza_adi_col(df)
    
    for _, row in df.iterrows():
        malzeme_kodu = str(row.get('Malzeme Kodu', ''))
        env_sayisi = int(row.get('Envanter Sayisi', 1) or 1)
        
        if env_sayisi <= 1:
            continue
        
        onceki = df_onceki[
            (df_onceki['malzeme_kodu'] == malzeme_kodu) & 
            (df_onceki['envanter_sayisi'] == env_sayisi - 1)
        ]
        
        if onceki.empty:
            continue
        
        onceki = onceki.iloc[0]
        
        fark_simdi = float(row.get('Fark Tutarı', 0) or 0)
        fark_onceki = float(onceki.get('fark_tutari', 0) or 0)
        fark_degisim = fark_simdi - fark_onceki
        
        # Kronik açık: Her sayımda açık artıyor
        if fark_degisim < -100:  # 100 TL'den fazla yeni açık
            sonuclar.append({
                'Mağaza Kodu': row.get('Mağaza Kodu', ''),
                'Mağaza Adı': row.get(magaza_adi_col, '') if magaza_adi_col else '',
                'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                'Env.Sayısı': f"{env_sayisi-1} → {env_sayisi}",
                'Önceki Fark': f"{fark_onceki:,.0f} TL",
                'Şimdiki Fark': f"{fark_simdi:,.0f} TL",
                'Yeni Açık': f"{fark_degisim:,.0f} TL"
            })
    
    return sonuclar

def analiz_sayim_atlama(df, beklenen_sayim=4):
    """Beklenen sayımdan az sayım yapılan ürünleri tespit et"""
    sonuclar = []
    magaza_adi_col = get_magaza_adi_col(df)
    
    for _, row in df.iterrows():
        env_sayisi = int(row.get('Envanter Sayisi', 1) or 1)
        
        if env_sayisi < beklenen_sayim:
            eksik = beklenen_sayim - env_sayisi
            sonuclar.append({
                'Mağaza Kodu': row.get('Mağaza Kodu', ''),
                'Mağaza Adı': row.get(magaza_adi_col, '') if magaza_adi_col else '',
                'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                'Yapılan Sayım': env_sayisi,
                'Beklenen': beklenen_sayim,
                'Eksik': f"⚠️ {eksik} sayım eksik"
            })
    
    return sonuclar

def analiz_iptal_artis(df, df_onceki=None):
    """İptal tutarı artışını tespit et"""
    sonuclar = []
    
    if df_onceki is None or df_onceki.empty:
        # Önceki yok, sadece yüksek iptalleri göster
        magaza_adi_col = get_magaza_adi_col(df)
        for _, row in df.iterrows():
            iptal = abs(float(row.get('İptal Satır Tutarı', 0) or 0))
            if iptal > 100:
                sonuclar.append({
                    'Mağaza Kodu': row.get('Mağaza Kodu', ''),
                    'Mağaza Adı': row.get(magaza_adi_col, '') if magaza_adi_col else '',
                    'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                    'İptal Tutarı': f"{iptal:,.0f} TL",
                    'Durum': 'Kümülatif iptal'
                })
        return sonuclar
    
    magaza_adi_col = get_magaza_adi_col(df)
    
    for _, row in df.iterrows():
        malzeme_kodu = str(row.get('Malzeme Kodu', ''))
        env_sayisi = int(row.get('Envanter Sayisi', 1) or 1)
        
        if env_sayisi <= 1:
            iptal = abs(float(row.get('İptal Satır Tutarı', 0) or 0))
            if iptal > 100:
                sonuclar.append({
                    'Mağaza Kodu': row.get('Mağaza Kodu', ''),
                    'Mağaza Adı': row.get(magaza_adi_col, '') if magaza_adi_col else '',
                    'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                    'İptal Tutarı': f"{iptal:,.0f} TL",
                    'Durum': 'İlk sayım iptal'
                })
            continue
        
        onceki = df_onceki[
            (df_onceki['malzeme_kodu'] == malzeme_kodu) & 
            (df_onceki['envanter_sayisi'] == env_sayisi - 1)
        ]
        
        if onceki.empty:
            continue
        
        onceki = onceki.iloc[0]
        
        iptal_simdi = abs(float(row.get('İptal Satır Tutarı', 0) or 0))
        iptal_onceki = abs(float(onceki.get('iptal_satir_tutari', 0) or 0))
        iptal_degisim = iptal_simdi - iptal_onceki
        
        if iptal_degisim > 50:  # 50 TL'den fazla yeni iptal
            sonuclar.append({
                'Mağaza Kodu': row.get('Mağaza Kodu', ''),
                'Mağaza Adı': row.get(magaza_adi_col, '') if magaza_adi_col else '',
                'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                'Env.Sayısı': f"{env_sayisi-1} → {env_sayisi}",
                'Önceki İptal': f"{iptal_onceki:,.0f} TL",
                'Şimdiki İptal': f"{iptal_simdi:,.0f} TL",
                'Yeni İptal': f"+{iptal_degisim:,.0f} TL"
            })

    return sonuclar


def analiz_ic_hirsizlik_surekli(df, df_onceki=None):
    """
    İÇ HIRSIZLIK TESPİTİ (Sürekli Envanter için - Parçalı mantığıyla)

    Kural: |Fark Değişim| ≈ İptal Değişim
    - Açık arttı (fark_degisim < 0)
    - İptal arttı (iptal_degisim > 0)
    - |fark_degisim| ≈ iptal_degisim → Satırı iptal edip çalmış olabilir!

    Risk seviyeleri (fark ne kadar yakınsa o kadar riskli):
    - TAM EŞİT → ÇOK YÜKSEK
    - ±2 birim → YÜKSEK
    - ±5 birim → ORTA
    - ±10 birim → DÜŞÜK-ORTA
    """
    sonuclar = []

    if df_onceki is None or df_onceki.empty:
        return sonuclar

    magaza_adi_col = get_magaza_adi_col(df)

    for _, row in df.iterrows():
        malzeme_kodu = str(row.get('Malzeme Kodu', row.get('Mal Kodu', '')))
        env_sayisi = int(row.get('Envanter Sayisi', row.get('Envanter Sayısı', 1)) or 1)

        if env_sayisi <= 1:
            continue

        # Önceki kaydı bul
        onceki = df_onceki[
            (df_onceki['malzeme_kodu'].astype(str) == malzeme_kodu) &
            (df_onceki['envanter_sayisi'] == env_sayisi - 1)
        ]

        if onceki.empty:
            continue

        onceki = onceki.iloc[0]

        # Miktar bazlı değişimler (tutardan daha güvenilir)
        fark_simdi = float(row.get('Fark Miktarı', 0) or 0)
        fark_onceki = float(onceki.get('fark_miktari', 0) or 0)
        iptal_simdi = abs(float(row.get('İptal Satır Miktarı', 0) or 0))
        iptal_onceki = abs(float(onceki.get('iptal_satir_miktari', 0) or 0))

        # Tutarlar
        fark_tutar_simdi = float(row.get('Fark Tutarı', 0) or 0)
        fark_tutar_onceki = float(onceki.get('fark_tutari', 0) or 0)

        # Değişimler
        fark_degisim = fark_simdi - fark_onceki  # Negatif = daha fazla açık
        iptal_degisim = iptal_simdi - iptal_onceki  # Pozitif = daha fazla iptal
        tutar_degisim = fark_tutar_simdi - fark_tutar_onceki

        # Kural: Açık arttı VE iptal arttı
        if fark_degisim >= 0 or iptal_degisim <= 0:
            continue

        # |Fark değişim| ile iptal değişim karşılaştır
        fark_mutlak = abs(abs(fark_degisim) - iptal_degisim)

        # Risk seviyesi belirle
        if fark_mutlak == 0:
            risk = "ÇOK YÜKSEK"
            esitlik = "TAM EŞİT"
        elif fark_mutlak <= 2:
            risk = "YÜKSEK"
            esitlik = "YAKIN (±2)"
        elif fark_mutlak <= 5:
            risk = "ORTA"
            esitlik = "YAKIN (±5)"
        elif fark_mutlak <= 10:
            risk = "DÜŞÜK-ORTA"
            esitlik = f"FARK: {fark_mutlak:.1f}"
        else:
            continue  # Fark çok büyük, iç hırsızlık olma ihtimali düşük

        sonuclar.append({
            'Mağaza Kodu': str(row.get('Mağaza Kodu', '')),
            'Mağaza Adı': str(row.get(magaza_adi_col, ''))[:30] if magaza_adi_col else '',
            'Malzeme Kodu': malzeme_kodu,
            'Ürün': str(row.get('Malzeme Tanımı', row.get('Mal Tanım', '')))[:30],
            'Kategori': str(row.get('Depolama Koşulu', '')),
            'Env.Sayısı': f"{env_sayisi-1} → {env_sayisi}",
            'Fark Değişim': f"{fark_degisim:+.1f} adet",
            'İptal Değişim': f"+{iptal_degisim:.1f} adet",
            'Tutar Değişim': f"{tutar_degisim:,.0f} TL",
            'Durum': esitlik,
            'Risk': risk,
            'Kamera': '📹 KONTROL ET!'
        })

    if sonuclar:
        # Risk sırasına göre sırala
        risk_order = {'ÇOK YÜKSEK': 0, 'YÜKSEK': 1, 'ORTA': 2, 'DÜŞÜK-ORTA': 3}
        sonuclar = sorted(sonuclar, key=lambda x: (risk_order.get(x['Risk'], 99), x['Tutar Değişim']))

    return sonuclar

def analiz_yuvarlak_sayi(df):
    """Yuvarlak sayı girişlerini tespit et (5, 10, 15, 20...)"""
    sonuclar = []
    magaza_adi_col = get_magaza_adi_col(df)
    
    for _, row in df.iterrows():
        miktar = row.get('Sayım Miktarı', 0)
        if pd.isna(miktar) or miktar == 0:
            continue
        
        # Yuvarlak sayı kontrolü (5'in katları)
        if miktar > 0 and miktar % 5 == 0 and miktar >= 5:
            sonuclar.append({
                'Mağaza Kodu': row.get('Mağaza Kodu', ''),
                'Mağaza Adı': row.get(magaza_adi_col, '') if magaza_adi_col else '',
                'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                'Miktar': f"{miktar:.0f}",
                'Durum': 'Yuvarlak sayı'
            })
    
    return sonuclar

def analiz_anormal_miktar(df, esik=50):
    """Anormal yüksek miktarları tespit et"""
    sonuclar = []
    magaza_adi_col = get_magaza_adi_col(df)
    
    # İstisna ürünler (patates, soğan gibi yüksek olabilir)
    istisnalar = ['PATATES', 'SOĞAN', 'SOGAN', 'KARPUZ', 'KAVUN']
    
    for _, row in df.iterrows():
        miktar = row.get('Sayım Miktarı', 0)
        if pd.isna(miktar):
            continue
        
        urun_adi = str(row.get('Malzeme Tanımı', '')).upper()
        
        # İstisna kontrolü
        if any(ist in urun_adi for ist in istisnalar):
            esik_urun = 200  # Bu ürünler için daha yüksek eşik
        else:
            esik_urun = esik
        
        if miktar > esik_urun:
            sonuclar.append({
                'Mağaza Kodu': row.get('Mağaza Kodu', ''),
                'Mağaza Adı': row.get(magaza_adi_col, '') if magaza_adi_col else '',
                'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                'Miktar': f"{miktar:.0f}",
                'Eşik': f">{esik_urun}",
                'Durum': '⚠️ Anormal yüksek'
            })
    
    return sonuclar

# ==================== RİSK SKORU HESAPLAMA ====================

def hesapla_risk_skoru(df, df_onceki=None, urun_medianlar=None):
    """
    Sürekli envanter risk skorunu hesaplar - Toplam 97 puan
    ESKİ KRİTERLER ile
    """
    detaylar = {}
    toplam_puan = 0
    
    magaza_kodu = str(df['Mağaza Kodu'].iloc[0]) if 'Mağaza Kodu' in df.columns else ''
    magaza_adi_col = get_magaza_adi_col(df)
    magaza_adi = str(df[magaza_adi_col].iloc[0]) if magaza_adi_col else ''
    
    # Helper: Satırdan mağaza adı al
    def get_row_magaza_adi(row):
        if magaza_adi_col and magaza_adi_col in row.index:
            return str(row[magaza_adi_col])
        return magaza_adi
    
    # 1. BÖLGE SAPMA (20p)
    sapma_detay = []
    if urun_medianlar:
        for _, row in df.iterrows():
            kod = str(row.get('Malzeme Kodu', ''))
            if kod in urun_medianlar:
                median = urun_medianlar[kod].get('median', 0)
                if median > 0:
                    fark = abs(float(row.get('Fark Tutarı', 0) or 0))
                    fire = abs(float(row.get('Fire Tutarı', 0) or 0))
                    satis = float(row.get('Satış Hasılatı', 0) or 0)
                    if satis > 500:
                        magaza_oran = (fark + fire) / satis * 100
                        if magaza_oran > median * 1.5:
                            sapma_detay.append({
                                'Mağaza Kodu': row.get('Mağaza Kodu', magaza_kodu),
                                'Mağaza Adı': get_row_magaza_adi(row),
                                'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                                'Oran': f"%{magaza_oran:.1f}",
                                'Median': f"%{median:.1f}",
                                'Kat': f"{magaza_oran/median:.1f}x"
                            })
    cnt = len(sapma_detay)
    puan = 20 if cnt >= 15 else 15 if cnt >= 10 else 10 if cnt >= 5 else 5 if cnt >= 2 else 0
    detaylar['bolge_sapma'] = {
        'puan': puan, 'max': 20,
        'aciklama': f"{cnt} ürün median üstü" if urun_medianlar else "Bölge verisi gerekli",
        'detay': sapma_detay
    }
    toplam_puan += puan
    
    # 2. SATIR İPTALİ (12p)
    iptal_detay = []
    if 'İptal Satır Tutarı' in df.columns:
        for _, row in df.iterrows():
            iptal = abs(float(row.get('İptal Satır Tutarı', 0) or 0))
            if iptal > 50:
                iptal_detay.append({
                    'Mağaza Kodu': row.get('Mağaza Kodu', magaza_kodu),
                    'Mağaza Adı': get_row_magaza_adi(row),
                    'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                    'İptal Tutarı': f"{iptal:,.0f} TL"
                })
    iptal_tutar = abs(df['İptal Satır Tutarı'].sum()) if 'İptal Satır Tutarı' in df.columns else 0
    puan = 12 if iptal_tutar > 1500 else 8 if iptal_tutar > 500 else 4 if iptal_tutar > 100 else 0
    detaylar['satir_iptali'] = {
        'puan': puan, 'max': 12,
        'aciklama': f"{iptal_tutar:,.0f} TL iptal",
        'detay': iptal_detay
    }
    toplam_puan += puan
    
    # 3. KRONİK AÇIK (10p) - Envanter sayısı bazlı
    kronik_acik_detay = []
    veri_var = df_onceki is not None and not df_onceki.empty
    if veri_var:
        for _, row in df.iterrows():
            malzeme_kodu = str(row.get('Malzeme Kodu', ''))
            env_sayisi = int(row.get('Envanter Sayisi', 1) or 1)
            if env_sayisi <= 1:
                continue
            onceki = df_onceki[
                (df_onceki['malzeme_kodu'].astype(str) == malzeme_kodu) & 
                (df_onceki['envanter_sayisi'] == env_sayisi - 1)
            ]
            if onceki.empty:
                continue
            onceki = onceki.iloc[0]
            fark_simdi = float(row.get('Fark Tutarı', 0) or 0)
            fark_onceki = float(onceki.get('fark_tutari', 0) or 0)
            if fark_simdi < fark_onceki - 50:  # Daha fazla açık
                kronik_acik_detay.append({
                    'Mağaza Kodu': row.get('Mağaza Kodu', magaza_kodu),
                    'Mağaza Adı': get_row_magaza_adi(row),
                    'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                    'Önceki': f"{fark_onceki:,.0f}",
                    'Şimdi': f"{fark_simdi:,.0f}",
                    'Durum': 'Açık artıyor'
                })
    cnt = len(kronik_acik_detay)
    puan = 10 if cnt >= 10 else 6 if cnt >= 5 else 3 if cnt >= 2 else 0
    detaylar['kronik_acik'] = {
        'puan': puan, 'max': 10,
        'aciklama': f"{cnt} ürün 2+ sayımda açık" if veri_var else "⏳ Önceki veri bekleniyor",
        'detay': kronik_acik_detay
    }
    toplam_puan += puan
    
    # 4. AİLE ANALİZİ (5p) - TODO
    detaylar['aile_analizi'] = {
        'puan': 0, 'max': 5,
        'aciklama': "Henüz aktif değil",
        'detay': []
    }
    
    # 5. KRONİK FİRE (8p)
    kronik_fire_detay = []
    if veri_var:
        for _, row in df.iterrows():
            malzeme_kodu = str(row.get('Malzeme Kodu', ''))
            env_sayisi = int(row.get('Envanter Sayisi', 1) or 1)
            if env_sayisi <= 1:
                continue
            onceki = df_onceki[
                (df_onceki['malzeme_kodu'].astype(str) == malzeme_kodu) & 
                (df_onceki['envanter_sayisi'] == env_sayisi - 1)
            ]
            if onceki.empty:
                continue
            onceki = onceki.iloc[0]
            fire_simdi = float(row.get('Fire Tutarı', 0) or 0)
            fire_onceki = float(onceki.get('fire_tutari', 0) or 0)
            if fire_simdi < fire_onceki - 50:  # Daha fazla fire
                kronik_fire_detay.append({
                    'Mağaza Kodu': row.get('Mağaza Kodu', magaza_kodu),
                    'Mağaza Adı': get_row_magaza_adi(row),
                    'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                    'Önceki': f"{fire_onceki:,.0f}",
                    'Şimdi': f"{fire_simdi:,.0f}",
                    'Durum': 'Fire artıyor'
                })
    cnt = len(kronik_fire_detay)
    puan = 8 if cnt >= 8 else 5 if cnt >= 4 else 2 if cnt >= 2 else 0
    detaylar['kronik_fire'] = {
        'puan': puan, 'max': 8,
        'aciklama': f"{cnt} ürün 2+ sayımda fire" if veri_var else "⏳ Önceki veri bekleniyor",
        'detay': kronik_fire_detay
    }
    toplam_puan += puan
    
    # 6. FİRE MANİPÜLASYONU (8p) - Fire var ama açık artıyor
    fire_manip_detay = []
    if veri_var:
        for _, row in df.iterrows():
            malzeme_kodu = str(row.get('Malzeme Kodu', ''))
            env_sayisi = int(row.get('Envanter Sayisi', 1) or 1)
            if env_sayisi <= 1:
                continue
            onceki = df_onceki[
                (df_onceki['malzeme_kodu'].astype(str) == malzeme_kodu) & 
                (df_onceki['envanter_sayisi'] == env_sayisi - 1)
            ]
            if onceki.empty:
                continue
            onceki = onceki.iloc[0]
            fark_simdi = float(row.get('Fark Tutarı', 0) or 0)
            fark_onceki = float(onceki.get('fark_tutari', 0) or 0)
            fire_simdi = float(row.get('Fire Tutarı', 0) or 0)
            fire_onceki = float(onceki.get('fire_tutari', 0) or 0)
            fark_degisim = fark_simdi - fark_onceki
            fire_degisim = fire_simdi - fire_onceki
            # Açık arttı (daha negatif) ama fire yazmadı
            if fark_degisim < -50 and fire_degisim > -10:
                fire_manip_detay.append({
                    'Mağaza Kodu': row.get('Mağaza Kodu', magaza_kodu),
                    'Mağaza Adı': get_row_magaza_adi(row),
                    'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                    'Fark Değişim': f"{fark_degisim:,.0f}",
                    'Fire Değişim': f"{fire_degisim:,.0f}",
                    'Durum': '🚨 Fire yazmadan açık'
                })
    cnt = len(fire_manip_detay)
    puan = 8 if cnt >= 5 else 5 if cnt >= 3 else 2 if cnt >= 1 else 0
    detaylar['fire_manipulasyon'] = {
        'puan': puan, 'max': 8,
        'aciklama': f"{cnt} üründe fire↑ açık↓" if veri_var else "⏳ Önceki veri bekleniyor",
        'detay': fire_manip_detay
    }
    toplam_puan += puan
    
    # 7. SAYILMAYAN ÜRÜN (8p) - Sayım atlama
    sayim_detay = []
    gun = datetime.now().day
    beklenen_sayim = min((gun // 7) + 1, 4)
    if 'Envanter Sayisi' in df.columns:
        for _, row in df.iterrows():
            env_sayisi = int(row.get('Envanter Sayisi', 1) or 1)
            if env_sayisi < beklenen_sayim:
                sayim_detay.append({
                    'Mağaza Kodu': row.get('Mağaza Kodu', magaza_kodu),
                    'Mağaza Adı': get_row_magaza_adi(row),
                    'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                    'Yapılan': env_sayisi,
                    'Beklenen': beklenen_sayim,
                    'Durum': f"⚠️ {beklenen_sayim - env_sayisi} eksik"
                })
    cnt = len(sayim_detay)
    puan = 8 if cnt >= 10 else 5 if cnt >= 5 else 2 if cnt >= 2 else 0
    detaylar['sayilmayan_urun'] = {
        'puan': puan, 'max': 8,
        'aciklama': f"{cnt} üründe sayım eksik (beklenen: {beklenen_sayim})",
        'detay': sayim_detay
    }
    toplam_puan += puan
    
    # 8. ANORMAL MİKTAR (10p)
    anormal_detay = []
    istisnalar = ['PATATES', 'SOĞAN', 'SOGAN', 'KARPUZ', 'KAVUN']
    for _, row in df.iterrows():
        miktar = row.get('Sayım Miktarı', 0)
        if pd.isna(miktar):
            continue
        urun_adi = str(row.get('Malzeme Tanımı', '')).upper()
        esik = 200 if any(ist in urun_adi for ist in istisnalar) else 50
        if miktar > esik:
            anormal_detay.append({
                'Mağaza Kodu': row.get('Mağaza Kodu', magaza_kodu),
                'Mağaza Adı': get_row_magaza_adi(row),
                'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                'Miktar': f"{miktar:.0f}",
                'Durum': f'>{esik} kg/adet'
            })
    cnt = len(anormal_detay)
    puan = 10 if cnt >= 5 else 6 if cnt >= 3 else 3 if cnt >= 1 else 0
    detaylar['anormal_miktar'] = {
        'puan': puan, 'max': 10,
        'aciklama': f"{cnt} üründe >50 kg/adet",
        'detay': anormal_detay
    }
    toplam_puan += puan
    
    # 9. TEKRAR MİKTAR (8p)
    tekrar_detay = []
    if veri_var:
        for _, row in df.iterrows():
            malzeme_kodu = str(row.get('Malzeme Kodu', ''))
            env_sayisi = int(row.get('Envanter Sayisi', 1) or 1)
            miktar = row.get('Sayım Miktarı', 0)
            if env_sayisi <= 1 or pd.isna(miktar) or miktar <= 0:
                continue
            onceki = df_onceki[
                (df_onceki['malzeme_kodu'].astype(str) == malzeme_kodu) & 
                (df_onceki['envanter_sayisi'] == env_sayisi - 1)
            ]
            if onceki.empty:
                continue
            onceki = onceki.iloc[0]
            onceki_miktar = float(onceki.get('sayim_miktari', 0) or 0)
            if onceki_miktar > 0 and abs(miktar - onceki_miktar) / onceki_miktar <= 0.03:
                tekrar_detay.append({
                    'Mağaza Kodu': row.get('Mağaza Kodu', magaza_kodu),
                    'Mağaza Adı': get_row_magaza_adi(row),
                    'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                    'Önceki': f"{onceki_miktar:.1f}",
                    'Şimdi': f"{miktar:.1f}",
                    'Durum': 'Aynı miktar'
                })
    cnt = len(tekrar_detay)
    puan = 8 if cnt >= 10 else 5 if cnt >= 5 else 2 if cnt >= 2 else 0
    detaylar['tekrar_miktar'] = {
        'puan': puan, 'max': 8,
        'aciklama': f"{cnt} ürün aynı miktar" if veri_var else "⏳ Önceki veri bekleniyor",
        'detay': tekrar_detay
    }
    toplam_puan += puan
    
    # 10. YUVARLAK SAYI (8p)
    yuvarlak_detay = []
    for _, row in df.iterrows():
        miktar = row.get('Sayım Miktarı', 0)
        if pd.isna(miktar) or miktar == 0:
            continue
        if miktar > 0 and miktar % 5 == 0 and miktar >= 5:
            yuvarlak_detay.append({
                'Mağaza Kodu': row.get('Mağaza Kodu', magaza_kodu),
                'Mağaza Adı': get_row_magaza_adi(row),
                'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                'Miktar': f"{miktar:.0f}",
                'Durum': 'Yuvarlak sayı'
            })
    cnt = len(yuvarlak_detay)
    yuvarlak_oran = cnt / max(len(df), 1)
    puan = 8 if yuvarlak_oran > 0.35 else 5 if yuvarlak_oran > 0.20 else 2 if yuvarlak_oran > 0.10 else 0
    detaylar['yuvarlak_sayi'] = {
        'puan': puan, 'max': 8,
        'aciklama': f"{cnt} ürün (%{yuvarlak_oran*100:.0f}) yuvarlak",
        'detay': yuvarlak_detay
    }
    toplam_puan += puan
    
    # Seviye belirleme
    if toplam_puan <= 25:
        seviye, emoji = 'normal', '✅'
    elif toplam_puan <= 50:
        seviye, emoji = 'dikkat', '⚠️'
    elif toplam_puan <= 75:
        seviye, emoji = 'riskli', '🟠'
    else:
        seviye, emoji = 'kritik', '🔴'
    
    return {
        'toplam_puan': toplam_puan,
        'max_puan': 97,
        'seviye': seviye,
        'emoji': emoji,
        'detaylar': detaylar,
        'magaza_kodu': magaza_kodu,
        'magaza_adi': magaza_adi
    }

# ==================== ÖZET FONKSİYONLARI ====================

def hesapla_kategori_ozet(df):
    """Kategori bazlı özet hesapla"""
    ozet = {}
    
    for _, row in df.iterrows():
        kategori = detect_kategori(row)
        if kategori == 'Diğer':
            continue
        
        if kategori not in ozet:
            ozet[kategori] = {'fark': 0, 'fire': 0, 'satis': 0, 'urun_sayisi': 0}
        
        ozet[kategori]['fark'] += float(row.get('Fark Tutarı', 0) or 0)
        ozet[kategori]['fire'] += float(row.get('Fire Tutarı', 0) or 0)
        ozet[kategori]['satis'] += float(row.get('Satış Hasılatı', 0) or 0)
        ozet[kategori]['urun_sayisi'] += 1
    
    # Oran hesapla
    for kat in ozet:
        kayip = abs(ozet[kat]['fark']) + abs(ozet[kat]['fire'])
        satis = ozet[kat]['satis']
        ozet[kat]['oran'] = (kayip / satis * 100) if satis > 0 else 0
    
    return ozet

def hesapla_magaza_ozet(df):
    """Mağaza bazlı özet hesapla"""
    magaza_adi_col = get_magaza_adi_col(df)
    
    agg_dict = {
        'Fark Tutarı': 'sum',
        'Fire Tutarı': 'sum',
        'Satış Hasılatı': 'sum',
        'Malzeme Kodu': 'count'
    }
    if magaza_adi_col:
        agg_dict[magaza_adi_col] = 'first'
    
    ozet = df.groupby('Mağaza Kodu').agg(agg_dict).reset_index()
    ozet.columns = ['Mağaza Kodu', 'Fark', 'Fire', 'Satış', 'Ürün Sayısı'] + (['Mağaza Adı'] if magaza_adi_col else [])
    
    ozet['Kayıp'] = abs(ozet['Fark']) + abs(ozet['Fire'])
    ozet['Oran'] = np.where(ozet['Satış'] > 0, ozet['Kayıp'] / ozet['Satış'] * 100, 0)
    
    # SM/BS ekle
    ozet['SM'] = ozet['Mağaza Kodu'].apply(lambda x: get_magaza_bilgi(x)['sm'])
    ozet['BS'] = ozet['Mağaza Kodu'].apply(lambda x: get_magaza_bilgi(x)['bs'])
    
    return ozet.sort_values('Oran', ascending=False)

def hesapla_sm_ozet(df):
    """SM bazlı özet hesapla"""
    magaza_ozet = hesapla_magaza_ozet(df)
    
    sm_ozet = magaza_ozet.groupby('SM').agg({
        'Mağaza Kodu': 'nunique',
        'Fark': 'sum',
        'Fire': 'sum',
        'Satış': 'sum',
        'Kayıp': 'sum'
    }).reset_index()
    
    sm_ozet.columns = ['SM', 'Mağaza Sayısı', 'Fark', 'Fire', 'Satış', 'Kayıp']
    sm_ozet['Oran'] = np.where(sm_ozet['Satış'] > 0, sm_ozet['Kayıp'] / sm_ozet['Satış'] * 100, 0)
    
    return sm_ozet.sort_values('Oran', ascending=False)

def hesapla_top10(df):
    """Top 10 listelerini hesapla"""
    magaza_ozet = hesapla_magaza_ozet(df)
    
    sonuc = {
        'top10_magaza': magaza_ozet.nlargest(10, 'Oran'),
        'top5_acik': None,
        'top5_fire': None
    }
    
    # Ürün bazlı
    if 'Malzeme Kodu' in df.columns:
        urun_ozet = df.groupby(['Malzeme Kodu', 'Malzeme Tanımı']).agg({
            'Fark Tutarı': 'sum',
            'Fire Tutarı': 'sum',
            'Mağaza Kodu': 'nunique'
        }).reset_index()
        
        urun_ozet.columns = ['Kod', 'Ürün', 'Fark', 'Fire', 'Mağaza Sayısı']
        
        sonuc['top5_acik'] = urun_ozet.nsmallest(5, 'Fark')[['Ürün', 'Fark', 'Mağaza Sayısı']]
        sonuc['top5_fire'] = urun_ozet.nsmallest(5, 'Fire')[['Ürün', 'Fire', 'Mağaza Sayısı']]
    
    return sonuc

# ==================== SAYIM DİSİPLİNİ ====================

def hesapla_sayim_disiplini(df, beklenen_sayim=None):
    """Sayım disiplini analizi - hangi ürünler kaç kez sayılmış"""
    if beklenen_sayim is None:
        gun = datetime.now().day
        beklenen_sayim = min((gun // 7) + 1, 4)
    
    sonuc = {
        'beklenen_sayim': beklenen_sayim,
        'urunler': [],
        'ozet': {}
    }
    
    magaza_adi_col = get_magaza_adi_col(df)
    
    # Envanter sayısı dağılımı
    if 'Envanter Sayisi' in df.columns:
        for env_sayisi in range(1, beklenen_sayim + 1):
            cnt = len(df[df['Envanter Sayisi'] == env_sayisi])
            sonuc['ozet'][f'sayim_{env_sayisi}'] = cnt
        
        # Eksik sayımlar
        eksik = df[df['Envanter Sayisi'] < beklenen_sayim]
        for _, row in eksik.iterrows():
            sonuc['urunler'].append({
                'Mağaza Kodu': row.get('Mağaza Kodu', ''),
                'Mağaza Adı': row.get(magaza_adi_col, '') if magaza_adi_col else '',
                'Ürün': str(row.get('Malzeme Tanımı', ''))[:30],
                'Yapılan': int(row.get('Envanter Sayisi', 1)),
                'Beklenen': beklenen_sayim,
                'Eksik': beklenen_sayim - int(row.get('Envanter Sayisi', 1))
            })
    
    return sonuc

# ==================== EXPORT ====================

# Geriye uyumluluk için eski fonksiyon isimleri
def detect_yuvarlak_sayi(df):
    """Yuvarlak sayı DataFrame döndür"""
    sonuclar = analiz_yuvarlak_sayi(df)
    if not sonuclar:
        return pd.DataFrame()
    return pd.DataFrame(sonuclar)

def detect_anormal_miktar(df):
    """Anormal miktar DataFrame döndür"""
    sonuclar = analiz_anormal_miktar(df)
    if not sonuclar:
        return pd.DataFrame()
    return pd.DataFrame(sonuclar)

def detect_fire_manipulasyon(df):
    """Fire manipülasyon - eski versiyon uyumluluğu"""
    # Yeni sistemde bu analiz_fire_yazmama ile yapılıyor
    return pd.DataFrame()

def hesapla_bolge_ozeti(df):
    """Bölge özeti - top10 ile aynı"""
    return hesapla_top10(df)

# ==================== GOOGLE SHEETS İPTAL VERİSİ ====================
# Parçalı envanterdeki gibi iptal verisi entegrasyonu

SUREKLI_IPTAL_SHEETS_ID = '1F4Th-xZ2n0jDyayy5vayIN2j-EGUzqw5Akd8mXQVh4o'
SUREKLI_IPTAL_SHEET_NAME = 'IptalVerisi'

def get_surekli_iptal_from_sheets():
    """
    Google Sheets'ten sürekli envanter için iptal verisini çeker
    Aynı parçalı envanterdeki sheets yapısını kullanır
    """
    from datetime import timedelta
    try:
        csv_url = f'https://docs.google.com/spreadsheets/d/{SUREKLI_IPTAL_SHEETS_ID}/gviz/tq?tqx=out:csv&sheet={SUREKLI_IPTAL_SHEET_NAME}'
        df = pd.read_csv(csv_url, encoding='utf-8')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        print(f"Sheets okuma hatası: {e}")
        return pd.DataFrame()


def get_iptal_for_surekli_urunler(magaza_kodu, urun_kodlari, envanter_tarihi=None):
    """
    Belirli mağaza ve ürünler için iptal bilgilerini getirir
    """
    from datetime import timedelta
    df_iptal = get_surekli_iptal_from_sheets()

    if df_iptal.empty:
        return {}

    df_iptal = df_iptal.copy()

    # Kolon isimleri
    col_magaza = 'Mağaza - Anahtar'
    col_malzeme = 'Malzeme - Anahtar'
    col_tarih = 'Tarih - Anahtar'
    col_saat = 'Fiş Saati'
    col_miktar = 'Miktar'
    col_islem_no = 'İşlem Numarası'
    col_kasa = 'Kasa numarası'

    cols = df_iptal.columns.tolist()
    if col_magaza not in cols and len(cols) > 7:
        col_magaza = cols[7]
    if col_malzeme not in cols and len(cols) > 17:
        col_malzeme = cols[17]
    if col_tarih not in cols and len(cols) > 3:
        col_tarih = cols[3]
    if col_saat not in cols and len(cols) > 31:
        col_saat = cols[31]
    if col_islem_no not in cols and len(cols) > 36:
        col_islem_no = cols[36]
    if col_kasa not in cols and len(cols) > 20:
        col_kasa = cols[20]

    def clean_code(x):
        return str(x).strip().replace('.0', '')

    df_iptal[col_magaza] = df_iptal[col_magaza].apply(clean_code)
    df_iptal[col_malzeme] = df_iptal[col_malzeme].apply(clean_code)

    magaza_str = clean_code(magaza_kodu)
    df_mag = df_iptal[df_iptal[col_magaza] == magaza_str]

    if df_mag.empty:
        return {}

    if envanter_tarihi:
        if isinstance(envanter_tarihi, str):
            envanter_tarihi = pd.to_datetime(envanter_tarihi)
        min_tarih = envanter_tarihi - timedelta(days=30)
        try:
            df_mag = df_mag.copy()
            df_mag[col_tarih] = pd.to_datetime(df_mag[col_tarih], errors='coerce')
            df_mag = df_mag[df_mag[col_tarih] >= min_tarih]
        except:
            pass

    urun_set = set(clean_code(u) for u in urun_kodlari)
    result = {}

    for _, row in df_mag.iterrows():
        malzeme = clean_code(row[col_malzeme])
        if malzeme not in urun_set:
            continue

        if malzeme not in result:
            result[malzeme] = []

        result[malzeme].append({
            'tarih': str(row.get(col_tarih, ''))[:10] if pd.notna(row.get(col_tarih)) else '',
            'saat': str(row.get(col_saat, '')) if pd.notna(row.get(col_saat)) else '',
            'miktar': float(row.get(col_miktar, 0)) if pd.notna(row.get(col_miktar)) else 0,
            'islem_no': str(row.get(col_islem_no, '')) if pd.notna(row.get(col_islem_no)) else '',
            'kasa_no': str(row.get(col_kasa, '')) if pd.notna(row.get(col_kasa)) else ''
        })

    return result


def enrich_with_iptal(df_karsilastirma, magaza_kodu, envanter_tarihi=None):
    """Karşılaştırma sonuçlarına iptal bilgisi ekler"""
    if df_karsilastirma is None or df_karsilastirma.empty:
        return df_karsilastirma

    df = df_karsilastirma.copy()

    # Ürün kodlarını al
    urun_col = 'malzeme_kodu' if 'malzeme_kodu' in df.columns else 'Malzeme Kodu'
    if urun_col not in df.columns:
        return df

    urun_kodlari = df[urun_col].astype(str).unique().tolist()
    iptal_dict = get_iptal_for_surekli_urunler(magaza_kodu, urun_kodlari, envanter_tarihi)

    df['iptal_sayisi'] = 0
    df['iptal_toplam'] = 0.0
    df['iptal_detay'] = ''
    df['kamera_kontrol'] = ''

    for idx, row in df.iterrows():
        urun_kodu = str(row[urun_col])

        if urun_kodu in iptal_dict:
            iptaller = iptal_dict[urun_kodu]
            df.at[idx, 'iptal_sayisi'] = len(iptaller)
            df.at[idx, 'iptal_toplam'] = sum(i['miktar'] for i in iptaller)

            detaylar = []
            for i in iptaller[:3]:
                detaylar.append(f"{i['tarih']} {i['saat']} ({i['miktar']} adet) Kasa:{i['kasa_no']}")
            df.at[idx, 'iptal_detay'] = ' | '.join(detaylar)

            # Uyarı varsa kamera kontrol
            if 'fire' in str(row.get('Durum', '')).lower() or 'açık' in str(row.get('Durum', '')).lower():
                df.at[idx, 'kamera_kontrol'] = f"📹 {len(iptaller)} iptal - Kamera kontrol!"

    return df


def analiz_donem_karsilastirma_with_sheets(supabase_client, df, envanter_tarihi=None):
    """
    v3 için dönem karşılaştırma + Sheets entegrasyonu + İç Hırsızlık Tespiti

    Returns:
        tuple: (sonuclar_dict, hata_mesaji)
        sonuclar_dict = {
            'fire_yazmama': DataFrame,
            'ic_hirsizlik': DataFrame,
            'iptal_artis': DataFrame,
            'kronik_acik': DataFrame
        }
    """
    # Mağaza kodunu al
    magaza_kodu = str(df['Mağaza Kodu'].iloc[0]) if 'Mağaza Kodu' in df.columns else ''

    # Envanter dönemini al
    if 'Envanter Dönemi' in df.columns:
        envanter_donemi = str(df['Envanter Dönemi'].iloc[0])
    else:
        envanter_donemi = datetime.now().strftime('%Y%m')

    # 1. Mevcut veriyi kaydet
    records = prepare_detay_kayitlar(df)
    if records:
        save_detay_to_supabase(supabase_client, records)

    # 2. Önceki veriyi çek
    df_onceki = get_magaza_onceki_kayitlar(supabase_client, magaza_kodu, envanter_donemi)

    # 3. Tüm analizleri yap
    sonuclar = {}

    # Fire yazmama analizi
    fire_yazmama = analiz_fire_yazmama(df, df_onceki)
    if fire_yazmama:
        df_fire = pd.DataFrame(fire_yazmama)
        df_fire = enrich_with_iptal(df_fire, magaza_kodu, envanter_tarihi)
        sonuclar['fire_yazmama'] = df_fire

    # İÇ HIRSIZLIK ANALİZİ (Parçalı envanterdeki gibi)
    ic_hirsizlik = analiz_ic_hirsizlik_surekli(df, df_onceki)
    if ic_hirsizlik:
        df_ic = pd.DataFrame(ic_hirsizlik)
        # Sheets iptal verisiyle zenginleştir
        df_ic = enrich_with_iptal(df_ic, magaza_kodu, envanter_tarihi)
        sonuclar['ic_hirsizlik'] = df_ic

    # İptal artış analizi
    iptal_artis = analiz_iptal_artis(df, df_onceki)
    if iptal_artis:
        sonuclar['iptal_artis'] = pd.DataFrame(iptal_artis)

    # Kronik açık analizi
    kronik_acik = analiz_kronik_acik(df, df_onceki)
    if kronik_acik:
        sonuclar['kronik_acik'] = pd.DataFrame(kronik_acik)

    if not sonuclar:
        return None, "Karşılaştırılacak değişiklik bulunamadı"

    return sonuclar, None


# Geriye uyumluluk - eski fonksiyon isimleri
def prepare_urun_bazli_kayit(df, envanter_tarihi=None):
    """Eski isim - yeni fonksiyona yönlendir"""
    return prepare_detay_kayitlar(df)

def save_urun_bazli_to_supabase(supabase_client, records, batch_size=100):
    """Eski isim - yeni fonksiyona yönlendir"""
    return save_detay_to_supabase(supabase_client, records)

def get_onceki_envanter_urunler(supabase_client, magaza_kodu, envanter_sayisi, envanter_tarihi=None):
    """Eski isim - yeni fonksiyona yönlendir"""
    envanter_donemi = datetime.now().strftime('%Y%m')
    return get_magaza_onceki_kayitlar(supabase_client, magaza_kodu, envanter_donemi)

def karsilastir_donemler(df_current, df_onceki):
    """Eski isim - analiz_fire_yazmama ile uyumlu"""
    return analiz_fire_yazmama(df_current, df_onceki)

def analiz_donem_karsilastirma(supabase_client, df, envanter_tarihi=None):
    """Eski isim - sheets olmadan karşılaştırma"""
    return analiz_donem_karsilastirma_with_sheets(supabase_client, df, envanter_tarihi)
