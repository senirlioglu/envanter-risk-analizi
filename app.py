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
    (Fark + Kısmi + Önceki) ≈ -İptal Satır VE Oran 1-5 arası
    1 iptal, 30 açık = İç hırsızlık DEĞİL
    """
    results = []
    
    for idx, row in df.iterrows():
        fark = row['Fark Miktarı']
        kismi = row['Kısmi Envanter Miktarı']
        onceki = row['Önceki Fark Miktarı']
        iptal = row['İptal Satır Miktarı']
        
        toplam = fark + kismi + onceki
        
        # Açık ve iptal olmalı
        if toplam >= 0 or iptal <= 0:
            continue
        
        # ORAN KONTROLÜ
        oran = abs(toplam) / iptal
        
        # Oran 1-5 arası olmalı (orantılı)
        if oran > 5:
            continue  # Orantısız - iç hırsızlık değil
        
        # Eşitlik durumu
        if abs(abs(toplam) - iptal) <= 1:
            esitlik = "TAM EŞİT"
            risk = "ÇOK YÜKSEK"
        elif oran <= 2:
            esitlik = "YAKIN EŞİT"
            risk = "YÜKSEK"
        else:
            esitlik = "ORANTILI"
            risk = "ORTA-YÜKSEK"
        
        results.append({
            'Malzeme Kodu': row.get('Malzeme Kodu', ''),
            'Malzeme Adı': row.get('Malzeme Adı', ''),
            'Ürün Grubu': row.get('Ürün Grubu', ''),
            'Fark Miktarı': fark,
            'Kısmi Envanter': kismi,
            'Önceki Fark': onceki,
            'TOPLAM': toplam,
            'İptal Satır (-)': -iptal,
            'Oran': round(oran, 2),
            'Eşitlik Durumu': esitlik,
            'Fark Tutarı (TL)': row['Fark Tutarı'],
            'Satış Miktarı': row['Satış Miktarı'],
            'Risk Seviyesi': risk
        })
    
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
    """En riskli 20 ürün"""
    
    risky_df = df[df['NET_ENVANTER_ETKİ_TUTARI'] < 0].copy()
    
    if len(risky_df) == 0:
        return pd.DataFrame(columns=['Sıra', 'Malzeme Kodu', 'Malzeme Adı', 'Ürün Grubu', 
                                     'Fark Miktarı', 'Kısmi Env.', 'Önceki Fark', 'TOPLAM',
                                     'İptal Satır', 'Fark Tutarı (TL)', 'Risk Türü', 'Gerekçe', 'Önerilen Aksiyon'])
    
    def classify(row):
        kod = str(row.get('Malzeme Kodu', ''))
        toplam = row['TOPLAM_MIKTAR']
        iptal = row['İptal Satır Miktarı']
        
        if kod in internal_codes:
            return "İÇ HIRSIZLIK", f"Matematik eşitliği: Toplam ({toplam}) ≈ -İptal ({iptal}). %90+ İç Hırsızlık"
        elif kod in chronic_codes:
            return "KRONİK AÇIK", f"Önceki envanterde de {row['Önceki Fark Miktarı']} adet açık. Kronik sorun"
        elif row['Fark Miktarı'] < 0 and row['Fire Miktarı'] == 0:
            return "DIŞ HIRSIZLIK / SAYIM HATASI", "Açık miktarı yüksek, fire kaydı yok"
        else:
            return "OPERASYONEL KAYIP", "Fire kaydı mevcut"
    
    def get_action(risk_type):
        actions = {
            "İÇ HIRSIZLIK": "Kasa kamera incelemesi, Personel görüşmesi, İptal yetkisi kısıtlama",
            "KRONİK AÇIK": "Raf yerleşimi kontrolü, Sayım eğitimi, Stok takip sıkılaştırma",
            "DIŞ HIRSIZLIK / SAYIM HATASI": "Sayım kontrolü, Depo-raf eşleşmesi, Kod kontrolü",
            "OPERASYONEL KAYIP": "Fire kayıt disiplini, Operasyonel süreç gözden geçirme"
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
        'Fark Tutarı (TL)': risky_df['Fark Tutarı'],
        'Risk Türü': risky_df['Risk Türü'],
        'Gerekçe': risky_df['Gerekçe'],
        'Önerilen Aksiyon': risky_df['Önerilen Aksiyon']
    })
    
    return result


def create_excel_report(df, internal_df, chronic_df, external_df, similar_df, fire_df, top20_df, magaza_kodu, magaza_adi, params):
    """Excel raporu oluştur - SENİN FORMATINDA"""
    
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
    ws['A6'] = "Başlangıç Tarihi:"
    ws['B6'] = params.get('baslangic', '')
    
    ws['A8'] = "GENEL DEĞERLER"
    ws['A8'].font = subtitle_font
    
    acik_veren = len(df[df['Fark Miktarı'] < 0])
    fazla_veren = len(df[df['Fark Miktarı'] > 0])
    
    ws['A9'] = "Toplam Ürün Sayısı:"
    ws['B9'] = len(df)
    ws['A10'] = "Açık Veren Ürün:"
    ws['B10'] = acik_veren
    ws['A11'] = "Fazla Veren Ürün:"
    ws['B11'] = fazla_veren
    
    ws['A13'] = "TUTARLAR"
    ws['A13'].font = subtitle_font
    
    toplam_satis = df['Satış Tutarı'].sum()
    net_fark = df['Fark Tutarı'].sum()
    toplam_acik = df[df['Fark Tutarı'] < 0]['Fark Tutarı'].sum()
    toplam_iptal = df['İptal Satır Tutarı'].sum()
    fire_tutari = df['Fire Tutarı'].sum()
    
    ws['A14'] = "Toplam Satış Hasılatı:"
    ws['B14'] = f"{toplam_satis:,.2f} TL"
    ws['A15'] = "Net Fark Tutarı:"
    ws['B15'] = f"{net_fark:,.2f} TL"
    ws['A16'] = "Toplam Açık Tutarı:"
    ws['B16'] = f"{toplam_acik:,.2f} TL"
    ws['A17'] = "Toplam İptal Satır Tutarı:"
    ws['B17'] = f"{toplam_iptal:,.2f} TL"
    ws['A18'] = "Fire Tutarı:"
    ws['B18'] = f"{fire_tutari:,.2f} TL"
    
    ws['A20'] = "ENVANTER DİSİPLİNİ"
    ws['A20'].font = subtitle_font
    
    acik_oran = abs(toplam_acik) / toplam_satis * 100 if toplam_satis > 0 else 0
    iptal_oran = toplam_iptal / toplam_satis * 100 if toplam_satis > 0 else 0
    
    ws['A21'] = "Açık/Satış Oranı:"
    ws['B21'] = f"%{acik_oran:.2f}"
    ws['A22'] = "İptal/Satış Oranı:"
    ws['B22'] = f"%{iptal_oran:.2f}"
    
    risk_seviyesi, _ = calculate_store_risk(df, internal_df, chronic_df)
    ws['A23'] = "DEĞERLENDİRME:"
    ws['B23'] = risk_seviyesi
    ws['B23'].fill = risk_fills.get(risk_seviyesi, PatternFill())
    ws['B23'].font = Font(bold=True)
    
    ws['A25'] = "RİSK DAĞILIMI"
    ws['A25'].font = subtitle_font
    
    ic_tutar = internal_df['Fark Tutarı (TL)'].sum() if len(internal_df) > 0 else 0
    
    ws['A26'] = "İç Hırsızlık Riski (Matematik Eşitliği):"
    ws['B26'] = f"{len(internal_df)} ürün ({ic_tutar:,.2f} TL)"
    ws['A27'] = "Kronik Sorunlu Ürün:"
    ws['B27'] = f"{len(chronic_df)} ürün"
    ws['A28'] = "Dış Hırsızlık Şüphesi:"
    ws['B28'] = f"{len(external_df)} ürün"
    
    ws.column_dimensions['A'].width = 40
    ws.column_dimensions['B'].width = 30
    
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
    
    # ===== KRONİK ÜRÜNLER =====
    ws3 = wb.create_sheet("KRONİK ÜRÜNLER")
    
    if len(chronic_df) > 0:
        headers = list(chronic_df.columns)
        for col, h in enumerate(headers, 1):
            cell = ws3.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for r_idx, row in chronic_df.head(30).iterrows():
            for c_idx, val in enumerate(row.values, 1):
                cell = ws3.cell(row=r_idx+2, column=c_idx, value=val)
                cell.border = border
    
    # ===== İÇ HIRSIZLIK DETAY =====
    ws4 = wb.create_sheet("İÇ HIRSIZLIK DETAY")
    
    if len(internal_df) > 0:
        headers = list(internal_df.columns)
        for col, h in enumerate(headers, 1):
            cell = ws4.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for r_idx, row in internal_df.head(50).iterrows():
            for c_idx, val in enumerate(row.values, 1):
                cell = ws4.cell(row=r_idx+2, column=c_idx, value=val)
                cell.border = border
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ===== ANA UYGULAMA =====
if uploaded_file is not None:
    try:
        df_raw = pd.read_excel(uploaded_file)
        st.success(f"✅ Dosya yüklendi! {len(df_raw)} satır, {len(df_raw.columns)} sütun")
        
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
        external_df = detect_external_theft(df_display)
        similar_df = find_similar_products(df_display)
        fire_df = detect_fire_manipulation(df_display)
        
        internal_codes = set(internal_df['Malzeme Kodu'].astype(str).tolist()) if len(internal_df) > 0 else set()
        chronic_codes = set(chronic_df['Malzeme Kodu'].astype(str).tolist()) if len(chronic_df) > 0 else set()
        
        top20_df = create_top_20_risky(df_display, internal_codes, chronic_codes)
        
        risk_seviyesi, risk_class = calculate_store_risk(df_display, internal_df, chronic_df)
        
        st.markdown("---")
        
        # Metrikler
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
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🔴 İç Hırsızlık", f"{len(internal_df)} ürün")
        with col2:
            st.metric("🟠 Kronik Açık", f"{len(chronic_df)} ürün")
        with col3:
            st.metric("🟡 Dış Hırsızlık Şüphesi", f"{len(external_df)} ürün")
        with col4:
            st.metric("🟣 Fire Manipülasyonu", f"{len(fire_df)} ürün")
        
        st.markdown("---")
        
        # Sekmeler
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📊 Özet", "🚨 En Riskli 20", "🔒 İç Hırsızlık", 
            "🔄 Kronik", "🟡 Dış Hırsızlık", "📥 İndir"
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
                    'Risk Türü': ['İç Hırsızlık', 'Kronik Açık', 'Dış Hırsızlık Şüphesi', 'Fire Manipülasyonu'],
                    'Sayı': [len(internal_df), len(chronic_df), len(external_df), len(fire_df)]
                }
                st.dataframe(pd.DataFrame(risk_data), hide_index=True, use_container_width=True)
        
        with tab2:
            st.subheader("🚨 En Riskli 20 Ürün")
            if len(top20_df) > 0:
                st.dataframe(top20_df, use_container_width=True, hide_index=True)
            else:
                st.success("Riskli ürün tespit edilmedi!")
        
        with tab3:
            st.subheader("🔒 İç Hırsızlık Detayı")
            st.markdown("""
            **Kural:** `|Fark + Kısmi + Önceki| ≈ İptal Satır` VE Oran 1-5 arası
            
            ⚠️ 1 iptal, 30 açık = Orantısız = İç hırsızlık DEĞİL
            """)
            if len(internal_df) > 0:
                st.dataframe(internal_df, use_container_width=True, hide_index=True)
            else:
                st.success("İç hırsızlık matematiğine uyan ürün yok!")
        
        with tab4:
            st.subheader("🔄 Kronik Açık Veren Ürünler")
            if len(chronic_df) > 0:
                st.dataframe(chronic_df, use_container_width=True, hide_index=True)
            else:
                st.success("Kronik açık veren ürün yok!")
        
        with tab5:
            st.subheader("🟡 Dış Hırsızlık / Sayım Hatası Şüphesi")
            st.markdown("**Kural:** Açık var ama Fire ve İptal Satır yok")
            if len(external_df) > 0:
                st.dataframe(external_df, use_container_width=True, hide_index=True)
            else:
                st.success("Dış hırsızlık şüphesi yok!")
        
        with tab6:
            st.subheader("📥 Excel Raporu İndir")
            
            excel_output = create_excel_report(
                df_display, internal_df, chronic_df, external_df, 
                similar_df, fire_df, top20_df,
                selected, magaza_adi, params
            )
            
            st.download_button(
                label=f"📥 {selected} Raporu İndir",
                data=excel_output,
                file_name=f"{selected}_Envanter_Risk_Raporu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
