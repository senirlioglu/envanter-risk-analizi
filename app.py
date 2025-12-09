import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
import zipfile

# Mobil uyumlu sayfa ayarı
st.set_page_config(page_title="Envanter Risk Analizi", layout="wide", page_icon="📊")

# Mobil uyumlu CSS
st.markdown("""
<style>
    .risk-kritik { background-color: #ff4444; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .risk-riskli { background-color: #ff8800; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .risk-dikkat { background-color: #ffcc00; color: black; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    .risk-temiz { background-color: #00cc66; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; }
    
    /* Mobil uyumluluk */
    @media (max-width: 768px) {
        .stMetric { font-size: 0.8rem; }
        .stDataFrame { font-size: 0.7rem; }
        div[data-testid="column"] { padding: 0.25rem !important; }
    }
    
    /* Tablo kaydırma */
    .stDataFrame { overflow-x: auto; }
</style>
""", unsafe_allow_html=True)

st.title("🔍 Envanter Risk Analizi")
st.markdown("*İç/dış hırsızlık, fire manipülasyonu, kod karışıklığı tespiti*")

with st.sidebar:
    st.header("📁 Veri Yükleme")
    uploaded_file = st.file_uploader("Excel dosyası yükleyin", type=['xlsx', 'xls'])


def analyze_inventory(df):
    """Veriyi analiz için hazırla"""
    df = df.copy()
    
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
    
    for old_col, new_col in col_mapping.items():
        if old_col in df.columns:
            df[new_col] = df[old_col]
    
    numeric_cols = ['Fark Miktarı', 'Fark Tutarı', 'Kısmi Envanter Miktarı', 'Kısmi Envanter Tutarı',
                    'Önceki Fark Miktarı', 'Önceki Fark Tutarı', 'İptal Satır Miktarı', 'İptal Satır Tutarı',
                    'Fire Miktarı', 'Fire Tutarı', 'Satış Miktarı', 'Satış Tutarı', 'Önceki Fire Miktarı', 
                    'Önceki Fire Tutarı', 'Birim Fiyat']
    
    for col in numeric_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if 'NET_ENVANTER_ETKİ_TUTARI' not in df.columns:
        df['NET_ENVANTER_ETKİ_TUTARI'] = df['Fark Tutarı'] + df['Fire Tutarı'] + df['Kısmi Envanter Tutarı']
    
    df['TOPLAM_MIKTAR'] = df['Fark Miktarı'] + df['Kısmi Envanter Miktarı'] + df['Önceki Fark Miktarı']
    
    return df


def is_balanced(row):
    """Dengelenmiş mi? Fark + Kısmi + Önceki = 0"""
    toplam = row['Fark Miktarı'] + row['Kısmi Envanter Miktarı'] + row['Önceki Fark Miktarı']
    return abs(toplam) <= 0.01


def get_first_two_words(text):
    """İlk 2 kelimeyi al"""
    if pd.isna(text):
        return ""
    words = str(text).strip().split()
    return " ".join(words[:2]).upper() if len(words) >= 2 else str(text).upper()


def get_last_word(text):
    """Son kelimeyi (marka) al"""
    if pd.isna(text):
        return ""
    words = str(text).strip().split()
    return words[-1].upper() if words else ""


def detect_internal_theft(df):
    """
    İÇ HIRSIZLIK TESPİTİ:
    - Satış Fiyatı >= 100 TL
    - Dengelenmemiş (Fark + Kısmi + Önceki ≠ 0)
    - |Toplam| ≈ İptal Satır, fark büyüdükçe risk AZALIR
    """
    results = []
    
    for idx, row in df.iterrows():
        # Dengelenmiş ise atla
        if is_balanced(row):
            continue
        
        satis_fiyati = row.get('Birim Fiyat', 0) or 0
        if satis_fiyati < 100:
            continue
        
        fark = row['Fark Miktarı']
        kismi = row['Kısmi Envanter Miktarı']
        onceki = row['Önceki Fark Miktarı']
        iptal = row['İptal Satır Miktarı']
        
        toplam = fark + kismi + onceki
        
        if toplam >= 0 or iptal <= 0:
            continue
        
        fark_mutlak = abs(abs(toplam) - iptal)
        
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
            esitlik = f"FARK: {fark_mutlak}"
        else:
            continue
        
        results.append({
            'Malzeme Kodu': row.get('Malzeme Kodu', ''),
            'Malzeme Adı': row.get('Malzeme Adı', ''),
            'Ürün Grubu': row.get('Ürün Grubu', ''),
            'Satış Fiyatı': satis_fiyati,
            'Fark Miktarı': fark,
            'Kısmi Env.': kismi,
            'Önceki Fark': onceki,
            'TOPLAM': toplam,
            'İptal Satır': iptal,
            'Fark': fark_mutlak,
            'Durum': esitlik,
            'Fark Tutarı (TL)': row['Fark Tutarı'],
            'Risk': risk
        })
    
    result_df = pd.DataFrame(results)
    if len(result_df) > 0:
        risk_order = {'ÇOK YÜKSEK': 0, 'YÜKSEK': 1, 'ORTA': 2, 'DÜŞÜK-ORTA': 3}
        result_df['_risk_sort'] = result_df['Risk'].map(risk_order)
        result_df = result_df.sort_values(['_risk_sort', 'Fark Tutarı (TL)'], ascending=[True, True])
        result_df = result_df.drop('_risk_sort', axis=1)
    
    return result_df


def detect_chronic_products(df):
    """Kronik açık - her iki dönemde de Fark < 0"""
    results = []
    
    for idx, row in df.iterrows():
        if is_balanced(row):
            continue
        
        if row['Önceki Fark Miktarı'] < 0 and row['Fark Miktarı'] < 0:
            results.append({
                'Malzeme Kodu': row.get('Malzeme Kodu', ''),
                'Malzeme Adı': row.get('Malzeme Adı', ''),
                'Ürün Grubu': row.get('Ürün Grubu', ''),
                'Bu Dönem Fark': row['Fark Miktarı'],
                'Bu Dönem Tutar': row['Fark Tutarı'],
                'Önceki Fark': row['Önceki Fark Miktarı'],
                'Önceki Tutar': row['Önceki Fark Tutarı'],
                'Toplam Tutar': row['Fark Tutarı'] + row['Önceki Fark Tutarı']
            })
    
    result_df = pd.DataFrame(results)
    if len(result_df) > 0:
        result_df = result_df.sort_values('Bu Dönem Tutar', ascending=True)
    
    return result_df


def detect_chronic_fire(df):
    """Kronik Fire - her iki dönemde de fire var"""
    results = []
    
    for idx, row in df.iterrows():
        onceki_fire = row.get('Önceki Fire Miktarı', 0) or 0
        bu_fire = row['Fire Miktarı']
        
        if onceki_fire != 0 and bu_fire != 0:
            results.append({
                'Malzeme Kodu': row.get('Malzeme Kodu', ''),
                'Malzeme Adı': row.get('Malzeme Adı', ''),
                'Ürün Grubu': row.get('Ürün Grubu', ''),
                'Bu Dönem Fire': bu_fire,
                'Bu Dönem Fire Tutarı': row['Fire Tutarı'],
                'Önceki Fire': onceki_fire,
                'Önceki Fire Tutarı': row.get('Önceki Fire Tutarı', 0),
                'Toplam Fire Tutarı': row['Fire Tutarı'] + row.get('Önceki Fire Tutarı', 0)
            })
    
    result_df = pd.DataFrame(results)
    if len(result_df) > 0:
        result_df = result_df.sort_values('Bu Dönem Fire Tutarı', ascending=True)
    
    return result_df


def detect_fire_manipulation(df):
    """Fire manipülasyonu: Fire var AMA Fark+Kısmi > 0"""
    results = []
    
    for idx, row in df.iterrows():
        fark_kismi = row['Fark Miktarı'] + row['Kısmi Envanter Miktarı']
        fire = row['Fire Miktarı']
        
        if fire < 0 and fark_kismi > 0:
            results.append({
                'Malzeme Kodu': row.get('Malzeme Kodu', ''),
                'Malzeme Adı': row.get('Malzeme Adı', ''),
                'Ürün Grubu': row.get('Ürün Grubu', ''),
                'Fark Miktarı': row['Fark Miktarı'],
                'Kısmi Env.': row['Kısmi Envanter Miktarı'],
                'Fark + Kısmi': fark_kismi,
                'Fire Miktarı': fire,
                'Fire Tutarı': row['Fire Tutarı'],
                'Sonuç': 'FAZLA FİRE GİRİLMİŞ'
            })
    
    result_df = pd.DataFrame(results)
    if len(result_df) > 0:
        result_df = result_df.sort_values('Fire Tutarı', ascending=True)
    
    return result_df


def detect_cigarette_shortage(df):
    """Sigara açığı - Fark < 0 olan sigaralar"""
    results = []
    sigara_keywords = ['sigara', 'sıgara', 'cigarette', 'tütün']
    
    for idx, row in df.iterrows():
        urun_grubu = str(row.get('Ürün Grubu', '')).lower()
        ana_grup = str(row.get('Ana Grup', '')).lower()
        
        is_sigara = any(kw in urun_grubu or kw in ana_grup for kw in sigara_keywords)
        
        if is_sigara and row['Fark Miktarı'] < 0:
            net_acik = row['Fark Miktarı'] + row['Kısmi Envanter Miktarı'] - row['İptal Satır Miktarı']
            
            results.append({
                'Malzeme Kodu': row.get('Malzeme Kodu', ''),
                'Malzeme Adı': row.get('Malzeme Adı', ''),
                'Fark Miktarı': row['Fark Miktarı'],
                'Kısmi Env.': row['Kısmi Envanter Miktarı'],
                'İptal Satır': row['İptal Satır Miktarı'],
                'NET AÇIK': net_acik,
                'Fark Tutarı': row['Fark Tutarı'],
                'Risk': 'YÜKSEK - SİGARA'
            })
    
    result_df = pd.DataFrame(results)
    if len(result_df) > 0:
        result_df = result_df.sort_values('Fark Tutarı', ascending=True)
    
    return result_df


def find_product_families(df):
    """
    Benzer ürün ailesi analizi
    Kural: İlk 2 kelime + Son kelime (marka) + Mal Grubu aynıysa = AİLE
    """
    df_copy = df.copy()
    df_copy['İlk2Kelime'] = df_copy['Malzeme Adı'].apply(get_first_two_words)
    df_copy['Marka'] = df_copy['Malzeme Adı'].apply(get_last_word)
    
    families = []
    
    grouped = df_copy.groupby(['Ürün Grubu', 'İlk2Kelime', 'Marka'])
    
    for (urun_grubu, ilk2, marka), group in grouped:
        if len(group) > 1:
            toplam_fark = group['Fark Miktarı'].sum()
            toplam_kismi = group['Kısmi Envanter Miktarı'].sum()
            toplam_onceki = group['Önceki Fark Miktarı'].sum()
            aile_toplami = toplam_fark + toplam_kismi + toplam_onceki
            
            if group['Fark Miktarı'].abs().sum() > 0:
                if abs(aile_toplami) <= 2:
                    sonuc = "KOD KARIŞIKLIĞI - HIRSIZLIK DEĞİL"
                    risk = "DÜŞÜK"
                elif aile_toplami < -2:
                    sonuc = "AİLEDE NET AÇIK VAR"
                    risk = "ORTA"
                else:
                    sonuc = "AİLEDE FAZLA VAR"
                    risk = "DÜŞÜK"
                
                urunler = group['Malzeme Adı'].tolist()
                farklar = group['Fark Miktarı'].tolist()
                
                families.append({
                    'Mal Grubu': urun_grubu,
                    'İlk 2 Kelime': ilk2,
                    'Marka': marka,
                    'Ürün Sayısı': len(group),
                    'Toplam Fark': toplam_fark,
                    'Toplam Kısmi': toplam_kismi,
                    'Toplam Önceki': toplam_onceki,
                    'AİLE TOPLAMI': aile_toplami,
                    'Sonuç': sonuc,
                    'Risk': risk,
                    'Ürünler': ' | '.join([f"{u[:30]}({f})" for u, f in zip(urunler[:5], farklar[:5])])
                })
    
    result_df = pd.DataFrame(families)
    if len(result_df) > 0:
        result_df = result_df.sort_values('AİLE TOPLAMI', ascending=True)
    
    return result_df


def detect_external_theft(df):
    """Dış hırsızlık - açık var ama fire/iptal yok"""
    results = []
    
    for idx, row in df.iterrows():
        if is_balanced(row):
            continue
        
        if row['Fark Miktarı'] < 0 and row['Fire Miktarı'] == 0 and row['İptal Satır Miktarı'] == 0:
            if abs(row['Fark Tutarı']) > 50:
                results.append({
                    'Malzeme Kodu': row.get('Malzeme Kodu', ''),
                    'Malzeme Adı': row.get('Malzeme Adı', ''),
                    'Ürün Grubu': row.get('Ürün Grubu', ''),
                    'Fark Miktarı': row['Fark Miktarı'],
                    'Fark Tutarı': row['Fark Tutarı'],
                    'Önceki Fark': row['Önceki Fark Miktarı'],
                    'Risk': 'DIŞ HIRSIZLIK / SAYIM HATASI'
                })
    
    result_df = pd.DataFrame(results)
    if len(result_df) > 0:
        result_df = result_df.sort_values('Fark Tutarı', ascending=True)
    
    return result_df


def generate_executive_summary(df):
    """Yönetici özeti - mal grubu bazlı yorumlar"""
    comments = []
    
    # Mal grubu bazlı analiz
    group_stats = df.groupby('Ürün Grubu').agg({
        'Fark Tutarı': 'sum',
        'Fire Tutarı': 'sum',
        'Satış Tutarı': 'sum',
        'Fark Miktarı': lambda x: (x < 0).sum()
    }).reset_index()
    
    group_stats.columns = ['Ürün Grubu', 'Toplam Fark', 'Toplam Fire', 'Toplam Satış', 'Açık Ürün Sayısı']
    group_stats['Açık Oranı'] = abs(group_stats['Toplam Fark']) / group_stats['Toplam Satış'].replace(0, 1) * 100
    
    # En yüksek açık
    top_acik = group_stats.nsmallest(3, 'Toplam Fark')
    for _, row in top_acik.iterrows():
        if row['Toplam Fark'] < -500:
            comments.append(f"⚠️ {row['Ürün Grubu']}: {row['Toplam Fark']:,.0f} TL açık ({row['Açık Ürün Sayısı']} ürün)")
    
    # En yüksek fire
    top_fire = group_stats.nsmallest(3, 'Toplam Fire')
    for _, row in top_fire.iterrows():
        if row['Toplam Fire'] < -500:
            comments.append(f"🔥 {row['Ürün Grubu']}: {row['Toplam Fire']:,.0f} TL fire")
    
    return comments, group_stats


def calculate_store_risk(df, internal_df, chronic_df, cigarette_df):
    """Mağaza risk seviyesi"""
    toplam_satis = df['Satış Tutarı'].sum()
    toplam_acik = df[df['Fark Tutarı'] < 0]['Fark Tutarı'].sum()
    
    kayip_orani = abs(toplam_acik) / toplam_satis * 100 if toplam_satis > 0 else 0
    ic_hirsizlik = len(internal_df)
    sigara_acik = len(cigarette_df)
    
    if kayip_orani > 2 or ic_hirsizlik > 50 or sigara_acik > 5:
        return "KRİTİK", "risk-kritik"
    elif kayip_orani > 1.5 or ic_hirsizlik > 30 or sigara_acik > 3:
        return "RİSKLİ", "risk-riskli"
    elif kayip_orani > 1 or ic_hirsizlik > 15 or sigara_acik > 0:
        return "DİKKAT", "risk-dikkat"
    else:
        return "TEMİZ", "risk-temiz"


def create_top_20_risky(df, internal_codes, chronic_codes, family_balanced_codes):
    """En riskli 20 ürün"""
    
    # Dengelenmişleri ve aile dengelenmişlerini çıkar
    risky_df = df[
        (df['NET_ENVANTER_ETKİ_TUTARI'] < 0) & 
        (~df.apply(is_balanced, axis=1)) &
        (~df['Malzeme Kodu'].astype(str).isin(family_balanced_codes))
    ].copy()
    
    if len(risky_df) == 0:
        return pd.DataFrame()
    
    def classify(row):
        kod = str(row.get('Malzeme Kodu', ''))
        
        if kod in internal_codes:
            return "İÇ HIRSIZLIK", "Kasa kamera incelemesi"
        elif kod in chronic_codes:
            return "KRONİK AÇIK", "Raf kontrolü, Sayım eğitimi"
        elif row['Fire Miktarı'] < 0:
            return "OPERASYONEL", "Fire kayıt kontrolü"
        else:
            return "DIŞ HIRSIZLIK/SAYIM", "Sayım ve kod kontrolü"
    
    risky_df['Risk Türü'] = risky_df.apply(lambda x: classify(x)[0], axis=1)
    risky_df['Aksiyon'] = risky_df.apply(lambda x: classify(x)[1], axis=1)
    
    risky_df = risky_df.sort_values('NET_ENVANTER_ETKİ_TUTARI', ascending=True).head(20)
    
    result = pd.DataFrame({
        'Sıra': range(1, len(risky_df) + 1),
        'Malzeme Kodu': risky_df['Malzeme Kodu'].values,
        'Malzeme Adı': risky_df['Malzeme Adı'].values,
        'Fark Mik.': risky_df['Fark Miktarı'].values,
        'Kısmi': risky_df['Kısmi Envanter Miktarı'].values,
        'Önceki': risky_df['Önceki Fark Miktarı'].values,
        'TOPLAM': risky_df['TOPLAM_MIKTAR'].values,
        'İptal': risky_df['İptal Satır Miktarı'].values,
        'Fire': risky_df['Fire Miktarı'].values,
        'Fire Tutarı': risky_df['Fire Tutarı'].values,
        'Fark Tutarı': risky_df['Fark Tutarı'].values,
        'Risk Türü': risky_df['Risk Türü'].values,
        'Aksiyon': risky_df['Aksiyon'].values
    })
    
    return result


def auto_adjust_column_width(ws):
    """Excel sütun genişliklerini otomatik ayarla"""
    for column_cells in ws.columns:
        max_length = 0
        column = column_cells[0].column_letter
        
        for cell in column_cells:
            try:
                if cell.value:
                    cell_length = len(str(cell.value))
                    if cell_length > max_length:
                        max_length = cell_length
            except:
                pass
        
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column].width = adjusted_width


def create_excel_report(df, internal_df, chronic_df, chronic_fire_df, cigarette_df, 
                       external_df, family_df, fire_manip_df, top20_df, 
                       exec_comments, group_stats, magaza_kodu, magaza_adi, params):
    """Excel raporu - tüm sheet'ler dahil"""
    
    wb = Workbook()
    
    header_font = Font(bold=True, color='FFFFFF', size=10)
    header_fill = PatternFill('solid', fgColor='1F4E79')
    title_font = Font(bold=True, size=14)
    subtitle_font = Font(bold=True, size=11)
    border = Border(left=Side(style='thin'), right=Side(style='thin'),
                    top=Side(style='thin'), bottom=Side(style='thin'))
    wrap_alignment = Alignment(wrap_text=True, vertical='top')
    
    # ===== ÖZET =====
    ws = wb.active
    ws.title = "ÖZET"
    
    ws['A1'] = f"MAĞAZA {magaza_kodu}"
    ws['A1'].font = title_font
    ws['A2'] = magaza_adi
    ws['A3'] = f"Dönem: {params.get('donem', '')} | Tarih: {params.get('tarih', '')}"
    
    ws['A5'] = "GENEL METRIKLER"
    ws['A5'].font = subtitle_font
    
    toplam_satis = df['Satış Tutarı'].sum()
    net_fark = df['Fark Tutarı'].sum()
    toplam_acik = df[df['Fark Tutarı'] < 0]['Fark Tutarı'].sum()
    fire_tutari = df['Fire Tutarı'].sum()
    acik_oran = abs(toplam_acik) / toplam_satis * 100 if toplam_satis > 0 else 0
    
    metrics = [
        ('Toplam Ürün', len(df)),
        ('Açık Veren Ürün', len(df[df['Fark Miktarı'] < 0])),
        ('Toplam Satış', f"{toplam_satis:,.0f} TL"),
        ('Net Fark', f"{net_fark:,.0f} TL"),
        ('Fire Tutarı', f"{fire_tutari:,.0f} TL"),
        ('Açık/Satış Oranı', f"%{acik_oran:.2f}"),
    ]
    
    for i, (label, value) in enumerate(metrics, start=6):
        ws[f'A{i}'] = label
        ws[f'B{i}'] = value
    
    ws['A13'] = "RİSK DAĞILIMI"
    ws['A13'].font = subtitle_font
    
    risks = [
        ('İç Hırsızlık (≥100TL)', len(internal_df)),
        ('Kronik Açık', len(chronic_df)),
        ('Kronik Fire', len(chronic_fire_df)),
        ('Sigara Açığı', len(cigarette_df)),
        ('Fire Manipülasyonu', len(fire_manip_df)),
    ]
    
    for i, (label, value) in enumerate(risks, start=14):
        ws[f'A{i}'] = label
        ws[f'B{i}'] = value
        if 'Sigara' in label and value > 0:
            ws[f'B{i}'].fill = PatternFill('solid', fgColor='FF4444')
            ws[f'B{i}'].font = Font(bold=True, color='FFFFFF')
    
    ws['A20'] = "YÖNETİCİ ÖZETİ"
    ws['A20'].font = subtitle_font
    
    for i, comment in enumerate(exec_comments[:10], start=21):
        ws[f'A{i}'] = comment
    
    auto_adjust_column_width(ws)
    
    # ===== EN RİSKLİ 20 =====
    if len(top20_df) > 0:
        ws2 = wb.create_sheet("EN RİSKLİ 20")
        for col, h in enumerate(top20_df.columns, 1):
            cell = ws2.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for r_idx, row in enumerate(top20_df.values, 2):
            for c_idx, val in enumerate(row, 1):
                cell = ws2.cell(row=r_idx, column=c_idx, value=val)
                cell.border = border
                cell.alignment = wrap_alignment
        
        auto_adjust_column_width(ws2)
    
    # ===== KRONİK AÇIK =====
    if len(chronic_df) > 0:
        ws3 = wb.create_sheet("KRONİK AÇIK")
        for col, h in enumerate(chronic_df.columns, 1):
            cell = ws3.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
        
        for r_idx, row in enumerate(chronic_df.head(100).values, 2):
            for c_idx, val in enumerate(row, 1):
                ws3.cell(row=r_idx, column=c_idx, value=val)
        
        auto_adjust_column_width(ws3)
    
    # ===== KRONİK FİRE =====
    if len(chronic_fire_df) > 0:
        ws4 = wb.create_sheet("KRONİK FİRE")
        for col, h in enumerate(chronic_fire_df.columns, 1):
            cell = ws4.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
        
        for r_idx, row in enumerate(chronic_fire_df.head(100).values, 2):
            for c_idx, val in enumerate(row, 1):
                ws4.cell(row=r_idx, column=c_idx, value=val)
        
        auto_adjust_column_width(ws4)
    
    # ===== SİGARA AÇIĞI =====
    ws5 = wb.create_sheet("SİGARA AÇIĞI")
    ws5['A1'] = "⚠️ SİGARA AÇIĞI - YÜKSEK RİSK"
    ws5['A1'].font = Font(bold=True, size=14, color='FF0000')
    
    if len(cigarette_df) > 0:
        for col, h in enumerate(cigarette_df.columns, 1):
            cell = ws5.cell(row=3, column=col, value=h)
            cell.font = header_font
            cell.fill = PatternFill('solid', fgColor='FF4444')
        
        for r_idx, row in enumerate(cigarette_df.values, 4):
            for c_idx, val in enumerate(row, 1):
                ws5.cell(row=r_idx, column=c_idx, value=val)
        
        auto_adjust_column_width(ws5)
    
    # ===== İÇ HIRSIZLIK =====
    if len(internal_df) > 0:
        ws6 = wb.create_sheet("İÇ HIRSIZLIK")
        ws6['A1'] = "Satış Fiyatı ≥ 100 TL | Fark büyüdükçe risk AZALIR"
        ws6['A1'].font = subtitle_font
        
        for col, h in enumerate(internal_df.columns, 1):
            cell = ws6.cell(row=3, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
        
        for r_idx, row in enumerate(internal_df.head(100).values, 4):
            for c_idx, val in enumerate(row, 1):
                ws6.cell(row=r_idx, column=c_idx, value=val)
        
        auto_adjust_column_width(ws6)
    
    # ===== AİLE ANALİZİ =====
    if len(family_df) > 0:
        ws7 = wb.create_sheet("AİLE ANALİZİ")
        ws7['A1'] = "Benzer Ürün Ailesi - Kod Karışıklığı Tespiti"
        ws7['A1'].font = subtitle_font
        
        for col, h in enumerate(family_df.columns, 1):
            cell = ws7.cell(row=3, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
        
        for r_idx, row in enumerate(family_df.head(100).values, 4):
            for c_idx, val in enumerate(row, 1):
                cell = ws7.cell(row=r_idx, column=c_idx, value=val)
                cell.alignment = wrap_alignment
        
        auto_adjust_column_width(ws7)
    
    # ===== FİRE MANİPÜLASYONU =====
    if len(fire_manip_df) > 0:
        ws8 = wb.create_sheet("FİRE MANİPÜLASYONU")
        for col, h in enumerate(fire_manip_df.columns, 1):
            cell = ws8.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
        
        for r_idx, row in enumerate(fire_manip_df.head(100).values, 2):
            for c_idx, val in enumerate(row, 1):
                ws8.cell(row=r_idx, column=c_idx, value=val)
        
        auto_adjust_column_width(ws8)
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ===== ANA UYGULAMA =====
if uploaded_file is not None:
    try:
        xl = pd.ExcelFile(uploaded_file)
        sheet_names = xl.sheet_names
        
        best_sheet = None
        max_cols = 0
        
        for sheet in sheet_names:
            temp_df = pd.read_excel(uploaded_file, sheet_name=sheet, nrows=5)
            if len(temp_df.columns) > max_cols:
                max_cols = len(temp_df.columns)
                best_sheet = sheet
        
        df_raw = pd.read_excel(uploaded_file, sheet_name=best_sheet)
        st.success(f"✅ {len(df_raw)} satır, {len(df_raw.columns)} sütun ({best_sheet})")
        
        df = analyze_inventory(df_raw)
        
        # Mağaza bilgisi
        if 'Mağaza Kodu' in df.columns:
            magazalar = df['Mağaza Kodu'].dropna().unique().tolist()
        else:
            magazalar = ['MAGAZA']
            df['Mağaza Kodu'] = 'MAGAZA'
        
        magaza_adi = df['Mağaza Adı'].iloc[0] if 'Mağaza Adı' in df.columns and len(df) > 0 else ''
        
        params = {
            'donem': str(df['Envanter Dönemi'].iloc[0]) if 'Envanter Dönemi' in df.columns else '',
            'tarih': str(df['Envanter Tarihi'].iloc[0])[:10] if 'Envanter Tarihi' in df.columns else '',
        }
        
        # Mağaza seçimi
        if len(magazalar) > 1:
            selected = st.selectbox("🏪 Mağaza Seçin", magazalar)
            df_display = df[df['Mağaza Kodu'] == selected].copy()
        else:
            selected = magazalar[0]
            df_display = df.copy()
        
        # Analizler
        internal_df = detect_internal_theft(df_display)
        chronic_df = detect_chronic_products(df_display)
        chronic_fire_df = detect_chronic_fire(df_display)
        cigarette_df = detect_cigarette_shortage(df_display)
        external_df = detect_external_theft(df_display)
        family_df = find_product_families(df_display)
        fire_manip_df = detect_fire_manipulation(df_display)
        exec_comments, group_stats = generate_executive_summary(df_display)
        
        internal_codes = set(internal_df['Malzeme Kodu'].astype(str).tolist()) if len(internal_df) > 0 else set()
        chronic_codes = set(chronic_df['Malzeme Kodu'].astype(str).tolist()) if len(chronic_df) > 0 else set()
        
        # Aile dengelenmişlerini bul
        family_balanced_codes = set()
        if len(family_df) > 0:
            balanced_families = family_df[family_df['Sonuç'].str.contains('KARIŞIKLIK', na=False)]
            # Bu ailelerdeki ürünleri bul
        
        top20_df = create_top_20_risky(df_display, internal_codes, chronic_codes, family_balanced_codes)
        
        risk_seviyesi, risk_class = calculate_store_risk(df_display, internal_df, chronic_df, cigarette_df)
        
        st.markdown("---")
        
        # Metrikler - Üst
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f'<div class="{risk_class}"><b>RİSK</b><br/><h2>{risk_seviyesi}</h2></div>', unsafe_allow_html=True)
        with col2:
            st.metric("💰 Satış", f"{df_display['Satış Tutarı'].sum():,.0f} TL")
        with col3:
            st.metric("📉 Fark", f"{df_display['Fark Tutarı'].sum():,.0f} TL")
        with col4:
            toplam_satis = df_display['Satış Tutarı'].sum()
            toplam_acik = df_display[df_display['Fark Tutarı'] < 0]['Fark Tutarı'].sum()
            oran = abs(toplam_acik) / toplam_satis * 100 if toplam_satis > 0 else 0
            st.metric("📊 Oran", f"%{oran:.2f}")
        
        # Metrikler - Alt
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("🔒 İç Hırs.", f"{len(internal_df)}")
        with col2:
            st.metric("🔄 Kronik", f"{len(chronic_df)}")
        with col3:
            st.metric("🔥 Kr.Fire", f"{len(chronic_fire_df)}")
        with col4:
            if len(cigarette_df) > 0:
                st.metric("🚬 SİGARA", f"{len(cigarette_df)}", delta="RİSK!", delta_color="inverse")
            else:
                st.metric("🚬 Sigara", "0")
        with col5:
            st.metric("👨‍👩‍👧 Aile", f"{len(family_df)}")
        
        # Yönetici Özeti
        if exec_comments:
            with st.expander("📋 Yönetici Özeti", expanded=True):
                for comment in exec_comments[:5]:
                    st.markdown(comment)
        
        st.markdown("---")
        
        # Sekmeler
        tabs = st.tabs(["🚨 Riskli 20", "🔒 İç Hırs.", "👨‍👩‍👧 Aile", "🔄 Kronik", "🔥 Fire", "🚬 Sigara", "📥 İndir"])
        
        with tabs[0]:
            st.subheader("🚨 En Riskli 20 Ürün")
            if len(top20_df) > 0:
                st.dataframe(top20_df, use_container_width=True, hide_index=True)
            else:
                st.success("Riskli ürün yok!")
        
        with tabs[1]:
            st.subheader("🔒 İç Hırsızlık (≥100TL)")
            st.caption("Fark büyüdükçe risk AZALIR, eşitse EN YÜKSEK")
            if len(internal_df) > 0:
                st.dataframe(internal_df, use_container_width=True, hide_index=True)
            else:
                st.success("İç hırsızlık riski yok!")
        
        with tabs[2]:
            st.subheader("👨‍👩‍👧 Benzer Ürün Ailesi")
            st.caption("İlk 2 kelime + Marka + Mal Grubu aynı = AİLE")
            if len(family_df) > 0:
                st.dataframe(family_df, use_container_width=True, hide_index=True)
            else:
                st.info("Aile grubu bulunamadı")
        
        with tabs[3]:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🔄 Kronik Açık")
                if len(chronic_df) > 0:
                    st.dataframe(chronic_df.head(30), use_container_width=True, hide_index=True)
                else:
                    st.success("Kronik açık yok!")
            with col2:
                st.subheader("🔥 Kronik Fire")
                if len(chronic_fire_df) > 0:
                    st.dataframe(chronic_fire_df.head(30), use_container_width=True, hide_index=True)
                else:
                    st.success("Kronik fire yok!")
        
        with tabs[4]:
            st.subheader("🔥 Fire Manipülasyonu")
            st.caption("Fire var ama Fark+Kısmi > 0 = Fazla fire girilmiş")
            if len(fire_manip_df) > 0:
                st.dataframe(fire_manip_df, use_container_width=True, hide_index=True)
            else:
                st.success("Fire manipülasyonu yok!")
        
        with tabs[5]:
            st.subheader("🚬 Sigara Açığı")
            if len(cigarette_df) > 0:
                st.error("⚠️ Sigarada açık = HIRSIZLIK BELİRTİSİ")
                st.dataframe(cigarette_df, use_container_width=True, hide_index=True)
            else:
                st.success("Sigara açığı yok!")
        
        with tabs[6]:
            st.subheader("📥 Rapor İndir")
            
            excel_output = create_excel_report(
                df_display, internal_df, chronic_df, chronic_fire_df, cigarette_df,
                external_df, family_df, fire_manip_df, top20_df,
                exec_comments, group_stats, selected, magaza_adi, params
            )
            
            st.download_button(
                label=f"📥 {selected} Raporu İndir",
                data=excel_output,
                file_name=f"{selected}_Risk_Raporu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            if len(magazalar) > 1:
                st.markdown("---")
                if st.button("🗜️ Tüm Mağazaları Hazırla (ZIP)"):
                    with st.spinner("Raporlar hazırlanıyor..."):
                        zip_buffer = BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for mag in magazalar:
                                df_mag = df[df['Mağaza Kodu'] == mag].copy()
                                mag_adi = df_mag['Mağaza Adı'].iloc[0] if 'Mağaza Adı' in df_mag.columns and len(df_mag) > 0 else ''
                                
                                int_df = detect_internal_theft(df_mag)
                                chr_df = detect_chronic_products(df_mag)
                                chr_fire_df = detect_chronic_fire(df_mag)
                                cig_df = detect_cigarette_shortage(df_mag)
                                ext_df = detect_external_theft(df_mag)
                                fam_df = find_product_families(df_mag)
                                fire_df = detect_fire_manipulation(df_mag)
                                exec_c, grp_s = generate_executive_summary(df_mag)
                                
                                int_codes = set(int_df['Malzeme Kodu'].astype(str).tolist()) if len(int_df) > 0 else set()
                                chr_codes = set(chr_df['Malzeme Kodu'].astype(str).tolist()) if len(chr_df) > 0 else set()
                                
                                t20_df = create_top_20_risky(df_mag, int_codes, chr_codes, set())
                                
                                excel_data = create_excel_report(
                                    df_mag, int_df, chr_df, chr_fire_df, cig_df,
                                    ext_df, fam_df, fire_df, t20_df,
                                    exec_c, grp_s, mag, mag_adi, params
                                )
                                
                                zf.writestr(f"{mag}_Risk_Raporu.xlsx", excel_data.getvalue())
                        
                        zip_buffer.seek(0)
                        st.download_button(
                            label=f"📥 {len(magazalar)} Mağaza ZIP İndir",
                            data=zip_buffer,
                            file_name="Tum_Magazalar_Rapor.zip",
                            mime="application/zip"
                        )
    
    except Exception as e:
        st.error(f"Hata: {str(e)}")
        st.exception(e)

else:
    st.info("👈 Excel dosyası yükleyin")
    
    st.markdown("""
    ### 📐 Kurallar
    
    | Durum | Kontrol | Sonuç |
    |-------|---------|-------|
    | Fark+Kısmi+Önceki=0 | Dengelenmiş | ✅ Sorun yok |
    | İlk 2 kelime + Marka + Mal Grubu aynı | Aile | 🔵 Kod karışıklığı |
    | Satış Fiyatı ≥100TL + Toplam≈İptal | İç Hırsızlık | 🔴 Yüksek risk |
    | Sigara + Fark<0 | Sigara Açığı | 🚬 HIRSIZLIK |
    """)
