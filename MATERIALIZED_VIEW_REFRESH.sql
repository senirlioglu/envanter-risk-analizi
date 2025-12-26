-- ========================================
-- MATERIALIZED VIEW ZATEN VAR! ✅
-- Sadece eksik adımları tamamla
-- ========================================

-- STEP 1: Timeout artır (geçici, bu session için)
SET statement_timeout = '300s';

-- STEP 2: INDEX'leri ekle (eğer yoksa)
-- Hata verirse sorun değil, zaten var demektir
CREATE INDEX IF NOT EXISTS idx_mv_magaza_ozet_donem ON v_magaza_ozet(envanter_donemi);
CREATE INDEX IF NOT EXISTS idx_mv_magaza_ozet_sm ON v_magaza_ozet(satis_muduru);
CREATE INDEX IF NOT EXISTS idx_mv_magaza_ozet_tarih ON v_magaza_ozet(envanter_tarihi);
CREATE INDEX IF NOT EXISTS idx_mv_magaza_ozet_composite ON v_magaza_ozet(envanter_donemi, satis_muduru);

-- STEP 3: REFRESH yap (1-2 dakika sürebilir)
REFRESH MATERIALIZED VIEW v_magaza_ozet;

-- STEP 4: Statement timeout'u kalıcı olarak artır
ALTER DATABASE postgres SET statement_timeout = '120s';

-- STEP 5: RPC fonksiyonu oluştur (Python'dan otomatik refresh için)
CREATE OR REPLACE FUNCTION refresh_magaza_ozet()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW v_magaza_ozet;
END;
$$;

-- STEP 6: Fonksiyona public erişim
GRANT EXECUTE ON FUNCTION refresh_magaza_ozet() TO anon, authenticated;

-- ========================================
-- TAMAMLANDI! ✅
-- ========================================

-- Test et:
SELECT COUNT(*) FROM v_magaza_ozet WHERE envanter_donemi = '202512';
-- 163 satır dönmeli ve HIZLI olmalı (< 1 saniye)

-- ========================================
-- ARTIK OTOMATIK REFRESH VAR! 🚀
-- ========================================
-- Excel yükleme sonrası Python otomatik refresh yapacak
-- Manuel refresh gerekirse: SELECT refresh_magaza_ozet();
