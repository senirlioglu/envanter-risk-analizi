# ==================== SÜREKLİ ENVANTER MODÜLÜ ====================
# Bu modül sürekli envanter (haftalık) analizi için kullanılır
# Et-Tavuk, Ekmek, Meyve/Sebze kategorileri için

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# ==================== SABİTLER ====================

# Hariç tutulacak nitelikler
HARIC_NITELIKLER = ['Geçici Delist', 'Bölgesel', 'Delist']

# Segment hiyerarşisi
SEGMENT_MAPPING = {
    'L': ['L', 'LA', 'LAB', 'LABC', 'LABCD'],
    'A': ['A', 'LA', 'LAB', 'LABC', 'LABCD'],
    'B': ['B', 'LAB', 'LABC', 'LABCD'],
    'C': ['C', 'LABC', 'LABCD'],
    'D': ['D', 'LABCD']
}

# Yüksek miktar istisnası
YUKSEK_MIKTAR_ISTISNALAR = ['PATATES', 'SOĞAN', 'SOGAN']

# Minimum filtre değerleri
MIN_SATIS_HASILATI = 500
MIN_SATIS_MIKTAR = 10

# Risk puan ağırlıkları
SUREKLI_RISK_WEIGHTS = {
    'bolge_sapma': 20, 'satir_iptali': 12, 'kronik_acik': 10, 'aile_analizi': 5,
    'kronik_fire': 8, 'fire_manipulasyon': 8, 'sayilmayan_urun': 8,
    'anormal_miktar': 10, 'tekrar_miktar': 8, 'yuvarlak_sayi': 8
}


# ==================== SM/BS MAĞAZA VERİSİ ====================
# 207 mağaza - sm_bs_mağaza_sayoıları.xlsx'ten

SM_BS_MAGAZA = {
    "7946": {"sm": "GİZEM TOSUN", "bs": "İSMAİL YAZGAN"},
    "B259": {"sm": "GİZEM TOSUN", "bs": "MEHMET KÜÇÜKOĞLU"},
    "5490": {"sm": "GİZEM TOSUN", "bs": "MEHMET KÜÇÜKOĞLU"},
    "4667": {"sm": "ALİ AKÇAY", "bs": "İBRAHİM DURBALİ"},
    "1339": {"sm": "GİZEM TOSUN", "bs": "İSMAİL YAZGAN"},
    "D014": {"sm": "GİZEM TOSUN", "bs": "İSMAİL YAZGAN"},
    "H023": {"sm": "GİZEM TOSUN", "bs": "İSMAİL YAZGAN"},
    "8406": {"sm": "GİZEM TOSUN", "bs": "MEHMET KÜÇÜKOĞLU"},
    "C509": {"sm": "GİZEM TOSUN", "bs": "İSMAİL UĞUR KAYA"},
    "461": {"sm": "GİZEM TOSUN", "bs": "DOĞAN İSTEMİHAN"},
    "F488": {"sm": "GİZEM TOSUN", "bs": "DOĞAN İSTEMİHAN"},
    "C545": {"sm": "GİZEM TOSUN", "bs": "FATİH SERT"},
    "C156": {"sm": "GİZEM TOSUN", "bs": "DOĞAN İSTEMİHAN"},
    "396": {"sm": "GİZEM TOSUN", "bs": "FATİH SERT"},
    "B056": {"sm": "GİZEM TOSUN", "bs": "DOĞAN İSTEMİHAN"},
    "4666": {"sm": "GİZEM TOSUN", "bs": "FATİH SERT"},
    "3812": {"sm": "GİZEM TOSUN", "bs": "İSMET YILMAZ"},
    "C029": {"sm": "GİZEM TOSUN", "bs": "İSMET YILMAZ"},
    "1259": {"sm": "GİZEM TOSUN", "bs": "İSMET YILMAZ"},
    "3819": {"sm": "GİZEM TOSUN", "bs": "FATİH SERT"},
    "B058": {"sm": "GİZEM TOSUN", "bs": "FATİH SERT"},
    "C132": {"sm": "GİZEM TOSUN", "bs": "İSMET YILMAZ"},
    "C371": {"sm": "GİZEM TOSUN", "bs": "İSMET YILMAZ"},
    "D214": {"sm": "GİZEM TOSUN", "bs": "İSMAİL YAZGAN"},
    "3305": {"sm": "ALİ AKÇAY", "bs": "NESLİHAN ÖZYURT"},
    "E317": {"sm": "ALİ AKÇAY", "bs": "NESLİHAN ÖZYURT"},
    "4377": {"sm": "ALİ AKÇAY", "bs": "NESLİHAN ÖZYURT"},
    "E319": {"sm": "ALİ AKÇAY", "bs": "NESLİHAN ÖZYURT"},
    "F813": {"sm": "ALİ AKÇAY", "bs": "AYŞE DAL"},
    "C401": {"sm": "ALİ AKÇAY", "bs": "AYŞE DAL"},
    "2022": {"sm": "GİZEM TOSUN", "bs": "FATİH SERT"},
    "E180": {"sm": "GİZEM TOSUN", "bs": "İSMET YILMAZ"},
    "B043": {"sm": "GİZEM TOSUN", "bs": "İSMAİL UĞUR KAYA"},
    "B368": {"sm": "GİZEM TOSUN", "bs": "İSMAİL UĞUR KAYA"},
    "E664": {"sm": "GİZEM TOSUN", "bs": "İSMAİL UĞUR KAYA"},
    "7164": {"sm": "GİZEM TOSUN", "bs": "İSMAİL UĞUR KAYA"},
    "2054": {"sm": "GİZEM TOSUN", "bs": "DOĞAN İSTEMİHAN"},
    "F296": {"sm": "GİZEM TOSUN", "bs": "İSMAİL UĞUR KAYA"},
    "8971": {"sm": "GİZEM TOSUN", "bs": "İSMAİL UĞUR KAYA"},
    "F516": {"sm": "GİZEM TOSUN", "bs": "İSMAİL YAZGAN"},
    "1142": {"sm": "GİZEM TOSUN", "bs": "İSMAİL UĞUR KAYA"},
    "G400": {"sm": "ALİ AKÇAY", "bs": "FİKRET HOCA"},
    "561": {"sm": "ALİ AKÇAY", "bs": "FİKRET HOCA"},
    "B750": {"sm": "ALİ AKÇAY", "bs": "AYŞE DAL"},
    "1408": {"sm": "ALİ AKÇAY", "bs": "AYŞE DAL"},
    "C241": {"sm": "ALİ AKÇAY", "bs": "FİKRET HOCA"},
    "8404": {"sm": "ALİ AKÇAY", "bs": "FİKRET HOCA"},
    "7832": {"sm": "ALİ AKÇAY", "bs": "FİKRET HOCA"},
    "434": {"sm": "ALİ AKÇAY", "bs": "NESLİHAN ÖZYURT"},
    "B931": {"sm": "ALİ AKÇAY", "bs": "AYŞE DAL"},
    "1071": {"sm": "ALİ AKÇAY", "bs": "ÜMİT KIRBAŞ"},
    "D589": {"sm": "ALİ AKÇAY", "bs": "FİKRET HOCA"},
    "9065": {"sm": "ALİ AKÇAY", "bs": "AYŞE DAL"},
    "4052": {"sm": "ALİ AKÇAY", "bs": "ÜMİT KIRBAŞ"},
    "B041": {"sm": "ALİ AKÇAY", "bs": "ÜMİT KIRBAŞ"},
    "4282": {"sm": "GİZEM TOSUN", "bs": "MUHAMMED BAŞARAN"},
    "B543": {"sm": "GİZEM TOSUN", "bs": "MUHAMMED BAŞARAN"},
    "D074": {"sm": "GİZEM TOSUN", "bs": "MUHAMMED BAŞARAN"},
    "2326": {"sm": "GİZEM TOSUN", "bs": "MUHAMMED BAŞARAN"},
    "9575": {"sm": "GİZEM TOSUN", "bs": "MUHAMMED BAŞARAN"},
    "1270": {"sm": "ALİ AKÇAY", "bs": "İBRAHİM DURBALİ"},
    "D471": {"sm": "ALİ AKÇAY", "bs": "İBRAHİM DURBALİ"},
    "2071": {"sm": "ALİ AKÇAY", "bs": "İBRAHİM DURBALİ"},
    "2454": {"sm": "ALİ AKÇAY", "bs": "İBRAHİM DURBALİ"},
    "B465": {"sm": "ALİ AKÇAY", "bs": "ÖZKAN DEMİR"},
    "4892": {"sm": "ALİ AKÇAY", "bs": "İBRAHİM DURBALİ"},
    "B072": {"sm": "ALİ AKÇAY", "bs": "İBRAHİM DURBALİ"},
    "1441": {"sm": "ALİ AKÇAY", "bs": "ÜMİT KIRBAŞ"},
    "7915": {"sm": "ALİ AKÇAY", "bs": "ÜMİT KIRBAŞ"},
    "4299": {"sm": "ALİ AKÇAY", "bs": "ÜMİT KIRBAŞ"},
    "8243": {"sm": "ALİ AKÇAY", "bs": "ÖZKAN DEMİR"},
    "C490": {"sm": "ALİ AKÇAY", "bs": "ÖZKAN DEMİR"},
    "B548": {"sm": "ALİ AKÇAY", "bs": "ÖZKAN DEMİR"},
    "C558": {"sm": "ALİ AKÇAY", "bs": "AYŞE DAL"},
    "E861": {"sm": "ALİ AKÇAY", "bs": "ÖZKAN DEMİR"},
    "8931": {"sm": "ALİ AKÇAY", "bs": "ÖZKAN DEMİR"},
    "1830": {"sm": "ALİ AKÇAY", "bs": "ÖZKAN DEMİR"},
    "E046": {"sm": "ALİ AKÇAY", "bs": "NESLİHAN ÖZYURT"},
    "B818": {"sm": "ALİ AKÇAY", "bs": "NESLİHAN ÖZYURT"},
    "D336": {"sm": "ŞADAN YURDAKUL", "bs": "ÜMİT KAAN ŞAHİN"},
    "E138": {"sm": "ŞADAN YURDAKUL", "bs": "ÜMİT KAAN ŞAHİN"},
    "B130": {"sm": "ŞADAN YURDAKUL", "bs": "ÜMİT KAAN ŞAHİN"},
    "9027": {"sm": "ŞADAN YURDAKUL", "bs": "ÜMİT KAAN ŞAHİN"},
    "7606": {"sm": "ŞADAN YURDAKUL", "bs": "ÜMİT KAAN ŞAHİN"},
    "C528": {"sm": "ŞADAN YURDAKUL", "bs": "ERDAL ARSLAN"},
    "C547": {"sm": "ŞADAN YURDAKUL", "bs": "ERDAL ARSLAN"},
    "9541": {"sm": "ŞADAN YURDAKUL", "bs": "ERDAL ARSLAN"},
    "E351": {"sm": "ŞADAN YURDAKUL", "bs": "ERDAL ARSLAN"},
    "F038": {"sm": "ŞADAN YURDAKUL", "bs": "ERDAL ARSLAN"},
    "D657": {"sm": "ŞADAN YURDAKUL", "bs": "ÜMİT KAAN ŞAHİN"},
    "C820": {"sm": "ALİ AKÇAY", "bs": "EMRAH AKINCI"},
    "C760": {"sm": "VELİ GÖK", "bs": "ÇAĞRI YALÇIN"},
    "648": {"sm": "VELİ GÖK", "bs": "ÇAĞRI YALÇIN"},
    "B397": {"sm": "VELİ GÖK", "bs": "ÇAĞRI YALÇIN"},
    "C553": {"sm": "VELİ GÖK", "bs": "ÇAĞRI YALÇIN"},
    "1715": {"sm": "VELİ GÖK", "bs": "ÇAĞRI YALÇIN"},
    "9423": {"sm": "VELİ GÖK", "bs": "TUĞÇE KOCABAŞ"},
    "C656": {"sm": "ALİ AKÇAY", "bs": "EMRAH AKINCI"},
    "B218": {"sm": "ALİ AKÇAY", "bs": "EMRAH AKINCI"},
    "D587": {"sm": "ŞADAN YURDAKUL", "bs": "ÜMİT KAAN ŞAHİN"},
    "B638": {"sm": "ŞADAN YURDAKUL", "bs": "ERDAL ARSLAN"},
    "F344": {"sm": "ALİ AKÇAY", "bs": "EMRAH AKINCI"},
    "B691": {"sm": "ALİ AKÇAY", "bs": "EMRAH AKINCI"},
    "1484": {"sm": "VELİ GÖK", "bs": "ÇAĞRI YALÇIN"},
    "1610": {"sm": "VELİ GÖK", "bs": "TUĞÇE KOCABAŞ"},
    "D483": {"sm": "VELİ GÖK", "bs": "ABDULLAH BAY"},
    "1125": {"sm": "VELİ GÖK", "bs": "TUĞÇE KOCABAŞ"},
    "E607": {"sm": "VELİ GÖK", "bs": "TUĞÇE KOCABAŞ"},
    "D549": {"sm": "VELİ GÖK", "bs": "TUĞÇE KOCABAŞ"},
    "9171": {"sm": "VELİ GÖK", "bs": "TUĞÇE KOCABAŞ"},
    "E227": {"sm": "VELİ GÖK", "bs": "TUĞÇE KOCABAŞ"},
    "D337": {"sm": "VELİ GÖK", "bs": "ABDULLAH BAY"},
    "B949": {"sm": "VELİ GÖK", "bs": "ABDULLAH BAY"},
    "F089": {"sm": "VELİ GÖK", "bs": "ABDULLAH BAY"},
    "376": {"sm": "VELİ GÖK", "bs": "ABDULLAH BAY"},
    "H174": {"sm": "VELİ GÖK", "bs": "ABDULLAH BAY"},
    "9088": {"sm": "ŞADAN YURDAKUL", "bs": "SİNEM ÖZKAYA"},
    "G743": {"sm": "ŞADAN YURDAKUL", "bs": "SİNEM ÖZKAYA"},
    "C668": {"sm": "ŞADAN YURDAKUL", "bs": "SİNEM ÖZKAYA"},
    "9626": {"sm": "ŞADAN YURDAKUL", "bs": "SİNEM ÖZKAYA"},
    "D627": {"sm": "ŞADAN YURDAKUL", "bs": "RAMAZAN ÇATALTAŞ"},
    "D706": {"sm": "ŞADAN YURDAKUL", "bs": "SİNEM ÖZKAYA"},
    "8687": {"sm": "ŞADAN YURDAKUL", "bs": "SİNEM ÖZKAYA"},
    "8047": {"sm": "ŞADAN YURDAKUL", "bs": "RAMAZAN ÇATALTAŞ"},
    "C007": {"sm": "VELİ GÖK", "bs": "KADİR ÇETİN"},
    "C346": {"sm": "VELİ GÖK", "bs": "SELİM GÜNDÜZ"},
    "651": {"sm": "VELİ GÖK", "bs": "KADİR ÇETİN"},
    "6346": {"sm": "VELİ GÖK", "bs": "KADİR ÇETİN"},
    "F408": {"sm": "VELİ GÖK", "bs": "KADİR ÇETİN"},
    "132": {"sm": "VELİ GÖK", "bs": "KADİR ÇETİN"},
    "5361": {"sm": "VELİ GÖK", "bs": "KERİM YÜREKLİ"},
    "9395": {"sm": "VELİ GÖK", "bs": "KERİM YÜREKLİ"},
    "D466": {"sm": "VELİ GÖK", "bs": "KERİM YÜREKLİ"},
    "D397": {"sm": "VELİ GÖK", "bs": "KERİM YÜREKLİ"},
    "5587": {"sm": "VELİ GÖK", "bs": "KERİM YÜREKLİ"},
    "6667": {"sm": "VELİ GÖK", "bs": "SELİM GÜNDÜZ"},
    "F118": {"sm": "ŞADAN YURDAKUL", "bs": "RAMAZAN ÇATALTAŞ"},
    "D912": {"sm": "ŞADAN YURDAKUL", "bs": "RAMAZAN ÇATALTAŞ"},
    "C947": {"sm": "ŞADAN YURDAKUL", "bs": "RAMAZAN ÇATALTAŞ"},
    "8568": {"sm": "ŞADAN YURDAKUL", "bs": "YUNUS BAYSAL"},
    "G874": {"sm": "ŞADAN YURDAKUL", "bs": "YUNUS BAYSAL"},
    "H035": {"sm": "VELİ GÖK", "bs": "TUĞBA ALDI"},
    "F973": {"sm": "VELİ GÖK", "bs": "TUĞBA ALDI"},
    "8574": {"sm": "VELİ GÖK", "bs": "TUĞBA ALDI"},
    "D705": {"sm": "ŞADAN YURDAKUL", "bs": "YUNUS BAYSAL"},
    "E965": {"sm": "VELİ GÖK", "bs": "TUĞBA ALDI"},
    "E257": {"sm": "VELİ GÖK", "bs": "TUĞBA ALDI"},
    "G669": {"sm": "ŞADAN YURDAKUL", "bs": "YUNUS BAYSAL"},
    "8878": {"sm": "ŞADAN YURDAKUL", "bs": "YUNUS BAYSAL"},
    "7707": {"sm": "ŞADAN YURDAKUL", "bs": "YUNUS BAYSAL"},
    "5945": {"sm": "ŞADAN YURDAKUL", "bs": "RAMAZAN ÇATALTAŞ"},
    "H203": {"sm": "GİZEM TOSUN", "bs": "DOĞAN İSTEMİHAN"},
    "H283": {"sm": "ALİ AKÇAY", "bs": "AYŞE DAL"},
    "H351": {"sm": "GİZEM TOSUN", "bs": "MUHAMMED BAŞARAN"},
    "H388": {"sm": "VELİ GÖK", "bs": "KADİR ÇETİN"},
    "H411": {"sm": "ŞADAN YURDAKUL", "bs": "YUNUS BAYSAL"},
    "H399": {"sm": "ŞADAN YURDAKUL", "bs": "RAMAZAN ÇATALTAŞ"},
    "H424": {"sm": "ŞADAN YURDAKUL", "bs": "YUNUS BAYSAL"},
    "H519": {"sm": "ŞADAN YURDAKUL", "bs": "RAMAZAN ÇATALTAŞ"},
    "H505": {"sm": "ALİ AKÇAY", "bs": "FİKRET HOCA"},
    "H552": {"sm": "VELİ GÖK", "bs": "TUĞBA ALDI"},
    "H641": {"sm": "VELİ GÖK", "bs": "SELİM GÜNDÜZ"},
    "H645": {"sm": "ŞADAN YURDAKUL", "bs": "RAMAZAN ÇATALTAŞ"},
    "H674": {"sm": "VELİ GÖK", "bs": "SELİM GÜNDÜZ"},
    "H748": {"sm": "VELİ GÖK", "bs": "SELİM GÜNDÜZ"},
    "H946": {"sm": "VELİ GÖK", "bs": "TUĞBA ALDI"},
    "H950": {"sm": "ŞADAN YURDAKUL", "bs": "RAMAZAN ÇATALTAŞ"},
    "I023": {"sm": "GİZEM TOSUN", "bs": "İSMAİL YAZGAN"},
    "I066": {"sm": "ALİ AKÇAY", "bs": "İBRAHİM DURBALİ"},
    "I174": {"sm": "GİZEM TOSUN", "bs": "MEHMET KÜÇÜKOĞLU"},
    "I251": {"sm": "ALİ AKÇAY", "bs": "ÖZKAN DEMİR"},
    "I252": {"sm": "ŞADAN YURDAKUL", "bs": "SİNEM ÖZKAYA"},
    "I431": {"sm": "GİZEM TOSUN", "bs": "İSMET YILMAZ"},
    "I566": {"sm": "ŞADAN YURDAKUL", "bs": "RAMAZAN ÇATALTAŞ"},
    "I568": {"sm": "VELİ GÖK", "bs": "ÇAĞRI YALÇIN"},
    "I578": {"sm": "ŞADAN YURDAKUL", "bs": "YUNUS BAYSAL"},
    "I628": {"sm": "ŞADAN YURDAKUL", "bs": "YUNUS BAYSAL"},
    "I702": {"sm": "VELİ GÖK", "bs": "KADİR ÇETİN"},
    "I693": {"sm": "ŞADAN YURDAKUL", "bs": "SİNEM ÖZKAYA"},
    "I725": {"sm": "VELİ GÖK", "bs": "SELİM GÜNDÜZ"},
    "I684": {"sm": "ALİ AKÇAY", "bs": "EMRAH AKINCI"},
    "I654": {"sm": "ALİ AKÇAY", "bs": "ÜMİT KIRBAŞ"},
    "I862": {"sm": "VELİ GÖK", "bs": "SELİM GÜNDÜZ"},
    "I824": {"sm": "ŞADAN YURDAKUL", "bs": "ERDAL ARSLAN"},
    "I879": {"sm": "GİZEM TOSUN", "bs": "İSMAİL YAZGAN"},
    "D550": {"sm": "ŞADAN YURDAKUL", "bs": "ÜMİT KAAN ŞAHİN"},
    "I984": {"sm": "VELİ GÖK", "bs": "ABDULLAH BAY"},
    "I996": {"sm": "VELİ GÖK", "bs": "KERİM YÜREKLİ"},
    "J187": {"sm": "VELİ GÖK", "bs": "KERİM YÜREKLİ"},
    "J218": {"sm": "VELİ GÖK", "bs": "SELİM GÜNDÜZ"},
    "J270": {"sm": "ŞADAN YURDAKUL", "bs": "YUNUS BAYSAL"},
    "J365": {"sm": "ALİ AKÇAY", "bs": "ÜMİT KIRBAŞ"},
    "J372": {"sm": "GİZEM TOSUN", "bs": "DOĞAN İSTEMİHAN"},
    "J366": {"sm": "GİZEM TOSUN", "bs": "MEHMET KÜÇÜKOĞLU"},
    "J433": {"sm": "GİZEM TOSUN", "bs": "MUHAMMED BAŞARAN"},
    "J506": {"sm": "ALİ AKÇAY", "bs": "FİKRET HOCA"},
    "J732": {"sm": "ŞADAN YURDAKUL", "bs": "RAMAZAN ÇATALTAŞ"},
    "J751": {"sm": "VELİ GÖK", "bs": "TUĞBA ALDI"},
    "J846": {"sm": "GİZEM TOSUN", "bs": "MEHMET KÜÇÜKOĞLU"},
    "J857": {"sm": "GİZEM TOSUN", "bs": "MEHMET KÜÇÜKOĞLU"},
    "J880": {"sm": "VELİ GÖK", "bs": "TUĞÇE KOCABAŞ"},
    "K004": {"sm": "GİZEM TOSUN", "bs": "İSMET YILMAZ"},
    "K121": {"sm": "GİZEM TOSUN", "bs": "MUHAMMED BAŞARAN"},
    "K143": {"sm": "GİZEM TOSUN", "bs": "FATİH SERT"},
    "K179": {"sm": "ALİ AKÇAY", "bs": "NESLİHAN ÖZYURT"},
    "K277": {"sm": "GİZEM TOSUN", "bs": "MEHMET KÜÇÜKOĞLU"},
    "K237": {"sm": "ŞADAN YURDAKUL", "bs": "YUNUS BAYSAL"},
}


# ==================== SEGMENT ÜRÜN LİSTESİ ====================
# 77 ürün - Meyve/Sebze segment bazlı

SEGMENT_URUN = {
    "20000835": {"tanim": "ANANAS", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 119.5},
    "20000812": {"tanim": "ARMUT DEVECİ", "tip": "LABCD", "nitelik": "Sezonluk", "fiyat": 99.5},
    "20000813": {"tanim": "ARMUT SANTA MARİA", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 99.5},
    "20000853": {"tanim": "AVOKADO", "tip": "LABC", "nitelik": "Sezonluk", "fiyat": 49.5},
    "20001343": {"tanim": "AVOKADO YEMEYE HAZIR PAKET", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 99.5},
    "20000815": {"tanim": "AYVA", "tip": "LABC", "nitelik": "Sezonluk", "fiyat": 129.5},
    "20001154": {"tanim": "BAL KABAĞI", "tip": "LA", "nitelik": "Delist", "fiyat": 37.9},
    "20000023": {"tanim": "BİBER ÇARLİSTON PAKET", "tip": "LABCD", "nitelik": "Sezonluk", "fiyat": 24.9},
    "20000025": {"tanim": "BİBER DOLMA PAKET", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 27.9},
    "20000642": {"tanim": "BİBER KALİFORNİYA PAKET", "tip": "L", "nitelik": "Sezonluk", "fiyat": 99.5},
    "20001373": {"tanim": "BİBER KIL SİVRİ PAKET", "tip": "L", "nitelik": "Sezonluk", "fiyat": 34.9},
    "20000026": {"tanim": "BİBER KIRMIZI PAKET", "tip": "LABC", "nitelik": "Regüler", "fiyat": 37.9},
    "20001374": {"tanim": "BİBER KÖY PAKET", "tip": "L", "nitelik": "Sezonluk", "fiyat": 27.9},
    "20000024": {"tanim": "BİBER SİVRİ PAKET", "tip": "LABC", "nitelik": "Sezonluk", "fiyat": 24.9},
    "20001278": {"tanim": "BİBER ŞİLİ PAKET", "tip": "L", "nitelik": "Sezonluk", "fiyat": 31.9},
    "20000818": {"tanim": "ÇİLEK", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 59.5},
    "20000821": {"tanim": "DOMATES", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 39.9},
    "20000022": {"tanim": "DOMATES PAKET", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 24.9},
    "20000824": {"tanim": "DOMATES SALKLI", "tip": "LABC", "nitelik": "Sezonluk", "fiyat": 64.9},
    "20001092": {"tanim": "DOMATES SOFRALIK PAKET", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 27.9},
    "20000826": {"tanim": "ELİK", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 69.5},
    "20001114": {"tanim": "ELMA GALA", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 79.5},
    "20001119": {"tanim": "ELMA GRANNY SMİTH", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 89.5},
    "20000829": {"tanim": "ELMA STARKING", "tip": "LABC", "nitelik": "Sezonluk", "fiyat": 89.5},
    "20000830": {"tanim": "ENGINAR", "tip": "LA", "nitelik": "Sezonluk", "fiyat": 39.5},
    "20000831": {"tanim": "ERİK", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 99.5},
    "20001281": {"tanim": "FASULYE AYŞE KADIN PAKET", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 44.9},
    "20000834": {"tanim": "GREYFURT", "tip": "LABC", "nitelik": "Sezonluk", "fiyat": 44.9},
    "20001376": {"tanim": "HAVUÇ PAKET", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 17.9},
    "20000837": {"tanim": "HIYAR", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 39.9},
    "20001282": {"tanim": "HIYAR PAKET", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 22.9},
    "20001377": {"tanim": "HIYAR SALATALIK PAKET", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 24.9},
    "20000840": {"tanim": "İNCİR TAZE", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 149.5},
    "20001286": {"tanim": "KABAK PAKET", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 22.9},
    "20000842": {"tanim": "KARPUZ", "tip": "LABCD", "nitelik": "Sezonluk", "fiyat": 19.9},
    "20000843": {"tanim": "KAVUN", "tip": "LABCD", "nitelik": "Sezonluk", "fiyat": 39.9},
    "20000844": {"tanim": "KAYISI", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 119.5},
    "20000846": {"tanim": "KİRAZ", "tip": "LA", "nitelik": "Sezonluk", "fiyat": 149.5},
    "20000847": {"tanim": "KİVİ", "tip": "LABC", "nitelik": "Sezonluk", "fiyat": 69.5},
    "20000848": {"tanim": "LAHANA", "tip": "LABC", "nitelik": "Regüler", "fiyat": 17.9},
    "20000850": {"tanim": "LİMON", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 49.9},
    "20000852": {"tanim": "MANDALİNA", "tip": "LABCD", "nitelik": "Sezonluk", "fiyat": 39.9},
    "20001323": {"tanim": "MANGO", "tip": "LA", "nitelik": "Sezonluk", "fiyat": 99.5},
    "20000854": {"tanim": "MARUL", "tip": "LABC", "nitelik": "Regüler", "fiyat": 24.9},
    "20001288": {"tanim": "MARUL GÖBEĞİ PAKET", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 27.9},
    "20000859": {"tanim": "MUZ", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 79.9},
    "20000860": {"tanim": "NAR", "tip": "LABC", "nitelik": "Sezonluk", "fiyat": 79.5},
    "20000861": {"tanim": "NEKTARİN", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 99.5},
    "20000862": {"tanim": "PATLICAN", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 44.9},
    "20001289": {"tanim": "PATLICAN KEMER PAKET", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 27.9},
    "20001290": {"tanim": "PATLICAN PARMAK PAKET", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 24.9},
    "20000864": {"tanim": "PATATES", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 24.9},
    "20001379": {"tanim": "PATATES PAKET", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 37.9},
    "20001381": {"tanim": "PATATES TURFANDA PAKET", "tip": "LA", "nitelik": "Sezonluk", "fiyat": 34.9},
    "20000866": {"tanim": "PIRASA", "tip": "LABC", "nitelik": "Sezonluk", "fiyat": 34.9},
    "20000867": {"tanim": "PORTAKAL", "tip": "LABCD", "nitelik": "Sezonluk", "fiyat": 29.9},
    "20000868": {"tanim": "PORTAKAL SIKI", "tip": "LABC", "nitelik": "Sezonluk", "fiyat": 34.9},
    "20001294": {"tanim": "SALATA KARIŞIK PAKET", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 34.9},
    "20001102": {"tanim": "SARIMSAK", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 149.5},
    "20001382": {"tanim": "SARIMSAK PAKET", "tip": "LABCD", "nitelik": "Tek seferlik", "fiyat": 29.9},
    "20000871": {"tanim": "SOĞAN KURU", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 17.9},
    "20001383": {"tanim": "SOĞAN PAKET", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 26.9},
    "20000872": {"tanim": "SOĞAN YEŞİL", "tip": "LABCD", "nitelik": "Regüler", "fiyat": 9.9},
    "20000874": {"tanim": "ŞEFTALİ", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 99.5},
    "20001384": {"tanim": "TURP KIRMIZI PAKET", "tip": "LAB", "nitelik": "Tek seferlik", "fiyat": 14.9},
    "20000877": {"tanim": "ÜZÜM ÇEKİRDEKSİZ", "tip": "LAB", "nitelik": "Sezonluk", "fiyat": 89.5},
    "20000878": {"tanim": "ÜZÜM TANE", "tip": "LA", "nitelik": "Sezonluk", "fiyat": 99.5},
    "20001387": {"tanim": "YER FISTIK", "tip": "LA", "nitelik": "Tek seferlik", "fiyat": 59.5},
    "20001356": {"tanim": "YEŞİLLİK DEREOTU PAKET", "tip": "LABC", "nitelik": "Regüler", "fiyat": 9.9},
    "20001355": {"tanim": "YEŞİLLİK MAYDANOZ PAKET", "tip": "LABC", "nitelik": "Regüler", "fiyat": 9.9},
    "20001357": {"tanim": "YEŞİLLİK NANE PAKET", "tip": "LABC", "nitelik": "Regüler", "fiyat": 9.9},
    "20001358": {"tanim": "YEŞİLLİK ROKA PAKET", "tip": "LABC", "nitelik": "Regüler", "fiyat": 9.9},
    "20001386": {"tanim": "ZENCEFİL", "tip": "LA", "nitelik": "Tek seferlik", "fiyat": 24.9},
    "20001091": {"tanim": "DOMATES CHERRY PAKET", "tip": "LABC", "nitelik": "Sezonluk", "fiyat": 34.9},
    "20001375": {"tanim": "DOMATES PEMBE PAKET", "tip": "L", "nitelik": "Sezonluk", "fiyat": 34.9},
    "20001155": {"tanim": "KEREVIZ", "tip": "LA", "nitelik": "Geçici Delist", "fiyat": 39.9},
    "20001156": {"tanim": "KARNABAHAR", "tip": "LA", "nitelik": "Geçici Delist", "fiyat": 39.9},
}


# ==================== FONKSİYONLAR ====================

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
        sonuc[kategori] = {'fark': fark, 'fire': fire, 'satis': satis, 'oran': oran, 'urun_sayisi': len(df_kat)}
    return sonuc


def detect_yuvarlak_sayi(df):
    """Yuvarlak sayı girişlerini tespit eder"""
    kontrol_kategoriler = ['Meyve/Sebz', 'Et-Tavuk']
    if 'Depolama Koşulu' in df.columns:
        df_filtered = df[df['Depolama Koşulu'].isin(kontrol_kategoriler)]
    else:
        df_filtered = df
    
    sayim_col = 'Sayım Miktarı' if 'Sayım Miktarı' in df.columns else None
    if sayim_col is None:
        return pd.DataFrame()
    
    yuvarlak = []
    for _, row in df_filtered.iterrows():
        miktar = row[sayim_col]
        if pd.notna(miktar) and miktar > 5:
            if miktar == int(miktar) and int(miktar) % 5 == 0:
                yuvarlak.append(row)
    return pd.DataFrame(yuvarlak)


def detect_anormal_miktar(df):
    """Anormal yüksek miktarları tespit eder (>50)"""
    sayim_col = 'Sayım Miktarı' if 'Sayım Miktarı' in df.columns else None
    tanim_col = 'Malzeme Tanımı' if 'Malzeme Tanımı' in df.columns else None
    if sayim_col is None:
        return pd.DataFrame()
    
    anormal = []
    for _, row in df.iterrows():
        miktar = row[sayim_col]
        tanim = str(row[tanim_col]).upper() if tanim_col else ''
        istisna = any(ist in tanim for ist in YUKSEK_MIKTAR_ISTISNALAR)
        if pd.notna(miktar) and miktar > 50 and not istisna:
            anormal.append(row)
    return pd.DataFrame(anormal)


def detect_tekrar_miktar(df_current, df_previous, tolerans=0.03):
    """Ardışık haftalarda aynı/yakın miktar tekrarını tespit eder"""
    if df_previous is None or df_previous.empty:
        return pd.DataFrame()
    
    sayim_col, kod_col = 'Sayım Miktarı', 'Malzeme Kodu'
    if sayim_col not in df_current.columns or kod_col not in df_current.columns:
        return pd.DataFrame()
    
    prev_dict = df_previous.set_index(kod_col)[sayim_col].to_dict()
    tekrar = []
    for _, row in df_current.iterrows():
        kod, miktar_su_an = row[kod_col], row[sayim_col]
        if kod in prev_dict:
            miktar_onceki = prev_dict[kod]
            if pd.notna(miktar_su_an) and pd.notna(miktar_onceki) and miktar_onceki > 0:
                fark_oran = abs(miktar_su_an - miktar_onceki) / miktar_onceki
                if fark_oran <= tolerans:
                    row_copy = row.copy()
                    row_copy['Önceki Miktar'] = miktar_onceki
                    tekrar.append(row_copy)
    return pd.DataFrame(tekrar)


def get_sayilmasi_gereken_urunler(magaza_kodu, segment='C', blokajli=None):
    """Bu mağazada sayılması gereken ürünleri döner"""
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


def get_sm_magaza_sayisi():
    """SM bazlı mağaza sayılarını döner"""
    sm_counts = {}
    for kod, bilgi in SM_BS_MAGAZA.items():
        sm = bilgi['sm']
        sm_counts[sm] = sm_counts.get(sm, 0) + 1
    return sm_counts


def get_bs_magaza_sayisi():
    """BS bazlı mağaza sayılarını döner"""
    bs_counts = {}
    for kod, bilgi in SM_BS_MAGAZA.items():
        bs = bilgi['bs']
        bs_counts[bs] = bs_counts.get(bs, 0) + 1
    return bs_counts


def get_sm_list():
    return list(set(v['sm'] for v in SM_BS_MAGAZA.values()))


def get_bs_list():
    return list(set(v['bs'] for v in SM_BS_MAGAZA.values()))


def get_magazalar_by_sm(sm):
    return {k: v for k, v in SM_BS_MAGAZA.items() if v['sm'] == sm}


def get_magazalar_by_bs(bs):
    return {k: v for k, v in SM_BS_MAGAZA.items() if v['bs'] == bs}


# ==================== RİSK SKORU HESAPLAMA ====================

def hesapla_surekli_risk_skoru(df, df_onceki=None, bolge_oran=None, blokajli=None, urun_medianlar=None):
    """
    Sürekli envanter risk skorunu hesaplar
    
    Args:
        df: Mağaza envanter verisi
        df_onceki: Önceki hafta verisi
        bolge_oran: Bölge ortalama oranı (eski yöntem)
        blokajli: Blokajlı ürünler dict
        urun_medianlar: Ürün bazlı bölge medianları (yeni yöntem)
    """
    risk = {'toplam_puan': 0, 'max_puan': 97, 'detaylar': {}, 'seviye': 'normal'}
    magaza_kodu = df['Mağaza Kodu'].iloc[0] if 'Mağaza Kodu' in df.columns else None
    
    # 1. BÖLGE SAPMA (20 puan) - MEDİAN BAZLI
    kat_ozet = hesapla_kategori_ozet(df)
    toplam_oran = sum(k.get('oran', 0) for k in kat_ozet.values()) / max(len(kat_ozet), 1)
    sapma_puan = 0
    sapma_detay = ""
    
    if urun_medianlar:
        # YENİ: Ürün bazlı median karşılaştırma
        sapan_urun_sayisi = 0
        for _, row in df.iterrows():
            kod = row.get('Malzeme Kodu')
            if kod and kod in urun_medianlar:
                median = urun_medianlar[kod]['median']
                if median > 0:
                    fark = abs(row.get('Fark Tutarı', 0) or 0)
                    fire = abs(row.get('Fire Tutarı', 0) or 0)
                    satis = row.get('Satış Hasılatı', 0) or 0
                    if satis > MIN_SATIS_HASILATI:
                        magaza_oran = (fark + fire) / satis * 100
                        if magaza_oran > median * 1.5:
                            sapan_urun_sayisi += 1
        
        # Sapan ürün sayısına göre puan
        if sapan_urun_sayisi >= 15:
            sapma_puan = 20
        elif sapan_urun_sayisi >= 10:
            sapma_puan = 15
        elif sapan_urun_sayisi >= 5:
            sapma_puan = 10
        elif sapan_urun_sayisi >= 2:
            sapma_puan = 5
        sapma_detay = f"{sapan_urun_sayisi} ürün medianın 1.5x üstünde"
    
    elif bolge_oran and bolge_oran > 0:
        # ESKİ: Genel oran karşılaştırma (fallback)
        sapma = toplam_oran / bolge_oran
        sapma_puan = 0 if sapma <= 1.2 else 5 if sapma <= 1.5 else 10 if sapma <= 2.0 else 15 if sapma <= 3.0 else 20
        sapma_detay = f"Mağaza: %{toplam_oran:.1f}, Bölge: %{bolge_oran:.1f}"
    
    risk['detaylar']['bolge_sapma'] = {'puan': sapma_puan, 'max': 20, 'detay': sapma_detay}
    risk['toplam_puan'] += sapma_puan
    
    # 2. SATIR İPTALİ (12 puan)
    iptal_col = 'İptal Satır Tutarı' if 'İptal Satır Tutarı' in df.columns else None
    iptal_tutar = abs(df[iptal_col].sum()) if iptal_col else 0
    iptal_puan = 0 if iptal_tutar <= 100 else 4 if iptal_tutar <= 500 else 8 if iptal_tutar <= 1500 else 12
    risk['detaylar']['satir_iptali'] = {'puan': iptal_puan, 'max': 12, 'tutar': iptal_tutar}
    risk['toplam_puan'] += iptal_puan
    
    # 3. KRONİK AÇIK (10 puan)
    kronik_puan = 0
    if df_onceki is not None and not df_onceki.empty:
        fark_col = 'Fark Miktarı' if 'Fark Miktarı' in df.columns else 'Fark Tutarı'
        if fark_col in df.columns and 'Malzeme Kodu' in df.columns:
            cur_neg = set(df[df[fark_col] < 0]['Malzeme Kodu'].astype(str))
            prev_neg = set(df_onceki[df_onceki[fark_col] < 0]['Malzeme Kodu'].astype(str))
            kronik = len(cur_neg & prev_neg)
            kronik_puan = 10 if kronik >= 10 else 6 if kronik >= 5 else 3 if kronik >= 2 else 0
    risk['detaylar']['kronik_acik'] = {'puan': kronik_puan, 'max': 10}
    risk['toplam_puan'] += kronik_puan
    
    # 4. AİLE ANALİZİ (5 puan) - TODO
    risk['detaylar']['aile_analizi'] = {'puan': 0, 'max': 5}
    
    # 5. KRONİK FİRE (8 puan)
    kronik_fire_puan = 0
    if df_onceki is not None and 'Fire Miktarı' in df.columns:
        cur_fire = set(df[df['Fire Miktarı'] < 0]['Malzeme Kodu'].astype(str))
        prev_fire = set(df_onceki[df_onceki['Fire Miktarı'] < 0]['Malzeme Kodu'].astype(str))
        kronik_fire = len(cur_fire & prev_fire)
        kronik_fire_puan = 8 if kronik_fire >= 8 else 5 if kronik_fire >= 4 else 2 if kronik_fire >= 2 else 0
    risk['detaylar']['kronik_fire'] = {'puan': kronik_fire_puan, 'max': 8}
    risk['toplam_puan'] += kronik_fire_puan
    
    # 6. FİRE MANİPÜLASYONU (8 puan)
    fire_manip_puan = 0
    if 'Fire Tutarı' in df.columns and 'Fark Tutarı' in df.columns:
        manip = df[(df['Fire Tutarı'].fillna(0) < 0) & (df['Fark Tutarı'].fillna(0) + df['Fire Tutarı'].fillna(0) > 0)]
        manip_count = len(manip)
        fire_manip_puan = 8 if manip_count >= 5 else 5 if manip_count >= 3 else 2 if manip_count >= 1 else 0
    risk['detaylar']['fire_manipulasyon'] = {'puan': fire_manip_puan, 'max': 8}
    risk['toplam_puan'] += fire_manip_puan
    
    # 7. SAYILMAYAN ÜRÜN (8 puan)
    sayilmayan_puan = 0
    if magaza_kodu:
        sayilmasi_gereken = get_sayilmasi_gereken_urunler(magaza_kodu, blokajli=blokajli)
        sayilan = set(str(k) for k in df['Malzeme Kodu'].unique()) if 'Malzeme Kodu' in df.columns else set()
        sayilmayan = len([u for u in sayilmasi_gereken if u not in sayilan])
        sayilmayan_puan = 8 if sayilmayan >= 10 else 5 if sayilmayan >= 5 else 2 if sayilmayan >= 2 else 0
    risk['detaylar']['sayilmayan_urun'] = {'puan': sayilmayan_puan, 'max': 8}
    risk['toplam_puan'] += sayilmayan_puan
    
    # 8. ANORMAL MİKTAR (10 puan)
    anormal_df = detect_anormal_miktar(df)
    anormal_count = len(anormal_df)
    anormal_puan = 10 if anormal_count >= 5 else 6 if anormal_count >= 3 else 3 if anormal_count >= 1 else 0
    risk['detaylar']['anormal_miktar'] = {'puan': anormal_puan, 'max': 10, 'count': anormal_count}
    risk['toplam_puan'] += anormal_puan
    
    # 9. TEKRAR MİKTAR (8 puan)
    tekrar_puan = 0
    if df_onceki is not None:
        tekrar_df = detect_tekrar_miktar(df, df_onceki)
        tekrar_count = len(tekrar_df)
        tekrar_puan = 8 if tekrar_count >= 10 else 5 if tekrar_count >= 5 else 2 if tekrar_count >= 2 else 0
    risk['detaylar']['tekrar_miktar'] = {'puan': tekrar_puan, 'max': 8}
    risk['toplam_puan'] += tekrar_puan
    
    # 10. YUVARLAK SAYI (8 puan)
    yuvarlak_df = detect_yuvarlak_sayi(df)
    yuvarlak_oran = len(yuvarlak_df) / max(len(df), 1)
    yuvarlak_puan = 8 if yuvarlak_oran > 0.35 else 5 if yuvarlak_oran > 0.20 else 2 if yuvarlak_oran > 0.10 else 0
    risk['detaylar']['yuvarlak_sayi'] = {'puan': yuvarlak_puan, 'max': 8, 'oran': yuvarlak_oran}
    risk['toplam_puan'] += yuvarlak_puan
    
    # Seviye belirle
    puan = risk['toplam_puan']
    if puan <= 25:
        risk['seviye'], risk['emoji'] = 'normal', '✅'
    elif puan <= 50:
        risk['seviye'], risk['emoji'] = 'dikkat', '⚠️'
    elif puan <= 75:
        risk['seviye'], risk['emoji'] = 'riskli', '🟠'
    else:
        risk['seviye'], risk['emoji'] = 'kritik', '🔴'
    
    return risk


# ==================== SAYIM DİSİPLİNİ ====================

def hesapla_sayim_disiplini(df, magaza_kodu=None, bs=None, sm=None):
    """Sayım disiplinini hesaplar (puan yok, gösterim)"""
    kategoriler = ['Meyve/Sebz', 'Et-Tavuk', 'Ekmek']
    kategori_col = 'Depolama Koşulu' if 'Depolama Koşulu' in df.columns else None
    if kategori_col is None:
        return None
    
    sonuc = {'kategoriler': {}, 'toplam_beklenen': 0, 'toplam_yapilan': 0}
    
    if magaza_kodu:
        df_mag = df[df['Mağaza Kodu'] == magaza_kodu] if 'Mağaza Kodu' in df.columns else df
        for kat in kategoriler:
            yapilan = 1 if kat in df_mag[kategori_col].values else 0
            sonuc['kategoriler'][kat] = {'beklenen': 1, 'yapilan': yapilan}
        sonuc['toplam_beklenen'] = 3
        sonuc['toplam_yapilan'] = sum(v['yapilan'] for v in sonuc['kategoriler'].values())
    
    elif bs:
        bs_magazalar = [k for k, v in SM_BS_MAGAZA.items() if v['bs'] == bs]
        magaza_sayisi = len(bs_magazalar)
        for kat in kategoriler:
            df_kat = df[df[kategori_col] == kat] if kategori_col in df.columns else pd.DataFrame()
            yapilan = df_kat['Mağaza Kodu'].nunique() if 'Mağaza Kodu' in df_kat.columns else 0
            sonuc['kategoriler'][kat] = {'beklenen': magaza_sayisi, 'yapilan': yapilan}
        sonuc['toplam_beklenen'] = magaza_sayisi * 3
        sonuc['toplam_yapilan'] = sum(v['yapilan'] for v in sonuc['kategoriler'].values())
        sonuc['magaza_sayisi'] = magaza_sayisi
    
    elif sm:
        sm_magazalar = [k for k, v in SM_BS_MAGAZA.items() if v['sm'] == sm]
        magaza_sayisi = len(sm_magazalar)
        for kat in kategoriler:
            df_kat = df[df[kategori_col] == kat] if kategori_col in df.columns else pd.DataFrame()
            yapilan = df_kat['Mağaza Kodu'].nunique() if 'Mağaza Kodu' in df_kat.columns else 0
            sonuc['kategoriler'][kat] = {'beklenen': magaza_sayisi, 'yapilan': yapilan}
        sonuc['toplam_beklenen'] = magaza_sayisi * 3
        sonuc['toplam_yapilan'] = sum(v['yapilan'] for v in sonuc['kategoriler'].values())
        sonuc['magaza_sayisi'] = magaza_sayisi
    
    sonuc['oran'] = (sonuc['toplam_yapilan'] / sonuc['toplam_beklenen'] * 100) if sonuc['toplam_beklenen'] > 0 else 0
    return sonuc


# ==================== BÖLGE ÖZETİ ====================

def hesapla_bolge_ozeti(df):
    """Bölge özeti - Top 10 mağaza, Top 5 ürün analizleri"""
    sonuc = {}
    
    # Mağaza adı kolonunu bul
    magaza_adi_col = 'Mağaza Adı' if 'Mağaza Adı' in df.columns else 'Mağaza Tanım' if 'Mağaza Tanım' in df.columns else None
    
    # Top 10 Riskli Mağaza
    if 'Mağaza Kodu' in df.columns:
        agg_dict = {'Fark Tutarı': 'sum', 'Fire Tutarı': 'sum', 'Satış Hasılatı': 'sum'}
        if magaza_adi_col:
            agg_dict[magaza_adi_col] = 'first'
        
        mag_ozet = df.groupby('Mağaza Kodu').agg(agg_dict).reset_index()
        
        # Kolon isimlerini standartlaştır
        if magaza_adi_col and magaza_adi_col in mag_ozet.columns:
            mag_ozet = mag_ozet.rename(columns={magaza_adi_col: 'Mağaza Adı'})
        else:
            mag_ozet['Mağaza Adı'] = mag_ozet['Mağaza Kodu']
        
        mag_ozet['Toplam Kayıp'] = abs(mag_ozet['Fark Tutarı']) + abs(mag_ozet['Fire Tutarı'])
        mag_ozet['Oran'] = np.where(mag_ozet['Satış Hasılatı'] > 0, 
                                     mag_ozet['Toplam Kayıp'] / mag_ozet['Satış Hasılatı'] * 100, 0)
        sonuc['top10_magaza'] = mag_ozet.nlargest(10, 'Oran')
    
    # Top 5 Açık Ürün
    if 'Malzeme Kodu' in df.columns and 'Fark Tutarı' in df.columns:
        urun_fark = df.groupby(['Malzeme Kodu', 'Malzeme Tanımı']).agg({
            'Fark Tutarı': 'sum', 'Mağaza Kodu': 'nunique'}).reset_index()
        urun_fark.columns = ['Kod', 'Tanım', 'Fark', 'Mağaza']
        urun_acik = urun_fark[urun_fark['Fark'] < 0].copy()
        urun_acik['Fark'] = abs(urun_acik['Fark'])
        sonuc['top5_acik'] = urun_acik.nlargest(5, 'Fark')
    
    # Top 5 Fire Ürün
    if 'Fire Tutarı' in df.columns:
        urun_fire = df.groupby(['Malzeme Kodu', 'Malzeme Tanımı']).agg({
            'Fire Tutarı': 'sum', 'Mağaza Kodu': 'nunique'}).reset_index()
        urun_fire.columns = ['Kod', 'Tanım', 'Fire', 'Mağaza']
        urun_fire_neg = urun_fire[urun_fire['Fire'] < 0].copy()
        urun_fire_neg['Fire'] = abs(urun_fire_neg['Fire'])
        sonuc['top5_fire'] = urun_fire_neg.nlargest(5, 'Fire')
    
    # Top 5 Oran (Filtreli)
    if 'Satış Hasılatı' in df.columns:
        urun_oran = df.groupby(['Malzeme Kodu', 'Malzeme Tanımı']).agg({
            'Fark Tutarı': 'sum', 'Fire Tutarı': 'sum', 
            'Satış Hasılatı': 'sum', 'Mağaza Kodu': 'nunique'}).reset_index()
        urun_oran = urun_oran[urun_oran['Satış Hasılatı'] >= MIN_SATIS_HASILATI]
        urun_oran['Kayıp'] = abs(urun_oran['Fark Tutarı']) + abs(urun_oran['Fire Tutarı'])
        urun_oran['Oran'] = urun_oran['Kayıp'] / urun_oran['Satış Hasılatı'] * 100
        urun_oran.columns = ['Kod', 'Tanım', 'Fark', 'Fire', 'Satış', 'Mağaza', 'Kayıp', 'Oran']
        sonuc['top5_oran'] = urun_oran.nlargest(5, 'Oran')[['Kod', 'Tanım', 'Oran', 'Satış', 'Mağaza']]
    
    return sonuc


# ==================== SUPABASE KAYIT ====================

def prepare_surekli_ozet_for_supabase(df, magaza_kodu, envanter_tarihi):
    """Supabase kayıt formatına çevirir"""
    kategori_ozet = hesapla_kategori_ozet(df)
    records = []
    for kategori, veriler in kategori_ozet.items():
        records.append({
            'magaza_kodu': str(magaza_kodu),
            'envanter_tarihi': str(envanter_tarihi),
            'kategori': kategori,
            'fark_tutari': float(veriler['fark']),
            'fire_tutari': float(veriler['fire']),
            'satis_hasilati': float(veriler['satis']),
            'oran': float(veriler['oran']),
            'urun_sayisi': int(veriler['urun_sayisi'])
        })
    return records



# ==================== MEDİAN BAZLI KARŞILAŞTIRMA ====================

def hesapla_urun_bolge_median(df_bolge):
    """
    Bölgedeki tüm mağazalar için ürün bazında median oran hesaplar
    Her ürün için: (|Fark| + |Fire|) / Satış × 100
    """
    if 'Malzeme Kodu' not in df_bolge.columns:
        return {}
    
    urun_oranlar = {}
    
    for kod in df_bolge['Malzeme Kodu'].unique():
        df_urun = df_bolge[df_bolge['Malzeme Kodu'] == kod]
        
        # Mağaza bazında oran hesapla
        magaza_oranlari = []
        for magaza in df_urun['Mağaza Kodu'].unique():
            df_mag = df_urun[df_urun['Mağaza Kodu'] == magaza]
            fark = abs(df_mag['Fark Tutarı'].sum()) if 'Fark Tutarı' in df_mag.columns else 0
            fire = abs(df_mag['Fire Tutarı'].sum()) if 'Fire Tutarı' in df_mag.columns else 0
            satis = df_mag['Satış Hasılatı'].sum() if 'Satış Hasılatı' in df_mag.columns else 0
            
            if satis > MIN_SATIS_HASILATI:  # Minimum filtre
                oran = (fark + fire) / satis * 100
                magaza_oranlari.append(oran)
        
        if magaza_oranlari:
            urun_oranlar[kod] = {
                'median': np.median(magaza_oranlari),
                'mean': np.mean(magaza_oranlari),
                'std': np.std(magaza_oranlari),
                'count': len(magaza_oranlari)
            }
    
    return urun_oranlar


def detect_median_sapma(df_magaza, urun_medianlar, carpan=1.5):
    """
    Mağazanın bölge medianından sapan ürünlerini tespit eder
    
    Args:
        df_magaza: Tek mağaza verisi
        urun_medianlar: hesapla_urun_bolge_median() çıktısı
        carpan: Sapma çarpanı (default 1.5x)
    
    Returns:
        List of dict: Sapan ürünler ve detayları
    """
    sapan_urunler = []
    
    if 'Malzeme Kodu' not in df_magaza.columns:
        return sapan_urunler
    
    for _, row in df_magaza.iterrows():
        kod = row['Malzeme Kodu']
        
        if kod not in urun_medianlar:
            continue
        
        median_data = urun_medianlar[kod]
        bolge_median = median_data['median']
        
        if bolge_median <= 0:
            continue
        
        # Mağaza oranı
        fark = abs(row.get('Fark Tutarı', 0) or 0)
        fire = abs(row.get('Fire Tutarı', 0) or 0)
        satis = row.get('Satış Hasılatı', 0) or 0
        
        if satis < MIN_SATIS_HASILATI:
            continue
        
        magaza_oran = (fark + fire) / satis * 100
        
        # Sapma kontrolü
        if magaza_oran > bolge_median * carpan:
            sapma_kati = magaza_oran / bolge_median if bolge_median > 0 else 0
            sapan_urunler.append({
                'Malzeme Kodu': kod,
                'Malzeme Tanımı': row.get('Malzeme Tanımı', ''),
                'Mağaza Oran': round(magaza_oran, 2),
                'Bölge Median': round(bolge_median, 2),
                'Sapma Katı': round(sapma_kati, 1),
                'Risk': '🔴' if sapma_kati > 3 else '🟠' if sapma_kati > 2 else '⚠️'
            })
    
    return sorted(sapan_urunler, key=lambda x: x['Sapma Katı'], reverse=True)


# ==================== SAYILMAYAN ÜRÜN ZAMAN BOYUTU ====================

def detect_sayilmayan_zaman(magaza_kodu, haftalik_veriler, segment='C', blokajli=None):
    """
    Ardışık haftalarda sayılmayan ürünleri tespit eder
    
    Args:
        magaza_kodu: Mağaza kodu
        haftalik_veriler: Dict of {hafta_no: DataFrame} veya List of DataFrames (tarih sıralı)
        segment: Mağaza segmenti
        blokajli: Blokajlı ürünler dict
    
    Returns:
        Dict: {urun_kodu: {'hafta_sayisi': int, 'seviye': str, 'tanim': str}}
    """
    sayilmasi_gereken = set(get_sayilmasi_gereken_urunler(magaza_kodu, segment, blokajli))
    
    if not sayilmasi_gereken:
        return {}
    
    # Haftalık sayılan ürünleri takip et
    hafta_sayilan = {}  # {hafta_idx: set(urun_kodlari)}
    
    if isinstance(haftalik_veriler, dict):
        for hafta, df in sorted(haftalik_veriler.items()):
            if 'Malzeme Kodu' in df.columns:
                hafta_sayilan[hafta] = set(str(k) for k in df['Malzeme Kodu'].unique())
    elif isinstance(haftalik_veriler, list):
        for i, df in enumerate(haftalik_veriler):
            if 'Malzeme Kodu' in df.columns:
                hafta_sayilan[i] = set(str(k) for k in df['Malzeme Kodu'].unique())
    
    if not hafta_sayilan:
        return {}
    
    # Her ürün için ardışık sayılmama sayısı
    urun_sayilmama = {}
    
    for urun in sayilmasi_gereken:
        ardisik = 0
        max_ardisik = 0
        
        for hafta in sorted(hafta_sayilan.keys(), reverse=True):  # En yeniden eskiye
            if urun not in hafta_sayilan[hafta]:
                ardisik += 1
                max_ardisik = max(max_ardisik, ardisik)
            else:
                break  # Ardışıklık bozuldu
        
        if ardisik >= 2:
            seviye = 'kritik' if ardisik >= 3 else 'uyari'
            urun_sayilmama[urun] = {
                'hafta_sayisi': ardisik,
                'seviye': seviye,
                'emoji': '🔴' if seviye == 'kritik' else '⚠️',
                'tanim': SEGMENT_URUN.get(urun, {}).get('tanim', urun)
            }
    
    return urun_sayilmama


# ==================== SM/BS RİSK PUANLAMASI ====================

def hesapla_sm_risk_skoru(df_bolge, sm_adi, df_onceki=None, blokajli=None):
    """
    SM'in altındaki tüm mağazaların risk ortalamasını hesaplar
    
    Returns:
        dict: SM risk özeti
    """
    sm_magazalar = get_magazalar_by_sm(sm_adi)
    sm_kodlari = list(sm_magazalar.keys())
    
    # Bu SM'e ait mağazaları filtrele
    df_sm = df_bolge[df_bolge['Mağaza Kodu'].astype(str).isin(sm_kodlari)]
    
    if df_sm.empty:
        return None
    
    # Bölge ortalaması hesapla
    bolge_kat_ozet = hesapla_kategori_ozet(df_bolge)
    bolge_oran = sum(k.get('oran', 0) for k in bolge_kat_ozet.values()) / max(len(bolge_kat_ozet), 1)
    
    # Her mağaza için risk skoru hesapla
    magaza_riskleri = []
    magaza_skorlari = []
    
    for magaza in df_sm['Mağaza Kodu'].unique():
        df_mag = df_sm[df_sm['Mağaza Kodu'] == magaza]
        df_mag_onceki = df_onceki[df_onceki['Mağaza Kodu'] == magaza] if df_onceki is not None else None
        
        risk = hesapla_surekli_risk_skoru(df_mag, df_mag_onceki, bolge_oran, blokajli)
        
        magaza_riskleri.append({
            'magaza': magaza,
            'skor': risk['toplam_puan'],
            'seviye': risk['seviye'],
            'emoji': risk['emoji']
        })
        magaza_skorlari.append(risk['toplam_puan'])
    
    # SM özeti
    return {
        'sm': sm_adi,
        'magaza_sayisi': len(magaza_riskleri),
        'ortalama_skor': np.mean(magaza_skorlari) if magaza_skorlari else 0,
        'median_skor': np.median(magaza_skorlari) if magaza_skorlari else 0,
        'max_skor': max(magaza_skorlari) if magaza_skorlari else 0,
        'min_skor': min(magaza_skorlari) if magaza_skorlari else 0,
        'kritik_sayisi': sum(1 for r in magaza_riskleri if r['seviye'] == 'kritik'),
        'riskli_sayisi': sum(1 for r in magaza_riskleri if r['seviye'] == 'riskli'),
        'dikkat_sayisi': sum(1 for r in magaza_riskleri if r['seviye'] == 'dikkat'),
        'normal_sayisi': sum(1 for r in magaza_riskleri if r['seviye'] == 'normal'),
        'magazalar': sorted(magaza_riskleri, key=lambda x: x['skor'], reverse=True)
    }


def hesapla_bs_risk_skoru(df_bolge, bs_adi, df_onceki=None, blokajli=None):
    """
    BS'in altındaki tüm mağazaların risk ortalamasını hesaplar
    
    Returns:
        dict: BS risk özeti
    """
    bs_magazalar = get_magazalar_by_bs(bs_adi)
    bs_kodlari = list(bs_magazalar.keys())
    
    df_bs = df_bolge[df_bolge['Mağaza Kodu'].astype(str).isin(bs_kodlari)]
    
    if df_bs.empty:
        return None
    
    # Bölge ortalaması
    bolge_kat_ozet = hesapla_kategori_ozet(df_bolge)
    bolge_oran = sum(k.get('oran', 0) for k in bolge_kat_ozet.values()) / max(len(bolge_kat_ozet), 1)
    
    # Her mağaza için risk
    magaza_riskleri = []
    magaza_skorlari = []
    
    for magaza in df_bs['Mağaza Kodu'].unique():
        df_mag = df_bs[df_bs['Mağaza Kodu'] == magaza]
        df_mag_onceki = df_onceki[df_onceki['Mağaza Kodu'] == magaza] if df_onceki is not None else None
        
        risk = hesapla_surekli_risk_skoru(df_mag, df_mag_onceki, bolge_oran, blokajli)
        
        magaza_riskleri.append({
            'magaza': magaza,
            'skor': risk['toplam_puan'],
            'seviye': risk['seviye'],
            'emoji': risk['emoji']
        })
        magaza_skorlari.append(risk['toplam_puan'])
    
    return {
        'bs': bs_adi,
        'magaza_sayisi': len(magaza_riskleri),
        'ortalama_skor': np.mean(magaza_skorlari) if magaza_skorlari else 0,
        'median_skor': np.median(magaza_skorlari) if magaza_skorlari else 0,
        'kritik_sayisi': sum(1 for r in magaza_riskleri if r['seviye'] == 'kritik'),
        'riskli_sayisi': sum(1 for r in magaza_riskleri if r['seviye'] == 'riskli'),
        'magazalar': sorted(magaza_riskleri, key=lambda x: x['skor'], reverse=True)
    }


def hesapla_tum_sm_risk(df_bolge, df_onceki=None, blokajli=None):
    """Tüm SM'lerin risk skorlarını hesaplar"""
    sm_list = get_sm_list()
    sonuc = []
    
    for sm in sm_list:
        sm_risk = hesapla_sm_risk_skoru(df_bolge, sm, df_onceki, blokajli)
        if sm_risk:
            sonuc.append(sm_risk)
    
    return sorted(sonuc, key=lambda x: x['ortalama_skor'], reverse=True)


def hesapla_tum_bs_risk(df_bolge, df_onceki=None, blokajli=None):
    """Tüm BS'lerin risk skorlarını hesaplar"""
    bs_list = get_bs_list()
    sonuc = []
    
    for bs in bs_list:
        bs_risk = hesapla_bs_risk_skoru(df_bolge, bs, df_onceki, blokajli)
        if bs_risk:
            sonuc.append(bs_risk)
    
    return sorted(sonuc, key=lambda x: x['ortalama_skor'], reverse=True)

