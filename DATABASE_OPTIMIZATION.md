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

### ⚠️ GÜNCELLEME: INDEX'LER ZATEN VAR!

INDEX eklerken `ERROR: relation "idx_envanter_donemi" already exists` hatası aldıysanız, **INDEX'ler zaten var** demektir. Bu durumda sorun başka.

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

## 🎯 Öncelik Sırası (GÜNCELLEME: INDEX'LER ZATEN VAR)

1. **HEMEN** → Veri hacmini kontrol et (`SELECT COUNT(*)` sorguları)
2. **HEMEN** → EXPLAIN PLAN ile VIEW'in nasıl çalıştığını gör
3. **HEMEN** → statement_timeout artır (15s → 30s veya 60s)
4. **KISA VADE** → VIEW tanımını gör ve optimize edilip edilemeyeceğini kontrol et
5. **ORTA VADE** → MATERIALIZED VIEW'e geç (en etkili çözüm)
6. **UZUN VADE** → VIEW tanımını yeniden yaz, gereksiz JOIN/aggregation kaldır

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
