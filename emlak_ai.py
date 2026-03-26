import streamlit as st
import openai
from PyPDF2 import PdfReader
import json
from datetime import datetime
import feedparser
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="EmlakBot - Akıllı Emlak Asistanı",
    page_icon="🏠",
    layout="wide"
)

# --- ÖZEL STİL ---
st.markdown("""
<style>
    /* Ana renk paleti */
    :root {
        --primary: #1a3c5e;
        --accent: #e8a020;
        --light: #f5f7fa;
        --card-bg: #ffffff;
    }

    .stApp {
        background-color: #f0f4f8;
    }

    /* Başlık stili */
    .main-header {
        background: linear-gradient(135deg, #1a3c5e 0%, #2d6a9f 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 4px 20px rgba(26,60,94,0.3);
    }

    .main-header h1 {
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }

    .main-header p {
        opacity: 0.85;
        margin: 0.4rem 0 0 0;
        font-size: 1rem;
    }

    /* Kart stilleri */
    .feature-card {
        background: white;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        border-left: 4px solid #e8a020;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }

    /* Tab stilleri */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: white;
        border-radius: 10px;
        padding: 6px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        font-weight: 600;
        color: #1a3c5e;
    }

    .stTabs [aria-selected="true"] {
        background-color: #1a3c5e !important;
        color: white !important;
    }

    /* Buton stilleri */
    .stButton > button {
        background: linear-gradient(135deg, #1a3c5e, #2d6a9f);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s ease;
        box-shadow: 0 2px 8px rgba(26,60,94,0.3);
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 16px rgba(26,60,94,0.4);
    }

    /* Bilgi kutuları */
    .info-box {
        background: #e8f4fd;
        border: 1px solid #b3d9f5;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.8rem 0;
    }

    .warning-box {
        background: #fff8e1;
        border: 1px solid #ffd54f;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.8rem 0;
    }

    .success-box {
        background: #e8f5e9;
        border: 1px solid #a5d6a7;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.8rem 0;
    }

    /* Müşteri kartları */
    .musteri-kart {
        background: white;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
        border: 1px solid #e0e8f0;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        transition: box-shadow 0.2s;
    }

    .musteri-kart:hover {
        box-shadow: 0 4px 16px rgba(26,60,94,0.12);
    }
</style>
""", unsafe_allow_html=True)

# --- GÜVENLİ API ANAHTARI KONTROLÜ ---
import os
api_key = os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", None)
if not api_key:
    st.sidebar.error("⚠️ API Anahtarı bulunamadı! OPENAI_API_KEY tanımlayın.")
    st.stop() 
# --- SESSION STATE BAŞLATMA ---
if 'musteriler' not in st.session_state:
    st.session_state['musteriler'] = []

# --- YARDIMCI FONKSİYONLAR ---

def gpt_calistir(prompt, sicaklik=0.3):
    """Merkezi GPT-4o çağrı fonksiyonu."""
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=sicaklik
    )
    return response.choices[0].message.content


def tapu_analiz_et(metin):
    """Tapu/sözleşme belgesini analiz eder."""
    prompt = f"""
    Aşağıdaki tapu, sözleşme veya imar belgesini bir uzman emlak hukukçusu titizliğiyle analiz et:

    1. GENEL BİLGİLER: Mülkün niteliği, tapu türü, kat durumu.
    2. RİSK TESPİTİ: İpotek, haciz, şerh, ihtiyati tedbir, irtifak hakkı gibi yükleri tespit et.
    3. İMAR DURUMU: İmar uygunluğu, yapı ruhsatı ve iskan sorunları.
    4. USUL HATALARI: Eksik imza, devir kısıtlaması, muvazaa riski vb.
    5. SATIN ALMA TAVSİYESİ: ✅ Güvenli / ⚠️ Dikkatli Ol / ❌ Riskli — gerekçesiyle açıkla.

    Belge:
    {metin}
    """
    return gpt_calistir(prompt, sicaklik=0.2)


def fiyat_raporu_olustur(ilce, mahalle, metrekare, oda_sayisi, bina_yasi, kat, ozellikler):
    """Piyasa fiyat analizi ve raporu oluşturur."""
    prompt = f"""
    Bir kıdemli emlak değerleme uzmanı olarak aşağıdaki mülk için kapsamlı bir fiyat ve piyasa analizi hazırla:

    MÜLK BİLGİLERİ:
    - Konum: {ilce} / {mahalle}
    - Alan: {metrekare} m²
    - Oda Sayısı: {oda_sayisi}
    - Bina Yaşı: {bina_yasi} yıl
    - Bulunduğu Kat: {kat}
    - Özellikler: {ozellikler}

    Rapor şunları içermeli:
    1. TAHMİNİ DEĞER ARALIĞI: Minimum, optimum ve maksimum fiyat (TL olarak)
    2. M² KARŞILAŞTIRMASI: Bölgedeki ortalama m² fiyatı ve bu mülkün konumu
    3. DEĞERİ ETKİLEYEN FAKTÖRLER: Artı ve eksi puanlar
    4. YATırım POTANSİYELİ: Kira getirisi tahmini ve ROI beklentisi
    5. PAZARLAMA STRATEJİSİ: Hangi alıcı profiline hitap etmeli, hangi platformda listelenmeli
    6. MÜZAKERE TAVSİYESİ: Satıcı için taban fiyat, alıcı için başlangıç teklif önerisi

    Türkiye emlak piyasası dinamiklerini ve 2024-2025 trendlerini göz önünde bulundur.
    """
    return gpt_calistir(prompt, sicaklik=0.3)


def ilan_metni_olustur(bilgiler, platform):
    """Platforma özel ilan ve pazarlama metni oluşturur."""
    platform_talimatlari = {
        "Sahibinden.com": "Detaylı, anahtar kelime zengin, SEO odaklı, 300-400 kelime",
        "Emlakjet": "Özellik odaklı, net ve sade, 200-300 kelime",
        "Instagram": "Duygusal, emoji kullanımlı, hikaye anlatımlı, hashtag listesiyle, 150-200 kelime",
        "WhatsApp Mesajı": "Kısa, net, vurgulu, paylaşmaya hazır format, 80-100 kelime"
    }

    prompt = f"""
    Aşağıdaki mülk bilgilerine dayanarak {platform} için profesyonel bir ilan metni yaz.

    Platform gereksinimleri: {platform_talimatlari.get(platform, 'Genel, profesyonel format')}

    MÜLK BİLGİLERİ:
    {bilgiler}

    Kurallar:
    - Mülkün güçlü yönlerini öne çıkar
    - Potansiyel alıcıyı harekete geçirecek dil kullan
    - {platform}'a özgü format ve ton kullan
    - Fiyat bilgisini belirgin şekilde göster
    - İletişim çağrısı (CTA) ekle
    """
    return gpt_calistir(prompt, sicaklik=0.7)


def musteri_eslestir(musteri_profili, portfoy):
    """Müşteri profiline uygun mülkleri eşleştirir."""
    prompt = f"""
    Aşağıdaki müşteri profiline en uygun mülkleri portföyden seç ve gerekçeli öner:

    MÜŞTERİ PROFİLİ:
    {musteri_profili}

    PORTFÖY:
    {portfoy}

    Çıktı formatı:
    1. EN UYGUN SEÇENEK: Hangi mülk ve neden (3-4 cümle)
    2. ALTERNATİF SEÇENEK: İkinci öneri ve gerekçesi
    3. SUNUM STRATEJİSİ: Müşteriyle görüşmede hangi özellikleri öne çıkarmalısın
    4. MUHTEMEL İTİRAZLAR: Müşteri ne sorarsa ne cevap vermelisin
    """
    return gpt_calistir(prompt, sicaklik=0.4)


# --- BÜLTEN FONKSİYONLARI ---

EMLAK_RSS_KAYNAKLARI = {
    "Türkiye": [
        {"ad": "Hürriyet Emlak", "url": "https://www.hurriyet.com.tr/rss/kategori/emlak"},
        {"ad": "NTV Ekonomi", "url": "https://www.ntv.com.tr/ekonomi.rss"},
        {"ad": "Sözcü Ekonomi", "url": "https://www.sozcu.com.tr/rss/ekonomi.xml"},
        {"ad": "Milliyet Emlak", "url": "https://www.milliyet.com.tr/rss/rssNew/emlakRss.xml"},
    ],
    "Dünya": [
        {"ad": "Reuters Real Estate", "url": "https://feeds.reuters.com/reuters/businessNews"},
        {"ad": "Housing Wire", "url": "https://www.housingwire.com/feed/"},
        {"ad": "The Real Deal", "url": "https://therealdeal.com/feed/"},
        {"ad": "Property Week", "url": "https://www.propertyweek.com/rss"},
    ]
}

def rss_haber_cek(feed_url, max_haber=3):
    """RSS feed'den haber başlıklarını ve özetlerini çeker."""
    try:
        feed = feedparser.parse(feed_url)
        haberler = []
        for entry in feed.entries[:max_haber]:
            haber = {
                "baslik": entry.get("title", ""),
                "ozet": entry.get("summary", entry.get("description", ""))[:300],
                "link": entry.get("link", ""),
                "tarih": entry.get("published", "")
            }
            if haber["baslik"]:
                haberler.append(haber)
        return haberler
    except Exception:
        return []

def bulten_olustur(tr_haberler, dunya_haberler, ton, dil):
    """GPT ile haftalık emlak bülteni oluşturur."""
    ton_talimatlari = {
        "Profesyonel": "Resmi, analitik, veri odaklı bir dil kullan. Sektör uzmanlarına hitap et.",
        "Samimi": "Sıcak, samimi ve anlaşılır bir dil kullan. Danışmanlara arkadaşça hitap et.",
        "Kısa & Öz": "Her bölümü maksimum 2-3 cümleyle özetle. Net ve direkt ol.",
        "Analitik": "Trend analizlerine, sayısal verilere ve piyasa yorumlarına ağırlık ver."
    }

    dil_talimati = {
        "Türkçe": "Bülteni tamamen Türkçe yaz.",
        "İngilizce": "Write the newsletter entirely in English.",
        "İki Dilde": "Her bölümü önce Türkçe, ardından İngilizce olarak yaz."
    }

    tr_metin = "\n".join([f"- {h['baslik']}: {h['ozet']}" for h in tr_haberler]) if tr_haberler else "Haber bulunamadı."
    dunya_metin = "\n".join([f"- {h['baslik']}: {h['ozet']}" for h in dunya_haberler]) if dunya_haberler else "Haber bulunamadı."

    prompt = f"""
Sen deneyimli bir emlak sektörü yazarısın. Aşağıdaki ham haber verilerini kullanarak
bu haftanın emlak bültenini hazırla.

TON: {ton_talimatlari.get(ton, '')}
DİL: {dil_talimati.get(dil, '')}

TÜRKİYE EMLAK HABERLERİ:
{tr_metin}

DÜNYA EMLAK HABERLERİ:
{dunya_metin}

Bülten şu bölümleri içermeli:

1. 📌 HAFTANIN ÖZETİ (2-3 cümle genel değerlendirme)
2. 🇹🇷 TÜRKİYE'DEN ÖNE ÇIKANLAR (3-4 madde, kısa yorumlarla)
3. 🌍 DÜNYADAN ÖNE ÇIKANLAR (3-4 madde, kısa yorumlarla)
4. 📊 HAFTANIN ANALİZİ (piyasa trendi, fırsat veya risk değerlendirmesi)
5. 💡 DANIŞMANLARA TAVSİYE (bu hafta müşterilere ne söylemeli, nasıl konumlanmalı)

Bülteni blog yazısı formatında, akıcı ve okunması kolay şekilde yaz.
Tarih olarak bu haftayı ({datetime.now().strftime('%d %B %Y')}) kullan.
"""
    return gpt_calistir(prompt, sicaklik=0.6)


def html_bulten_olustur(bulten_metni, baslik):
    """Bülteni HTML e-posta şablonuna dönüştürür."""
    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f4f8; margin: 0; padding: 20px; }}
  .container {{ max-width: 680px; margin: 0 auto; background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
  .header {{ background: linear-gradient(135deg, #1a3c5e 0%, #2d6a9f 100%); padding: 30px 40px; color: white; }}
  .header h1 {{ margin: 0; font-size: 24px; }}
  .header p {{ margin: 8px 0 0 0; opacity: 0.85; font-size: 14px; }}
  .content {{ padding: 30px 40px; color: #333; line-height: 1.7; white-space: pre-wrap; }}
  .footer {{ background: #f5f7fa; padding: 20px 40px; text-align: center; color: #888; font-size: 12px; border-top: 1px solid #e0e8f0; }}
  .accent {{ color: #e8a020; font-weight: bold; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🏠 EmlakBot Haftalık Bülten</h1>
    <p>{baslik} · {datetime.now().strftime('%d %B %Y')}</p>
  </div>
  <div class="content">{bulten_metni}</div>
  <div class="footer">
    <p>Bu bülten <span class="accent">EmlakBot</span> tarafından yapay zeka ile hazırlanmıştır.</p>
    <p>emlak-ai.site</p>
  </div>
</div>
</body>
</html>
"""
    return html


def email_gonder(smtp_server, smtp_port, gonderen_email, sifre, alicilar, konu, html_icerik):
    """SMTP üzerinden HTML e-posta gönderir."""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = konu
        msg['From'] = gonderen_email
        msg['To'] = ", ".join(alicilar)
        msg.attach(MIMEText(html_icerik, 'html', 'utf-8'))

        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(gonderen_email, sifre)
            server.sendmail(gonderen_email, alicilar, msg.as_string())
        return True, "✅ E-posta başarıyla gönderildi!"
    except Exception as e:
        return False, f"❌ Hata: {str(e)}"


# --- ANA BAŞLIK ---
st.markdown("""
<div class="main-header">
    <h1>🏠 EmlakBot v1.1</h1>
    <p><b>EmlakBot</b>, emlak danışmanlarının iş akışını hızlandıran yapay zeka destekli asistanıdır.
    Tapu analizi, fiyat raporu, ilan metni, müşteri portföy yönetimi ve haftalık bülten tek platformda.</p>
</div>
""", unsafe_allow_html=True)

# --- ANA SEKMELER ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📄 Sözleşme & Tapu Analizi",
    "📊 Fiyat & Piyasa Raporu",
    "✍️ İlan & Pazarlama Metni",
    "👥 Müşteri Portföy Yönetimi",
    "📰 Haftalık Emlak Bülteni",
    "📰 Emlak Haberleri"
])


# ============================================================
# TAB 1: TAPU ANALİZİ
# ============================================================
with tab1:
    st.subheader("📄 Sözleşme & Tapu Analizi")
    st.markdown("Tapu fotokopisi, satış vaadi sözleşmesi veya imar belgesi PDF'ini yükleyin. Sistem ipotek, haciz, şerh ve usul risklerini otomatik tespit eder.")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("#### 📁 Belge Yükleme")
        yuklenen_dosya = st.file_uploader(
            "PDF dosyasını buraya sürükleyin",
            type="pdf",
            key="tapu_pdf"
        )

        if yuklenen_dosya:
            with st.spinner("📖 Belge okunuyor..."):
                reader = PdfReader(yuklenen_dosya)
                ham_metin = "".join([
                    page.extract_text() for page in reader.pages
                    if page.extract_text()
                ])

            if ham_metin:
                st.success(f"✅ Belge yüklendi — {len(reader.pages)} sayfa, {len(ham_metin)} karakter")
                st.session_state['tapu_ham_metin'] = ham_metin

                if st.button("🔍 Tapu & Risk Analizini Başlat", key="tapu_analiz_btn"):
                    with st.spinner("🤖 Analiz yapılıyor..."):
                        sonuc = tapu_analiz_et(st.session_state['tapu_ham_metin'])
                    st.session_state['tapu_analiz'] = sonuc
            else:
                st.warning("⚠️ PDF'den metin çıkarılamadı. Taranmış görüntü olabilir.")

        st.markdown("---")
        st.markdown("#### 💡 Neler tespit edilir?")
        for item in ["İpotek ve haciz yükleri", "Şerh ve ihtiyati tedbirler",
                     "İmar uyumsuzlukları", "Kat irtifakı sorunları",
                     "Eksik belgeler ve usul hataları"]:
            st.markdown(f"• {item}")

    with col2:
        st.markdown("#### 🔍 Analiz Sonuçları")
        if 'tapu_analiz' in st.session_state:
            st.markdown(st.session_state['tapu_analiz'])
            st.download_button(
                label="📥 Analiz Raporunu İndir (.txt)",
                data=st.session_state['tapu_analiz'],
                file_name=f"tapu_analiz_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain"
            )
        else:
            st.markdown("""
            <div class="info-box">
            📋 Belgeyi yükleyip <b>Analizi Başlat</b> butonuna tıkladığınızda sonuçlar burada görünecek.
            </div>
            """, unsafe_allow_html=True)


# ============================================================
# TAB 2: FİYAT & PİYASA RAPORU
# ============================================================
with tab2:
    st.subheader("📊 Fiyat & Piyasa Raporu")
    st.markdown("Mülk bilgilerini girin, yapay zeka destekli değerleme ve yatırım analizi alın.")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("#### 🏘️ Mülk Bilgileri")

        ilce = st.text_input("İlçe", placeholder="örn: Kadıköy, Çankaya, Karşıyaka")
        mahalle = st.text_input("Mahalle / Semt", placeholder="örn: Moda, Kızılay, Alsancak")

        col_a, col_b = st.columns(2)
        with col_a:
            metrekare = st.number_input("Alan (m²)", min_value=20, max_value=2000, value=100)
        with col_b:
            bina_yasi = st.number_input("Bina Yaşı", min_value=0, max_value=100, value=10)

        col_c, col_d = st.columns(2)
        with col_c:
            oda_sayisi = st.selectbox("Oda Sayısı", ["1+0", "1+1", "2+1", "3+1", "4+1", "4+2 ve üzeri"])
        with col_d:
            kat = st.text_input("Bulunduğu Kat", placeholder="örn: 3/8")

        ozellikler = st.text_area(
            "Öne Çıkan Özellikler",
            placeholder="örn: Deniz manzarası, ebeveyn banyosu, merkezi ısıtma, otopark, güvenlik, yeni mutfak...",
            height=100
        )

        if st.button("📊 Fiyat Raporu Oluştur", key="fiyat_rapor"):
            if ilce and mahalle:
                st.session_state['fiyat_tetik'] = True
                st.session_state['fiyat_params'] = (ilce, mahalle, metrekare, oda_sayisi, bina_yasi, kat, ozellikler)
            else:
                st.warning("Lütfen en az ilçe ve mahalle bilgisini girin.")
        
        if st.session_state.get('fiyat_tetik'):
            st.session_state['fiyat_tetik'] = False
            params = st.session_state.get('fiyat_params', ())
            with st.spinner("📈 Piyasa analizi yapılıyor..."):
                st.session_state['fiyat_raporu'] = fiyat_raporu_olustur(*params)
            st.rerun()

    with col2:
        st.markdown("#### 📈 Değerleme Raporu")
        if 'fiyat_raporu' in st.session_state:
            st.markdown(st.session_state['fiyat_raporu'])
            st.download_button(
                label="📥 Raporu İndir (.txt)",
                data=st.session_state['fiyat_raporu'],
                file_name=f"fiyat_raporu_{ilce}_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )
        else:
            st.markdown("""
            <div class="info-box">
            📊 Mülk bilgilerini doldurarak <b>Fiyat Raporu Oluştur</b>'a tıklayın.
            Tahminî değer aralığı, kira getirisi ve yatırım analizi burada görünecek.
            </div>
            """, unsafe_allow_html=True)


# ============================================================
# TAB 3: İLAN & PAZARLAMA METNİ
# ============================================================
with tab3:
    st.subheader("✍️ İlan & Pazarlama Metni Üretici")
    st.markdown("Mülk bilgilerini girin, istediğiniz platforma özel profesyonel ilan metni saniyeler içinde hazır olsun.")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("#### 🏠 Mülk Tanımı")

        ilan_baslik = st.text_input("Mülk Başlığı", placeholder="örn: Kadıköy Moda'da Deniz Manzaralı 3+1")
        ilan_fiyat = st.text_input("Satış / Kira Fiyatı", placeholder="örn: 8.500.000 TL / 45.000 TL/ay")
        ilan_konum = st.text_input("Konum", placeholder="örn: Kadıköy, Moda - metroya 5 dk yürüyüş")

        ilan_ozellikler = st.text_area(
            "Mülk Özellikleri",
            placeholder="Brüt 140m², 3+1, 2 banyo, ebeveyn banyosu, 7. kat, asansörlü, otoparklı, güvenlikli site, kombi ısıtma, yeni mutfak dolabı, balkon...",
            height=120
        )

        platform = st.selectbox(
            "Platform Seçin",
            ["Sahibinden.com", "Emlakjet", "Instagram", "WhatsApp Mesajı"]
        )

        if st.button("✨ İlan Metni Oluştur", key="ilan_olustur"):
            if ilan_baslik and ilan_ozellikler:
                bilgiler = f"Başlık: {ilan_baslik}\nFiyat: {ilan_fiyat}\nKonum: {ilan_konum}\nÖzellikler: {ilan_ozellikler}"
                st.session_state['ilan_tetik'] = True
                st.session_state['ilan_bilgiler'] = bilgiler
                st.session_state['ilan_platform'] = platform
            else:
                st.warning("Lütfen en az başlık ve özellikler kısmını doldurun.")
        
        if st.session_state.get('ilan_tetik'):
            st.session_state['ilan_tetik'] = False
            with st.spinner(f"✍️ {st.session_state.get('ilan_platform', '')} için metin hazırlanıyor..."):
                st.session_state['ilan_metni'] = ilan_metni_olustur(
                    st.session_state.get('ilan_bilgiler', ''),
                    st.session_state.get('ilan_platform', '')
                )
            st.rerun()

    with col2:
        st.markdown("#### 📋 Hazırlanan İlan Metni")
        if 'ilan_metni' in st.session_state:
            st.success(f"✅ {st.session_state['ilan_platform']} için ilan hazır!")
            ilan_duzenle = st.text_area(
                "Metni düzenleyebilirsiniz:",
                value=st.session_state['ilan_metni'],
                height=400
            )
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                st.download_button(
                    label="📥 Metni İndir (.txt)",
                    data=ilan_duzenle,
                    file_name=f"ilan_{st.session_state['ilan_platform']}_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain"
                )
            with col_btn2:
                if st.button("🔄 Farklı Platform İçin Yeniden Oluştur"):
                    st.info("Sol panelden farklı bir platform seçip tekrar oluşturabilirsiniz.")
        else:
            st.markdown("""
            <div class="info-box">
            ✍️ Mülk bilgilerini doldurun ve platformu seçin.
            Her platform için farklı ton ve format otomatik uygulanır.
            </div>
            """, unsafe_allow_html=True)

            st.markdown("#### 🎯 Platform Farkları")
            for platform_info in [
                ("🏠 Sahibinden.com", "SEO odaklı, detaylı, anahtar kelime zengin"),
                ("🔍 Emlakjet", "Özellik odaklı, sade ve net"),
                ("📱 Instagram", "Duygusal, emoji'li, hashtag'li"),
                ("💬 WhatsApp", "Kısa, vurgulu, paylaşmaya hazır"),
            ]:
                st.markdown(f"**{platform_info[0]}**: {platform_info[1]}")


# ============================================================
# TAB 4: MÜŞTERİ & PORTFÖY YÖNETİMİ
# ============================================================
with tab4:
    st.subheader("👥 Müşteri & Mülk Portföy Yönetimi")

    p_tab1, p_tab2, p_tab3 = st.tabs([
        "👤 Müşteriler",
        "🏠 Mülk Portföyü",
        "🎯 Akıllı Eşleştirme"
    ])

    with p_tab1:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("#### ➕ Yeni Müşteri Ekle")
            with st.form("musteri_formu", clear_on_submit=True):
                m_ad   = st.text_input("Ad Soyad *", placeholder="örn: Ahmet Yılmaz")
                m_tel  = st.text_input("Telefon", placeholder="05XX XXX XX XX")
                m_eposta = st.text_input("E-posta", placeholder="ornek@email.com")

                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    m_butce_min = st.number_input("Min. Bütçe (TL)", min_value=0, step=100000, value=1000000)
                with col_f2:
                    m_butce_max = st.number_input("Max. Bütçe (TL)", min_value=0, step=100000, value=5000000)

                m_konum = st.text_input("Tercih Bölge(ler)", placeholder="örn: Kadıköy, Üsküdar")
                m_tip   = st.multiselect("Aranan Mülk Tipi", ["Daire", "Villa", "Müstakil", "Arsa", "Ticari"])
                m_oda   = st.selectbox("Min. Oda", ["Farketmez", "1+1", "2+1", "3+1", "4+1+"])
                m_oncelik = st.multiselect("Öncelikler", ["Ulaşım", "Okul", "Sessizlik", "Manzara", "Yeni bina", "Balkon", "Otopark"])
                m_notlar = st.text_area("Özel Notlar", placeholder="Evcil hayvan dostu site, takas düşünür...", height=70)

                if st.form_submit_button("✅ Müşteriyi Kaydet"):
                    if m_ad:
                        yeni = {
                            "id": len(st.session_state['musteriler']) + 1,
                            "ad": m_ad, "tel": m_tel, "eposta": m_eposta,
                            "butce_min": m_butce_min, "butce_max": m_butce_max,
                            "konum": m_konum, "tip": m_tip, "oda": m_oda,
                            "oncelik": m_oncelik, "notlar": m_notlar,
                            "tarih": datetime.now().strftime("%d.%m.%Y"),
                            "durum": "Aktif"
                        }
                        st.session_state['musteriler'].append(yeni)
                        st.success(f"✅ {m_ad} portföye eklendi!")
                    else:
                        st.warning("Ad Soyad zorunludur.")

        with col2:
            st.markdown("#### 📋 Müşteri Listesi")
            if st.session_state['musteriler']:
                for m in st.session_state['musteriler']:
                    etiket = f"👤 {m['ad']}  |  {m['konum']}  |  {m['butce_min']:,}–{m['butce_max']:,} TL"
                    with st.expander(etiket):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown(f"📞 **Tel:** {m['tel']}")
                            st.markdown(f"📧 **E-posta:** {m.get('eposta','—')}")
                            st.markdown(f"🛏️ **Min. Oda:** {m['oda']}")
                        with c2:
                            st.markdown(f"🏠 **Tip:** {', '.join(m['tip']) if m['tip'] else '—'}")
                            st.markdown(f"⭐ **Öncelik:** {', '.join(m.get('oncelik',[])) if m.get('oncelik') else '—'}")
                            st.markdown(f"📅 **Eklenme:** {m['tarih']}")
                        if m['notlar']:
                            st.markdown(f"📝 **Not:** {m['notlar']}")
            else:
                st.markdown('<div class="info-box">👥 Henüz müşteri eklenmedi.</div>', unsafe_allow_html=True)

    with p_tab2:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("#### ➕ Yeni Mülk Ekle")
            with st.form("mulk_formu", clear_on_submit=True):
                mulk_baslik = st.text_input("Mülk Başlığı *", placeholder="örn: Kadıköy Moda 3+1")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    mulk_ilce = st.text_input("İlçe", placeholder="Kadıköy")
                with col_b:
                    mulk_mahalle = st.text_input("Mahalle", placeholder="Moda")

                col_c, col_d = st.columns(2)
                with col_c:
                    mulk_fiyat = st.number_input("Fiyat (TL)", min_value=0, step=100000, value=5000000)
                with col_d:
                    mulk_m2 = st.number_input("Alan (m²)", min_value=0, step=5, value=100)

                col_e, col_f = st.columns(2)
                with col_e:
                    mulk_oda = st.selectbox("Oda Sayısı", ["1+0","1+1","2+1","3+1","4+1","4+2+"])
                with col_f:
                    mulk_yas = st.number_input("Bina Yaşı", min_value=0, max_value=100, value=5)

                mulk_ozellik = st.multiselect("Özellikler",
                    ["Balkon","Asansör","Otopark","Güvenlik","Havuz","Manzara",
                     "Ebeveyn Banyosu","Kombili","Merkezi Isıtma","Yeni bina","Site içi"])
                mulk_not = st.text_area("Ek Notlar", height=60, placeholder="Kiracılı, tapu temiz, acil satış...")

                if st.form_submit_button("✅ Mülkü Portföye Ekle"):
                    if mulk_baslik:
                        if 'mulkler' not in st.session_state:
                            st.session_state['mulkler'] = []
                        yeni_mulk = {
                            "id": len(st.session_state['mulkler']) + 1,
                            "baslik": mulk_baslik,
                            "ilce": mulk_ilce, "mahalle": mulk_mahalle,
                            "fiyat": mulk_fiyat, "m2": mulk_m2,
                            "oda": mulk_oda, "yas": mulk_yas,
                            "ozellik": mulk_ozellik, "not": mulk_not,
                            "tarih": datetime.now().strftime("%d.%m.%Y")
                        }
                        st.session_state['mulkler'].append(yeni_mulk)
                        st.success(f"✅ '{mulk_baslik}' portföye eklendi!")
                    else:
                        st.warning("Mülk başlığı zorunludur.")

        with col2:
            st.markdown("#### 🏠 Mülk Listesi")
            if 'mulkler' not in st.session_state:
                st.session_state['mulkler'] = []

            if st.session_state['mulkler']:
                for mulk in st.session_state['mulkler']:
                    m2_fiyat = int(mulk['fiyat'] / mulk['m2']) if mulk['m2'] > 0 else 0
                    etiket = f"🏠 {mulk['baslik']}  |  {mulk['fiyat']:,} TL  |  {mulk['m2']} m²"
                    with st.expander(etiket):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown(f"📍 **Konum:** {mulk['ilce']} / {mulk['mahalle']}")
                            st.markdown(f"🛏️ **Oda:** {mulk['oda']}")
                            st.markdown(f"🏗️ **Bina Yaşı:** {mulk['yas']} yıl")
                        with c2:
                            st.markdown(f"💰 **m² Fiyatı:** {m2_fiyat:,} TL")
                            st.markdown(f"✨ **Özellikler:** {', '.join(mulk['ozellik']) if mulk['ozellik'] else '—'}")
                            st.markdown(f"📅 **Eklenme:** {mulk['tarih']}")
                        if mulk['not']:
                            st.markdown(f"📝 **Not:** {mulk['not']}")
            else:
                st.markdown('<div class="info-box">🏠 Henüz mülk eklenmedi.</div>', unsafe_allow_html=True)

    with p_tab3:
        st.markdown("#### 🎯 Akıllı Eşleştirme — % Uyum Skorlu")

        if not st.session_state.get('musteriler') or not st.session_state.get('mulkler'):
            st.markdown("""
            <div class="warning-box">
            ⚠️ Eşleştirme için <b>en az 1 müşteri</b> ve <b>en az 1 mülk</b> eklenmiş olmalıdır.
            </div>
            """, unsafe_allow_html=True)
        else:
            yon = st.radio(
                "Arama Yönü",
                ["👤 Müşteriye göre mülk bul", "🏠 Mülke göre müşteri bul"],
                horizontal=True
            )
            st.divider()

            if yon == "👤 Müşteriye göre mülk bul":
                secilen_m = st.selectbox(
                    "Müşteri Seçin",
                    [f"{m['ad']} — {m['konum']} | {m['butce_min']:,}–{m['butce_max']:,} TL"
                     for m in st.session_state['musteriler']]
                )
                m_idx = [f"{m['ad']} — {m['konum']} | {m['butce_min']:,}–{m['butce_max']:,} TL"
                         for m in st.session_state['musteriler']].index(secilen_m)
                musteri = st.session_state['musteriler'][m_idx]

                if st.button("🤖 Tüm Mülkleri Analiz Et & Skora Göre Sırala", key="m2mulk"):
                    mulk_listesi = "\n".join([
                        f"Mülk #{mulk['id']}: {mulk['baslik']} | {mulk['ilce']}/{mulk['mahalle']} | "
                        f"{mulk['fiyat']:,} TL | {mulk['m2']}m² | {mulk['oda']} | "
                        f"Bina yaşı: {mulk['yas']} | Özellikler: {', '.join(mulk['ozellik'])} | Not: {mulk['not']}"
                        for mulk in st.session_state['mulkler']
                    ])
                    profil = f"""
                    Ad: {musteri['ad']}
                    Bütçe: {musteri['butce_min']:,} – {musteri['butce_max']:,} TL
                    Konum tercihi: {musteri['konum']}
                    Mülk tipi: {', '.join(musteri['tip'])}
                    Min. oda: {musteri['oda']}
                    Öncelikler: {', '.join(musteri.get('oncelik', []))}
                    Özel notlar: {musteri['notlar']}
                    """
                    st.session_state['esles_tetik'] = True
                    st.session_state['esles_profil'] = profil
                    st.session_state['esles_mulkler'] = mulk_listesi
                    st.session_state['esles_yon'] = 'musteri'

            else:
                secilen_mulk = st.selectbox(
                    "Mülk Seçin",
                    [f"{mulk['baslik']} — {mulk['ilce']} | {mulk['fiyat']:,} TL"
                     for mulk in st.session_state['mulkler']]
                )
                mulk_idx = [f"{mulk['baslik']} — {mulk['ilce']} | {mulk['fiyat']:,} TL"
                            for mulk in st.session_state['mulkler']].index(secilen_mulk)
                mulk = st.session_state['mulkler'][mulk_idx]

                if st.button("🤖 Tüm Müşterileri Analiz Et & Skora Göre Sırala", key="mulk2m"):
                    musteri_listesi = "\n".join([
                        f"Müşteri #{m['id']}: {m['ad']} | Bütçe: {m['butce_min']:,}–{m['butce_max']:,} TL | "
                        f"Bölge: {m['konum']} | Tip: {', '.join(m['tip'])} | Min oda: {m['oda']} | "
                        f"Öncelikler: {', '.join(m.get('oncelik',[]))} | Not: {m['notlar']}"
                        for m in st.session_state['musteriler']
                    ])
                    mulk_detay = (
                        f"{mulk['baslik']} | {mulk['ilce']}/{mulk['mahalle']} | "
                        f"{mulk['fiyat']:,} TL | {mulk['m2']}m² | {mulk['oda']} | "
                        f"Bina yaşı: {mulk['yas']} | Özellikler: {', '.join(mulk['ozellik'])} | Not: {mulk['not']}"
                    )
                    st.session_state['esles_tetik'] = True
                    st.session_state['esles_profil'] = mulk_detay
                    st.session_state['esles_mulkler'] = musteri_listesi
                    st.session_state['esles_yon'] = 'mulk'

            if st.session_state.get('esles_tetik'):
                st.session_state['esles_tetik'] = False
                yon_flag = st.session_state.get('esles_yon', 'musteri')

                if yon_flag == 'musteri':
                    prompt = f"""
Sen bir uzman emlak danışmanısın. Aşağıdaki müşteri profiline göre portföydeki her mülkü değerlendir
ve 0-100 arası uyum skoru ver. Skoru belirlerken şu kriterleri ağırlıklandır:
- Bütçe uyumu (30 puan)
- Konum uyumu (25 puan)
- Oda/tip uyumu (20 puan)
- Öncelikler & özel talepler (25 puan)

MÜŞTERİ:
{st.session_state.get('esles_profil','')}

PORTFÖY:
{st.session_state.get('esles_mulkler','')}

Yanıtını şu formatta ver — her mülk için ayrı blok:

---
🏠 Mülk #[ID]: [Başlık]
📊 UYUM SKORU: [0-100]/100
✅ GÜÇLÜ YÖNLER: [müşteri kriterlerine göre neden uygun]
⚠️ ZAYIF YÖNLER: [neden uyumsuz olabilir]
💬 SUNUM STRATEJİSİ: [bu müşteriye bu mülkü nasıl sun]
---

En yüksek skordan en düşüğe doğru sırala.
"""
                else:
                    prompt = f"""
Sen bir uzman emlak danışmanısın. Aşağıdaki mülk için müşteri listesindeki her müşteriyi değerlendir
ve 0-100 arası uyum skoru ver.

MÜLK:
{st.session_state.get('esles_profil','')}

MÜŞTERİLER:
{st.session_state.get('esles_mulkler','')}

Yanıtını şu formatta ver — her müşteri için ayrı blok:

---
👤 Müşteri #[ID]: [Ad]
📊 UYUM SKORU: [0-100]/100
✅ UYUM NEDENLERİ: [neden bu mülk bu müşteriye uygun]
⚠️ RİSK NOKTALARI: [neden itiraz edebilir]
💬 YAKLAŞIM TAVSİYESİ: [bu müşteriyle görüşmede nasıl davran]
---

En yüksek skordan en düşüğe doğru sırala.
"""
                with st.spinner("🤖 GPT-4o tüm eşleşmeleri analiz ediyor..."):
                    st.session_state['esles_sonuc'] = gpt_calistir(prompt, sicaklik=0.3)
                st.rerun()

            if 'esles_sonuc' in st.session_state:
                st.success("✅ Eşleştirme Tamamlandı — Skora Göre Sıralandı")
                st.markdown(st.session_state['esles_sonuc'])
                st.download_button(
                    "📥 Raporu İndir",
                    data=st.session_state['esles_sonuc'],
                    file_name=f"eslestirme_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    mime="text/plain"
                )


# ============================================================
# TAB 5: HAFTALIK EMLAK BÜLTENİ
# ============================================================
with tab5:
    st.subheader("📰 Haftalık Emlak Bülteni")
    st.markdown("Türkiye ve dünya emlak haberlerini otomatik topla, GPT ile blog tarzı bülten oluştur, müşterilerine e-posta ile gönder.")

    b_tab1, b_tab2, b_tab3 = st.tabs([
        "1️⃣ Haberleri Topla",
        "2️⃣ Bülten Oluştur",
        "3️⃣ E-posta ile Gönder"
    ])

    # ── ADIM 1: HABERLERİ TOPLA ──────────────────────────────
    with b_tab1:
        st.markdown("#### 📡 Haber Kaynakları")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**🇹🇷 Türkiye Kaynakları**")
            tr_secili = []
            for kaynak in EMLAK_RSS_KAYNAKLARI["Türkiye"]:
                if st.checkbox(kaynak["ad"], value=True, key=f"tr_{kaynak['ad']}"):
                    tr_secili.append(kaynak)

        with col2:
            st.markdown("**🌍 Dünya Kaynakları**")
            dunya_secili = []
            for kaynak in EMLAK_RSS_KAYNAKLARI["Dünya"]:
                if st.checkbox(kaynak["ad"], value=True, key=f"dunya_{kaynak['ad']}"):
                    dunya_secili.append(kaynak)

        st.markdown("---")
        st.markdown("#### ➕ Ek RSS Kaynağı Ekle (İsteğe Bağlı)")
        col_ek1, col_ek2 = st.columns([1, 2])
        with col_ek1:
            ek_ad = st.text_input("Kaynak Adı", placeholder="örn: Sabah Ekonomi")
        with col_ek2:
            ek_url = st.text_input("RSS URL", placeholder="https://...")

        haber_sayisi = st.slider("Kaynak başına haber sayısı", min_value=1, max_value=5, value=3)

        if st.button("📡 Haberleri Çek", key="haber_cek", type="primary"):
            tr_haberler = []
            dunya_haberler = []
            hata_sayisi = 0

            progress = st.progress(0, text="Haberler çekiliyor...")
            toplam = len(tr_secili) + len(dunya_secili) + (1 if ek_url else 0)
            tamamlanan = 0

            for kaynak in tr_secili:
                haberler = rss_haber_cek(kaynak["url"], haber_sayisi)
                if haberler:
                    tr_haberler.extend(haberler)
                else:
                    hata_sayisi += 1
                tamamlanan += 1
                progress.progress(tamamlanan / max(toplam, 1), text=f"'{kaynak['ad']}' çekiliyor...")

            for kaynak in dunya_secili:
                haberler = rss_haber_cek(kaynak["url"], haber_sayisi)
                if haberler:
                    dunya_haberler.extend(haberler)
                else:
                    hata_sayisi += 1
                tamamlanan += 1
                progress.progress(tamamlanan / max(toplam, 1), text=f"'{kaynak['ad']}' çekiliyor...")

            if ek_url and ek_ad:
                haberler = rss_haber_cek(ek_url, haber_sayisi)
                if haberler:
                    tr_haberler.extend(haberler)
                tamamlanan += 1
                progress.progress(1.0, text="Tamamlandı!")

            progress.empty()

            st.session_state['bulten_tr_haberler'] = tr_haberler
            st.session_state['bulten_dunya_haberler'] = dunya_haberler

            if tr_haberler or dunya_haberler:
                st.success(f"✅ {len(tr_haberler)} TR haberi + {len(dunya_haberler)} dünya haberi çekildi.")
                if hata_sayisi > 0:
                    st.warning(f"⚠️ {hata_sayisi} kaynak yanıt vermedi (RSS değişmiş olabilir).")

                col_tr, col_dunya = st.columns(2)
                with col_tr:
                    st.markdown("**🇹🇷 TR Haberleri**")
                    for h in tr_haberler[:6]:
                        st.markdown(f"• [{h['baslik'][:60]}...]({h['link']})" if h['link'] else f"• {h['baslik'][:60]}...")

                with col_dunya:
                    st.markdown("**🌍 Dünya Haberleri**")
                    for h in dunya_haberler[:6]:
                        st.markdown(f"• [{h['baslik'][:60]}...]({h['link']})" if h['link'] else f"• {h['baslik'][:60]}...")

                st.info("➡️ **2. Bülten Oluştur** sekmesine geçerek bülteni oluşturun.")
            else:
                st.error("❌ Hiçbir kaynaktan haber çekilemedi. İnternet bağlantısını veya RSS adreslerini kontrol edin.")

    # ── ADIM 2: BÜLTEN OLUŞTUR ───────────────────────────────
    with b_tab2:
        st.markdown("#### ✍️ Bülten Ayarları")

        if not st.session_state.get('bulten_tr_haberler') and not st.session_state.get('bulten_dunya_haberler'):
            st.markdown("""
            <div class="warning-box">
            ⚠️ Önce <b>1. Haberleri Topla</b> sekmesinden haberleri çekin.
            </div>
            """, unsafe_allow_html=True)
        else:
            tr_sayi = len(st.session_state.get('bulten_tr_haberler', []))
            dunya_sayi = len(st.session_state.get('bulten_dunya_haberler', []))
            st.success(f"✅ {tr_sayi} TR + {dunya_sayi} dünya haberi hazır.")

            col1, col2, col3 = st.columns(3)
            with col1:
                bulten_baslik = st.text_input("Bülten Başlığı", value=f"Haftalık Emlak Bülteni — {datetime.now().strftime('%d %B %Y')}")
            with col2:
                ton = st.selectbox("Yazım Tonu", ["Profesyonel", "Samimi", "Kısa & Öz", "Analitik"])
            with col3:
                dil = st.selectbox("Dil", ["Türkçe", "İngilizce", "İki Dilde"])

            if st.button("🤖 Bülteni Oluştur", key="bulten_olustur", type="primary"):
                with st.spinner("📝 GPT-4o bülteni yazıyor..."):
                    bulten_metni = bulten_olustur(
                        st.session_state.get('bulten_tr_haberler', []),
                        st.session_state.get('bulten_dunya_haberler', []),
                        ton, dil
                    )
                st.session_state['bulten_metni'] = bulten_metni
                st.session_state['bulten_baslik'] = bulten_baslik
                st.rerun()

            if 'bulten_metni' in st.session_state:
                st.success("✅ Bülten hazır!")
                st.divider()

                bulten_duzenle = st.text_area(
                    "Bülteni düzenleyebilirsiniz:",
                    value=st.session_state['bulten_metni'],
                    height=500
                )
                st.session_state['bulten_metni_son'] = bulten_duzenle

                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    st.download_button(
                        "📥 Metin Olarak İndir (.txt)",
                        data=bulten_duzenle,
                        file_name=f"bulten_{datetime.now().strftime('%Y%m%d')}.txt",
                        mime="text/plain"
                    )
                with col_dl2:
                    html_icerik = html_bulten_olustur(bulten_duzenle, st.session_state.get('bulten_baslik', ''))
                    st.download_button(
                        "📧 HTML E-posta Olarak İndir",
                        data=html_icerik,
                        file_name=f"bulten_{datetime.now().strftime('%Y%m%d')}.html",
                        mime="text/html"
                    )

                st.info("➡️ **3. E-posta ile Gönder** sekmesinden müşterilerinize gönderin.")

    # ── ADIM 3: E-POSTA GÖNDER ───────────────────────────────
    with b_tab3:
        st.markdown("#### 📧 E-posta Gönderimi")

        if 'bulten_metni' not in st.session_state:
            st.markdown("""
            <div class="warning-box">
            ⚠️ Önce <b>2. Bülten Oluştur</b> sekmesinden bülteni hazırlayın.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.success(f"✅ Bülten hazır: **{st.session_state.get('bulten_baslik', '')}**")
            st.divider()

            col1, col2 = st.columns([1, 1])

            with col1:
                st.markdown("#### ⚙️ SMTP Ayarları")
                smtp_server = st.selectbox(
                    "E-posta Sağlayıcısı",
                    ["smtp.gmail.com", "smtp.yandex.com", "smtp.outlook.com", "Diğer"]
                )
                if smtp_server == "Diğer":
                    smtp_server = st.text_input("SMTP Sunucu Adresi")
                smtp_port = st.number_input("Port", value=465, min_value=1, max_value=9999)
                gonderen = st.text_input("Gönderen E-posta", placeholder="sizin@gmail.com")
                sifre = st.text_input("Uygulama Şifresi", type="password",
                    help="Gmail için: Google Hesabı > Güvenlik > Uygulama Şifreleri")
                konu = st.text_input("E-posta Konusu",
                    value=st.session_state.get('bulten_baslik', 'Haftalık Emlak Bülteni'))

            with col2:
                st.markdown("#### 👥 Alıcılar")

                # Müşteri listesinden otomatik çek
                if st.session_state.get('musteriler'):
                    musteri_emailler = [
                        m['eposta'] for m in st.session_state['musteriler']
                        if m.get('eposta') and '@' in m.get('eposta', '')
                    ]
                    if musteri_emailler:
                        st.markdown(f"**Portföydeki müşteriler ({len(musteri_emailler)} kişi):**")
                        portfoy_sec = st.multiselect(
                            "Müşterilerden seçin:",
                            options=musteri_emailler,
                            default=musteri_emailler
                        )
                    else:
                        portfoy_sec = []
                        st.info("ℹ️ Müşteri portföyünde e-posta adresi bulunamadı.")
                else:
                    portfoy_sec = []

                ek_alicilar_txt = st.text_area(
                    "Ek Alıcılar (her satıra bir e-posta)",
                    placeholder="musteri1@email.com\nmusteri2@email.com",
                    height=120
                )
                ek_alicilar = [e.strip() for e in ek_alicilar_txt.strip().splitlines() if '@' in e]
                tum_alicilar = list(set(portfoy_sec + ek_alicilar))

                if tum_alicilar:
                    st.success(f"📬 Toplam **{len(tum_alicilar)}** alıcıya gönderilecek.")
                else:
                    st.warning("⚠️ En az bir alıcı ekleyin.")

            st.divider()

            if st.button("📤 Bülteni Gönder", type="primary", disabled=not tum_alicilar):
                if not gonderen or not sifre:
                    st.error("❌ Gönderen e-posta ve şifre zorunludur.")
                else:
                    html_icerik = html_bulten_olustur(
                        st.session_state.get('bulten_metni_son', st.session_state.get('bulten_metni', '')),
                        st.session_state.get('bulten_baslik', '')
                    )
                    with st.spinner(f"📤 {len(tum_alicilar)} alıcıya gönderiliyor..."):
                        basari, mesaj = email_gonder(
                            smtp_server, smtp_port, gonderen, sifre,
                            tum_alicilar, konu, html_icerik
                        )
                    if basari:
                        st.success(mesaj)
                        st.balloons()
                    else:
                        st.error(mesaj)
                        st.markdown("""
                        <div class="info-box">
                        💡 <b>Gmail kullanıyorsanız:</b> Normal şifreniz değil, <b>Uygulama Şifresi</b> gereklidir.
                        Google Hesabı → Güvenlik → 2 Adımlı Doğrulama → Uygulama Şifreleri
                        </div>
                        """, unsafe_allow_html=True)


# --- ALT BİLGİ ---
st.markdown("---")
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    st.caption("🏠 EmlakBot | Yapay Zeka Destekli Emlak Asistanı")
with col_f2:
    st.caption("⚡ GPT-4o + Streamlit")
with col_f3:
    st.caption("🔒 Verileriniz model eğitimi için kullanılmaz")
