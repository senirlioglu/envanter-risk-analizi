-- ========================================
-- MATERIALIZED VIEW MIGRATION
-- v_magaza_ozet VIEW'ini MATERIALIZED VIEW'e çevir
-- ========================================

-- STEP 1: Timeout artır (geçici olarak, migration için)
SET statement_timeout = '300s';

-- STEP 2: Mevcut VIEW'i sil
DROP VIEW IF EXISTS v_magaza_ozet;

-- STEP 3: MATERIALIZED VIEW oluştur
CREATE MATERIALIZED VIEW v_magaza_ozet AS
WITH base AS (
    SELECT
        e.id,
        e.magaza_kodu,
        e.magaza_tanim,
        e.satis_muduru,
        e.bolge_sorumlusu,
        e.depolama_kosulu_grubu,
        e.depolama_kosulu,
        e.envanter_donemi,
        e.envanter_tarihi,
        e.envanter_baslangic_tarihi,
        e.urun_grubu_kodu,
        e.urun_grubu_tanimi,
        e.mal_grubu_kodu,
        e.mal_grubu_tanimi,
        e.malzeme_kodu,
        e.malzeme_tanimi,
        e.satis_fiyati,
        e.sayim_miktari,
        e.sayim_tutari,
        e.kaydi_miktar,
        e.kaydi_tutar,
        e.fark_miktari,
        e.fark_tutari,
        e.kismi_envanter_miktari,
        e.kismi_envanter_tutari,
        e.fire_miktari,
        e.fire_tutari,
        e.onceki_fark_miktari,
        e.onceki_fark_tutari,
        e.onceki_fire_miktari,
        e.onceki_fire_tutari,
        e.satis_miktari,
        e.satis_hasilati,
        e.iade_miktari,
        e.iade_tutari,
        e.iptal_fisteki_miktar,
        e.iptal_fis_tutari,
        e.iptal_gp_miktari,
        e.iptal_gp_tutari,
        e.iptal_satir_miktari,
        e.iptal_satir_tutari,
        e.created_at,
        (k.malzeme_kodu IS NOT NULL) AS is_kasa,
        ((translate(upper((e.mal_grubu_tanimi)::text), 'İÜÖÇŞĞıüöçşğ'::text, 'IUOCSGiuocsg'::text) ~~ '%SIGARA%'::text)
         OR (translate(upper((e.mal_grubu_tanimi)::text), 'İÜÖÇŞĞıüöçşğ'::text, 'IUOCSGiuocsg'::text) ~~ '%TUTUN%'::text)) AS is_sigara
    FROM envanter_veri e
    LEFT JOIN kasa_malzeme_list k ON k.malzeme_kodu = e.malzeme_kodu::text
)
SELECT
    magaza_kodu,
    magaza_tanim,
    satis_muduru,
    bolge_sorumlusu,
    envanter_donemi,
    max(envanter_tarihi) AS envanter_tarihi,
    min(envanter_baslangic_tarihi) AS envanter_baslangic_tarihi,
    sum(fark_tutari) AS fark_tutari,
    sum(kismi_envanter_tutari) AS kismi_tutari,
    sum(fire_tutari) AS fire_tutari,
    sum(satis_hasilati) AS satis,
    sum(fark_miktari) AS fark_miktari,
    sum(kismi_envanter_miktari) AS kismi_miktari,
    sum(onceki_fark_miktari) AS onceki_fark_miktari,
    sum(
        CASE
            WHEN is_sigara THEN ((fark_miktari + COALESCE(kismi_envanter_miktari, 0::numeric)) + COALESCE(onceki_fark_miktari, 0::numeric))
            ELSE 0::numeric
        END) AS sigara_net,
    count(
        CASE
            WHEN ((satis_fiyati >= 100::numeric) AND (fark_miktari < 0::numeric)) THEN 1
            ELSE NULL::integer
        END) AS ic_hirsizlik,
    count(
        CASE
            WHEN ((onceki_fark_miktari < 0::numeric) AND (fark_miktari < 0::numeric)) THEN 1
            ELSE NULL::integer
        END) AS kronik_acik,
    count(
        CASE
            WHEN ((onceki_fire_miktari < 0::numeric) AND (fire_miktari < 0::numeric)) THEN 1
            ELSE NULL::integer
        END) AS kronik_fire,
    sum(
        CASE
            WHEN is_kasa THEN (fark_miktari + COALESCE(kismi_envanter_miktari, 0::numeric))
            ELSE 0::numeric
        END) AS kasa_adet,
    sum(
        CASE
            WHEN is_kasa THEN (fark_tutari + COALESCE(kismi_envanter_tutari, 0::numeric))
            ELSE 0::numeric
        END) AS kasa_tutar
FROM base
GROUP BY magaza_kodu, magaza_tanim, satis_muduru, bolge_sorumlusu, envanter_donemi;

-- STEP 4: INDEX'leri oluştur
CREATE INDEX idx_mv_magaza_ozet_donem ON v_magaza_ozet(envanter_donemi);
CREATE INDEX idx_mv_magaza_ozet_sm ON v_magaza_ozet(satis_muduru);
CREATE INDEX idx_mv_magaza_ozet_tarih ON v_magaza_ozet(envanter_tarihi);
CREATE INDEX idx_mv_magaza_ozet_composite ON v_magaza_ozet(envanter_donemi, satis_muduru);

-- STEP 5: İlk REFRESH (bu biraz zaman alacak - 1-2 dakika)
REFRESH MATERIALIZED VIEW v_magaza_ozet;

-- STEP 6: Statement timeout'u kalıcı olarak artır
ALTER DATABASE postgres SET statement_timeout = '120s';

-- STEP 7: RPC fonksiyonu oluştur (Python'dan çağrılacak)
-- Bu fonksiyon Excel yükleme sonrası otomatik refresh için
CREATE OR REPLACE FUNCTION refresh_magaza_ozet()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW v_magaza_ozet;
END;
$$;

-- Fonksiyona public erişimi ver (Supabase anon key ile çağrılabilsin)
GRANT EXECUTE ON FUNCTION refresh_magaza_ozet() TO anon, authenticated;

-- ========================================
-- TAMAMLANDI!
-- ========================================

-- Test et:
SELECT COUNT(*) FROM v_magaza_ozet WHERE envanter_donemi = '202512';
-- 163 satır dönmeli ve HIZLI olmalı (< 1 saniye)

-- ========================================
-- ARTIK MANUEL REFRESH GEREKMEZ! ✅
-- ========================================
-- Python uygulaması Excel yükleme sonrası otomatik olarak
-- refresh_magaza_ozet() fonksiyonunu çağıracak.
--
-- Eğer manuel refresh gerekirse:
-- SELECT refresh_magaza_ozet();
-- VEYA
-- REFRESH MATERIALIZED VIEW v_magaza_ozet;
