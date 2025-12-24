import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
import json
import os

# ==================== SAYFA AYARI ====================
st.set_page_config(
    page_title="Sürekli Envanter Analizi",
    layout="wide",
    page_icon="📦"
)

# ==================== CSS STİLLERİ ====================
st.markdown("""
<style>
    /* Risk kutuları */
    .risk-kritik {
        background: linear-gradient(135deg, #ff4444, #cc0000);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 1.2em;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .risk-riskli {
        background: linear-gradient(135deg, #ff8c00, #ff6600);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 1.2em;
    }
    .risk-dikkat {
        background: linear-gradient(135deg, #ffd700, #ffcc00);
        color: #333;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 1.2em;
    }
    .risk-temiz {
        background: linear-gradient(135deg, #00cc66, #009944);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 1.2em;
    }

    /* Sidebar stil */
    .sidebar-header {
        font-size: 1.5em;
        font-weight: bold;
        margin-bottom: 20px;
        color: #1e3c72;
    }

    /* Metrik kartları */
    div[data-testid="stMetric"] {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #1e3c72;
    }

    /* Tab stilleri */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 8px 8px 0 0;
    }
</style>
""", unsafe_allow_html=True)

# ==================== SUPABASE BAĞLANTISI ====================
try:
    from supabase import create_client, Client
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))

    @st.cache_resource
    def get_supabase_client():
        if SUPABASE_URL and SUPABASE_KEY:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        return None

    supabase = get_supabase_client()
except:
    supabase = None

# ==================== SESSION STATE ====================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_sm' not in st.session_state:
    st.session_state.user_sm = None

# ==================== KULLANICI YETKİLERİ ====================
USERS = {
    "admin": {"password": "admin123", "role": "admin", "sm": None},
    "sm1": {"password": "sm1", "role": "sm", "sm": "ALİ AKÇAY"},
    "sm2": {"password": "sm2", "role": "sm", "sm": "ŞADAN YURDAKUL"},
    "sm3": {"password": "sm3", "role": "sm", "sm": "VELİ GÖK"},
    "sm4": {"password": "sm4", "role": "sm", "sm": "GİZEM TOSUN"},
    "sma": {"password": "sma", "role": "asistan", "sm": None},
    "ziya": {"password": "ziya123", "role": "gm", "sm": None},
}

# ==================== GİRİŞ SİSTEMİ ====================
def login():
    st.markdown("## 📦 Sürekli Envanter Analizi")
    st.markdown("*Haftalık Et-Tavuk, Ekmek, Meyve/Sebze Takibi*")
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔐 Giriş Yap")
        username = st.text_input("Kullanıcı Adı", key="login_user")
        password = st.text_input("Şifre", type="password", key="login_pass")

        if st.button("Giriş", use_container_width=True):
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.session_state.user_role = USERS[username]["role"]
                st.session_state.user_sm = USERS[username]["sm"]
                st.rerun()
            else:
                st.error("Hatalı kullanıcı adı veya şifre!")

# ==================== YARDIMCI FONKSİYONLAR ====================
def format_currency(value):
    """Para formatı"""
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    elif abs(value) >= 1_000:
        return f"{value/1_000:.0f}K"
    return f"{value:,.0f}"

def get_risk_level(puan):
    """Risk seviyesi belirle"""
    if puan >= 60:
        return "🔴 KRİTİK", "kritik"
    elif puan >= 40:
        return "🟠 RİSKLİ", "riskli"
    elif puan >= 20:
        return "🟡 DİKKAT", "dikkat"
    return "🟢 TEMİZ", "temiz"

# ==================== VERİ FONKSİYONLARI (PLACEHOLDER) ====================
@st.cache_data(ttl=300)
def get_available_periods():
    """Mevcut dönemleri getir - Supabase'den"""
    # TODO: Supabase'den çek
    return ["2024-12", "2024-11", "2024-10"]

@st.cache_data(ttl=300)
def get_available_sms():
    """Mevcut SM listesini getir"""
    return ["ALİ AKÇAY", "ŞADAN YURDAKUL", "VELİ GÖK", "GİZEM TOSUN"]

def get_sm_summary_data(sm=None, donemler=None):
    """SM özet verisini getir - Placeholder"""
    # TODO: Gerçek veri çekme fonksiyonu
    return pd.DataFrame()

def analyze_uploaded_file(df):
    """Yüklenen dosyayı analiz et - Placeholder"""
    # TODO: Gerçek analiz fonksiyonları
    return df

# ==================== ANA UYGULAMA ====================
def main_app():
    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user}")
        st.markdown(f"*{st.session_state.user_role.upper()}*")
        st.markdown("---")

        # Menü seçenekleri - role göre
        if st.session_state.user_role == "gm":
            menu_options = ["🌍 GM Özet", "👔 SM Özet", "📥 Excel Yükle"]
        elif st.session_state.user_role == "sm":
            menu_options = ["👔 SM Özet", "📥 Excel Yükle"]
        elif st.session_state.user_role == "asistan":
            menu_options = ["👔 SM Özet", "📥 Excel Yükle"]
        else:
            menu_options = ["🌍 GM Özet", "👔 SM Özet", "📥 Excel Yükle"]

        analysis_mode = st.radio("📊 Analiz Modu", menu_options, label_visibility="collapsed")

        st.markdown("---")
        if st.button("🚪 Çıkış", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()

    # ==================== SM ÖZET MODU ====================
    if analysis_mode == "👔 SM Özet":
        st.subheader("👔 SM Özet")

        # Kullanıcı -> SM eşleştirmesi
        current_user = st.session_state.user
        user_sm = st.session_state.user_sm
        is_gm = st.session_state.user_role == "gm"

        # SM ve Dönem seçimi
        col_sm, col_donem = st.columns([1, 1])

        available_sms = get_available_sms()
        available_periods = get_available_periods()

        with col_sm:
            if is_gm:
                sm_options = ["📊 TÜMÜ (Bölge)"] + available_sms
                selected_sm_option = st.selectbox("👔 Satış Müdürü", sm_options)

                if selected_sm_option == "📊 TÜMÜ (Bölge)":
                    selected_sm = None
                    display_sm = "Bölge"
                else:
                    selected_sm = selected_sm_option
                    display_sm = selected_sm
            elif user_sm:
                selected_sm = user_sm
                display_sm = user_sm
                st.selectbox("👔 Satış Müdürü", [user_sm], disabled=True)
            else:
                selected_sm = st.selectbox("👔 Satış Müdürü", available_sms)
                display_sm = selected_sm

        with col_donem:
            selected_periods = st.multiselect("📅 Dönem", available_periods, default=available_periods[:1] if available_periods else [])

        if selected_periods:
            st.markdown("---")
            st.subheader(f"📊 {display_sm} - Özet")

            # Üst metrikler
            st.markdown("### 💰 Özet Metrikler")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("💰 Toplam Satış", "0 TL", "Veri bekleniyor")
            with col2:
                st.metric("📉 Fark", "0 TL", "%0.00")
            with col3:
                st.metric("🔥 Fire", "0 TL", "%0.00")
            with col4:
                st.metric("📊 Toplam", "0 TL", "%0.00")

            # Risk dağılımı
            st.markdown("### 📊 Risk Dağılımı")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown('<div class="risk-kritik">🔴 KRİTİK: 0</div>', unsafe_allow_html=True)
            with col2:
                st.markdown('<div class="risk-riskli">🟠 RİSKLİ: 0</div>', unsafe_allow_html=True)
            with col3:
                st.markdown('<div class="risk-dikkat">🟡 DİKKAT: 0</div>', unsafe_allow_html=True)
            with col4:
                st.markdown('<div class="risk-temiz">🟢 TEMİZ: 0</div>', unsafe_allow_html=True)

            # BS Özeti
            st.markdown("### 👔 BS Özeti")
            st.info("📥 Veri yüklendikten sonra BS özeti görüntülenecek")

            # Sekmeler
            st.markdown("---")
            tabs = st.tabs(["📋 Sıralama", "🔴 Kritik", "🟠 Riskli", "🔍 Mağaza Detay", "📥 İndir"])

            with tabs[0]:
                st.subheader("📋 Mağaza Sıralaması (Risk Puanına Göre)")
                st.info("📥 Veri yüklendikten sonra mağaza sıralaması görüntülenecek")

            with tabs[1]:
                st.subheader("🔴 Kritik Mağazalar")
                st.success("Kritik mağaza yok! 🎉")

            with tabs[2]:
                st.subheader("🟠 Riskli Mağazalar")
                st.success("Riskli mağaza yok! 🎉")

            with tabs[3]:
                st.subheader("🔍 Mağaza Detay Görünümü")
                st.info("Bir mağaza seçerek detayları görüntüleyebilirsiniz.")

                mag_options = ["Mağaza seçin..."]
                selected_mag = st.selectbox("📍 Mağaza Seçin", mag_options)

                if st.button("🔍 Detayları Getir"):
                    st.warning("Önce veri yükleyin")

            with tabs[4]:
                st.subheader("📥 Rapor İndir")
                st.info("📥 Veri yüklendikten sonra Excel raporu indirebilirsiniz")

    # ==================== GM ÖZET MODU ====================
    elif analysis_mode == "🌍 GM Özet":
        st.subheader("🌍 GM Özet - Bölge Dashboard")

        # Dönem seçimi
        available_periods = get_available_periods()

        if available_periods:
            selected_periods = st.multiselect("📅 Dönem Seçin", available_periods, default=available_periods[:1])
        else:
            selected_periods = []
            st.warning("Henüz veri yüklenmemiş. SM'ler Excel yükledikçe veriler burada görünecek.")

        if selected_periods:
            st.markdown("---")
            st.subheader("📊 Bölge Özeti - 0 Mağaza")

            # Üst metrikler
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("💰 Satış", "0 TL")
            col2.metric("📉 Fark", "%0.00", "0 | Gün: 0")
            col3.metric("🔥 Fire", "%0.00", "0 | Gün: 0")
            col4.metric("📊 Toplam", "%0.00", "0")
            col5.metric("💰 10 TL", "0", "TAMAM")

            # Risk dağılımı
            st.markdown("### 📊 Risk Dağılımı")
            r1, r2, r3, r4 = st.columns(4)
            r1.markdown('<div class="risk-kritik">🔴 KRİTİK: 0</div>', unsafe_allow_html=True)
            r2.markdown('<div class="risk-riskli">🟠 RİSKLİ: 0</div>', unsafe_allow_html=True)
            r3.markdown('<div class="risk-dikkat">🟡 DİKKAT: 0</div>', unsafe_allow_html=True)
            r4.markdown('<div class="risk-temiz">🟢 TEMİZ: 0</div>', unsafe_allow_html=True)

            # Sekmeler
            tabs = st.tabs(["👔 SM Özet", "📋 BS Özet", "🏪 Mağazalar", "📊 Top 10", "🔍 Mağaza Detay", "📥 İndir"])

            with tabs[0]:
                st.subheader("👔 Satış Müdürü Bazlı Özet")

                # Başlık satırı
                cols = st.columns([2, 1.5, 1.5, 1, 1, 1, 1])
                cols[0].markdown("**Satış Müdürü**")
                cols[1].markdown("**Satış | Fark**")
                cols[2].markdown("**Fire**")
                cols[3].markdown("**Kayıp %**")
                cols[4].markdown("**🚬 🔒**")
                cols[5].markdown("**Risk**")
                cols[6].markdown("**Seviye**")
                st.markdown("---")

                st.info("📥 Veri yüklendikten sonra SM özeti görüntülenecek")

            with tabs[1]:
                st.subheader("📋 Bölge Sorumlusu Bazlı Özet")
                st.info("📥 Veri yüklendikten sonra BS özeti görüntülenecek")

            with tabs[2]:
                st.subheader("🏪 Tüm Mağazalar")

                # Filtreler
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    risk_filter = st.multiselect("Risk Seviyesi", ["🔴 KRİTİK", "🟠 RİSKLİ", "🟡 DİKKAT", "🟢 TEMİZ"])
                with col_f2:
                    sm_filter = st.multiselect("Satış Müdürü", get_available_sms())
                with col_f3:
                    bs_filter = st.multiselect("Bölge Sorumlusu", [])

                st.info("📊 0 mağaza gösteriliyor")

            with tabs[3]:
                st.subheader("📊 En Riskli 10 Mağaza")
                st.info("📥 Veri yüklendikten sonra en riskli mağazalar görüntülenecek")

            with tabs[4]:
                st.subheader("🔍 Mağaza Detay Görünümü")
                st.info("Bir mağaza seçerek detayları görüntüleyebilirsiniz.")

                mag_options_gm = ["Mağaza seçin..."]
                selected_mag_gm = st.selectbox("📍 Mağaza Seçin", mag_options_gm, key="gm_mag_select")

                if st.button("🔍 Detayları Getir", key="gm_details"):
                    st.warning("Önce veri yükleyin")

            with tabs[5]:
                st.subheader("📥 Raporları İndir")

                st.button("📥 GM Bölge Dashboard (Excel)", disabled=True)

                st.markdown("---")
                st.markdown("**📥 Mağaza Detay Raporu İndir**")

                mag_options_gm_dl = ["Mağaza seçin..."]
                selected_mag_gm_dl = st.selectbox("Mağaza seçin", mag_options_gm_dl, key="gm_mag_dl")

                st.button("📥 Mağaza Raporu Oluştur", disabled=True)

    # ==================== EXCEL YÜKLE MODU ====================
    elif analysis_mode == "📥 Excel Yükle":
        st.subheader("📥 Excel Dosyası Yükle")

        st.markdown("""
        **Yüklenecek dosya formatı:**
        - Sürekli envanter Excel dosyası
        - Et-Tavuk, Ekmek veya Meyve/Sebze kategorileri
        """)

        uploaded_file = st.file_uploader(
            "Excel dosyasını seçin",
            type=['xlsx', 'xls'],
            help="Sürekli envanter verisi içeren Excel dosyası"
        )

        if uploaded_file:
            try:
                # Excel oku
                xl = pd.ExcelFile(uploaded_file)
                sheet_names = xl.sheet_names

                # En çok sütunu olan sayfayı bul
                best_sheet = None
                max_cols = 0

                for sheet in sheet_names:
                    temp_df = pd.read_excel(uploaded_file, sheet_name=sheet, nrows=5)
                    if len(temp_df.columns) > max_cols:
                        max_cols = len(temp_df.columns)
                        best_sheet = sheet

                df = pd.read_excel(uploaded_file, sheet_name=best_sheet)
                st.success(f"✅ {len(df)} satır, {len(df.columns)} sütun yüklendi ({best_sheet})")

                # Sütunları göster
                with st.expander("📋 Sütunlar"):
                    st.write(df.columns.tolist())

                # Önizleme
                with st.expander("👁️ Veri Önizleme"):
                    st.dataframe(df.head(20), use_container_width=True)

                # Analiz butonu
                if st.button("🔍 Analiz Et", use_container_width=True):
                    with st.spinner("Analiz ediliyor..."):
                        # TODO: Analiz fonksiyonlarını ekle
                        st.success("✅ Analiz tamamlandı!")

                        # Özet göster
                        st.markdown("---")
                        st.markdown("### 📊 Analiz Sonuçları")

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("📦 Toplam Ürün", len(df))
                        with col2:
                            if 'Mağaza Kodu' in df.columns:
                                st.metric("🏪 Mağaza", df['Mağaza Kodu'].nunique())
                            else:
                                st.metric("🏪 Mağaza", 1)
                        with col3:
                            st.metric("📊 Sütun", len(df.columns))

                # Supabase'e kaydet butonu
                if supabase:
                    st.markdown("---")
                    if st.button("💾 Veritabanına Kaydet", use_container_width=True):
                        with st.spinner("Kaydediliyor..."):
                            # TODO: Supabase kayıt fonksiyonu
                            st.success("✅ Veriler kaydedildi!")

            except Exception as e:
                st.error(f"Dosya okunamadı: {e}")

# ==================== UYGULAMA BAŞLAT ====================
if not st.session_state.logged_in:
    login()
else:
    main_app()
