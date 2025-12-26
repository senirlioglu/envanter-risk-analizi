# VIEW Timeout Sorunu - Veritabanı Optimizasyonu

## 🔴 Sorun

GM Özet ve SM Özet ekranlarında `v_magaza_ozet` VIEW'inden veri çekilirken PostgreSQL timeout hatası (error code: 57014) alınıyor.

## 🔍 Kök Neden

VIEW sorgusu çok yavaş çalışıyor. Muhtemel sebepler:

1. **INDEX eksikliği** - VIEW'de sık kullanılan kolonlarda index yok
2. **Kompleks aggregation** - VIEW çok fazla JOIN ve GROUP BY içeriyor
3. **Veri hacmi** - Seçilen dönemde beklenenden çok fazla veri var
4. **Supabase timeout ayarı** - Statement timeout çok düşük ayarlanmış

## ✅ Yapılması Gerekenler

### 1. VIEW Tanımını Kontrol Et

Supabase'de `v_magaza_ozet` VIEW'inin tanımını incele:

```sql
-- VIEW tanımını görmek için:
SELECT definition FROM pg_views WHERE viewname = 'v_magaza_ozet';
```

### 2. INDEX Ekle

Sık kullanılan filter kolonlarına index ekle:

```sql
-- envanter_veri tablosuna indexler ekle (eğer yoksa)
CREATE INDEX IF NOT EXISTS idx_envanter_donemi ON envanter_veri(envanter_donemi);
CREATE INDEX IF NOT EXISTS idx_satis_muduru ON envanter_veri(satis_muduru);
CREATE INDEX IF NOT EXISTS idx_envanter_tarihi ON envanter_veri(envanter_tarihi);
CREATE INDEX IF NOT EXISTS idx_magaza_kodu ON envanter_veri(magaza_kodu);

-- Composite index - dönem ve tarih birlikte kullanıldığı için
CREATE INDEX IF NOT EXISTS idx_donem_tarih ON envanter_veri(envanter_donemi, envanter_tarihi);
```

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

## 🎯 Öncelik Sırası

1. **HEMEN** → INDEX ekle (envanter_donemi, satis_muduru, envanter_tarihi)
2. **KISA VADE** → statement_timeout artır (15s → 30s)
3. **ORTA VADE** → MATERIALIZED VIEW'e geç
4. **UZUN VADE** → VIEW tanımını optimize et, gereksiz JOIN'leri kaldır

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
