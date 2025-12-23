# ==================== SÜREKLİ ENVANTER MODÜLÜ v2 ====================
# Haftalık envanter analizi: Et-Tavuk, Ekmek, Meyve/Sebze
# Supabase entegrasyonu ile

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
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
YUKSEK_MIKTAR_ISTISNALAR = ['PATATES', 'SOĞAN', 'SOGAN']
MIN_SATIS_HASILATI = 500

# Risk puan ağırlıkları (toplam 97)
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

# ==================== TEMEL FONKSİYONLAR ====================

def detect_envanter_type(df):
    """Sürekli mi parçalı mı algılar"""
    if 'Depolama Koşulu Grubu' in df.columns:
        if df['Depolama Koşulu Grubu'].astype(str).str.contains('Sürekli', case=False, na=False).any():
            return 'surekli'
    if 'Önceki Fark Miktarı' in df.columns:
        return 'parcali'
    if 'Depolama Koşulu' in df.columns:
        kosullar = set(df['Depolama Koşulu'].dropna().unique())
        surekli_kosullar = {'Et-Tavuk', 'Ekmek', 'Meyve/Sebz'}
        if kosullar.issubset(surekli_kosullar) or kosullar & surekli_kosullar:
            return 'surekli'
    return 'parcali'

def get_magaza_adi_col(df):
    """Mağaza adı kolonunu bul"""
    for col in ['Mağaza Adı', 'Mağaza Tanım']:
        if col in df.columns:
            return col
    return None

def hesapla_kategori_ozet(df):
    """Kategori bazlı özet hesaplar"""
    kategori_col = 'Depolama Koşulu' if 'Depolama Koşulu' in df.columns else None
    if kategori_col is None:
        return {}
    
    sonuc = {}
    for kategori in df[kategori_col].unique():
        df_kat = df[df[kategori_col] == kategori]
        fark = df_kat['Fark Tutarı'].sum() if 'Fark Tutarı' in df_kat.columns else 0
        fire = df_kat['Fire Tutarı'].sum() if 'Fire Tutarı' in df_kat.columns else 0
        satis = df_kat['Satış Hasılatı'].sum() if 'Satış Hasılatı' in df_kat.columns else 0
        toplam_kayip = abs(fark) + abs(fire)
        oran = (toplam_kayip / satis * 100) if satis > 0 else 0
        sonuc[kategori] = {
            'fark': fark, 'fire': fire, 'satis': satis, 
            'oran': oran, 'urun_sayisi': len(df_kat), 'toplam_kayip': toplam_kayip
        }
    return sonuc

# ==================== SM/BS FONKSİYONLARI ====================

def get_sm_list():
    return list(set(v['sm'] for v in SM_BS_MAGAZA.values())) if SM_BS_MAGAZA else []

def get_bs_list():
    return list(set(v['bs'] for v in SM_BS_MAGAZA.values())) if SM_BS_MAGAZA else []

def get_sm_magaza_sayisi():
    sm_counts = {}
    for bilgi in SM_BS_MAGAZA.values():
        sm_counts[bilgi['sm']] = sm_counts.get(bilgi['sm'], 0) + 1
    return sm_counts

def get_bs_magaza_sayisi():
    bs_counts = {}
    for bilgi in SM_BS_MAGAZA.values():
        bs_counts[bilgi['bs']] = bs_counts.get(bilgi['bs'], 0) + 1
    return bs_counts

def get_magazalar_by_sm(sm):
    return {k: v for k, v in SM_BS_MAGAZA.items() if v['sm'] == sm}

def get_magazalar_by_bs(bs):
    return {k: v for k, v in SM_BS_MAGAZA.items() if v['bs'] == bs}

def get_magaza_bilgi(magaza_kodu):
    return SM_BS_MAGAZA.get(str(magaza_kodu), {'sm': 'Bilinmiyor', 'bs': 'Bilinmiyor'})

# ==================== MANİPÜLASYON TESPİT ====================

def detect_yuvarlak_sayi(df):
    """Yuvarlak sayı girişlerini tespit eder"""
    kontrol_kategoriler = ['Meyve/Sebz', 'Et-Tavuk']
    df_filtered = df[df['Depolama Koşulu'].isin(kontrol_kategoriler)] if 'Depolama Koşulu' in df.columns else df
    
    if 'Sayım Miktarı' not in df.columns:
        return pd.DataFrame()
    
    yuvarlak = []
    for _, row in df_filtered.iterrows():
        miktar = row['Sayım Miktarı']
        if pd.notna(miktar) and miktar > 5 and miktar == int(miktar) and int(miktar) % 5 == 0:
            yuvarlak.append(row)
    return pd.DataFrame(yuvarlak)

def detect_anormal_miktar(df):
    """Anormal yüksek miktarları tespit eder"""
    if 'Sayım Miktarı' not in df.columns:
        return pd.DataFrame()
    
    anormal = []
    for _, row in df.iterrows():
        miktar = row['Sayım Miktarı']
        tanim = str(row.get('Malzeme Tanımı', '')).upper()
        istisna = any(ist in tanim for ist in YUKSEK_MIKTAR_ISTISNALAR)
        if pd.notna(miktar) and miktar > 50 and not istisna:
            anormal.append(row)
    return pd.DataFrame(anormal)

def detect_fire_manipulasyon(df):
    """Fire manipülasyonu tespit eder"""
    if 'Fire Tutarı' not in df.columns or 'Fark Tutarı' not in df.columns:
        return pd.DataFrame()
    
    df_check = df.copy()
    df_check['Fire'] = df_check['Fire Tutarı'].fillna(0)
    df_check['Fark'] = df_check['Fark Tutarı'].fillna(0)
    return df_check[(df_check['Fire'] < 0) & (df_check['Fark'] + df_check['Fire'] > 0)]

def get_sayilmasi_gereken_urunler(magaza_kodu, segment='C', blokajli=None):
    """Sayılması gereken ürünleri döner"""
    gecerli_tipler = SEGMENT_MAPPING.get(segment, ['LABCD'])
    sayilmasi_gereken = []
    
    for kod, bilgi in SEGMENT_URUN.items():
        if bilgi['tip'] not in gecerli_tipler:
            continue
        if bilgi['nitelik'] in HARIC_NITELIKLER:
            continue
        sayilmasi_gereken.append(kod)
    
    if blokajli and str(magaza_kodu) in blokajli:
        blokajlilar = set(str(b) for b in blokajli[str(magaza_kodu)])
        sayilmasi_gereken = [u for u in sayilmasi_gereken if u not in blokajlilar]
    
    return sayilmasi_gereken

def detect_sayilmayan_urunler(df, magaza_kodu, blokajli=None):
    """Sayılmayan ürünleri tespit eder"""
    sayilmasi_gereken = get_sayilmasi_gereken_urunler(magaza_kodu, blokajli=blokajli)
    sayilan = set(str(k) for k in df['Malzeme Kodu'].unique()) if 'Malzeme Kodu' in df.columns else set()
    
    sayilmayan = []
    for kod in sayilmasi_gereken:
        if kod not in sayilan:
            urun_bilgi = SEGMENT_URUN.get(kod, {})
            sayilmayan.append({
                'Malzeme Kodu': kod,
                'Malzeme Tanımı': urun_bilgi.get('tanim', kod),
                'Segment': urun_bilgi.get('tip', ''),
                'Fiyat': urun_bilgi.get('fiyat', 0)
            })
    return sayilmayan

# ==================== RİSK SKORU HESAPLAMA ====================

def hesapla_risk_skoru(df, df_onceki=None, urun_medianlar=None, blokajli=None):
    """Sürekli envanter risk skorunu hesaplar - Toplam 97 puan"""
    magaza_kodu = str(df['Mağaza Kodu'].iloc[0]) if 'Mağaza Kodu' in df.columns else None
    detaylar = {}
    toplam_puan = 0
    
    # 1. BÖLGE SAPMA (20p)
    sapma_puan = 0
    sapma_urunler = []
    if urun_medianlar:
        for _, row in df.iterrows():
            kod = str(row.get('Malzeme Kodu', ''))
            if kod in urun_medianlar:
                median = urun_medianlar[kod]['median']
                if median > 0:
                    fark = abs(row.get('Fark Tutarı', 0) or 0)
                    fire = abs(row.get('Fire Tutarı', 0) or 0)
                    satis = row.get('Satış Hasılatı', 0) or 0
                    if satis > MIN_SATIS_HASILATI:
                        magaza_oran = (fark + fire) / satis * 100
                        if magaza_oran > median * 1.5:
                            sapma_urunler.append(str(row.get('Malzeme Tanımı', kod))[:30])
        
        cnt = len(sapma_urunler)
        sapma_puan = 20 if cnt >= 15 else 15 if cnt >= 10 else 10 if cnt >= 5 else 5 if cnt >= 2 else 0
    
    detaylar['bolge_sapma'] = {'puan': sapma_puan, 'max': 20, 'aciklama': f"{len(sapma_urunler)} ürün median üstü", 'urunler': sapma_urunler[:5]}
    toplam_puan += sapma_puan
    
    # 2. SATIR İPTALİ (12p)
    iptal_tutar = abs(df['İptal Satır Tutarı'].sum()) if 'İptal Satır Tutarı' in df.columns else 0
    iptal_puan = 12 if iptal_tutar > 1500 else 8 if iptal_tutar > 500 else 4 if iptal_tutar > 100 else 0
    detaylar['satir_iptali'] = {'puan': iptal_puan, 'max': 12, 'aciklama': f"{iptal_tutar:,.0f} TL iptal", 'tutar': iptal_tutar}
    toplam_puan += iptal_puan
    
    # 3. KRONİK AÇIK (10p)
    kronik_acik_puan = 0
    kronik_acik_urunler = []
    veri_var = df_onceki is not None and not df_onceki.empty
    if veri_var:
        fark_col = 'Fark Miktarı' if 'Fark Miktarı' in df.columns else 'Fark Tutarı'
        if fark_col in df.columns and fark_col in df_onceki.columns:
            cur_neg = set(df[df[fark_col] < 0]['Malzeme Kodu'].astype(str))
            prev_neg = set(df_onceki[df_onceki[fark_col] < 0]['Malzeme Kodu'].astype(str))
            kronik_acik_urunler = list(cur_neg & prev_neg)
            cnt = len(kronik_acik_urunler)
            kronik_acik_puan = 10 if cnt >= 10 else 6 if cnt >= 5 else 3 if cnt >= 2 else 0
    
    detaylar['kronik_acik'] = {'puan': kronik_acik_puan, 'max': 10, 'aciklama': f"{len(kronik_acik_urunler)} ürün 2+ hafta açık" if veri_var else "⏳ Geçmiş veri bekleniyor", 'veri_var': veri_var}
    toplam_puan += kronik_acik_puan
    
    # 4. AİLE ANALİZİ (5p) - TODO
    detaylar['aile_analizi'] = {'puan': 0, 'max': 5, 'aciklama': "Henüz aktif değil"}
    
    # 5. KRONİK FİRE (8p)
    kronik_fire_puan = 0
    kronik_fire_urunler = []
    if veri_var and 'Fire Miktarı' in df.columns and 'Fire Miktarı' in df_onceki.columns:
        cur_fire = set(df[df['Fire Miktarı'] < 0]['Malzeme Kodu'].astype(str))
        prev_fire = set(df_onceki[df_onceki['Fire Miktarı'] < 0]['Malzeme Kodu'].astype(str))
        kronik_fire_urunler = list(cur_fire & prev_fire)
        cnt = len(kronik_fire_urunler)
        kronik_fire_puan = 8 if cnt >= 8 else 5 if cnt >= 4 else 2 if cnt >= 2 else 0
    
    detaylar['kronik_fire'] = {'puan': kronik_fire_puan, 'max': 8, 'aciklama': f"{len(kronik_fire_urunler)} ürün 2+ hafta fire" if veri_var else "⏳ Geçmiş veri bekleniyor", 'veri_var': veri_var}
    toplam_puan += kronik_fire_puan
    
    # 6. FİRE MANİPÜLASYONU (8p)
    fire_manip_df = detect_fire_manipulasyon(df)
    cnt = len(fire_manip_df)
    fire_manip_puan = 8 if cnt >= 5 else 5 if cnt >= 3 else 2 if cnt >= 1 else 0
    detaylar['fire_manipulasyon'] = {'puan': fire_manip_puan, 'max': 8, 'aciklama': f"{cnt} üründe fire↑ açık↓"}
    toplam_puan += fire_manip_puan
    
    # 7. SAYILMAYAN ÜRÜN (8p)
    sayilmayan_puan = 0
    sayilmayan = []
    if magaza_kodu:
        sayilmayan = detect_sayilmayan_urunler(df, magaza_kodu, blokajli)
        cnt = len(sayilmayan)
        sayilmayan_puan = 8 if cnt >= 10 else 5 if cnt >= 5 else 2 if cnt >= 2 else 0
    
    detaylar['sayilmayan_urun'] = {'puan': sayilmayan_puan, 'max': 8, 'aciklama': f"{len(sayilmayan)} ürün sayılmamış", 'urunler': [u['Malzeme Tanımı'] for u in sayilmayan[:5]]}
    toplam_puan += sayilmayan_puan
    
    # 8. ANORMAL MİKTAR (10p)
    anormal_df = detect_anormal_miktar(df)
    cnt = len(anormal_df)
    anormal_puan = 10 if cnt >= 5 else 6 if cnt >= 3 else 3 if cnt >= 1 else 0
    detaylar['anormal_miktar'] = {'puan': anormal_puan, 'max': 10, 'aciklama': f"{cnt} üründe >50 kg/adet"}
    toplam_puan += anormal_puan
    
    # 9. TEKRAR MİKTAR (8p)
    tekrar_puan = 0
    tekrar_urunler = []
    if veri_var and 'Sayım Miktarı' in df.columns and 'Sayım Miktarı' in df_onceki.columns:
        try:
            prev_dict = df_onceki.set_index('Malzeme Kodu')['Sayım Miktarı'].to_dict()
            for _, row in df.iterrows():
                kod = row.get('Malzeme Kodu')
                miktar = row.get('Sayım Miktarı', 0)
                if kod in prev_dict and pd.notna(miktar) and miktar > 0:
                    prev = prev_dict[kod]
                    if pd.notna(prev) and prev > 0 and abs(miktar - prev) / prev <= 0.03:
                        tekrar_urunler.append(str(row.get('Malzeme Tanımı', kod))[:30])
            cnt = len(tekrar_urunler)
            tekrar_puan = 8 if cnt >= 10 else 5 if cnt >= 5 else 2 if cnt >= 2 else 0
        except:
            pass
    
    detaylar['tekrar_miktar'] = {'puan': tekrar_puan, 'max': 8, 'aciklama': f"{len(tekrar_urunler)} ürün aynı miktar" if veri_var else "⏳ Geçmiş veri bekleniyor", 'veri_var': veri_var}
    toplam_puan += tekrar_puan
    
    # 10. YUVARLAK SAYI (8p)
    yuvarlak_df = detect_yuvarlak_sayi(df)
    yuvarlak_oran = len(yuvarlak_df) / max(len(df), 1)
    yuvarlak_puan = 8 if yuvarlak_oran > 0.35 else 5 if yuvarlak_oran > 0.20 else 2 if yuvarlak_oran > 0.10 else 0
    detaylar['yuvarlak_sayi'] = {'puan': yuvarlak_puan, 'max': 8, 'aciklama': f"{len(yuvarlak_df)} ürün (%{yuvarlak_oran*100:.0f}) yuvarlak"}
    toplam_puan += yuvarlak_puan
    
    # Seviye
    if toplam_puan <= 25: seviye, emoji = 'normal', '✅'
    elif toplam_puan <= 50: seviye, emoji = 'dikkat', '⚠️'
    elif toplam_puan <= 75: seviye, emoji = 'riskli', '🟠'
    else: seviye, emoji = 'kritik', '🔴'
    
    return {'toplam_puan': toplam_puan, 'max_puan': 97, 'seviye': seviye, 'emoji': emoji, 'detaylar': detaylar}

# ==================== BÖLGE ÖZETİ ====================

def hesapla_bolge_ozeti(df):
    """Top 10 mağaza, Top 5 ürün"""
    sonuc = {}
    magaza_adi_col = get_magaza_adi_col(df)
    
    if 'Mağaza Kodu' in df.columns:
        agg_dict = {'Fark Tutarı': 'sum', 'Fire Tutarı': 'sum', 'Satış Hasılatı': 'sum'}
        if magaza_adi_col:
            agg_dict[magaza_adi_col] = 'first'
        
        mag_ozet = df.groupby('Mağaza Kodu').agg(agg_dict).reset_index()
        if magaza_adi_col:
            mag_ozet = mag_ozet.rename(columns={magaza_adi_col: 'Mağaza Adı'})
        else:
            mag_ozet['Mağaza Adı'] = mag_ozet['Mağaza Kodu']
        
        mag_ozet['Toplam Kayıp'] = abs(mag_ozet['Fark Tutarı']) + abs(mag_ozet['Fire Tutarı'])
        mag_ozet['Oran'] = np.where(mag_ozet['Satış Hasılatı'] > 0, mag_ozet['Toplam Kayıp'] / mag_ozet['Satış Hasılatı'] * 100, 0)
        sonuc['top10_magaza'] = mag_ozet.nlargest(10, 'Oran')
    
    if 'Malzeme Kodu' in df.columns and 'Fark Tutarı' in df.columns:
        urun = df.groupby(['Malzeme Kodu', 'Malzeme Tanımı']).agg({'Fark Tutarı': 'sum', 'Mağaza Kodu': 'nunique'}).reset_index()
        urun.columns = ['Kod', 'Tanım', 'Fark', 'Mağaza']
        acik = urun[urun['Fark'] < 0].copy()
        acik['Fark'] = abs(acik['Fark'])
        sonuc['top5_acik'] = acik.nlargest(5, 'Fark')
    
    if 'Fire Tutarı' in df.columns:
        urun = df.groupby(['Malzeme Kodu', 'Malzeme Tanımı']).agg({'Fire Tutarı': 'sum', 'Mağaza Kodu': 'nunique'}).reset_index()
        urun.columns = ['Kod', 'Tanım', 'Fire', 'Mağaza']
        fire = urun[urun['Fire'] < 0].copy()
        fire['Fire'] = abs(fire['Fire'])
        sonuc['top5_fire'] = fire.nlargest(5, 'Fire')
    
    return sonuc

def hesapla_urun_bolge_median(df):
    """Ürün bazında bölge medianı"""
    if 'Malzeme Kodu' not in df.columns:
        return {}
    
    urun_oranlar = {}
    for kod in df['Malzeme Kodu'].unique():
        df_urun = df[df['Malzeme Kodu'] == kod]
        oranlar = []
        for mag in df_urun['Mağaza Kodu'].unique():
            df_m = df_urun[df_urun['Mağaza Kodu'] == mag]
            fark = abs(df_m['Fark Tutarı'].sum()) if 'Fark Tutarı' in df_m.columns else 0
            fire = abs(df_m['Fire Tutarı'].sum()) if 'Fire Tutarı' in df_m.columns else 0
            satis = df_m['Satış Hasılatı'].sum() if 'Satış Hasılatı' in df_m.columns else 0
            if satis > MIN_SATIS_HASILATI:
                oranlar.append((fark + fire) / satis * 100)
        if oranlar:
            urun_oranlar[str(kod)] = {'median': np.median(oranlar), 'mean': np.mean(oranlar), 'count': len(oranlar)}
    return urun_oranlar

# ==================== SAYIM DİSİPLİNİ ====================

def hesapla_sayim_disiplini(df, magaza_kodu=None, bs=None, sm=None):
    """Sayım disiplini - sadece dosyadaki mağazalar için"""
    kategoriler = ['Meyve/Sebz', 'Et-Tavuk', 'Ekmek']
    if 'Depolama Koşulu' not in df.columns:
        return None
    
    dosyadaki = set(df['Mağaza Kodu'].astype(str).unique()) if 'Mağaza Kodu' in df.columns else set()
    sonuc = {'kategoriler': {}, 'toplam_beklenen': 0, 'toplam_yapilan': 0}
    
    if magaza_kodu:
        df_m = df[df['Mağaza Kodu'].astype(str) == str(magaza_kodu)]
        for kat in kategoriler:
            sonuc['kategoriler'][kat] = {'beklenen': 1, 'yapilan': 1 if kat in df_m['Depolama Koşulu'].values else 0}
        sonuc['toplam_beklenen'] = 3
        sonuc['toplam_yapilan'] = sum(v['yapilan'] for v in sonuc['kategoriler'].values())
        sonuc['magaza_sayisi'] = 1
    
    elif bs:
        bs_mag = set(k for k, v in SM_BS_MAGAZA.items() if v['bs'] == bs)
        aktif = bs_mag & dosyadaki
        if not aktif:
            return None
        for kat in kategoriler:
            df_k = df[(df['Depolama Koşulu'] == kat) & (df['Mağaza Kodu'].astype(str).isin(aktif))]
            sonuc['kategoriler'][kat] = {'beklenen': len(aktif), 'yapilan': df_k['Mağaza Kodu'].nunique()}
        sonuc['toplam_beklenen'] = len(aktif) * 3
        sonuc['toplam_yapilan'] = sum(v['yapilan'] for v in sonuc['kategoriler'].values())
        sonuc['magaza_sayisi'] = len(aktif)
    
    elif sm:
        sm_mag = set(k for k, v in SM_BS_MAGAZA.items() if v['sm'] == sm)
        aktif = sm_mag & dosyadaki
        if not aktif:
            return None
        for kat in kategoriler:
            df_k = df[(df['Depolama Koşulu'] == kat) & (df['Mağaza Kodu'].astype(str).isin(aktif))]
            sonuc['kategoriler'][kat] = {'beklenen': len(aktif), 'yapilan': df_k['Mağaza Kodu'].nunique()}
        sonuc['toplam_beklenen'] = len(aktif) * 3
        sonuc['toplam_yapilan'] = sum(v['yapilan'] for v in sonuc['kategoriler'].values())
        sonuc['magaza_sayisi'] = len(aktif)
    
    sonuc['oran'] = (sonuc['toplam_yapilan'] / sonuc['toplam_beklenen'] * 100) if sonuc['toplam_beklenen'] > 0 else 0
    return sonuc

# ==================== SM/BS RİSK ÖZETİ ====================

def hesapla_tum_sm_risk(df, df_onceki=None):
    """Dosyadaki SM'lerin risk skorları"""
    dosyadaki = set(df['Mağaza Kodu'].astype(str).unique())
    aktif_sm = set(SM_BS_MAGAZA[m]['sm'] for m in dosyadaki if m in SM_BS_MAGAZA)
    
    sonuc = []
    for sm in aktif_sm:
        sm_mag = set(k for k, v in SM_BS_MAGAZA.items() if v['sm'] == sm) & dosyadaki
        if not sm_mag:
            continue
        
        skorlar = []
        for m in sm_mag:
            df_m = df[df['Mağaza Kodu'].astype(str) == m]
            df_m_onceki = df_onceki[df_onceki['Mağaza Kodu'].astype(str) == m] if df_onceki is not None else None
            risk = hesapla_risk_skoru(df_m, df_m_onceki)
            skorlar.append({'magaza': m, 'skor': risk['toplam_puan'], 'seviye': risk['seviye'], 'emoji': risk['emoji']})
        
        s = [x['skor'] for x in skorlar]
        sonuc.append({
            'sm': sm, 'magaza_sayisi': len(skorlar), 'ortalama_skor': np.mean(s), 'median_skor': np.median(s),
            'kritik': sum(1 for x in skorlar if x['seviye'] == 'kritik'),
            'riskli': sum(1 for x in skorlar if x['seviye'] == 'riskli'),
            'dikkat': sum(1 for x in skorlar if x['seviye'] == 'dikkat'),
            'normal': sum(1 for x in skorlar if x['seviye'] == 'normal'),
            'magazalar': sorted(skorlar, key=lambda x: x['skor'], reverse=True)
        })
    return sorted(sonuc, key=lambda x: x['ortalama_skor'], reverse=True)

def hesapla_tum_bs_risk(df, df_onceki=None):
    """Dosyadaki BS'lerin risk skorları"""
    dosyadaki = set(df['Mağaza Kodu'].astype(str).unique())
    aktif_bs = set(SM_BS_MAGAZA[m]['bs'] for m in dosyadaki if m in SM_BS_MAGAZA)
    
    sonuc = []
    for bs in aktif_bs:
        bs_mag = set(k for k, v in SM_BS_MAGAZA.items() if v['bs'] == bs) & dosyadaki
        if not bs_mag:
            continue
        
        skorlar = []
        for m in bs_mag:
            df_m = df[df['Mağaza Kodu'].astype(str) == m]
            df_m_onceki = df_onceki[df_onceki['Mağaza Kodu'].astype(str) == m] if df_onceki is not None else None
            risk = hesapla_risk_skoru(df_m, df_m_onceki)
            skorlar.append({'magaza': m, 'skor': risk['toplam_puan'], 'seviye': risk['seviye'], 'emoji': risk['emoji']})
        
        s = [x['skor'] for x in skorlar]
        sonuc.append({
            'bs': bs, 'magaza_sayisi': len(skorlar), 'ortalama_skor': np.mean(s),
            'kritik': sum(1 for x in skorlar if x['seviye'] == 'kritik'),
            'riskli': sum(1 for x in skorlar if x['seviye'] == 'riskli'),
            'magazalar': sorted(skorlar, key=lambda x: x['skor'], reverse=True)
        })
    return sorted(sonuc, key=lambda x: x['ortalama_skor'], reverse=True)

# ==================== SUPABASE FONKSİYONLARI ====================

def prepare_surekli_kayit(df, envanter_tarihi=None):
    """Supabase için kayıt hazırla"""
    if envanter_tarihi is None:
        envanter_tarihi = pd.to_datetime(df['Envanter Tarihi']).max() if 'Envanter Tarihi' in df.columns else datetime.now()
    if isinstance(envanter_tarihi, str):
        envanter_tarihi = pd.to_datetime(envanter_tarihi)
    
    records = []
    magaza_adi_col = get_magaza_adi_col(df)
    if 'Depolama Koşulu' not in df.columns or 'Mağaza Kodu' not in df.columns:
        return records
    
    for magaza in df['Mağaza Kodu'].unique():
        df_m = df[df['Mağaza Kodu'] == magaza]
        kod = str(magaza)
        adi = str(df_m[magaza_adi_col].iloc[0])[:100] if magaza_adi_col else ''
        bilgi = get_magaza_bilgi(kod)
        risk = hesapla_risk_skoru(df_m)
        
        for kat in df_m['Depolama Koşulu'].unique():
            df_k = df_m[df_m['Depolama Koşulu'] == kat]
            fark = float(df_k['Fark Tutarı'].sum()) if 'Fark Tutarı' in df_k.columns else 0
            fire = float(df_k['Fire Tutarı'].sum()) if 'Fire Tutarı' in df_k.columns else 0
            satis = float(df_k['Satış Hasılatı'].sum()) if 'Satış Hasılatı' in df_k.columns else 0
            oran = (abs(fark) + abs(fire)) / satis * 100 if satis > 0 else 0
            
            records.append({
                'magaza_kodu': kod, 'magaza_adi': adi, 'sm': bilgi['sm'], 'bs': bilgi['bs'],
                'envanter_tarihi': envanter_tarihi.strftime('%Y-%m-%d'), 'kategori': kat,
                'fark_tutari': round(fark, 2), 'fire_tutari': round(fire, 2),
                'satis_hasilati': round(satis, 2), 'oran': round(oran, 2),
                'sayilan_urun_sayisi': len(df_k), 'toplam_urun_sayisi': len(df_k),
                'risk_skoru': risk['toplam_puan']
            })
    return records

def save_surekli_to_supabase(supabase_client, records):
    """Kayıtları Supabase'e yaz"""
    if not records:
        return 0, 0
    inserted, skipped = 0, 0
    for r in records:
        try:
            supabase_client.table('surekli_envanter_ozet').upsert(r, on_conflict='magaza_kodu,envanter_tarihi,kategori').execute()
            inserted += 1
        except Exception as e:
            if 'duplicate' in str(e).lower():
                skipped += 1
            else:
                raise
    return inserted, skipped

def get_onceki_hafta_verisi(supabase_client, magaza_kodu, envanter_tarihi, gun=7):
    """Önceki hafta verisini çek"""
    if isinstance(envanter_tarihi, str):
        envanter_tarihi = pd.to_datetime(envanter_tarihi)
    onceki = (envanter_tarihi - timedelta(days=gun)).strftime('%Y-%m-%d')
    try:
        r = supabase_client.table('surekli_envanter_ozet').select('*').eq('magaza_kodu', str(magaza_kodu)).eq('envanter_tarihi', onceki).execute()
        return pd.DataFrame(r.data) if r.data else None
    except:
        return None

def get_magaza_gecmis(supabase_client, magaza_kodu, hafta=4):
    """Son N hafta geçmişi"""
    try:
        r = supabase_client.table('surekli_envanter_ozet').select('*').eq('magaza_kodu', str(magaza_kodu)).order('envanter_tarihi', desc=True).limit(hafta * 3).execute()
        return pd.DataFrame(r.data) if r.data else None
    except:
        return None
