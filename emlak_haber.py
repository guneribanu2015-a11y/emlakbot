import streamlit as st
import feedparser
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# KAYNAK TANIMI
# ─────────────────────────────────────────────

KAYNAKLAR = [
    # ── Türkiye ──────────────────────────────
    {"kategori": "🇹🇷 Türkiye", "etiket": "Emlak Haberi",  "sorgu": "site:emlakhaberi.com"},
    {"kategori": "🇹🇷 Türkiye", "etiket": "Emlak Kulisi",  "sorgu": "site:emlakkulisi.com"},
    {"kategori": "🇹🇷 Türkiye", "etiket": "TÜİK",          "sorgu": "TÜİK konut satış istatistik"},
    {"kategori": "🇹🇷 Türkiye", "etiket": "Emlakjet",      "sorgu": "site:emlakjet.com/haber"},
    # ── Avrupa ───────────────────────────────
    {"kategori": "🇪🇺 Avrupa",  "etiket": "Property Forum",   "sorgu": "site:property-forum.eu"},
    {"kategori": "🇪🇺 Avrupa",  "etiket": "EuropaProperty",   "sorgu": "site:europaproperty.com"},
    # ── Asya ─────────────────────────────────
    {"kategori": "🌏 Asya",     "etiket": "Mingtiandi",       "sorgu": "site:mingtiandi.com"},
    {"kategori": "🌏 Asya",     "etiket": "Real Estate Asia",  "sorgu": "site:realestateasia.com"},
    # ── Amerika ──────────────────────────────
    {"kategori": "🇺🇸 Amerika", "etiket": "The Real Deal",    "sorgu": "site:therealdeal.com"},
    {"kategori": "🇺🇸 Amerika", "etiket": "Inman",            "sorgu": "site:inman.com"},
]

KATEGORI_LISTESI = ["Tümü", "🇹🇷 Türkiye", "🇪🇺 Avrupa", "🌏 Asya", "🇺🇸 Amerika"]

KATEGORI_RENK = {
    "🇹🇷 Türkiye": "🟢",
    "🇪🇺 Avrupa":  "🔵",
    "🌏 Asya":     "🟡",
    "🇺🇸 Amerika": "🟠",
}

# ─────────────────────────────────────────────
# VERİ ÇEKME
# ─────────────────────────────────────────────

def google_news_url(sorgu: str, dil: str = "tr", bolge: str = "TR") -> str:
    """Google News RSS URL'i oluşturur."""
    import urllib.parse
    params = urllib.parse.urlencode({
        "q": sorgu,
        "hl": dil,
        "gl": bolge,
        "ceid": f"{bolge}:{dil}",
    })
    return f"https://news.google.com/rss/search?{params}"


@st.cache_data(ttl=1800)
def haber_cek(sorgu: str, etiket: str, kategori: str, max_haber: int = 5) -> list[dict]:
    url = google_news_url(sorgu)
    try:
        feed = feedparser.parse(url)
        haberler = []
        simdi = datetime.now()
        yedi_gun_once = simdi - timedelta(days=7)
        for entry in feed.entries[:max_haber*3]:
            if not hasattr(entry, "published_parsed") or not entry.published_parsed:
                continue
            try:
                haber_tarihi = datetime(*entry.published_parsed[:6])
                if haber_tarihi < yedi_gun_once:
                    continue
                tarih = haber_tarihi.strftime("%d %b %Y")
            except:
                continue
            baslik = entry.get("title", "")
            if not baslik:
                continue
            haberler.append({
                "baslik": baslik,
                "link":   entry.get("link", "#"),
                "tarih":  tarih,
                "kaynak": etiket,
                "kategori": kategori,
            })
            if len(haberler) >= max_haber:
                break
        return haberler
    except Exception:
        return []

@st.cache_data(ttl=1800)
def tum_haberleri_cek(max_haber_per_kaynak: int = 5) -> list[dict]:
    """Tüm kaynaklardan haberleri çeker ve birleştirir."""
    sonuc = []
    for k in KAYNAKLAR:
        haberler = haber_cek(k["sorgu"], k["etiket"], k["kategori"], max_haber_per_kaynak)
        sonuc.extend(haberler)
    return sonuc

# ─────────────────────────────────────────────
# GÖRÜNTÜLEME
# ─────────────────────────────────────────────

def haber_karti(haber: dict):
    """Tek bir haberi kart olarak gösterir."""
    renk = KATEGORI_RENK.get(haber["kategori"], "⚪")
    with st.container():
        col1, col2 = st.columns([8, 2])
        with col1:
            st.markdown(
                f"**[{haber['baslik']}]({haber['link']})**",
                unsafe_allow_html=False,
            )
        with col2:
            st.caption(haber.get("tarih", ""))
        st.caption(f"{renk} {haber['kaynak']}  ·  {haber['kategori']}")
        st.divider()


def haber_bolumu_goster(max_haber_per_kaynak: int = 5):
    """
    Ana haber bölümü.
    Streamlit uygulamanıza şu şekilde ekleyin:

        from emlak_haber import haber_bolumu_goster
        haber_bolumu_goster()
    """
    st.subheader("📰 Emlak Haberleri")

    # Kategori filtresi
    secili_kategori = st.selectbox(
        "Bölge",
        options=KATEGORI_LISTESI,
        index=0,
        label_visibility="collapsed",
    )

    # Yenile butonu
    col_bos, col_btn = st.columns([6, 1])
    with col_btn:
        if st.button("🔄 Yenile"):
            st.cache_data.clear()
            st.rerun()

    # Haberleri çek
    with st.spinner("Haberler yükleniyor..."):
        haberler = tum_haberleri_cek(max_haber_per_kaynak)

    # Filtrele
    if secili_kategori != "Tümü":
        haberler = [h for h in haberler if h["kategori"] == secili_kategori]

    if not haberler:
        st.info("Şu an haber bulunamadı. Lütfen daha sonra tekrar deneyin.")
        return

    st.caption(f"{len(haberler)} haber listeleniyor")

    for haber in haberler:
        haber_karti(haber)


# ─────────────────────────────────────────────
# BAĞIMSIZ ÇALIŞTIRMA (test için)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    st.set_page_config(page_title="Emlak Haberleri", page_icon="🏠", layout="wide")
    haber_bolumu_goster()
