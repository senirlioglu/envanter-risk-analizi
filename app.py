import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import datetime
import zipfile

st.set_page_config(page_title="Envanter Risk Analizi", layout="wide", page_icon="📊")

st.markdown("""
<style>
    .risk-kritik { background-color: #ff4444; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .risk-riskli { background-color: #ff8800; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .risk-dikkat { background-color: #ffcc00; color: black; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .risk-temiz { background-color: #00cc66; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🔍 Envanter Risk Analizi Sistemi")
st.markdown("**Perakende envanter denetimi, iç/dış hırsızlık, kasa davranışı ve stok manipülasyonu analizi**")

with st.sidebar:
    st.header("📁 Veri Yükleme")
    uploaded_file = st.file_uploader("Excel dosyası yükleyin", type=['xlsx', 'xls'])


def analyze_inventory(df):
    """Veriyi analiz için hazırla - SENİN SÜTUN İSİMLERİNE GÖRE"""
    
    df = df.copy()
    
    # Sütun eşleştirme - senin veri formatına göre
    col_mapping = {
        'Mağaza Kodu': 'Mağaza Kodu',
        'Mağaza Tanım': 'Mağaza Adı',
        'Malzeme Kodu': 'Malzeme Kodu',
        'Malzeme Tanımı': 'Malzeme Adı',
        'Mal Grubu Tanımı': 'Ürün Grubu',
        'Ürün Grubu Tanımı': 'Ana Grup',
        'Fark Miktarı': 'Fark Miktarı',
        'Fark Tutarı': 'Fark Tutarı',
        'Kısmi Envanter Miktarı': 'Kısmi Envanter Miktarı',
        'Kısmi Envanter Tutarı': 'Kısmi Envanter Tutarı',
        'Önceki Fark Miktarı': 'Önceki Fark Miktarı',
        'Önceki Fark Tutarı': 'Önceki Fark Tutarı',
        'Önceki Fire Miktarı': 'Önceki Fire Miktarı',
        'Önceki Fire Tutarı': 'Önceki Fire Tutarı',
        'İptal Satır Miktarı': 'İptal Satır Miktarı',
        'İptal Satır Tutarı': 'İptal Satır Tutarı',
        'Fire Miktarı': 'Fire Miktarı',
        'Fire Tutarı': 'Fire Tutarı',
        'Satış Miktarı': 'Satış Miktarı',
        'Satış Hasılatı': 'Satış Tutarı',
        'Satış Fiyatı': 'Birim Fiyat',
        'Fark+Fire+Kısmi Envanter Tutarı': 'NET_ENVANTER_ETKİ_TUTARI',
        'Envanter Dönemi': 'Envanter Dönemi',
        'Envanter Tarihi': 'Envanter Tarihi',
    }
    
    # Mevcut sütunları eşleştir
    for old_col, new_col in col_mapping.items():
        if old_col in df.columns:
            df[new_col] = df[old_col]
    
    # Eksik sütunları oluştur
    numeric_cols = ['Fark Miktarı', 'Fark Tutarı', 'Kısmi Envanter Miktarı', 'Kısmi Envanter Tutarı',
                    'Önceki Fark Miktarı', 'Önceki Fark Tutarı', 'İptal Satır Miktarı', 'İptal Satır Tutarı',
                    'Fire Miktarı', 'Fire Tutarı', 'Satış Miktarı', 'Satış Tutarı']
    
    for col in numeric_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # NET_ENVANTER_ETKİ_TUTARI yoksa hesapla
    if 'NET_ENVANTER_ETKİ_TUTARI' not in df.columns:
        df['NET_ENVANTER_ETKİ_TUTARI'] = df['Fark Tutarı'] + df['Fire Tutarı'] + df['Kısmi Envanter Tutarı']
    
    # TOPLAM Miktar
    df['TOPLAM_MIKTAR'] = df['Fark Miktarı'] + df['Kısmi Envanter Miktarı'] + df['Önceki Fark Miktarı']
    
    # Fark + Kısmi
    df['FARK_KISMI'] = df['Fark Miktarı'] + df['Kısmi Envanter Miktarı']
    
    return df


def detect_internal_theft(df):
    """
    İÇ HIRSIZLIK TESPİTİ:
    - Satış Fiyatı >= 100 TL
    - (Fark + Kısmi + Önceki) ≈ -İptal Satır
    - Fark büyüdükçe risk AZALIR, eşitse EN YÜKSEK
    """
    results = []
    
    for idx, row in df.iterrows():
        # Satış fiyatı kontrolü - 100 TL ve üzeri
        satis_fiyati = row.get('Birim Fiyat', 0) or 0
        if satis_fiyati < 100:
            continue
        
        fark = row['Fark Miktarı']
        kismi = row['Kısmi Envanter Miktarı']
        onceki = row['Önceki Fark Miktarı']
        iptal = row['İptal Satır Miktarı']
        
        toplam = fark + kismi + onceki
        
        # Açık ve iptal olmalı
        if toplam >= 0 or iptal <= 0:
            continue
        
        # FARK HESAPLA - Eşitliğe yakınlık
        fark_mutlak = abs(abs(toplam) - iptal)
        
        # Risk seviyesi - fark büyüdükçe risk azalır
        if fark_mutlak == 0:
            risk = "ÇOK YÜKSEK"
            esitlik = "TAM EŞİT"
        elif fark_mutlak <= 2:
            risk = "YÜKSEK"
            esitlik = "YAKIN EŞİT (±2)"
        elif fark_mutlak <= 5:
            risk = "ORTA"
            esitlik = "YAKIN (±5)"
        elif fark_mutlak <= 10:
            risk = "DÜŞÜK-ORTA"
            esitlik = f"FARK: {fark_mutlak}"
        else:
            continue  # Fark çok büyük, iç hırsızlık değil
        
        results.append({
            'Malzeme Kodu': row.get('Malzeme Kodu', ''),
            'Malzeme Adı': row.get('Malzeme Adı', ''),
            'Ürün Grubu': row.get('Ürün Grubu', ''),
            'Satış Fiyatı': satis_fiyati,
            'Fark Miktarı': fark,
            'Kısmi Envanter': kismi,
            'Önceki Fark': onceki,
            'TOPLAM': toplam,
            'İptal Satır': iptal,
            'Fark (Toplam-İptal)': fark_mutlak,
            'Eşitlik Durumu': esitlik,
            'Fark Tutarı (TL)': row['Fark Tutarı'],
            'Satış Miktarı': row['Satış Miktarı'],
            'Risk Seviyesi': risk
        })
    
    # Risk seviyesine göre sırala
    if results:
        risk_order = {'ÇOK YÜKSEK': 0, 'YÜKSEK': 1, 'ORTA': 2, 'DÜŞÜK-ORTA': 3}
        results.sort(key=lambda x: (risk_order.get(x['Risk Seviyesi'], 99), -abs(x['Fark Tutarı (TL)'])))
    
    return pd.DataFrame(results)


def detect_chronic_products(df):
    """Kronik sorunlu ürünler - ardışık dönemlerde açık"""
    results = []
    
    for idx, row in df.iterrows():
        if row['Önceki Fark Miktarı'] < 0 and row['Fark Miktarı'] < 0:
            results.append({
                'Malzeme Kodu': row.get('Malzeme Kodu', ''),
                'Malzeme Adı': row.get('Malzeme Adı', ''),
                'Ürün Grubu': row.get('Ürün Grubu', ''),
                'Bu Dönem Fark': row['Fark Miktarı'],
                'Bu Dönem Tutar (TL)': row['Fark Tutarı'],
                'Önceki Dönem Fark': row['Önceki Fark Miktarı'],
                'Önceki Dönem Tutar (TL)': row['Önceki Fark Tutarı'],
                'İptal Satır': row['İptal Satır Miktarı'],
                'Satış Miktarı': row['Satış Miktarı']
            })
    
    return pd.DataFrame(results)


def detect_chronic_fire(df):
    """Kronik Fire - ardışık dönemlerde fire kaydı olan ürünler"""
    results = []
    
    for idx, row in df.iterrows():
        onceki_fire = row.get('Önceki Fire Miktarı', 0) or 0
        bu_fire = row['Fire Miktarı']
        
        # Her iki dönemde de fire varsa (negatif = fire girişi)
        if onceki_fire != 0 and bu_fire != 0:
            results.append({
                'Malzeme Kodu': row.get('Malzeme Kodu', ''),
                'Malzeme Adı': row.get('Malzeme Adı', ''),
                'Ürün Grubu': row.get('Ürün Grubu', ''),
                'Bu Dönem Fire': bu_fire,
                'Bu Dönem Fire Tutarı (TL)': row['Fire Tutarı'],
                'Önceki Dönem Fire': onceki_fire,
                'Önceki Fire Tutarı (TL)': row.get('Önceki Fire Tutarı', 0),
                'Toplam Fire Tutarı': row['Fire Tutarı'] + row.get('Önceki Fire Tutarı', 0),
                'Satış Miktarı': row['Satış Miktarı']
            })
    
    # Fire tutarına göre yüksekten düşüğe sırala
    result_df = pd.DataFrame(results)
    if len(result_df) > 0:
        result_df = result_df.sort_values('Toplam Fire Tutarı', ascending=True)  # En negatif en üstte
    
    return result_df


def detect_fire_manipulation(df):
    """Fire manipülasyonu: Fire yüksek AMA Fark+Kısmi > 0"""
    results = []
    
    for idx, row in df.iterrows():
        fark_kismi = row['Fark Miktarı'] + row['Kısmi Envanter Miktarı']
        fire = row['Fire Miktarı']
        
        # Fire var (negatif veya pozitif olabilir) ve Fark+Kısmi pozitif
        if abs(fire) > 0 and fark_kismi > 0:
            results.append({
                'Malzeme Kodu': row.get('Malzeme Kodu', ''),
                'Malzeme Adı': row.get('Malzeme Adı', ''),
                'Ürün Grubu': row.get('Ürün Grubu', ''),
                'Fark Miktarı': row['Fark Miktarı'],
                'Kısmi Envanter': row['Kısmi Envanter Miktarı'],
                'Fark + Kısmi': fark_kismi,
                'Fire Miktarı': fire,
                'Fire Tutarı': row['Fire Tutarı'],
                'Sonuç': 'FAZLADAN FİRE GİRİLMİŞ OLABİLİR',
                'Satış Miktarı': row['Satış Miktarı']
            })
    
    return pd.DataFrame(results)


def find_similar_products(df):
    """Benzer ürün ailesi analizi - Mal Grubu bazlı"""
    results = []
    
    if 'Ürün Grubu' not in df.columns:
        return pd.DataFrame()
    
    # Mal Grubu bazında grupla
    for grup, group_df in df.groupby('Ürün Grubu'):
        if len(group_df) > 1:
            toplam_fark = group_df['Fark Miktarı'].sum()
            toplam_kismi = group_df['Kısmi Envanter Miktarı'].sum()
            toplam_onceki = group_df['Önceki Fark Miktarı'].sum()
            aile_toplami = toplam_fark + toplam_kismi + toplam_onceki
            
            # Fark olan ürünler var mı?
            fark_var = (group_df['Fark Miktarı'] != 0).any()
            
            if fark_var and abs(aile_toplami) <= 3:
                results.append({
                    'Ürün Grubu': grup,
                    'Ürün Sayısı': len(group_df),
                    'Toplam Fark': toplam_fark,
                    'Toplam Kısmi': toplam_kismi,
                    'Toplam Önceki': toplam_onceki,
                    'Aile Toplamı': aile_toplami,
                    'Sonuç': 'KOD KARIŞIKLIĞI - HIRSIZLIK DEĞİL' if abs(aile_toplami) <= 2 else 'MUHTEMEL KARIŞIKLIK',
                    'Risk': 'DÜŞÜK',
                    'Ürünler': ', '.join(group_df['Malzeme Adı'].head(5).tolist())
                })
    
    return pd.DataFrame(results)


def detect_external_theft(df):
    """Dış hırsızlık şüphesi - açık var ama fire/iptal yok"""
    results = []
    
    for idx, row in df.iterrows():
        toplam = row['Fark Miktarı'] + row['Kısmi Envanter Miktarı'] + row['Önceki Fark Miktarı']
        
        if toplam < 0 and row['Fire Miktarı'] == 0 and row['İptal Satır Miktarı'] == 0:
            if abs(row['Fark Tutarı']) > 100:  # 100 TL üstü
                results.append({
                    'Malzeme Kodu': row.get('Malzeme Kodu', ''),
                    'Malzeme Adı': row.get('Malzeme Adı', ''),
                    'Ürün Grubu': row.get('Ürün Grubu', ''),
                    'Fark Miktarı': row['Fark Miktarı'],
                    'Fark Tutarı': row['Fark Tutarı'],
                    'Kısmi Envanter': row['Kısmi Envanter Miktarı'],
                    'Önceki Fark': row['Önceki Fark Miktarı'],
                    'Fire': row['Fire Miktarı'],
                    'İptal Satır': row['İptal Satır Miktarı'],
                    'Satış Miktarı': row['Satış Miktarı'],
                    'Risk Türü': 'DIŞ HIRSIZLIK / SAYIM HATASI'
                })
    
    return pd.DataFrame(results)


def detect_cigarette_shortage(df):
    """
    SİGARA AÇIĞI - ÇOK ÖNEMLİ HIRSIZLIK BELİRTİSİ
    Mal Grubu = Sigara
    Formül: Fark + Kısmi Envanter Miktarı - İptal Satır Miktarı
    Negatifse → HIRSIZLIK
    """
    results = []
    
    # Sigara mal gruplarını bul (case insensitive)
    sigara_keywords = ['sigara', 'sıgara', 'cigarette', 'tütün']
    
    for idx, row in df.iterrows():
        urun_grubu = str(row.get('Ürün Grubu', '')).lower()
        mal_grubu = str(row.get('Ana Grup', '')).lower()
        
        is_sigara = any(kw in urun_grubu or kw in mal_grubu for kw in sigara_keywords)
        
        if is_sigara:
            fark = row['Fark Miktarı']
            kismi = row['Kısmi Envanter Miktarı']
            iptal = row['İptal Satır Miktarı']
            
            # Net açık = Fark + Kısmi - İptal
            net_acik = fark + kismi - iptal
            
            if net_acik < 0:  # Açık varsa
                results.append({
                    'Malzeme Kodu': row.get('Malzeme Kodu', ''),
                    'Malzeme Adı': row.get('Malzeme Adı', ''),
                    'Fark Miktarı': fark,
                    'Kısmi Envanter': kismi,
                    'İptal Satır': iptal,
                    'NET AÇIK': net_acik,
                    'Fark Tutarı (TL)': row['Fark Tutarı'],
                    'Satış Miktarı': row['Satış Miktarı'],
                    'Risk': 'YÜKSEK - SİGARA HIRSIZLIĞI'
                })
    
    result_df = pd.DataFrame(results)
    if len(result_df) > 0:
        result_df = result_df.sort_values('NET AÇIK', ascending=True)
    
    return result_df


def calculate_store_risk(df, internal_df, chronic_df):
    """Mağaza risk seviyesi hesapla"""
    toplam_satis = df['Satış Tutarı'].sum()
    toplam_acik = df[df['Fark Tutarı'] < 0]['Fark Tutarı'].sum()
    
    kayip_orani = abs(toplam_acik) / toplam_satis * 100 if toplam_satis > 0 else 0
    ic_hirsizlik = len(internal_df)
    
    if kayip_orani > 2 or ic_hirsizlik > 50:
        return "KRİTİK", "risk-kritik"
    elif kayip_orani > 1.5 or ic_hirsizlik > 30:
        return "RİSKLİ", "risk-riskli"
    elif kayip_orani > 1 or ic_hirsizlik > 15:
        return "DİKKAT", "risk-dikkat"
    else:
        return "TEMİZ", "risk-temiz"


def create_top_20_risky(df, internal_codes, chronic_codes):
    """En riskli 20 ürün - Fire Tutarı dahil"""
    
    risky_df = df[df['NET_ENVANTER_ETKİ_TUTARI'] < 0].copy()
    
    if len(risky_df) == 0:
        return pd.DataFrame(columns=['Sıra', 'Malzeme Kodu', 'Malzeme Adı', 'Ürün Grubu', 
                                     'Fark Miktarı', 'Kısmi Env.', 'Önceki Fark', 'TOPLAM',
                                     'İptal Satır', 'Fire Miktarı', 'Fire Tutarı', 'Fark Tutarı (TL)', 
                                     'Risk Türü', 'Gerekçe', 'Önerilen Aksiyon'])
    
    def classify(row):
        kod = str(row.get('Malzeme Kodu', ''))
        toplam = row['TOPLAM_MIKTAR']
        iptal = row['İptal Satır Miktarı']
        fire = row['Fire Miktarı']
        
        if kod in internal_codes:
            return "İÇ HIRSIZLIK", f"Matematik eşitliği: Toplam ({toplam}) ≈ -İptal ({iptal}). Satış Fiyatı ≥100TL"
        elif kod in chronic_codes:
            return "KRONİK AÇIK", f"Önceki envanterde de {row['Önceki Fark Miktarı']} adet açık. Kronik sorun"
        elif abs(fire) > 0 and row['Fark Miktarı'] < 0:
            return "OPERASYONEL KAYIP", f"Fire kaydı: {fire} adet. Fire ile birlikte açık"
        elif row['Fark Miktarı'] < 0 and fire == 0:
            return "DIŞ HIRSIZLIK / SAYIM HATASI", "Açık var, fire kaydı yok"
        else:
            return "DİĞER", "Detaylı inceleme gerekli"
    
    def get_action(risk_type):
        actions = {
            "İÇ HIRSIZLIK": "Kasa kamera incelemesi, Personel görüşmesi, İptal yetkisi kısıtlama",
            "KRONİK AÇIK": "Raf yerleşimi kontrolü, Sayım eğitimi, Stok takip sıkılaştırma",
            "DIŞ HIRSIZLIK / SAYIM HATASI": "Sayım kontrolü, Depo-raf eşleşmesi, Kod kontrolü",
            "OPERASYONEL KAYIP": "Fire kayıt disiplini, Son kullanma tarihi takibi",
            "DİĞER": "Detaylı inceleme"
        }
        return actions.get(risk_type, "Detaylı inceleme")
    
    risky_df['Risk Türü'] = risky_df.apply(lambda x: classify(x)[0], axis=1)
    risky_df['Gerekçe'] = risky_df.apply(lambda x: classify(x)[1], axis=1)
    risky_df['Önerilen Aksiyon'] = risky_df['Risk Türü'].apply(get_action)
    
    risky_df = risky_df.sort_values('NET_ENVANTER_ETKİ_TUTARI', ascending=True).head(20).reset_index(drop=True)
    
    result = pd.DataFrame({
        'Sıra': range(1, len(risky_df) + 1),
        'Malzeme Kodu': risky_df['Malzeme Kodu'],
        'Malzeme Adı': risky_df['Malzeme Adı'],
        'Ürün Grubu': risky_df['Ürün Grubu'],
        'Fark Miktarı': risky_df['Fark Miktarı'],
        'Kısmi Env.': risky_df['Kısmi Envanter Miktarı'],
        'Önceki Fark': risky_df['Önceki Fark Miktarı'],
        'TOPLAM': risky_df['TOPLAM_MIKTAR'],
        'İptal Satır': risky_df['İptal Satır Miktarı'],
        'Fire Miktarı': risky_df['Fire Miktarı'],
        'Fire Tutarı': risky_df['Fire Tutarı'],
        'Fark Tutarı (TL)': risky_df['Fark Tutarı'],
        'Risk Türü': risky_df['Risk Türü'],
        'Gerekçe': risky_df['Gerekçe'],
        'Önerilen Aksiyon': risky_df['Önerilen Aksiyon']
    })
    
    return result


def create_excel_report(df, internal_df, chronic_df, chronic_fire_df, cigarette_df, external_df, similar_df, fire_df, top20_df, magaza_kodu, magaza_adi, params):
    """Excel raporu oluştur - TÜM ANALİZLER DAHİL"""
    
    wb = Workbook()
    
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill('solid', fgColor='1F4E79')
    title_font = Font(bold=True, size=14)
    subtitle_font = Font(bold=True, size=11)
    border = Border(left=Side(style='thin'), right=Side(style='thin'),
                    top=Side(style='thin'), bottom=Side(style='thin'))
    
    risk_fills = {
        'KRİTİK': PatternFill('solid', fgColor='FF4444'),
        'RİSKLİ': PatternFill('solid', fgColor='FF8800'),
        'DİKKAT': PatternFill('solid', fgColor='FFCC00'),
        'TEMİZ': PatternFill('solid', fgColor='00CC66')
    }
    
    # ===== ÖZET =====
    ws = wb.active
    ws.title = "ÖZET"
    
    ws['A1'] = f"MAĞAZA {magaza_kodu} - {magaza_adi}"
    ws['A1'].font = title_font
    ws['A2'] = "ENVANTER ANALİZ RAPORU"
    ws['A2'].font = subtitle_font
    
    ws['A4'] = "Envanter Dönemi:"
    ws['B4'] = params.get('donem', '')
    ws['A5'] = "Envanter Tarihi:"
    ws['B5'] = params.get('tarih', '')
    
    ws['A7'] = "GENEL DEĞERLER"
    ws['A7'].font = subtitle_font
    
    acik_veren = len(df[df['Fark Miktarı'] < 0])
    fazla_veren = len(df[df['Fark Miktarı'] > 0])
    
    ws['A8'] = "Toplam Ürün Sayısı:"
    ws['B8'] = len(df)
    ws['A9'] = "Açık Veren Ürün:"
    ws['B9'] = acik_veren
    ws['A10'] = "Fazla Veren Ürün:"
    ws['B10'] = fazla_veren
    
    ws['A12'] = "TUTARLAR"
    ws['A12'].font = subtitle_font
    
    toplam_satis = df['Satış Tutarı'].sum()
    net_fark = df['Fark Tutarı'].sum()
    toplam_acik = df[df['Fark Tutarı'] < 0]['Fark Tutarı'].sum()
    toplam_iptal = df['İptal Satır Tutarı'].sum()
    fire_tutari = df['Fire Tutarı'].sum()
    
    ws['A13'] = "Toplam Satış Hasılatı:"
    ws['B13'] = f"{toplam_satis:,.2f} TL"
    ws['A14'] = "Net Fark Tutarı:"
    ws['B14'] = f"{net_fark:,.2f} TL"
    ws['A15'] = "Toplam Açık Tutarı:"
    ws['B15'] = f"{toplam_acik:,.2f} TL"
    ws['A16'] = "Toplam İptal Satır Tutarı:"
    ws['B16'] = f"{toplam_iptal:,.2f} TL"
    ws['A17'] = "Fire Tutarı:"
    ws['B17'] = f"{fire_tutari:,.2f} TL"
    
    ws['A19'] = "ENVANTER DİSİPLİNİ"
    ws['A19'].font = subtitle_font
    
    acik_oran = abs(toplam_acik) / toplam_satis * 100 if toplam_satis > 0 else 0
    
    ws['A20'] = "Açık/Satış Oranı:"
    ws['B20'] = f"%{acik_oran:.2f}"
    
    risk_seviyesi, _ = calculate_store_risk(df, internal_df, chronic_df)
    ws['A21'] = "DEĞERLENDİRME:"
    ws['B21'] = risk_seviyesi
    ws['B21'].fill = risk_fills.get(risk_seviyesi, PatternFill())
    ws['B21'].font = Font(bold=True)
    
    ws['A23'] = "RİSK DAĞILIMI"
    ws['A23'].font = subtitle_font
    
    ic_tutar = internal_df['Fark Tutarı (TL)'].sum() if len(internal_df) > 0 else 0
    
    ws['A24'] = "İç Hırsızlık (≥100TL ürünler):"
    ws['B24'] = f"{len(internal_df)} ürün ({ic_tutar:,.2f} TL)"
    ws['A25'] = "Kronik Açık:"
    ws['B25'] = f"{len(chronic_df)} ürün"
    ws['A26'] = "Kronik Fire:"
    ws['B26'] = f"{len(chronic_fire_df)} ürün"
    ws['A27'] = "Dış Hırsızlık Şüphesi:"
    ws['B27'] = f"{len(external_df)} ürün"
    
    # SİGARA AÇIĞI - ÖNEMLİ
    ws['A29'] = "🚬 SİGARA AÇIĞI:"
    ws['A29'].font = Font(bold=True, color='FF0000')
    ws['B29'] = f"{len(cigarette_df)} ürün"
    if len(cigarette_df) > 0:
        ws['B29'].fill = PatternFill('solid', fgColor='FF4444')
        ws['B29'].font = Font(bold=True, color='FFFFFF')
        ws['C29'] = "⚠️ HIRSIZLIK BELİRTİSİ!"
        ws['C29'].font = Font(bold=True, color='FF0000')
    
    ws.column_dimensions['A'].width = 40
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 25
    
    # ===== EN RİSKLİ 20 ÜRÜN =====
    ws2 = wb.create_sheet("EN RİSKLİ 20 ÜRÜN")
    
    if len(top20_df) > 0:
        headers = list(top20_df.columns)
        for col, h in enumerate(headers, 1):
            cell = ws2.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for r_idx, row in top20_df.iterrows():
            for c_idx, val in enumerate(row.values, 1):
                cell = ws2.cell(row=r_idx+2, column=c_idx, value=val)
                cell.border = border
    
    # ===== KRONİK AÇIK =====
    ws3 = wb.create_sheet("KRONİK AÇIK")
    
    if len(chronic_df) > 0:
        headers = list(chronic_df.columns)
        for col, h in enumerate(headers, 1):
            cell = ws3.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for r_idx, row in chronic_df.head(50).iterrows():
            for c_idx, val in enumerate(row.values, 1):
                cell = ws3.cell(row=r_idx+2, column=c_idx, value=val)
                cell.border = border
    
    # ===== KRONİK FİRE =====
    ws_fire = wb.create_sheet("KRONİK FİRE")
    
    if len(chronic_fire_df) > 0:
        headers = list(chronic_fire_df.columns)
        for col, h in enumerate(headers, 1):
            cell = ws_fire.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for r_idx, row in chronic_fire_df.head(50).iterrows():
            for c_idx, val in enumerate(row.values, 1):
                cell = ws_fire.cell(row=r_idx+2, column=c_idx, value=val)
                cell.border = border
    
    # ===== SİGARA AÇIĞI =====
    ws_cig = wb.create_sheet("SİGARA AÇIĞI")
    
    ws_cig['A1'] = "⚠️ SİGARA AÇIĞI - YÜKSEK RİSK"
    ws_cig['A1'].font = Font(bold=True, size=14, color='FF0000')
    ws_cig['A2'] = "Sigarada açık = HIRSIZLIK BELİRTİSİ"
    
    if len(cigarette_df) > 0:
        headers = list(cigarette_df.columns)
        for col, h in enumerate(headers, 1):
            cell = ws_cig.cell(row=4, column=col, value=h)
            cell.font = header_font
            cell.fill = PatternFill('solid', fgColor='FF4444')
            cell.border = border
        
        for r_idx, row in cigarette_df.iterrows():
            for c_idx, val in enumerate(row.values, 1):
                cell = ws_cig.cell(row=r_idx+5, column=c_idx, value=val)
                cell.border = border
    
    # ===== İÇ HIRSIZLIK DETAY =====
    ws4 = wb.create_sheet("İÇ HIRSIZLIK DETAY")
    
    ws4['A1'] = "İç Hırsızlık Analizi (Satış Fiyatı ≥ 100 TL)"
    ws4['A1'].font = title_font
    ws4['A2'] = "Fark büyüdükçe risk AZALIR, eşitse EN YÜKSEK"
    
    if len(internal_df) > 0:
        headers = list(internal_df.columns)
        for col, h in enumerate(headers, 1):
            cell = ws4.cell(row=4, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for r_idx, row in internal_df.head(50).iterrows():
            for c_idx, val in enumerate(row.values, 1):
                cell = ws4.cell(row=r_idx+5, column=c_idx, value=val)
                cell.border = border
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ===== ANA UYGULAMA =====
if uploaded_file is not None:
    try:
        # Önce sheet isimlerini kontrol et
        xl = pd.ExcelFile(uploaded_file)
        sheet_names = xl.sheet_names
        
        # En çok satırı olan veya 'Sayfa1' sheet'ini bul
        best_sheet = None
        max_rows = 0
        
        for sheet in sheet_names:
            temp_df = pd.read_excel(uploaded_file, sheet_name=sheet, nrows=5)
            # Sütun sayısı 20'den fazlaysa muhtemelen veri sheet'i
            if len(temp_df.columns) > 20:
                full_df = pd.read_excel(uploaded_file, sheet_name=sheet)
                if len(full_df) > max_rows:
                    max_rows = len(full_df)
                    best_sheet = sheet
        
        # Eğer uygun sheet bulunamadıysa ilk sheet'i kullan
        if best_sheet is None:
            best_sheet = sheet_names[0]
        
        df_raw = pd.read_excel(uploaded_file, sheet_name=best_sheet)
        st.success(f"✅ Dosya yüklendi! {len(df_raw)} satır, {len(df_raw.columns)} sütun (Sheet: {best_sheet})")
        
        with st.expander("📋 Yüklenen Sütunlar"):
            st.write(df_raw.columns.tolist())
        
        # Analiz
        df = analyze_inventory(df_raw)
        
        # Mağaza bilgisi
        if 'Mağaza Kodu' in df.columns:
            magazalar = df['Mağaza Kodu'].dropna().unique().tolist()
        else:
            magazalar = ['MAGAZA']
            df['Mağaza Kodu'] = 'MAGAZA'
        
        if 'Mağaza Adı' in df.columns:
            magaza_adi = df['Mağaza Adı'].iloc[0] if len(df) > 0 else ''
        else:
            magaza_adi = ''
        
        # Dönem bilgisi
        params = {
            'donem': df['Envanter Dönemi'].iloc[0] if 'Envanter Dönemi' in df.columns else '',
            'tarih': str(df['Envanter Tarihi'].iloc[0])[:10] if 'Envanter Tarihi' in df.columns else '',
            'baslangic': ''
        }
        
        # Mağaza seçimi
        if len(magazalar) > 1:
            selected = st.selectbox("🏪 Mağaza Seçin", magazalar)
            df_display = df[df['Mağaza Kodu'] == selected]
        else:
            selected = magazalar[0]
            df_display = df
        
        # Analizler
        internal_df = detect_internal_theft(df_display)
        chronic_df = detect_chronic_products(df_display)
        chronic_fire_df = detect_chronic_fire(df_display)
        external_df = detect_external_theft(df_display)
        similar_df = find_similar_products(df_display)
        fire_df = detect_fire_manipulation(df_display)
        cigarette_df = detect_cigarette_shortage(df_display)
        
        internal_codes = set(internal_df['Malzeme Kodu'].astype(str).tolist()) if len(internal_df) > 0 else set()
        chronic_codes = set(chronic_df['Malzeme Kodu'].astype(str).tolist()) if len(chronic_df) > 0 else set()
        
        top20_df = create_top_20_risky(df_display, internal_codes, chronic_codes)
        
        risk_seviyesi, risk_class = calculate_store_risk(df_display, internal_df, chronic_df)
        
        st.markdown("---")
        
        # Metrikler - Üst Satır
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f'<div class="{risk_class}"><h3>RİSK SEVİYESİ</h3><h2>{risk_seviyesi}</h2></div>', unsafe_allow_html=True)
        with col2:
            st.metric("💰 Toplam Satış", f"{df_display['Satış Tutarı'].sum():,.2f} TL")
        with col3:
            st.metric("📉 Net Fark", f"{df_display['Fark Tutarı'].sum():,.2f} TL")
        with col4:
            toplam_satis = df_display['Satış Tutarı'].sum()
            toplam_acik = df_display[df_display['Fark Tutarı'] < 0]['Fark Tutarı'].sum()
            oran = abs(toplam_acik) / toplam_satis * 100 if toplam_satis > 0 else 0
            st.metric("📊 Açık/Satış", f"%{oran:.2f}")
        
        # Metrikler - Alt Satır
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("🔴 İç Hırsızlık", f"{len(internal_df)} ürün")
        with col2:
            st.metric("🟠 Kronik Açık", f"{len(chronic_df)} ürün")
        with col3:
            st.metric("🔥 Kronik Fire", f"{len(chronic_fire_df)} ürün")
        with col4:
            st.metric("🟣 Fire Manip.", f"{len(fire_df)} ürün")
        with col5:
            # SİGARA AÇIĞI - ÇOK ÖNEMLİ
            sigara_count = len(cigarette_df)
            if sigara_count > 0:
                st.metric("🚬 SİGARA AÇIĞI", f"{sigara_count} ürün", delta="HIRSIZLIK!", delta_color="inverse")
            else:
                st.metric("🚬 Sigara Açığı", "0 ürün")
        
        st.markdown("---")
        
        # Sekmeler
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
            "📊 Özet", "🚨 En Riskli 20", "🔒 İç Hırsızlık", 
            "🔄 Kronik Açık", "🔥 Kronik Fire", "🚬 Sigara", "🟡 Dış Hırsızlık", "📥 İndir"
        ])
        
        with tab1:
            st.subheader("📊 Genel Özet")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Metrikler")
                metrics = {
                    'Metrik': ['Toplam Ürün', 'Açık Veren', 'Fazla Veren', 'Toplam Satış', 'Net Fark', 'Fire Tutarı'],
                    'Değer': [
                        len(df_display),
                        len(df_display[df_display['Fark Miktarı'] < 0]),
                        len(df_display[df_display['Fark Miktarı'] > 0]),
                        f"{df_display['Satış Tutarı'].sum():,.2f} TL",
                        f"{df_display['Fark Tutarı'].sum():,.2f} TL",
                        f"{df_display['Fire Tutarı'].sum():,.2f} TL"
                    ]
                }
                st.dataframe(pd.DataFrame(metrics), hide_index=True, use_container_width=True)
            
            with col2:
                st.markdown("#### Risk Dağılımı")
                risk_data = {
                    'Risk Türü': ['İç Hırsızlık (≥100TL)', 'Kronik Açık', 'Kronik Fire', 'Sigara Açığı', 'Fire Manipülasyonu'],
                    'Sayı': [len(internal_df), len(chronic_df), len(chronic_fire_df), len(cigarette_df), len(fire_df)]
                }
                st.dataframe(pd.DataFrame(risk_data), hide_index=True, use_container_width=True)
                
                if len(cigarette_df) > 0:
                    st.error(f"⚠️ **SİGARA AÇIĞI TESPİT EDİLDİ!** {len(cigarette_df)} üründe açık var - HIRSIZLIK BELİRTİSİ")
        
        with tab2:
            st.subheader("🚨 En Riskli 20 Ürün")
            st.markdown("*Fire Tutarı dahil - Operasyonel kayıpları görebilirsiniz*")
            if len(top20_df) > 0:
                st.dataframe(top20_df, use_container_width=True, hide_index=True)
            else:
                st.success("Riskli ürün tespit edilmedi!")
        
        with tab3:
            st.subheader("🔒 İç Hırsızlık Detayı")
            st.markdown("""
            **Kurallar:**
            - Satış Fiyatı ≥ **100 TL** olan ürünler
            - `|Fark + Kısmi + Önceki| ≈ İptal Satır`
            - Fark büyüdükçe risk **AZALIR**, eşitse **EN YÜKSEK**
            
            ⚠️ 1 iptal, 30 açık = Fark çok büyük = İç hırsızlık **DEĞİL**
            """)
            if len(internal_df) > 0:
                st.dataframe(internal_df, use_container_width=True, hide_index=True)
            else:
                st.success("İç hırsızlık matematiğine uyan ürün yok!")
        
        with tab4:
            st.subheader("🔄 Kronik Açık Veren Ürünler")
            st.markdown("**Kural:** Hem bu dönem hem önceki dönemde Fark < 0")
            if len(chronic_df) > 0:
                st.dataframe(chronic_df, use_container_width=True, hide_index=True)
            else:
                st.success("Kronik açık veren ürün yok!")
        
        with tab5:
            st.subheader("🔥 Kronik Fire")
            st.markdown("**Kural:** Hem bu dönem hem önceki dönemde Fire kaydı var (Yüksekten düşüğe sıralı)")
            if len(chronic_fire_df) > 0:
                st.dataframe(chronic_fire_df, use_container_width=True, hide_index=True)
            else:
                st.success("Kronik fire kaydı yok!")
        
        with tab6:
            st.subheader("🚬 Sigara Açığı - YÜKSEK RİSK")
            st.markdown("""
            **Kural:** Mal Grubu = Sigara
            
            **Formül:** `Fark + Kısmi Envanter - İptal Satır < 0`
            
            ⚠️ **Sigarada açık = HIRSIZLIK BELİRTİSİ**
            """)
            if len(cigarette_df) > 0:
                st.error(f"🚨 **{len(cigarette_df)} üründe sigara açığı tespit edildi!**")
                st.dataframe(cigarette_df, use_container_width=True, hide_index=True)
            else:
                st.success("Sigara açığı yok!")
        
        with tab7:
            st.subheader("🟡 Dış Hırsızlık / Sayım Hatası Şüphesi")
            st.markdown("**Kural:** Açık var ama Fire ve İptal Satır yok")
            if len(external_df) > 0:
                st.dataframe(external_df, use_container_width=True, hide_index=True)
            else:
                st.success("Dış hırsızlık şüphesi yok!")
        
        with tab8:
            st.subheader("📥 Excel Raporu İndir")
            
            # Tek mağaza raporu
            excel_output = create_excel_report(
                df_display, internal_df, chronic_df, chronic_fire_df, cigarette_df,
                external_df, similar_df, fire_df, top20_df,
                selected, magaza_adi, params
            )
            
            st.download_button(
                label=f"📥 {selected} Raporu İndir",
                data=excel_output,
                file_name=f"{selected}_Envanter_Risk_Raporu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # Çoklu mağaza - ZIP indirme
            if len(magazalar) > 1:
                st.markdown("---")
                st.markdown("### 📦 Tüm Mağazalar (ZIP)")
                
                if st.button("🗜️ Tüm Mağaza Raporlarını Hazırla"):
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for mag in magazalar:
                            df_mag = df[df['Mağaza Kodu'] == mag]
                            mag_adi = df_mag['Mağaza Adı'].iloc[0] if 'Mağaza Adı' in df_mag.columns and len(df_mag) > 0 else ''
                            
                            # Her mağaza için analiz
                            int_df = detect_internal_theft(df_mag)
                            chr_df = detect_chronic_products(df_mag)
                            chr_fire_df = detect_chronic_fire(df_mag)
                            cig_df = detect_cigarette_shortage(df_mag)
                            ext_df = detect_external_theft(df_mag)
                            sim_df = find_similar_products(df_mag)
                            fir_df = detect_fire_manipulation(df_mag)
                            
                            int_codes = set(int_df['Malzeme Kodu'].astype(str).tolist()) if len(int_df) > 0 else set()
                            chr_codes = set(chr_df['Malzeme Kodu'].astype(str).tolist()) if len(chr_df) > 0 else set()
                            
                            t20_df = create_top_20_risky(df_mag, int_codes, chr_codes)
                            
                            excel_data = create_excel_report(
                                df_mag, int_df, chr_df, chr_fire_df, cig_df,
                                ext_df, sim_df, fir_df, t20_df,
                                mag, mag_adi, params
                            )
                            
                            zf.writestr(f"{mag}_Envanter_Risk_Raporu.xlsx", excel_data.getvalue())
                    
                    zip_buffer.seek(0)
                    st.download_button(
                        label=f"📥 {len(magazalar)} Mağaza Raporu İndir (ZIP)",
                        data=zip_buffer,
                        file_name="Tum_Magazalar_Envanter_Raporu.zip",
                        mime="application/zip"
                    )
    
    except Exception as e:
        st.error(f"Hata: {str(e)}")
        st.exception(e)

else:
    st.info("👈 Lütfen sol taraftan Excel dosyası yükleyin.")
    
    st.markdown("""
    ### 📐 Analiz Kuralları
    
    | Durum | Formül | Sonuç |
    |-------|--------|-------|
    | ✅ Dengelenmiş | Fark + Kısmi = -Önceki | SORUN YOK |
    | ⚠️ Kayıtsız Açık | Fark + Kısmi + Önceki < 0 | AÇIK VAR |
    | 🔴 İç Hırsızlık | \|Toplam\| ≈ İptal VE Oran 1-5 | YÜKSEK RİSK |
    | ❌ Orantısız | 1 iptal, 30 açık | İç Hırsızlık DEĞİL |
    
    ### ⛔ Altın Kural
    > **Matematik desteklemiyorsa SUÇLAMA YAPMA!**
    """)
