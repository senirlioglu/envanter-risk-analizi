# VIEW Timeout Sorunu - Veritabanı Optimizasyonu

## 🔴 Sorun

GM Özet ve SM Özet ekranlarında `v_magaza_ozet` VIEW'inden veri çekilirken PostgreSQL timeout hatası (error code: 57014) alınıyor.

## 🔍 KÖK NEDEN BULUNDU! ✅

**Veri Hacmi:**
- 202512 dönemi: **503,460 satır** (yarım milyon!)
- VIEW çıktısı: 163 satır (GROUP BY ile aggregate ediliyor)

**VIEW Her Sorguda Şunları Yapıyor:**

1. ❌ **500K+ satırda text transformation**:
   ```sql
   translate(upper(mal_grubu_tanimi), 'İÜÖÇŞĞıüöçşğ', 'IUOCSGiuocsg') ~~ '%SIGARA%'
   ```
   Bu işlem HER SATIR için 2 kez yapılıyor (SIGARA ve TUTUN kontrolü)

2. ❌ **LEFT JOIN kasa_malzeme_list** - 500K satır için JOIN

3. ❌ **6-7 farklı CASE WHEN** - Her satır için kompleks koşullar:
   - ic_hirsizlik (100 TL üzeri kontrolü)
   - kronik_acik
   - kronik_fire
   - sigara_net
   - kasa hesaplamaları

4. ✅ **GROUP BY** - 500K satırı 163'e indiriyor

**TIMEOUT SEBEBI**: Text transformation ve CASE WHEN'ler 500K satırda çok yavaş!

## ✅ Yapılması Gerekenler

### ⚠️ GÜNCELLEME: INDEX'LER ZATEN VAR!

INDEX eklerken `ERROR: relation "idx_envanter_donemi" already exists` hatası aldıysanız, **INDEX'ler zaten var** demektir.

**Asıl sorun**: VIEW 500K+ satırda text transformation ve CASE WHEN yapıyor.

### 🚀 ÇÖZÜM 1: MATERIALIZED VIEW (EN HIZLI - ÖNERİLEN)

VIEW'i MATERIALIZED VIEW'e çevir ve sonuçları cache'le:

```sql
-- 1. Önce mevcut VIEW'i yedekle
CREATE VIEW v_magaza_ozet_backup AS
SELECT * FROM v_magaza_ozet LIMIT 0;  -- Sadece yapı

-- 2. VIEW'i sil ve MATERIALIZED olarak yeniden oluştur
DROP VIEW v_magaza_ozet;

CREATE MATERIALIZED VIEW v_magaza_ozet AS
WITH base AS (
  -- (Mevcut VIEW tanımını buraya kopyala)
  -- ... tüm VIEW kodu ...
)
SELECT
  magaza_kodu,
  magaza_tanim,
  satis_muduru,
  bolge_sorumlusu,
  envanter_donemi,
  max(envanter_tarihi) AS envanter_tarihi,
  -- ... diğer kolonlar ...
FROM base
GROUP BY magaza_kodu, magaza_tanim, satis_muduru, bolge_sorumlusu, envanter_donemi;

-- 3. Index ekle (MATERIALIZED VIEW'de index kullanılabilir!)
CREATE INDEX idx_mv_magaza_ozet_donem ON v_magaza_ozet(envanter_donemi);
CREATE INDEX idx_mv_magaza_ozet_sm ON v_magaza_ozet(satis_muduru);
CREATE INDEX idx_mv_magaza_ozet_tarih ON v_magaza_ozet(envanter_tarihi);
CREATE INDEX idx_mv_magaza_ozet_composite ON v_magaza_ozet(envanter_donemi, satis_muduru);

-- 4. İlk refresh
REFRESH MATERIALIZED VIEW v_magaza_ozet;
```

**Avantajları:**
- ✅ Sorgu anında çalışır (milisaniyeler)
- ✅ Timeout olmaz
- ✅ INDEX kullanabilir
- ✅ Uygulama kodu değişmez

**Dezavantajı:**
- ❌ Yeni veri yüklendiğinde manuel REFRESH gerekir

**REFRESH için:**
```sql
-- Her veri yüklemesinden sonra çalıştırın:
REFRESH MATERIALIZED VIEW v_magaza_ozet;

-- VEYA concurrent refresh (tabloya lock atmaz):
REFRESH MATERIALIZED VIEW CONCURRENTLY v_magaza_ozet;
-- (Bunun için UNIQUE INDEX gerekir)
```

### 🔧 ÇÖZÜM 2: Base Tabloya Computed Kolonlar Ekle (UZUN VADE)

Text transformation'ları her sorguda yapmak yerine, base tabloda sakla:

```sql
-- envanter_veri tablosuna yeni kolonlar ekle
ALTER TABLE envanter_veri
  ADD COLUMN IF NOT EXISTS is_sigara BOOLEAN,
  ADD COLUMN IF NOT EXISTS is_kasa BOOLEAN;

-- Mevcut verileri güncelle
UPDATE envanter_veri SET
  is_sigara = (
    translate(upper(mal_grubu_tanimi), 'İÜÖÇŞĞıüöçşğ', 'IUOCSGiuocsg') ~~ '%SIGARA%'
    OR translate(upper(mal_grubu_tanimi), 'İÜÖÇŞĞıüöçşğ', 'IUOCSGiuocsg') ~~ '%TUTUN%'
  ),
  is_kasa = EXISTS(
    SELECT 1 FROM kasa_malzeme_list k WHERE k.malzeme_kodu = envanter_veri.malzeme_kodu
  );

-- INDEX ekle
CREATE INDEX idx_envanter_is_sigara ON envanter_veri(is_sigara) WHERE is_sigara = true;
CREATE INDEX idx_envanter_is_kasa ON envanter_veri(is_kasa) WHERE is_kasa = true;

-- VIEW'i güncelle (text transformation yerine is_sigara kolonunu kullan)
-- CTE'deki LEFT JOIN ve text transformation'ları kaldır
```

**Avantajları:**
- ✅ VIEW çok daha hızlı olur
- ✅ Text transformation sadece 1 kez yapılır

**Dezavantajı:**
- ❌ Uygulama kodu değişikliği gerekebilir (veri yükleme sırasında is_sigara/is_kasa set edilmeli)

### ⚡ ÇÖZÜM 3: Statement Timeout Artır (GEÇİCİ)

En hızlı geçici çözüm:

```sql
-- Database seviyesinde
ALTER DATABASE postgres SET statement_timeout = '120s';

-- VEYA sadece bu session için
SET statement_timeout = '120s';
```

**Not**: Bu sadece semptomu gizler, asıl sorunu çözmez.

### 1. VIEW Tanımını ve EXPLAIN PLAN'i Kontrol Et

VIEW'in nasıl çalıştığını anlamak için:

```sql
-- VIEW tanımını gör
SELECT definition FROM pg_views WHERE viewname = 'v_magaza_ozet';

-- Query plan analizi - VIEW'in nasıl execute edildiğini gör
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT * FROM v_magaza_ozet
WHERE envanter_donemi = '202512'
LIMIT 100;
```

**Aranacak problemler:**
- ❌ "Seq Scan" (Sequential Scan) - INDEX kullanılmıyor demek
- ❌ Yüksek "cost" değerleri (örn: cost=10000..50000)
- ❌ "Hash Join" veya "Nested Loop" çok uzun sürüyorsa
- ❌ "execution time" > 10 saniye

### 2. Veri Hacmini Kontrol Et

202512 döneminde kaç satır var?

```sql
-- Toplam satır sayısı
SELECT COUNT(*) FROM envanter_veri WHERE envanter_donemi = '202512';

-- VIEW'den kaç satır dönüyor?
SELECT COUNT(*) FROM v_magaza_ozet WHERE envanter_donemi = '202512';

-- Her dönemdeki satır sayısı
SELECT envanter_donemi, COUNT(*) as satir_sayisi
FROM envanter_veri
GROUP BY envanter_donemi
ORDER BY envanter_donemi DESC;
```

**Eğer 202512'de çok fazla satır varsa (>50,000):** VIEW aggregation yaparken çok zaman alıyor olabilir.

### 3. MATERIALIZED VIEW Kullan

VIEW yerine MATERIALIZED VIEW kullanarak cache'lenmiş sonuçlar sağla:

```sql
-- Önce VIEW'i materialized yap
DROP VIEW IF EXISTS v_magaza_ozet;

CREATE MATERIALIZED VIEW v_magaza_ozet AS
-- (mevcut VIEW tanımı buraya)
;

-- Index ekle
CREATE INDEX idx_mv_magaza_ozet_donem ON v_magaza_ozet(envanter_donemi);
CREATE INDEX idx_mv_magaza_ozet_sm ON v_magaza_ozet(satis_muduru);
CREATE INDEX idx_mv_magaza_ozet_tarih ON v_magaza_ozet(envanter_tarihi);

-- Veri yüklendiğinde refresh edilmeli:
REFRESH MATERIALIZED VIEW v_magaza_ozet;
```

### 4. Statement Timeout Artır

Supabase admin panelinde veya SQL ile:

```sql
-- Session bazında
SET statement_timeout = '30s';  -- Varsayılan genelde 15s

-- Veya database seviyesinde (kalıcı)
ALTER DATABASE your_database SET statement_timeout = '30s';
```

### 5. Query Plan Analizi

VIEW'in nasıl çalıştığını analiz et:

```sql
EXPLAIN ANALYZE
SELECT * FROM v_magaza_ozet
WHERE envanter_donemi = '202512'
LIMIT 100;
```

Sonuçlara bakarak:
- "Seq Scan" varsa INDEX ekle
- "Hash Join" veya "Merge Join" çok uzun sürüyorsa query'yi optimize et

## 📊 Uygulama Tarafında Yapılan Optimizasyonlar

### Kod İyileştirmeleri (app.py):

1. ✅ **SELECT * yerine spesifik kolonlar** - Gereksiz kolonlar çekilmiyor
2. ✅ **LIMIT 5000** eklendi - Çok fazla veri timeout olmasın diye
3. ✅ **ORDER BY** eklendi - Index kullanımı için
4. ✅ **Retry mekanizması** - 3 kez yeniden dene
5. ✅ **Tarih filtresi** - Kullanıcı tarih aralığı ile veriyi daraltabilir

### Kullanıcı Tarafında:

1. **Daha kısa dönem seç** - Tek seferde çok fazla dönem seçme
2. **Tarih aralığı kullan** - "📆 Tarih Aralığı Filtresi" expander'ını kullan
3. **Cache'i temizle** - Sayfayı yenile (F5)

## 🎯 Öncelik Sırası (KÖK NEDEN BULUNDU!)

**Sorun**: VIEW 503,460 satırda text transformation ve CASE WHEN yapıyor.

### Hızlı Çözüm (Bu Hafta):
1. **ŞİMDİ** → statement_timeout artır (`ALTER DATABASE ... SET statement_timeout = '120s'`) - 5 dakika
2. **BUGÜN** → MATERIALIZED VIEW'e geç - 30 dakika
   - DROP VIEW → CREATE MATERIALIZED VIEW
   - INDEX ekle
   - REFRESH MATERIALIZED VIEW
3. **BUGÜN** → Excel yükleme sonrası REFRESH ekle - 10 dakika

### Orta Vade (Bu Ay):
4. **BU HAFTA** → envanter_veri'ye `is_sigara` ve `is_kasa` kolonları ekle
5. **BU HAFTA** → VIEW'i optimize et (text transformation'ları kaldır)

### Uzun Vade:
6. **İLERİDE** → Veri retention policy (eski dönemleri archive et)

## 📝 Test

INDEX ekledikten sonra test et:

```sql
-- Aynı sorguyu çalıştır
SELECT * FROM v_magaza_ozet
WHERE envanter_donemi IN ('202512')
LIMIT 5000;

-- Süreyi ölç
\timing on
```

Eğer hala yavaşsa query plan'a bak ve VIEW tanımını optimize et.
