import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import datetime
import re
import zipfile

st.set_page_config(page_title="Envanter Risk Analizi", layout="wide", page_icon="📊")

# CSS Stilleri
st.markdown("""
<style>
    .risk-kritik { background-color: #ff4444; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .risk-riskli { background-color: #ff8800; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .risk-dikkat { background-color: #ffcc00; color: black; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .risk-temiz { background-color: #00cc66; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .metric-box { background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin: 5px 0; }
</style>
""", unsafe_allow_html=True)

st.title("🔍 Envanter Risk Analizi Sistemi")
st.markdown("**Perakende envanter denetimi, iç/dış hırsızlık, kasa davranışı ve stok manipülasyonu analizi**")

# Sidebar
with st.sidebar:
    st.header("📁 Veri Yükleme")
    uploaded_file = st.file_uploader("Excel dosyası yükleyin", type=['xlsx', 'xls'])
    
    st.markdown("---")
    st.header("⚙️ Parametreler")
    envanter_donemi = st.text_input("Envanter Dönemi", value="202512")
    envanter_tarihi = st.date_input("Envanter Tarihi", value=datetime.now())
    baslangic_tarihi = st.date_input("Başlangıç Tarihi", value=datetime(2025, 10, 4))
    
    st.markdown("---")
    st.header("📋 Beklenen Sütunlar")
    st.markdown("""
    **Zorunlu:**
    - Mağaza Kodu
    - Malzeme Kodu
    - Malzeme Adı
    - Mal Grubu / Ürün Grubu
    - Marka
    - Fark Miktarı, Fark Tutarı
    - Kısmi Env. Miktarı/Tutarı
    - Önceki Fark Miktarı/Tutarı
    - İptal Satır Miktarı/Tutarı
    - Fire Miktarı/Tutarı
    - Satış Miktarı/Tutarı
    """)


def turkish_lower(text):
    """Türkçe karakterleri düzgün küçültür"""
    if pd.isna(text):
        return ''
    return str(text).lower().replace('I', 'ı').replace('İ', 'i').replace('Ş', 'ş').replace('Ğ', 'ğ').replace('Ü', 'ü').replace('Ö', 'ö').replace('Ç', 'ç')


def analyze_inventory(df):
    """Ana analiz fonksiyonu - sütunları normalize et ve hesapla"""
    
    df = df.copy()
    df.columns = df.columns.str.strip()
    
    # Sütun eşleştirme
    col_mapping = {}
    for col in df.columns:
        col_lower = col.lower()
        if 'mağaza' in col_lower or 'magaza' in col_lower:
            col_mapping[col] = 'Mağaza Kodu'
        elif 'malzeme kodu' in col_lower or 'sku' in col_lower:
            col_mapping[col] = 'Malzeme Kodu'
        elif 'malzeme adı' in col_lower or 'malzeme adi' in col_lower or 'ürün adı' in col_lower:
            col_mapping[col] = 'Malzeme Adı'
        elif 'mal grubu' in col_lower or 'ürün grubu' in col_lower or 'urun grubu' in col_lower:
            col_mapping[col] = 'Ürün Grubu'
        elif col_lower == 'marka':
            col_mapping[col] = 'Marka'
        elif 'fark miktarı' in col_lower or 'fark miktar' in col_lower:
            col_mapping[col] = 'Fark Miktarı'
        elif 'fark tutarı' in col_lower or 'fark tutar' in col_lower:
            col_mapping[col] = 'Fark Tutarı'
        elif 'kısmi' in col_lower and 'miktar' in col_lower:
            col_mapping[col] = 'Kısmi Envanter Miktarı'
        elif 'kısmi' in col_lower and 'tutar' in col_lower:
            col_mapping[col] = 'Kısmi Envanter Tutarı'
        elif 'önceki' in col_lower and 'miktar' in col_lower:
            col_mapping[col] = 'Önceki Fark Miktarı'
        elif 'önceki' in col_lower and 'tutar' in col_lower:
            col_mapping[col] = 'Önceki Fark Tutarı'
        elif 'iptal' in col_lower and 'miktar' in col_lower:
            col_mapping[col] = 'İptal Satır Miktarı'
        elif 'iptal' in col_lower and 'tutar' in col_lower:
            col_mapping[col] = 'İptal Satır Tutarı'
        elif 'fire' in col_lower and 'miktar' in col_lower:
            col_mapping[col] = 'Fire Miktarı'
        elif 'fire' in col_lower and 'tutar' in col_lower:
            col_mapping[col] = 'Fire Tutarı'
        elif 'satış miktarı' in col_lower or 'satis miktar' in col_lower:
            col_mapping[col] = 'Satış Miktarı'
        elif 'satış tutarı' in col_lower or 'satis tutar' in col_lower:
            col_mapping[col] = 'Satış Tutarı'
    
    df = df.rename(columns=col_mapping)
    
    # Eksik sütunları 0 ile doldur
    required_cols = ['Mağaza Kodu', 'Malzeme Kodu', 'Malzeme Adı', 'Ürün Grubu', 'Marka',
                     'Fark Miktarı', 'Fark Tutarı', 'Kısmi Envanter Miktarı', 'Kısmi Envanter Tutarı',
                     'Önceki Fark Miktarı', 'Önceki Fark Tutarı', 'İptal Satır Miktarı', 'İptal Satır Tutarı',
                     'Fire Miktarı', 'Fire Tutarı', 'Satış Miktarı', 'Satış Tutarı']
    
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0 if col not in ['Mağaza Kodu', 'Malzeme Kodu', 'Malzeme Adı', 'Ürün Grubu', 'Marka'] else ''
    
    # Sayısal dönüşüm
    numeric_cols = ['Fark Miktarı', 'Fark Tutarı', 'Kısmi Envanter Miktarı', 'Kısmi Envanter Tutarı',
                    'Önceki Fark Miktarı', 'Önceki Fark Tutarı', 'İptal Satır Miktarı', 'İptal Satır Tutarı',
                    'Fire Miktarı', 'Fire Tutarı', 'Satış Miktarı', 'Satış Tutarı']
    
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # HESAPLAMALAR
    # NET_ENVANTER_ETKİ_TUTARI = Fark Tutarı + Fire Tutarı + Kısmi Envanter Tutarı
    df['NET_ENVANTER_ETKİ_TUTARI'] = df['Fark Tutarı'] + df['Fire Tutarı'] + df['Kısmi Envanter Tutarı']
    
    # TOPLAM = Fark + Kısmi + Önceki
    df['TOPLAM_MIKTAR'] = df['Fark Miktarı'] + df['Kısmi Envanter Miktarı'] + df['Önceki Fark Miktarı']
    
    # Fark + Kısmi (önceki hariç)
    df['FARK_KISMI'] = df['Fark Miktarı'] + df['Kısmi Envanter Miktarı']
    
    # Birim fiyat
    df['Birim Fiyat'] = np.where(df['Fark Miktarı'] != 0, abs(df['Fark Tutarı'] / df['Fark Miktarı']), 0)
    
    return df


def find_similar_products(df):
    """
    Benzer ürün / aile bazlı analiz
    Aynı Mal Grubu + Aynı Marka + Benzer isim = Aile
    Aile toplamı ≈ 0 ise kod/sayım karışıklığı
    """
    
    results = []
    
    # Mal Grubu ve Marka bazında grupla
    if 'Ürün Grubu' in df.columns and 'Marka' in df.columns:
        grouped = df.groupby(['Ürün Grubu', 'Marka'])
        
        for (grup, marka), group_df in grouped:
            if len(group_df) > 1 and pd.notna(marka) and str(marka).strip() != '':
                # Aile toplamı hesapla
                toplam_fark = group_df['Fark Miktarı'].sum()
                toplam_kismi = group_df['Kısmi Envanter Miktarı'].sum()
                toplam_onceki = group_df['Önceki Fark Miktarı'].sum()
                aile_toplami = toplam_fark + toplam_kismi + toplam_onceki
                
                # Fark olan ürünler var mı?
                fark_var = (group_df['Fark Miktarı'] != 0).any()
                
                if fark_var:
                    # Aile toplamı sıfıra yakın mı? (±2 tolerans)
                    if abs(aile_toplami) <= 2:
                        sonuc = "KOD KARIŞIKLIĞI - HIRSIZLIK DEĞİL"
                        risk = "DÜŞÜK"
                    elif aile_toplami < -2:
                        sonuc = "AİLE BAZINDA KAYITSIZ AÇIK"
                        risk = "YÜKSEK"
                    else:
                        sonuc = "AİLE BAZINDA FAZLA"
                        risk = "DÜŞÜK"
                    
                    results.append({
                        'Ürün Grubu': grup,
                        'Marka': marka,
                        'Ürün Sayısı': len(group_df),
                        'Toplam Fark': toplam_fark,
                        'Toplam Kısmi': toplam_kismi,
                        'Toplam Önceki': toplam_onceki,
                        'Aile Toplamı': aile_toplami,
                        'Sonuç': sonuc,
                        'Risk': risk,
                        'Ürünler': ', '.join(group_df['Malzeme Adı'].head(5).tolist())
                    })
    
    return pd.DataFrame(results)


def detect_internal_theft(df):
    """
    İÇ HIRSIZLIK TESPİTİ - DOĞRU KURALLAR:
    
    1. Fark + Kısmi = -Önceki Envanter → SORUN YOK (dengelendi)
    2. Fark + Kısmi + Önceki < 0 → KAYITSIZ AÇIK VAR
    3. Fark + Kısmi + Önceki (eksi) = -İptal Satır Miktarı → ÇOK MUHTEMEL İÇ HIRSIZLIK
       ANCAK: 1 iptal ama 30 açık varsa → İÇ HIRSIZLIK DEĞİL (orantısız)
    """
    
    results = []
    
    for idx, row in df.iterrows():
        fark = row['Fark Miktarı']
        kismi = row['Kısmi Envanter Miktarı']
        onceki = row['Önceki Fark Miktarı']
        iptal = row['İptal Satır Miktarı']
        
        fark_kismi = fark + kismi
        toplam = fark + kismi + onceki
        
        # Sadece açık varsa analiz yap
        if toplam >= 0:
            continue
        
        # İptal satır yoksa iç hırsızlık değil
        if iptal <= 0:
            continue
        
        # ORAN KONTROLÜ: İptal miktarı ile açık miktarı orantılı olmalı
        # Eğer 1 iptal var ama 30 açık varsa → orantısız → iç hırsızlık değil
        oran = abs(toplam) / iptal if iptal > 0 else 999
        
        # Orantılılık kuralı: Oran 1-5 arası olmalı (makul)
        if oran > 5:
            # Orantısız - iç hırsızlık değil
            continue
        
        # Matematik eşitliği kontrolü
        if abs(toplam) == iptal:
            esitlik = "TAM EŞİT"
            risk_seviyesi = "ÇOK YÜKSEK"
        elif abs(toplam) <= iptal * 1.2:  # %20 tolerans
            esitlik = "YAKIN EŞİT"
            risk_seviyesi = "YÜKSEK"
        elif abs(toplam) < iptal:
            esitlik = "TOPLAM < İPTAL"
            risk_seviyesi = "ORTA"
        else:
            esitlik = "TOPLAM > İPTAL (Orantılı)"
            risk_seviyesi = "YÜKSEK"
        
        results.append({
            'Malzeme Kodu': row['Malzeme Kodu'],
            'Malzeme Adı': row['Malzeme Adı'],
            'Ürün Grubu': row.get('Ürün Grubu', ''),
            'Fark Miktarı': fark,
            'Kısmi Envanter': kismi,
            'Önceki Fark': onceki,
            'TOPLAM': toplam,
            'İptal Satır': iptal,
            'Oran (Açık/İptal)': round(oran, 2),
            'Eşitlik Durumu': esitlik,
            'Fark Tutarı': row['Fark Tutarı'],
            'Satış Miktarı': row['Satış Miktarı'],
            'Risk Seviyesi': risk_seviyesi
        })
    
    return pd.DataFrame(results)


def detect_unrecorded_loss(df):
    """
    KAYITSIZ AÇIK TESPİTİ:
    Fark + Kısmi + Önceki Envanter < 0 → Kayıtsız açık var
    (İç hırsızlık matematiğine uymayan ama açık olan ürünler)
    """
    
    results = []
    
    for idx, row in df.iterrows():
        fark = row['Fark Miktarı']
        kismi = row['Kısmi Envanter Miktarı']
        onceki = row['Önceki Fark Miktarı']
        iptal = row['İptal Satır Miktarı']
        toplam = fark + kismi + onceki
        
        # Kayıtsız açık: toplam eksi ve iç hırsızlık matematiğine uymuyor
        if toplam < 0:
            # İç hırsızlık matematiğine uyuyor mu kontrol et
            if iptal > 0:
                oran = abs(toplam) / iptal
                if 0.8 <= oran <= 5:  # Orantılı iptal varsa iç hırsızlık olabilir
                    continue
            
            # Fire var mı?
            fire = row['Fire Miktarı']
            
            if fire == 0:
                sonuc = "DIŞ HIRSIZLIK / SAYIM HATASI"
            else:
                sonuc = "OPERASYONEL KAYIP"
            
            results.append({
                'Malzeme Kodu': row['Malzeme Kodu'],
                'Malzeme Adı': row['Malzeme Adı'],
                'Ürün Grubu': row.get('Ürün Grubu', ''),
                'Fark Miktarı': fark,
                'Kısmi Envanter': kismi,
                'Önceki Fark': onceki,
                'TOPLAM': toplam,
                'Fire': fire,
                'İptal Satır': iptal,
                'Fark Tutarı': row['Fark Tutarı'],
                'Sonuç': sonuc
            })
    
    return pd.DataFrame(results)


def detect_fire_manipulation(df):
    """
    FİRE MANİPÜLASYONU TESPİTİ:
    Fire yüksek AMA Fark + Kısmi > 0 → Fazladan fire giriliyor
    """
    
    results = []
    
    for idx, row in df.iterrows():
        fark = row['Fark Miktarı']
        kismi = row['Kısmi Envanter Miktarı']
        fire = row['Fire Miktarı']
        fark_kismi = fark + kismi
        
        # Fire var ve Fark+Kısmi pozitif ise → manipülasyon şüphesi
        if fire < 0 and fark_kismi > 0:  # Fire negatif tutar olarak gelir genelde
            results.append({
                'Malzeme Kodu': row['Malzeme Kodu'],
                'Malzeme Adı': row['Malzeme Adı'],
                'Ürün Grubu': row.get('Ürün Grubu', ''),
                'Fark Miktarı': fark,
                'Kısmi Envanter': kismi,
                'Fark + Kısmi': fark_kismi,
                'Fire Miktarı': row['Fire Miktarı'],
                'Fire Tutarı': row['Fire Tutarı'],
                'Sonuç': 'FAZLADAN FİRE GİRİLMİŞ OLABİLİR',
                'Satış Miktarı': row['Satış Miktarı']
            })
        
        # Alternatif: Fire miktarı pozitif olarak tutuluyorsa
        if fire > 0 and fark_kismi > 0:
            results.append({
                'Malzeme Kodu': row['Malzeme Kodu'],
                'Malzeme Adı': row['Malzeme Adı'],
                'Ürün Grubu': row.get('Ürün Grubu', ''),
                'Fark Miktarı': fark,
                'Kısmi Envanter': kismi,
                'Fark + Kısmi': fark_kismi,
                'Fire Miktarı': row['Fire Miktarı'],
                'Fire Tutarı': row['Fire Tutarı'],
                'Sonuç': 'FAZLADAN FİRE GİRİLMİŞ OLABİLİR',
                'Satış Miktarı': row['Satış Miktarı']
            })
    
    return pd.DataFrame(results)


def detect_chronic_products(df):
    """Kronik sorunlu ürün tespiti - ardışık dönemlerde açık"""
    
    results = []
    
    for idx, row in df.iterrows():
        if row['Önceki Fark Miktarı'] < 0 and row['Fark Miktarı'] < 0:
            results.append({
                'Malzeme Kodu': row['Malzeme Kodu'],
                'Malzeme Adı': row['Malzeme Adı'],
                'Ürün Grubu': row.get('Ürün Grubu', ''),
                'Bu Dönem Fark': row['Fark Miktarı'],
                'Bu Dönem Tutar': row['Fark Tutarı'],
                'Önceki Dönem Fark': row['Önceki Fark Miktarı'],
                'Önceki Dönem Tutar': row['Önceki Fark Tutarı'],
                'Toplam Kronik Açık': row['Fark Miktarı'] + row['Önceki Fark Miktarı'],
                'İptal Satır': row['İptal Satır Miktarı'],
                'Satış Miktarı': row['Satış Miktarı']
            })
    
    return pd.DataFrame(results)


def detect_balanced_products(df):
    """
    DENGELENMİŞ ÜRÜNLER - SORUN YOK:
    Fark + Kısmi = -Önceki Envanter → Dengelenmiş, sorun yok
    """
    
    results = []
    
    for idx, row in df.iterrows():
        fark = row['Fark Miktarı']
        kismi = row['Kısmi Envanter Miktarı']
        onceki = row['Önceki Fark Miktarı']
        
        fark_kismi = fark + kismi
        
        # Fark+Kısmi = -Önceki (±1 tolerans)
        if onceki != 0 and abs(fark_kismi - (-onceki)) <= 1:
            results.append({
                'Malzeme Kodu': row['Malzeme Kodu'],
                'Malzeme Adı': row['Malzeme Adı'],
                'Fark Miktarı': fark,
                'Kısmi Envanter': kismi,
                'Fark + Kısmi': fark_kismi,
                'Önceki Fark': onceki,
                '-Önceki': -onceki,
                'Durum': 'DENGELENDİ - SORUN YOK'
            })
    
    return pd.DataFrame(results)


def analyze_special_categories(df):
    """Özel kategori analizleri - Sigara, Ekmek vb."""
    
    results = {}
    
    # SİGARA ANALİZİ
    cig_keywords = ['sigara', 'winston', 'marlboro', 'camel', 'parliament', 'kent', 'tekel', 'polo', 'muratti', 'lark']
    cig_mask = (df['Malzeme Adı'].apply(turkish_lower).str.contains('|'.join(cig_keywords), na=False) |
                df['Ürün Grubu'].apply(turkish_lower).str.contains('tütün|sigara', na=False))
    cig_df = df[cig_mask]
    
    if len(cig_df) > 0:
        acik_df = cig_df[cig_df['Fark Miktarı'] < 0]
        results['Sigara'] = {
            'Toplam SKU': len(cig_df),
            'Açık Veren SKU': len(acik_df),
            'Toplam Açık Miktarı': acik_df['Fark Miktarı'].sum() if len(acik_df) > 0 else 0,
            'Toplam Açık Tutarı': acik_df['Fark Tutarı'].sum() if len(acik_df) > 0 else 0,
            'Satış Hasılatı': cig_df['Satış Tutarı'].sum()
        }
    
    # EKMEK ANALİZİ
    bread_keywords = ['ekmek', 'fırın', 'firin', 'somun', 'pide', 'simit', 'poğaça', 'pogaca', 'francala']
    bread_mask = df['Malzeme Adı'].apply(turkish_lower).str.contains('|'.join(bread_keywords), na=False)
    bread_df = df[bread_mask]
    
    if len(bread_df) > 0:
        acik_df = bread_df[bread_df['Fark Miktarı'] < 0]
        fire_var = bread_df['Fire Miktarı'].sum() != 0
        results['Ekmek'] = {
            'Toplam SKU': len(bread_df),
            'Açık Veren SKU': len(acik_df),
            'Toplam Açık Miktarı': acik_df['Fark Miktarı'].sum() if len(acik_df) > 0 else 0,
            'Fire Kaydı': 'VAR' if fire_var else 'YOK',
            'Not': 'Benzer ürün karışıklığı olabilir - Aile analizi yapılmalı'
        }
    
    return results


def analyze_low_value_gaps(df, threshold=100):
    """100 TL altı çoklu açık analizi"""
    
    low_value_df = df[(df['NET_ENVANTER_ETKİ_TUTARI'] < 0) & 
                      (df['NET_ENVANTER_ETKİ_TUTARI'] > -threshold)].copy()
    
    return low_value_df, {
        'Ürün Sayısı': len(low_value_df),
        'Toplam Tutar': low_value_df['NET_ENVANTER_ETKİ_TUTARI'].sum() if len(low_value_df) > 0 else 0,
        'Risk': 'PARÇALI RİSK / KONTROLSÜZLÜK' if len(low_value_df) >= 10 else 'Normal'
    }


def calculate_store_risk_level(df, internal_theft_df, chronic_df):
    """Mağaza risk seviyesi"""
    
    toplam_satis = df['Satış Tutarı'].sum()
    toplam_acik = df[df['Fark Tutarı'] < 0]['Fark Tutarı'].sum()
    
    if toplam_satis > 0:
        kayip_orani = abs(toplam_acik) / toplam_satis * 100
    else:
        kayip_orani = 0
    
    ic_hirsizlik_sayisi = len(internal_theft_df)
    
    if kayip_orani > 2 or ic_hirsizlik_sayisi > 50:
        return "KRİTİK", "risk-kritik"
    elif kayip_orani > 1.5 or ic_hirsizlik_sayisi > 30:
        return "RİSKLİ", "risk-riskli"
    elif kayip_orani > 1 or ic_hirsizlik_sayisi > 15:
        return "DİKKAT", "risk-dikkat"
    else:
        return "TEMİZ", "risk-temiz"


def classify_product_risk(row, internal_codes, chronic_codes, family_mixup_codes):
    """Ürün risk sınıflandırması"""
    
    kod = row['Malzeme Kodu']
    toplam = row['TOPLAM_MIKTAR']
    
    if kod in family_mixup_codes:
        return "KOD KARIŞIKLIĞI", "Aile bazlı analiz: Toplam ≈ 0, hırsızlık değil"
    elif kod in internal_codes:
        return "İÇ HIRSIZLIK", f"Matematik eşitliği: Toplam ({toplam}) ≈ -İptal ({row['İptal Satır Miktarı']})"
    elif kod in chronic_codes:
        return "KRONİK AÇIK", f"Önceki dönemde de açık: {row['Önceki Fark Miktarı']}"
    elif row['Fark Miktarı'] < 0 and row['Fire Miktarı'] == 0:
        return "DIŞ HIRSIZLIK / SAYIM HATASI", "Açık var, fire kaydı yok"
    elif row['Fark Miktarı'] < 0:
        return "OPERASYONEL KAYIP", "Fire kaydı mevcut"
    else:
        return "DİĞER", ""


def get_action_recommendation(risk_type):
    """Önerilen aksiyon"""
    actions = {
        "İÇ HIRSIZLIK": "Kasa kamera incelemesi, Personel görüşmesi, İptal yetkisi kısıtlama",
        "DIŞ HIRSIZLIK / SAYIM HATASI": "Sayım kontrolü, Depo-raf eşleşmesi, Güvenlik etiketi",
        "KRONİK AÇIK": "Raf yerleşimi kontrolü, Sayım eğitimi, Stok takip sıkılaştırma",
        "KOD KARIŞIKLIĞI": "Barkod/kod eğitimi, Benzer ürün ayrımı, Raf düzeni",
        "OPERASYONEL KAYIP": "Fire kayıt disiplini, Operasyonel süreç gözden geçirme"
    }
    return actions.get(risk_type, "Detaylı inceleme")


def create_top_20_risky(df, internal_codes, chronic_codes, family_mixup_codes):
    """En riskli 20 ürün"""
    
    risky_df = df[df['NET_ENVANTER_ETKİ_TUTARI'] < 0].copy()
    
    risky_df['Risk Türü'], risky_df['Gerekçe'] = zip(*risky_df.apply(
        lambda x: classify_product_risk(x, internal_codes, chronic_codes, family_mixup_codes), axis=1))
    
    risky_df['Önerilen Aksiyon'] = risky_df['Risk Türü'].apply(get_action_recommendation)
    
    risky_df = risky_df.sort_values('NET_ENVANTER_ETKİ_TUTARI', ascending=True).head(20)
    
    result = risky_df[['Malzeme Kodu', 'Malzeme Adı', 'Ürün Grubu', 'Fark Miktarı', 
                       'Kısmi Envanter Miktarı', 'Önceki Fark Miktarı', 'TOPLAM_MIKTAR',
                       'İptal Satır Miktarı', 'Fark Tutarı', 'Risk Türü', 'Gerekçe', 
                       'Önerilen Aksiyon']].copy()
    
    result.columns = ['Malzeme Kodu', 'Malzeme Adı', 'Ürün Grubu', 'Fark Miktarı', 
                      'Kısmi Env.', 'Önceki Fark', 'TOPLAM', 'İptal Satır', 
                      'Fark Tutarı (TL)', 'Risk Türü', 'Gerekçe', 'Önerilen Aksiyon']
    
    return result.reset_index(drop=True)


def create_excel_report(df, internal_theft_df, chronic_df, similar_products_df, 
                        fire_manip_df, top_20_df, params, magaza_kodu, magaza_adi):
    """Excel raporu oluştur"""
    
    wb = Workbook()
    
    # Stiller
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill('solid', fgColor='1F4E79')
    title_font = Font(bold=True, size=14)
    subtitle_font = Font(bold=True, size=11)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    
    risk_colors = {
        'KRİTİK': PatternFill('solid', fgColor='FF4444'),
        'RİSKLİ': PatternFill('solid', fgColor='FF8800'),
        'DİKKAT': PatternFill('solid', fgColor='FFCC00'),
        'TEMİZ': PatternFill('solid', fgColor='00CC66')
    }
    
    # ===== ÖZET SAYFASI =====
    ws = wb.active
    ws.title = "ÖZET"
    
    ws['A1'] = f"MAĞAZA {magaza_kodu} - {magaza_adi}"
    ws['A1'].font = title_font
    ws['A2'] = "ENVANTER ANALİZ RAPORU"
    ws['A2'].font = subtitle_font
    
    ws['A4'] = "Envanter Dönemi:"
    ws['B4'] = params['envanter_donemi']
    ws['A5'] = "Envanter Tarihi:"
    ws['B5'] = params['envanter_tarihi']
    ws['A6'] = "Başlangıç Tarihi:"
    ws['B6'] = params['baslangic_tarihi']
    
    ws['A8'] = "GENEL DEĞERLER"
    ws['A8'].font = subtitle_font
    
    ws['A9'] = "Toplam Ürün Sayısı:"
    ws['B9'] = len(df)
    ws['A10'] = "Açık Veren Ürün:"
    ws['B10'] = len(df[df['Fark Miktarı'] < 0])
    ws['A11'] = "Fazla Veren Ürün:"
    ws['B11'] = len(df[df['Fark Miktarı'] > 0])
    
    ws['A13'] = "TUTARLAR"
    ws['A13'].font = subtitle_font
    
    toplam_satis = df['Satış Tutarı'].sum()
    net_fark = df['Fark Tutarı'].sum()
    toplam_acik = df[df['Fark Tutarı'] < 0]['Fark Tutarı'].sum()
    
    ws['A14'] = "Toplam Satış Hasılatı:"
    ws['B14'] = f"{toplam_satis:,.2f} TL"
    ws['A15'] = "Net Fark Tutarı:"
    ws['B15'] = f"{net_fark:,.2f} TL"
    ws['A16'] = "Toplam Açık Tutarı:"
    ws['B16'] = f"{toplam_acik:,.2f} TL"
    ws['A17'] = "Fire Tutarı:"
    ws['B17'] = f"{df['Fire Tutarı'].sum():,.2f} TL"
    ws['A18'] = "İptal Satır Tutarı:"
    ws['B18'] = f"{df['İptal Satır Tutarı'].sum():,.2f} TL"
    
    ws['A20'] = "ENVANTER DİSİPLİNİ"
    ws['A20'].font = subtitle_font
    
    acik_oran = abs(toplam_acik) / toplam_satis * 100 if toplam_satis > 0 else 0
    ws['A21'] = "Açık/Satış Oranı:"
    ws['B21'] = f"%{acik_oran:.2f}"
    
    risk_seviyesi, _ = calculate_store_risk_level(df, internal_theft_df, chronic_df)
    ws['A22'] = "DEĞERLENDİRME:"
    ws['B22'] = risk_seviyesi
    ws['B22'].fill = risk_colors.get(risk_seviyesi, PatternFill())
    
    ws['A24'] = "RİSK DAĞILIMI"
    ws['A24'].font = subtitle_font
    
    ws['A25'] = "İç Hırsızlık (Matematik Eşitliği):"
    ws['B25'] = f"{len(internal_theft_df)} ürün"
    ws['A26'] = "Kronik Sorunlu Ürün:"
    ws['B26'] = f"{len(chronic_df)} ürün"
    ws['A27'] = "Kod Karışıklığı (Aile Bazlı):"
    ws['B27'] = f"{len(similar_products_df[similar_products_df['Risk'] == 'DÜŞÜK']) if len(similar_products_df) > 0 else 0} aile"
    ws['A28'] = "Fire Manipülasyonu Şüphesi:"
    ws['B28'] = f"{len(fire_manip_df)} ürün"
    
    ws.column_dimensions['A'].width = 35
    ws.column_dimensions['B'].width = 30
    
    # ===== EN RİSKLİ 20 ÜRÜN =====
    ws2 = wb.create_sheet("EN RİSKLİ 20 ÜRÜN")
    
    headers = ['Sıra', 'Malzeme Kodu', 'Malzeme Adı', 'Ürün Grubu', 'Fark Miktarı', 
               'Kısmi Env.', 'Önceki Fark', 'TOPLAM', 'İptal Satır', 'Fark Tutarı (TL)', 
               'Risk Türü', 'Gerekçe', 'Önerilen Aksiyon']
    
    for col, header in enumerate(headers, 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
    
    for row_idx, row_data in top_20_df.iterrows():
        ws2.cell(row=row_idx+2, column=1, value=row_idx+1).border = border
        for col_idx, val in enumerate(row_data.values):
            cell = ws2.cell(row=row_idx+2, column=col_idx+2, value=val)
            cell.border = border
    
    # ===== KRONİK ÜRÜNLER =====
    ws3 = wb.create_sheet("KRONİK ÜRÜNLER")
    
    if len(chronic_df) > 0:
        headers = list(chronic_df.columns)
        for col, header in enumerate(headers, 1):
            cell = ws3.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for row_idx, row_data in chronic_df.head(30).iterrows():
            for col_idx, val in enumerate(row_data.values):
                cell = ws3.cell(row=row_idx+2, column=col_idx+1, value=val)
                cell.border = border
    
    # ===== İÇ HIRSIZLIK DETAY =====
    ws4 = wb.create_sheet("İÇ HIRSIZLIK DETAY")
    
    if len(internal_theft_df) > 0:
        headers = list(internal_theft_df.columns)
        for col, header in enumerate(headers, 1):
            cell = ws4.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for row_idx, row_data in internal_theft_df.head(50).iterrows():
            for col_idx, val in enumerate(row_data.values):
                cell = ws4.cell(row=row_idx+2, column=col_idx+1, value=val)
                cell.border = border
    
    # ===== AİLE ANALİZİ (KOD KARIŞIKLIĞI) =====
    ws5 = wb.create_sheet("AİLE ANALİZİ")
    
    if len(similar_products_df) > 0:
        headers = list(similar_products_df.columns)
        for col, header in enumerate(headers, 1):
            cell = ws5.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for row_idx, row_data in similar_products_df.head(50).iterrows():
            for col_idx, val in enumerate(row_data.values):
                cell = ws5.cell(row=row_idx+2, column=col_idx+1, value=val)
                cell.border = border
    
    # ===== FİRE MANİPÜLASYONU =====
    if len(fire_manip_df) > 0:
        ws6 = wb.create_sheet("FİRE MANİPÜLASYONU")
        
        headers = list(fire_manip_df.columns)
        for col, header in enumerate(headers, 1):
            cell = ws6.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for row_idx, row_data in fire_manip_df.head(30).iterrows():
            for col_idx, val in enumerate(row_data.values):
                cell = ws6.cell(row=row_idx+2, column=col_idx+1, value=val)
                cell.border = border
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    return output


def process_single_store(df_store, params, magaza_kodu):
    """Tek mağaza için tüm analizleri yap"""
    
    # Mağaza adını bul
    if 'Mağaza Adı' in df_store.columns:
        magaza_adi = df_store['Mağaza Adı'].iloc[0] if len(df_store) > 0 else magaza_kodu
    else:
        magaza_adi = magaza_kodu
    
    # Analizler
    internal_theft_df = detect_internal_theft(df_store)
    chronic_df = detect_chronic_products(df_store)
    similar_products_df = find_similar_products(df_store)
    fire_manip_df = detect_fire_manipulation(df_store)
    
    # Kod listeleri
    internal_codes = set(internal_theft_df['Malzeme Kodu'].tolist()) if len(internal_theft_df) > 0 else set()
    chronic_codes = set(chronic_df['Malzeme Kodu'].tolist()) if len(chronic_df) > 0 else set()
    
    # Aile bazlı kod karışıklığı olanlar
    family_mixup_codes = set()
    if len(similar_products_df) > 0:
        mixup_families = similar_products_df[similar_products_df['Risk'] == 'DÜŞÜK']
        for _, row in mixup_families.iterrows():
            # Bu ailedeki ürünleri bul
            mask = (df_store['Ürün Grubu'] == row['Ürün Grubu']) & (df_store['Marka'] == row['Marka'])
            family_mixup_codes.update(df_store[mask]['Malzeme Kodu'].tolist())
    
    # Top 20
    top_20_df = create_top_20_risky(df_store, internal_codes, chronic_codes, family_mixup_codes)
    
    # Excel raporu
    excel_output = create_excel_report(
        df_store, internal_theft_df, chronic_df, similar_products_df,
        fire_manip_df, top_20_df, params, magaza_kodu, magaza_adi
    )
    
    return {
        'magaza_kodu': magaza_kodu,
        'magaza_adi': magaza_adi,
        'df': df_store,
        'internal_theft_df': internal_theft_df,
        'chronic_df': chronic_df,
        'similar_products_df': similar_products_df,
        'fire_manip_df': fire_manip_df,
        'top_20_df': top_20_df,
        'excel_output': excel_output
    }


# ===== ANA UYGULAMA =====
if uploaded_file is not None:
    try:
        df_raw = pd.read_excel(uploaded_file)
        st.success(f"✅ Dosya yüklendi! {len(df_raw)} satır, {len(df_raw.columns)} sütun")
        
        with st.expander("📋 Yüklenen Sütunlar"):
            st.write(df_raw.columns.tolist())
        
        # Analiz
        df = analyze_inventory(df_raw)
        
        # Mağaza listesi
        if 'Mağaza Kodu' in df.columns and df['Mağaza Kodu'].nunique() > 1:
            magazalar = df['Mağaza Kodu'].unique().tolist()
            magazalar = [m for m in magazalar if pd.notna(m) and str(m).strip() != '']
            st.info(f"📍 {len(magazalar)} farklı mağaza tespit edildi: {', '.join(str(m) for m in magazalar[:10])}...")
        else:
            magazalar = ['MAGAZA']
            if 'Mağaza Kodu' not in df.columns:
                df['Mağaza Kodu'] = 'MAGAZA'
        
        params = {
            'envanter_donemi': envanter_donemi,
            'envanter_tarihi': envanter_tarihi.strftime('%Y-%m-%d'),
            'baslangic_tarihi': baslangic_tarihi.strftime('%Y-%m-%d')
        }
        
        # Mağaza seçimi
        if len(magazalar) > 1:
            selected_store = st.selectbox("🏪 Mağaza Seçin", ["TÜM MAĞAZALAR"] + magazalar)
        else:
            selected_store = magazalar[0]
        
        # Seçilen mağaza için analiz
        if selected_store == "TÜM MAĞAZALAR":
            df_display = df
        else:
            df_display = df[df['Mağaza Kodu'] == selected_store]
        
        # Analizler
        internal_theft_df = detect_internal_theft(df_display)
        chronic_df = detect_chronic_products(df_display)
        similar_products_df = find_similar_products(df_display)
        fire_manip_df = detect_fire_manipulation(df_display)
        balanced_df = detect_balanced_products(df_display)
        
        internal_codes = set(internal_theft_df['Malzeme Kodu'].tolist()) if len(internal_theft_df) > 0 else set()
        chronic_codes = set(chronic_df['Malzeme Kodu'].tolist()) if len(chronic_df) > 0 else set()
        family_mixup_codes = set()
        
        if len(similar_products_df) > 0:
            mixup_families = similar_products_df[similar_products_df['Risk'] == 'DÜŞÜK']
            for _, row in mixup_families.iterrows():
                mask = (df_display['Ürün Grubu'] == row['Ürün Grubu']) & (df_display['Marka'] == row['Marka'])
                family_mixup_codes.update(df_display[mask]['Malzeme Kodu'].tolist())
        
        top_20_df = create_top_20_risky(df_display, internal_codes, chronic_codes, family_mixup_codes)
        
        risk_seviyesi, risk_class = calculate_store_risk_level(df_display, internal_theft_df, chronic_df)
        
        st.markdown("---")
        
        # Metrikler
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f'<div class="{risk_class}"><h3>RİSK SEVİYESİ</h3><h2>{risk_seviyesi}</h2></div>', 
                       unsafe_allow_html=True)
        with col2:
            st.metric("💰 Toplam Satış", f"{df_display['Satış Tutarı'].sum():,.0f} TL")
        with col3:
            st.metric("📉 Net Fark", f"{df_display['Fark Tutarı'].sum():,.0f} TL")
        with col4:
            toplam_satis = df_display['Satış Tutarı'].sum()
            toplam_acik = df_display[df_display['Fark Tutarı'] < 0]['Fark Tutarı'].sum()
            oran = abs(toplam_acik) / toplam_satis * 100 if toplam_satis > 0 else 0
            st.metric("📊 Açık/Satış", f"%{oran:.2f}")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🔴 İç Hırsızlık", f"{len(internal_theft_df)} ürün")
        with col2:
            st.metric("🟠 Kronik Açık", f"{len(chronic_df)} ürün")
        with col3:
            mixup_count = len(similar_products_df[similar_products_df['Risk'] == 'DÜŞÜK']) if len(similar_products_df) > 0 else 0
            st.metric("🔵 Kod Karışıklığı", f"{mixup_count} aile")
        with col4:
            st.metric("🟣 Fire Manipülasyonu", f"{len(fire_manip_df)} ürün")
        
        st.markdown("---")
        
        # Sekmeler
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "📊 Özet", "🚨 En Riskli 20", "🔒 İç Hırsızlık", 
            "👨‍👩‍👧 Aile Analizi", "🔄 Kronik", "🔥 Fire Manip.", "📥 İndir"
        ])
        
        with tab1:
            st.subheader("📊 Analiz Kuralları ve Özet")
            
            st.markdown("""
            ### 📐 Temel Matematik Kuralları
            
            | Durum | Formül | Sonuç |
            |-------|--------|-------|
            | ✅ Dengelenmiş | Fark + Kısmi = -Önceki | SORUN YOK |
            | ⚠️ Kayıtsız Açık | Fark + Kısmi + Önceki < 0 | AÇIK VAR |
            | 🔴 İç Hırsızlık | (Fark + Kısmi + Önceki) ≈ -İptal Satır | YÜKSEK RİSK |
            | 🟣 Fire Manip. | Fire yüksek AMA Fark + Kısmi > 0 | FAZLA FİRE |
            | 🔵 Kod Karışıklığı | Aile Toplamı ≈ 0 | HIRSIZLIK DEĞİL |
            
            **ÖNEMLİ:** 1 iptal ama 30 açık varsa → İç hırsızlık DEĞİL (orantısız)
            """)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Metrikler")
                metrics = {
                    "Toplam Ürün": len(df_display),
                    "Açık Veren": len(df_display[df_display['Fark Miktarı'] < 0]),
                    "Fazla Veren": len(df_display[df_display['Fark Miktarı'] > 0]),
                    "Dengelenmiş": len(balanced_df),
                    "Toplam Satış": f"{df_display['Satış Tutarı'].sum():,.2f} TL",
                    "Net Fark": f"{df_display['Fark Tutarı'].sum():,.2f} TL"
                }
                st.dataframe(pd.DataFrame(list(metrics.items()), columns=['Metrik', 'Değer']), 
                           hide_index=True, use_container_width=True)
            
            with col2:
                st.markdown("#### Risk Dağılımı")
                risk_data = {
                    "Risk Türü": ["İç Hırsızlık", "Kronik Açık", "Kod Karışıklığı", "Fire Manipülasyonu"],
                    "Sayı": [len(internal_theft_df), len(chronic_df), mixup_count, len(fire_manip_df)]
                }
                st.dataframe(pd.DataFrame(risk_data), hide_index=True, use_container_width=True)
        
        with tab2:
            st.subheader("🚨 En Riskli 20 Ürün")
            st.dataframe(top_20_df, use_container_width=True, hide_index=True)
        
        with tab3:
            st.subheader("🔒 İç Hırsızlık Detayı")
            st.markdown("""
            **Kural:** `|Fark + Kısmi + Önceki| ≈ İptal Satır Miktarı` VE oran orantılı (1-5x)
            
            ⚠️ 1 iptal, 30 açık = İç hırsızlık DEĞİL (orantısız)
            """)
            if len(internal_theft_df) > 0:
                st.dataframe(internal_theft_df, use_container_width=True, hide_index=True)
            else:
                st.success("İç hırsızlık matematiğine uyan ürün tespit edilmedi!")
        
        with tab4:
            st.subheader("👨‍👩‍👧 Aile Bazlı Analiz (Kod Karışıklığı)")
            st.markdown("""
            **Kural:** Aynı Mal Grubu + Aynı Marka + Aile Toplamı ≈ 0 → Kod karışıklığı, hırsızlık değil
            
            Benzer ürünlerde (renk, koku, ml farkı) kodlar karışabilir.
            """)
            if len(similar_products_df) > 0:
                st.dataframe(similar_products_df, use_container_width=True, hide_index=True)
            else:
                st.info("Aile bazlı analiz için Marka sütunu gerekli.")
        
        with tab5:
            st.subheader("🔄 Kronik Açık Veren Ürünler")
            if len(chronic_df) > 0:
                st.dataframe(chronic_df, use_container_width=True, hide_index=True)
            else:
                st.success("Kronik açık veren ürün yok!")
        
        with tab6:
            st.subheader("🔥 Fire Manipülasyonu Şüphesi")
            st.markdown("**Kural:** Fire yüksek AMA Fark + Kısmi > 0 → Fazladan fire giriliyor olabilir")
            if len(fire_manip_df) > 0:
                st.dataframe(fire_manip_df, use_container_width=True, hide_index=True)
            else:
                st.success("Fire manipülasyonu tespit edilmedi!")
        
        with tab7:
            st.subheader("📥 Raporları İndir")
            
            if len(magazalar) > 1:
                st.markdown("### 📦 Tüm Mağazalar İçin ZIP İndir")
                
                if st.button("🗜️ Tüm Mağaza Raporlarını Oluştur"):
                    with st.spinner("Raporlar oluşturuluyor..."):
                        zip_buffer = BytesIO()
                        
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            for mag_kodu in magazalar:
                                df_mag = df[df['Mağaza Kodu'] == mag_kodu]
                                if len(df_mag) > 0:
                                    result = process_single_store(df_mag, params, str(mag_kodu))
                                    zip_file.writestr(
                                        f"{mag_kodu}_Envanter_Risk_Raporu.xlsx",
                                        result['excel_output'].getvalue()
                                    )
                        
                        zip_buffer.seek(0)
                        
                        st.download_button(
                            label="📥 ZIP Dosyasını İndir",
                            data=zip_buffer,
                            file_name=f"Envanter_Raporlari_{envanter_donemi}.zip",
                            mime="application/zip"
                        )
                        st.success(f"✅ {len(magazalar)} mağaza raporu hazır!")
            
            st.markdown("---")
            st.markdown("### 📄 Seçili Mağaza Raporu")
            
            if selected_store != "TÜM MAĞAZALAR":
                result = process_single_store(df_display, params, selected_store)
                
                st.download_button(
                    label=f"📥 {selected_store} Raporu İndir",
                    data=result['excel_output'],
                    file_name=f"{selected_store}_Envanter_Risk_Raporu.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    except Exception as e:
        st.error(f"Hata: {str(e)}")
        st.exception(e)

else:
    st.info("👈 Lütfen sol taraftan Excel dosyası yükleyin.")
    
    st.markdown("""
    ### 📐 Analiz Kuralları
    
    | # | Durum | Formül | Sonuç |
    |---|-------|--------|-------|
    | 1 | ✅ Dengelenmiş | Fark + Kısmi = -Önceki | SORUN YOK |
    | 2 | ⚠️ Kayıtsız Açık | Fark + Kısmi + Önceki < 0 | AÇIK VAR |
    | 3 | 🔴 İç Hırsızlık | (Fark + Kısmi + Önceki) ≈ -İptal | YÜKSEK RİSK |
    | 4 | 🟣 Fire Manipülasyonu | Fire yüksek, Fark + Kısmi > 0 | FAZLA FİRE GİRİLMİŞ |
    | 5 | 🔵 Kod Karışıklığı | Aile Toplamı ≈ 0 | HIRSIZLIK DEĞİL |
    
    ### ⚠️ Önemli Kurallar
    
    - **1 iptal, 30 açık = İç hırsızlık DEĞİL** (orantısız)
    - **Aile analizi:** Aynı marka, aynı grup, benzer isim → Kod karışıklığı olabilir
    - **Matematik desteklemiyorsa SUÇLAMA YAPMA!**
    """)
