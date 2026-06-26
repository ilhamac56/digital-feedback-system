"""
Digital Feedback System & Monitoring Dashboard
Kampung Sumber Alam Resort
=============================================
Sistem ulasan tamu berbasis web dengan analisis sentimen lexicon-based
dan dashboard monitoring untuk admin.

Jalankan: streamlit run app.py
"""

import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
import re
import os
import base64

# ============================================================
# KONFIGURASI HALAMAN
# ============================================================
st.set_page_config(
    page_title="Kampung Sumber Alam - Feedback System",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="auto",
)

# ============================================================
# SESSION STATE DEFAULTS
# ============================================================
if "page" not in st.session_state:
    st.session_state.page = "form"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ============================================================
# ============================================================
# DATABASE SETUP (MySQL — lokal via Laragon / cloud via Secrets)
# ============================================================

def _get_secret(key: str, default: str = "") -> str:
    """
    Ambil konfigurasi dari environment variable terlebih dahulu,
    lalu fallback ke st.secrets (Streamlit Cloud), lalu default.
    Default value = konfigurasi Laragon lokal.
    """
    # 1. Environment variable (Railway, Render, VPS, dll.)
    val = os.environ.get(key)
    if val:
        return val

    # 2. Streamlit secrets (Streamlit Community Cloud)
    try:
        if hasattr(st, "secrets") and "database" in st.secrets:
            return str(st.secrets["database"].get(key, default))
    except Exception:
        pass

    return default


DB_CONFIG = {
    "host": _get_secret("DB_HOST", "127.0.0.1"),
    "port": int(_get_secret("DB_PORT", "3306")),
    "user": _get_secret("DB_USER", "root"),
    "password": _get_secret("DB_PASSWORD", ""),
    "database": _get_secret("DB_NAME", "digital_feedback_system"),
    "charset": "utf8mb4",
    "use_pure": True,
}


def get_connection():
    """Membuat koneksi ke database MySQL (lokal atau cloud dengan SSL)."""
    config = DB_CONFIG.copy()
    host = config.get("host", "127.0.0.1")

    # Aktifkan SSL jika koneksi bukan ke localhost (cloud database)
    if host not in ("127.0.0.1", "localhost", "::1"):
        config["ssl_disabled"] = False
        # Coba gunakan certifi CA bundle jika tersedia
        try:
            import certifi
            config["ssl_ca"] = certifi.where()
        except ImportError:
            # Tanpa certifi, gunakan ssl_verify_cert=False
            config["ssl_verify_cert"] = False
            config["ssl_verify_identity"] = False

    conn = mysql.connector.connect(**config)
    return conn


def init_database():
    """Inisialisasi tabel guest_feedback jika belum ada."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guest_feedback (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tanggal DATE DEFAULT (CURDATE()),
                nama_tamu VARCHAR(255) NOT NULL,
                rating_bintang TINYINT NOT NULL CHECK(rating_bintang BETWEEN 1 AND 5),
                q1_tangibles TINYINT NOT NULL CHECK(q1_tangibles BETWEEN 1 AND 5),
                q2_reliability TINYINT NOT NULL CHECK(q2_reliability BETWEEN 1 AND 5),
                q3_responsiveness TINYINT NOT NULL CHECK(q3_responsiveness BETWEEN 1 AND 5),
                q4_assurance TINYINT NOT NULL CHECK(q4_assurance BETWEEN 1 AND 5),
                q5_empathy TINYINT NOT NULL CHECK(q5_empathy BETWEEN 1 AND 5),
                teks_ulasan TEXT,
                dimensi_terdeteksi VARCHAR(500),
                sentimen_akhir ENUM('Positif', 'Netral', 'Negatif')
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"⚠️ **Gagal terhubung ke Database MySQL!**\n\nSistem sedang mengalami gangguan koneksi. Mohon hubungi administrator.")
        st.stop()


# ============================================================
# NLP / TEXT PROCESSING  (MODULAR)
# ============================================================

# --- Kamus Kata Kunci ---
DIMENSION_KEYWORDS = {
    "Tangibles": ["kamar", "bersih", "kotor", "fasilitas", "ac", "air", "handuk", "bau", "luas"],
    "Reliability": ["janji", "sesuai", "nilai", "harga", "pesan", "jadwal"],
    "Responsiveness": ["cepat", "lambat", "sigap", "respon", "lama", "tunggu", "jam"],
    "Assurance": ["aman", "nyaman", "ramah", "sopan", "ketus", "satpam"],
    "Empathy": ["perhatian", "peduli", "bantu", "personal", "senyum"],
}

POSITIVE_KEYWORDS = [
    "bersih", "ramah", "cepat", "nyaman", "bagus", "enak", "sigap", "sopan",
    "puas", "memuaskan", "mantap", "indah", "asri", "sejuk", "tenang",
    "menyenangkan", "terbaik", "recommended", "rekomen", "suka", "senang",
    "lezat", "wangi", "terawat", "rapi", "luas", "membantu", "responsif",
]
NEGATIVE_KEYWORDS = [
    "kotor", "lambat", "bau", "lama", "ketus", "buruk", "mahal", "mati", "keras",
    "kurang", "kecewa", "mengecewakan", "jelek", "rusak", "bocor", "sempit",
    "berisik", "ribut", "bising", "jorok", "lecek", "kusam", "lusuh",
    "gelap", "pengap", "lembab", "apek", "payah", "parah",
    "komplain", "keluhan", "ganggu", "terganggu", "susah", "sulit", "ribet",
    "kumuh", "dekil", "buluk", "ancur", "hancur", "sampah",
    "kecil", "semrawut", "berantakan", "tua", "usang",
    "mengecewakan", "rugi", "menyesal", "protes",
    "tidak", "tdk", "gak", "nggak",
]

STOPWORDS_ID = {"di", "ke", "dari", "yang", "dan", "atau", "tapi"}


def _preprocess_text(text: str) -> list[str]:
    """
    Pra-pemrosesan teks ulasan:
    1. Case folding (lowercase)
    2. Cleansing (hapus tanda baca & angka)
    3. Tokenization (split by space)
    4. Stopword removal (kata hubung dasar Bahasa Indonesia)
    Tanpa stemming.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return []

    # 1. Case Folding
    text = text.lower()

    # 2. Cleansing — hanya sisakan alfabet dan spasi
    text = re.sub(r"[^a-z\s]", "", text)

    # 3. Tokenization
    tokens = text.split()

    # 4. Stopword Removal
    tokens = [t for t in tokens if t not in STOPWORDS_ID]

    return tokens


def _classify_dimensions(tokens: list[str]) -> list[str]:
    """Deteksi dimensi SERVPERF berdasarkan keyword matching."""
    detected = []
    for dimension, keywords in DIMENSION_KEYWORDS.items():
        if any(token in keywords for token in tokens):
            detected.append(dimension)
    return detected


def _classify_sentiment(tokens: list[str], rating: int) -> str:
    """
    Klasifikasi sentimen berdasarkan heuristik kata kunci
    dan rating override rule.
    """
    pos_count = sum(1 for t in tokens if t in POSITIVE_KEYWORDS)
    neg_count = sum(1 for t in tokens if t in NEGATIVE_KEYWORDS)

    # Jika ada kata negatif → langsung Negatif
    if neg_count > 0:
        sentiment = "Negatif"
    elif pos_count > 0:
        sentiment = "Positif"
    else:
        sentiment = "Netral"

    # RATING OVERRIDE RULE
    if rating <= 2:
        sentiment = "Negatif"
    elif rating == 3 and sentiment == "Positif":
        sentiment = "Netral"

    return sentiment


def analyze_feedback(teks: str, rating_bintang: int) -> tuple[str, str]:
    """
    Fungsi modular utama untuk analisis feedback.
    Digunakan oleh form tamu (manual) maupun upload Excel (batch).

    Args:
        teks: Teks ulasan dari tamu.
        rating_bintang: Rating bintang (1-5).

    Returns:
        Tuple (dimensi_terdeteksi, sentimen_akhir)
    """
    tokens = _preprocess_text(teks)
    dimensions = _classify_dimensions(tokens)
    sentiment = _classify_sentiment(tokens, rating_bintang)

    dim_str = ", ".join(dimensions) if dimensions else "Tidak Terdeteksi"
    return dim_str, sentiment


# ============================================================
# DATABASE OPERATIONS
# ============================================================

def insert_feedback(data: dict) -> bool:
    """Menyimpan data feedback ke database. Mengembalikan True jika sukses."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO guest_feedback
            (tanggal, nama_tamu, rating_bintang,
             q1_tangibles, q2_reliability, q3_responsiveness,
             q4_assurance, q5_empathy, teks_ulasan,
             dimensi_terdeteksi, sentimen_akhir)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data["tanggal"],
            data["nama_tamu"],
            data["rating_bintang"],
            data["q1_tangibles"],
            data["q2_reliability"],
            data["q3_responsiveness"],
            data["q4_assurance"],
            data["q5_empathy"],
            data["teks_ulasan"],
            data["dimensi_terdeteksi"],
            data["sentimen_akhir"],
        ))
        conn.commit()
        conn.close()
        return True
    except mysql.connector.Error as e:
        st.error(f"Gagal menyimpan data: {e}")
        return False


def insert_feedback_batch(rows: list[dict]) -> int:
    """
    Menyimpan banyak feedback sekaligus (batch insert).
    Returns: jumlah baris yang berhasil disimpan.
    """
    success_count = 0
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for data in rows:
            try:
                cursor.execute("""
                    INSERT INTO guest_feedback
                    (tanggal, nama_tamu, rating_bintang,
                     q1_tangibles, q2_reliability, q3_responsiveness,
                     q4_assurance, q5_empathy, teks_ulasan,
                     dimensi_terdeteksi, sentimen_akhir)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    data["tanggal"],
                    data["nama_tamu"],
                    data["rating_bintang"],
                    data["q1_tangibles"],
                    data["q2_reliability"],
                    data["q3_responsiveness"],
                    data["q4_assurance"],
                    data["q5_empathy"],
                    data["teks_ulasan"],
                    data["dimensi_terdeteksi"],
                    data["sentimen_akhir"],
                ))
                success_count += 1
            except mysql.connector.Error:
                continue  # Skip baris yang error, lanjutkan yang lain
        conn.commit()
        conn.close()
    except mysql.connector.Error as e:
        st.error(f"Gagal koneksi database: {e}")
    return success_count


def load_all_feedback() -> pd.DataFrame:
    """Memuat seluruh data feedback dari database ke DataFrame."""
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM guest_feedback ORDER BY id DESC", conn)
        conn.close()
        return df
    except mysql.connector.Error as e:
        st.error(f"Gagal memuat data: {e}")
        return pd.DataFrame()


# ============================================================
# CUSTOM CSS — PREMIUM STYLING
# ============================================================

def inject_css():
    """Menyuntikkan CSS kustom untuk tampilan premium."""
    st.markdown("""
    <style>
    /* ---------- Google Font ---------- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="st-"] {
        font-family: 'Inter', sans-serif;
    }

    /* ---------- Mobile-friendly form ---------- */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #145a32 0%, #1e8449 50%, #27ae60 100%);
    }
    section[data-testid="stSidebar"] * {
        color: #e0e0e0 !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stRadio label span {
        font-size: 1.05rem;
        font-weight: 500;
    }

    /* ---------- KPI Card ---------- */
    .kpi-card {
        background: linear-gradient(135deg, #ffffff 0%, #f0f4f8 100%);
        border-radius: 16px;
        padding: 24px 20px;
        text-align: center;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.06);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.12);
    }
    .kpi-icon { font-size: 2rem; margin-bottom: 6px; }
    .kpi-value {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1e8449, #2ecc71);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.2;
    }
    .kpi-label {
        font-size: 0.85rem;
        color: #64748b;
        font-weight: 500;
        margin-top: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* ---------- Section Header ---------- */
    .section-header {
        font-size: 1.3rem;
        font-weight: 700;
        color: #1e293b;
        margin: 2rem 0 1rem;
        padding-bottom: 8px;
        border-bottom: 3px solid #2ecc71;
        display: inline-block;
    }

    /* ---------- Form Header ---------- */
    .form-header {
        text-align: center;
        padding: 1.5rem 0.5rem 0.5rem;
    }
    .form-header h1 {
        font-size: 1.6rem;
        font-weight: 800;
        background: linear-gradient(135deg, #145a32, #27ae60);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .form-header p {
        color: #64748b;
        font-size: 0.9rem;
        margin-top: 4px;
    }

    /* ---------- Success Box ---------- */
    .success-box {
        background: linear-gradient(135deg, #d4edda, #c3e6cb);
        border-left: 5px solid #28a745;
        border-radius: 12px;
        padding: 20px;
        margin: 20px 0;
        text-align: center;
    }
    .success-box h3 { color: #155724; margin: 0; }
    .success-box p { color: #155724; margin: 4px 0 0; font-size: 0.95rem; }

    /* ---------- Star Rating ---------- */
    .star-rating-display {
        display: flex;
        gap: 4px;
        justify-content: center;
        font-size: 2rem;
        margin: 8px 0;
    }
    .star-filled { color: #f59e0b; }
    .star-empty { color: #d1d5db; }

    /* ---------- Likert Label ---------- */
    .likert-statement {
        background: #f0fdf4;
        border-left: 4px solid #27ae60;
        padding: 12px 16px;
        border-radius: 0 10px 10px 0;
        margin-bottom: 8px;
        font-size: 0.9rem;
        color: #334155;
        line-height: 1.5;
    }

    /* ---------- Dashboard Title ---------- */
    .dash-title {
        font-size: 1.6rem;
        font-weight: 800;
        color: #1e293b;
        margin-bottom: 0.2rem;
    }
    .dash-subtitle {
        color: #94a3b8;
        font-size: 0.9rem;
        margin-bottom: 1.5rem;
    }

    /* ---------- Login Card ---------- */
    .login-card {
        max-width: 420px;
        margin: 3rem auto;
        background: linear-gradient(135deg, #ffffff 0%, #f0f4f8 100%);
        border-radius: 20px;
        padding: 2.5rem 2rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 8px 40px rgba(0,0,0,0.08);
        text-align: center;
    }
    .login-card h2 {
        font-size: 1.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #145a32, #27ae60);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .login-card p {
        color: #64748b;
        font-size: 0.9rem;
        margin-bottom: 1.5rem;
    }

    /* ---------- Upload Info Box ---------- */
    .upload-info {
        background: #f0fdf4;
        border-left: 4px solid #27ae60;
        padding: 14px 18px;
        border-radius: 0 10px 10px 0;
        margin-bottom: 16px;
        font-size: 0.9rem;
        color: #145a32;
        line-height: 1.6;
    }

    /* ---------- Misc Buttons ---------- */
    .stButton > button {
        background: linear-gradient(135deg, #1e8449, #27ae60) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.6rem 2rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
        width: 100%;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(39,174,96,0.35) !important;
    }

    /* ---------- Admin nav button (top-right) ---------- */
    .admin-nav-btn button {
        background: transparent !important;
        color: #1e8449 !important;
        border: 2px solid #27ae60 !important;
        border-radius: 10px !important;
        padding: 0.35rem 1.2rem !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        width: auto !important;
    }
    .admin-nav-btn button:hover {
        background: linear-gradient(135deg, #1e8449, #27ae60) !important;
        color: white !important;
        transform: none !important;
        box-shadow: none !important;
    }

    /* Hide Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# NAVIGASI HELPER
# ============================================================

def go_to(page: str):
    """Ubah halaman aktif di session state."""
    st.session_state.page = page


def do_logout():
    """Reset sesi login dan kembali ke form."""
    st.session_state.logged_in = False
    st.session_state.page = "form"


# ============================================================
# HALAMAN: FORM ULASAN TAMU (MOBILE-FRIENDLY)
# ============================================================

def page_guest_form():
    """Render halaman form input ulasan untuk tamu (mobile-like di layar wide)."""
    inject_css()

    # --- Trik layout: bungkus form di kolom tengah agar menyerupai layar HP ---
    col_kiri, col_tengah, col_kanan = st.columns([1, 2, 1])

    with col_tengah:

        # --- Header dengan tombol admin yang lega ---
        col_header_teks, col_header_tombol = st.columns([3, 2])
        with col_header_teks:
            st.markdown("""
            <div class="form-header" style="text-align:left;padding:1rem 0 0.5rem;">
                <h1>🏨 Kampung Sumber Alam</h1>
                <p>Form Ulasan Tamu</p>
            </div>
            """, unsafe_allow_html=True)
        with col_header_tombol:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="admin-nav-btn">', unsafe_allow_html=True)
            if st.button("🔒 Dashboard Admin", key="btn_go_admin", use_container_width=True):
                go_to("login")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.caption("Bantu kami meningkatkan layanan dengan feedback Anda")
        st.divider()

        # --- Form (semua elemen tersusun VERTIKAL, mobile-friendly) ---
        with st.form("feedback_form", clear_on_submit=True):

            # Nama Tamu
            st.markdown("##### 👤 Nama Lengkap")
            nama = st.text_input(
                "Nama Lengkap",
                placeholder="Masukkan nama lengkap Anda",
                label_visibility="collapsed",
            )

            # Tanggal Menginap
            st.markdown("##### 📅 Tanggal Menginap")
            tanggal_menginap = st.date_input(
                "Tanggal Menginap",
                value=date.today(),
                max_value=date.today(),
                label_visibility="collapsed",
                key="tanggal_menginap",
            )

            st.markdown("---")

            # Star Rating — radio horizontal
            st.markdown("##### ⭐ Rating Keseluruhan")
            st.caption("Berikan penilaian keseluruhan pengalaman Anda (1 = Sangat Buruk, 5 = Sangat Baik)")
            rating = st.radio(
                "Rating Bintang",
                options=[1, 2, 3, 4, 5],
                index=2,
                horizontal=True,
                label_visibility="collapsed",
                key="rating_radio",
            )
            # Tampilkan bintang visual
            stars_html = "".join(
                ['<span class="star-filled">★</span>' if i < rating else '<span class="star-empty">★</span>'
                 for i in range(5)]
            )
            st.markdown(f'<div class="star-rating-display">{stars_html}</div>', unsafe_allow_html=True)

            st.markdown("---")

            # 5 Pertanyaan SERVPERF — radio horizontal, full-width vertikal
            st.markdown("##### 📋 Evaluasi Layanan (Skala 1–5)")
            st.caption("Pilih angka 1 (Sangat Tidak Setuju) hingga 5 (Sangat Setuju)")

            likert_questions = {
                "q1_tangibles": (
                    "Kebersihan & Fasilitas Kamar",
                    "Kamar, estetika bangunan, dan fasilitas fisik di resor ini sangat bersih "
                    "dan nyaman untuk digunakan."
                ),
                "q2_reliability": (
                    "Kesesuaian Layanan & Biaya",
                    "Fasilitas dan layanan yang saya terima sejak kedatangan sudah sesuai "
                    "dengan apa yang dijanjikan."
                ),
                "q3_responsiveness": (
                    "Kecepatan & Kesigapan Staf",
                    "Staf resor sangat cepat dan sigap dalam merespons serta melayani setiap "
                    "permintaan saya."
                ),
                "q4_assurance": (
                    "Kenyamanan & Keamanan",
                    "Keramahan dan kesopanan staf, serta jaminan keamanan di resor ini membuat "
                    "saya merasa sangat nyaman."
                ),
                "q5_empathy": (
                    "Perhatian Personal Staf",
                    "Staf resor memberikan perhatian khusus yang ramah dan sangat memahami "
                    "kebutuhan personal saya selama menginap."
                ),
            }

            likert_values = {}
            for key, (dim_name, statement) in likert_questions.items():
                st.markdown(
                    f'<div class="likert-statement"><strong>{dim_name}</strong><br>{statement}</div>',
                    unsafe_allow_html=True,
                )
                likert_values[key] = st.radio(
                    dim_name,
                    options=[1, 2, 3, 4, 5],
                    index=2,
                    horizontal=True,
                    label_visibility="collapsed",
                    key=key,
                )

            st.markdown("---")

            # Teks Ulasan
            st.markdown("##### 💬 Ulasan Anda")
            ulasan = st.text_area(
                "Ulasan",
                placeholder="Tuliskan keluhan atau pujian spesifik Anda di sini...",
                height=120,
                label_visibility="collapsed",
            )

            st.markdown("")  # spacing

            # Tombol Kirim
            submitted = st.form_submit_button("🚀 Kirim Ulasan", use_container_width=True)

        # --- Pemrosesan setelah submit ---
        if submitted:
            # Validasi input dasar
            if not nama or not nama.strip():
                st.warning("⚠️ Silakan masukkan nama lengkap Anda.")
                return

            # Proses NLP menggunakan fungsi modular
            dimensi, sentimen = analyze_feedback(ulasan, rating)

            # Siapkan data
            data = {
                "tanggal": tanggal_menginap.isoformat(),
                "nama_tamu": nama.strip(),
                "rating_bintang": rating,
                "q1_tangibles": likert_values["q1_tangibles"],
                "q2_reliability": likert_values["q2_reliability"],
                "q3_responsiveness": likert_values["q3_responsiveness"],
                "q4_assurance": likert_values["q4_assurance"],
                "q5_empathy": likert_values["q5_empathy"],
                "teks_ulasan": ulasan.strip() if ulasan else "",
                "dimensi_terdeteksi": dimensi,
                "sentimen_akhir": sentimen,
            }

            # Simpan ke database
            if insert_feedback(data):
                st.markdown(f"""
                <div class="success-box">
                    <h3>✅ Terima Kasih, {nama.strip()}!</h3>
                    <p>Ulasan Anda telah berhasil disimpan. Sentimen terdeteksi: <strong>{sentimen}</strong></p>
                </div>
                """, unsafe_allow_html=True)

                st.metric("⭐ Rating", f"{rating}/5")
                st.metric("📊 Sentimen", sentimen)
                st.metric("🏷️ Dimensi", dimensi if len(dimensi) < 40 else f"{len(dimensi.split(','))} dimensi")

                st.balloons()


# ============================================================
# HALAMAN: LOGIN ADMIN
# ============================================================

# Kredensial statis
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


def page_login():
    """Render halaman login admin."""
    inject_css()

    # Centering login di layar wide
    col_l, col_c, col_r = st.columns([1, 2, 1])

    with col_c:
        st.markdown("""
        <div class="login-card">
            <span style="font-size:3rem;">🔐</span>
            <h2>Login Dashboard Admin</h2>
            <p>Masukkan kredensial untuk mengakses dashboard monitoring</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("👤 Username", placeholder="Masukkan username")
            password = st.text_input("🔑 Password", type="password", placeholder="Masukkan password")

            st.markdown("")
            btn_login = st.form_submit_button("🚀 Masuk", use_container_width=True)

        if btn_login:
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                st.session_state.logged_in = True
                st.session_state.page = "admin_dashboard"
                st.rerun()
            else:
                st.error("❌ Username atau password salah. Silakan coba lagi.")

        st.markdown("")
        if st.button("← Kembali ke Form Ulasan", key="btn_back_form"):
            go_to("form")
            st.rerun()


# ============================================================
# HALAMAN ADMIN: DASHBOARD MONITORING
# ============================================================

def page_dashboard_monitoring():
    """Render halaman dashboard monitoring (KPI, grafik, tabel)."""

    # --- Judul Dashboard ---
    st.markdown('<p class="dash-title">📊 Dashboard Monitoring Ulasan</p>', unsafe_allow_html=True)
    st.markdown('<p class="dash-subtitle">Kampung Sumber Alam — Analisis Real-time Feedback Tamu</p>',
                unsafe_allow_html=True)

    # Muat data
    df = load_all_feedback()

    if df.empty:
        st.info("📭 Belum ada data ulasan. Silakan isi form ulasan atau upload data OTA terlebih dahulu.")
        return

    # Pastikan kolom tanggal bertipe datetime untuk filtering
    df["tanggal"] = pd.to_datetime(df["tanggal"], errors="coerce")

    # ----------------------------------------------------------------
    # SIDEBAR: FILTER (ditambahkan ke sidebar yang sudah ada)
    # ----------------------------------------------------------------
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🔍 Filter Data")

        # Filter Sentimen
        sentimen_options = ["Semua"] + sorted(df["sentimen_akhir"].dropna().unique().tolist())
        filter_sentimen = st.selectbox("Sentimen", sentimen_options, key="filter_sentimen")

        # Filter Dimensi
        all_dimensions = set()
        for dims in df["dimensi_terdeteksi"].dropna():
            for d in dims.split(", "):
                if d.strip() and d.strip() != "Tidak Terdeteksi":
                    all_dimensions.add(d.strip())
        dimensi_options = ["Semua"] + sorted(all_dimensions)
        filter_dimensi = st.selectbox("Dimensi", dimensi_options, key="filter_dimensi")

        st.markdown("---")

        # Filter Ulasan Terbaru (berdasarkan rentang waktu)
        st.markdown("### 🕐 Ulasan Terbaru")
        filter_terbaru = st.selectbox(
            "Tampilkan ulasan dari",
            ["Semua Waktu", "Hari Ini", "7 Hari Terakhir", "30 Hari Terakhir", "90 Hari Terakhir"],
            key="filter_terbaru",
        )

    # Terapkan filter
    df_filtered = df.copy()

    if filter_sentimen != "Semua":
        df_filtered = df_filtered[df_filtered["sentimen_akhir"] == filter_sentimen]
    if filter_dimensi != "Semua":
        df_filtered = df_filtered[
            df_filtered["dimensi_terdeteksi"].str.contains(filter_dimensi, na=False)
        ]

    # Filter berdasarkan waktu
    today = pd.Timestamp(date.today())
    if filter_terbaru == "Hari Ini":
        df_filtered = df_filtered[df_filtered["tanggal"] >= today]
    elif filter_terbaru == "7 Hari Terakhir":
        df_filtered = df_filtered[df_filtered["tanggal"] >= today - timedelta(days=7)]
    elif filter_terbaru == "30 Hari Terakhir":
        df_filtered = df_filtered[df_filtered["tanggal"] >= today - timedelta(days=30)]
    elif filter_terbaru == "90 Hari Terakhir":
        df_filtered = df_filtered[df_filtered["tanggal"] >= today - timedelta(days=90)]

    # ----------------------------------------------------------------
    # KPI CARDS — menggunakan seluruh data (tanpa filter)
    # ----------------------------------------------------------------
    st.markdown('<p class="section-header">📈 Key Performance Indicators</p>', unsafe_allow_html=True)

    total_ulasan = len(df)
    pct_negatif = (
        (df["sentimen_akhir"] == "Negatif").sum() / total_ulasan * 100
        if total_ulasan > 0 else 0
    )
    avg_rating = df["rating_bintang"].mean() if total_ulasan > 0 else 0
    avg_servperf = (
        df[["q1_tangibles", "q2_reliability", "q3_responsiveness",
            "q4_assurance", "q5_empathy"]].mean().mean()
        if total_ulasan > 0 else 0
    )

    k1, k2, k3, k4 = st.columns(4)

    with k1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon">📝</div>
            <div class="kpi-value">{total_ulasan}</div>
            <div class="kpi-label">Total Ulasan</div>
        </div>
        """, unsafe_allow_html=True)

    with k2:
        color_neg = "#e74c3c" if pct_negatif > 30 else "#f39c12" if pct_negatif > 15 else "#2ecc71"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon">⚠️</div>
            <div class="kpi-value" style="background:none;-webkit-text-fill-color:{color_neg};">{pct_negatif:.1f}%</div>
            <div class="kpi-label">Sentimen Negatif</div>
        </div>
        """, unsafe_allow_html=True)

    with k3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon">⭐</div>
            <div class="kpi-value">{avg_rating:.2f}</div>
            <div class="kpi-label">Rata-rata Rating</div>
        </div>
        """, unsafe_allow_html=True)

    with k4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon">📊</div>
            <div class="kpi-value">{avg_servperf:.2f}</div>
            <div class="kpi-label">Rata-rata SERVPERF</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ----------------------------------------------------------------
    # GRAFIK — berdampingan [3, 2] agar bar chart lebih lebar
    # ----------------------------------------------------------------
    chart_col1, chart_col2 = st.columns([3, 2], gap="large")

    # --- Bar Chart: Rata-rata Skor Dimensi ---
    with chart_col1:
        st.markdown('<p class="section-header">📊 Rata-rata Skor per Dimensi SERVPERF</p>',
                    unsafe_allow_html=True)

        dim_means = pd.DataFrame({
            "Dimensi": ["Q1 Tangibles", "Q2 Reliability", "Q3 Responsiveness",
                         "Q4 Assurance", "Q5 Empathy"],
            "Rata-rata": [
                df["q1_tangibles"].mean(),
                df["q2_reliability"].mean(),
                df["q3_responsiveness"].mean(),
                df["q4_assurance"].mean(),
                df["q5_empathy"].mean(),
            ]
        })

        colors = ["#145a32", "#1e8449", "#27ae60", "#2ecc71", "#82e0aa"]
        fig_bar = px.bar(
            dim_means,
            x="Dimensi",
            y="Rata-rata",
            color="Dimensi",
            color_discrete_sequence=colors,
            text_auto=".2f",
        )
        fig_bar.update_layout(
            height=450,
            yaxis_range=[0, 5.5],
            yaxis_title="Skor Rata-rata (1–5)",
            xaxis_title="",
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", size=13),
            margin=dict(t=30, b=60, l=50, r=30),
            bargap=0.3,
        )
        fig_bar.update_traces(
            textposition="outside",
            marker_line_width=0,
            marker_cornerradius=8,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- Donut Chart: Distribusi Sentimen ---
    with chart_col2:
        st.markdown('<p class="section-header">🎯 Distribusi Sentimen</p>', unsafe_allow_html=True)

        sentimen_counts = df["sentimen_akhir"].value_counts().reset_index()
        sentimen_counts.columns = ["Sentimen", "Jumlah"]

        color_map = {"Positif": "#2ecc71", "Netral": "#f39c12", "Negatif": "#e74c3c"}
        fig_donut = px.pie(
            sentimen_counts,
            names="Sentimen",
            values="Jumlah",
            hole=0.55,
            color="Sentimen",
            color_discrete_map=color_map,
        )
        fig_donut.update_traces(
            textinfo="label+percent",
            textposition="outside",
            textfont_size=12,
            pull=[0.03] * len(sentimen_counts),
        )
        fig_donut.update_layout(
            height=450,
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", size=12),
            margin=dict(t=30, b=30, l=60, r=40),
            annotations=[
                dict(
                    text=f"<b>{total_ulasan}</b><br>Ulasan",
                    x=0.5, y=0.5,
                    font_size=15,
                    showarrow=False,
                    font=dict(family="Inter", color="#1e293b"),
                )
            ],
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    # ----------------------------------------------------------------
    # TABEL DATA — termasuk kolom X1–X5
    # ----------------------------------------------------------------
    st.markdown('<p class="section-header">📋 Data Ulasan Tamu</p>', unsafe_allow_html=True)

    active_filters = []
    if filter_sentimen != "Semua":
        active_filters.append(f"Sentimen={filter_sentimen}")
    if filter_dimensi != "Semua":
        active_filters.append(f"Dimensi={filter_dimensi}")
    if filter_terbaru != "Semua Waktu":
        active_filters.append(f"Waktu={filter_terbaru}")

    if active_filters:
        st.caption(
            f"🔎 Menampilkan {len(df_filtered)} dari {total_ulasan} ulasan "
            f"(Filter: {', '.join(active_filters)})"
        )
    else:
        st.caption(f"Menampilkan seluruh {total_ulasan} ulasan")

    # Pilih & rename kolom untuk tampilan
    display_cols = {
        "tanggal": "Tanggal",
        "nama_tamu": "Nama Tamu",
        "rating_bintang": "Rating Bintang",
        "q1_tangibles": "X1 Tangibles",
        "q2_reliability": "X2 Reliability",
        "q3_responsiveness": "X3 Responsiveness",
        "q4_assurance": "X4 Assurance",
        "q5_empathy": "X5 Empathy",
        "dimensi_terdeteksi": "Dimensi Terdeteksi",
        "sentimen_akhir": "Sentimen",
        "teks_ulasan": "Teks Ulasan",
    }
    df_display = df_filtered[list(display_cols.keys())].rename(columns=display_cols)

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=400,
        column_config={
            "Tanggal": st.column_config.DateColumn(format="DD MMM YYYY"),
            "Rating Bintang": st.column_config.NumberColumn(format="%d ⭐"),
            "X1 Tangibles": st.column_config.NumberColumn(format="%d"),
            "X2 Reliability": st.column_config.NumberColumn(format="%d"),
            "X3 Responsiveness": st.column_config.NumberColumn(format="%d"),
            "X4 Assurance": st.column_config.NumberColumn(format="%d"),
            "X5 Empathy": st.column_config.NumberColumn(format="%d"),
            "Sentimen": st.column_config.TextColumn(width="small"),
        },
    )


# ============================================================
# HALAMAN ADMIN: UPLOAD DATA OTA
# ============================================================

def page_upload_ota():
    """Render halaman upload data OTA dari file Excel."""

    st.markdown('<p class="dash-title">📤 Unggah Data Ekstraksi OTA</p>', unsafe_allow_html=True)
    st.markdown('<p class="dash-subtitle">Impor data ulasan dari platform OTA ke dalam sistem</p>',
                unsafe_allow_html=True)

    # Informasi format yang diharapkan
    st.markdown("""
    <div class="upload-info">
        <strong>📋 Format kolom Excel yang diharapkan:</strong><br>
        <code>Tanggal | Nama | Rating | Q1 | Q2 | Q3 | Q4 | Q5 | Ulasan</code><br><br>
        <strong>Keterangan:</strong><br>
        • <strong>Tanggal</strong> — Format tanggal (YYYY-MM-DD atau DD/MM/YYYY)<br>
        • <strong>Nama</strong> — Nama tamu (teks)<br>
        • <strong>Rating</strong> — Rating bintang (angka 1–5)<br>
        • <strong>Q1–Q5</strong> — Skor dimensi Tangibles, Reliability, Responsiveness, Assurance, Empathy (angka 1–5)<br>
        • <strong>Ulasan</strong> — Teks ulasan tamu
    </div>
    """, unsafe_allow_html=True)

    # File uploader
    uploaded_file = st.file_uploader(
        "Pilih file Excel (.xlsx)",
        type=["xlsx"],
        key="ota_upload",
        help="Hanya menerima file berformat .xlsx",
    )

    if uploaded_file is not None:
        try:
            df_upload = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"❌ Gagal membaca file Excel: {e}")
            return

        # Validasi jumlah kolom minimal
        if df_upload.shape[1] < 9:
            st.error(
                f"❌ File harus memiliki minimal 9 kolom "
                f"(Tanggal, Nama, Rating, Q1, Q2, Q3, Q4, Q5, Ulasan). "
                f"File Anda memiliki {df_upload.shape[1]} kolom."
            )
            return

        # Normalisasi nama kolom — ambil 9 kolom pertama
        df_upload = df_upload.iloc[:, :9]
        expected_cols = ["Tanggal", "Nama", "Rating", "Q1", "Q2", "Q3", "Q4", "Q5", "Ulasan"]
        df_upload.columns = expected_cols

        # Preview data
        st.markdown("##### 👁️ Preview Data (5 baris pertama)")
        st.dataframe(df_upload.head(), use_container_width=True, hide_index=True)
        st.caption(f"Total baris dalam file: **{len(df_upload)}**")

        st.markdown("---")

        # Tombol proses
        if st.button("⚙️ Proses & Simpan ke Database", key="btn_process_ota", use_container_width=True):
            rows_to_insert = []
            error_rows = []

            for idx, row in df_upload.iterrows():
                try:
                    # Parsing & validasi tiap baris
                    tanggal_val = pd.to_datetime(row["Tanggal"], errors="coerce")
                    tanggal_str = tanggal_val.strftime("%Y-%m-%d") if pd.notna(tanggal_val) else date.today().isoformat()

                    nama_val = str(row["Nama"]).strip() if pd.notna(row["Nama"]) else "Anonim"
                    rating_val = int(row["Rating"]) if pd.notna(row["Rating"]) else 3
                    rating_val = max(1, min(5, rating_val))  # Clamp 1-5

                    q1 = int(row["Q1"]) if pd.notna(row["Q1"]) else 3
                    q2 = int(row["Q2"]) if pd.notna(row["Q2"]) else 3
                    q3 = int(row["Q3"]) if pd.notna(row["Q3"]) else 3
                    q4 = int(row["Q4"]) if pd.notna(row["Q4"]) else 3
                    q5 = int(row["Q5"]) if pd.notna(row["Q5"]) else 3

                    # Clamp Q1-Q5 ke rentang 1-5
                    q1, q2, q3, q4, q5 = [max(1, min(5, q)) for q in [q1, q2, q3, q4, q5]]

                    ulasan_val = str(row["Ulasan"]).strip() if pd.notna(row["Ulasan"]) else ""

                    # Jalankan fungsi NLP modular
                    dimensi, sentimen = analyze_feedback(ulasan_val, rating_val)

                    rows_to_insert.append({
                        "tanggal": tanggal_str,
                        "nama_tamu": nama_val,
                        "rating_bintang": rating_val,
                        "q1_tangibles": q1,
                        "q2_reliability": q2,
                        "q3_responsiveness": q3,
                        "q4_assurance": q4,
                        "q5_empathy": q5,
                        "teks_ulasan": ulasan_val,
                        "dimensi_terdeteksi": dimensi,
                        "sentimen_akhir": sentimen,
                    })

                except Exception:
                    error_rows.append(idx + 2)  # +2 karena header + 0-index

            if rows_to_insert:
                saved = insert_feedback_batch(rows_to_insert)
                st.markdown(f"""
                <div class="success-box">
                    <h3>✅ Import Berhasil!</h3>
                    <p><strong>{saved}</strong> dari {len(df_upload)} data berhasil disimpan ke database.</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ Tidak ada data valid yang bisa diimpor.")

            if error_rows:
                st.warning(
                    f"⚠️ {len(error_rows)} baris bermasalah (baris Excel: "
                    f"{', '.join(str(r) for r in error_rows[:10])}"
                    f"{'...' if len(error_rows) > 10 else ''}). "
                    f"Baris tersebut dilewati."
                )


# ============================================================
# HALAMAN ADMIN: ROUTING INTERNAL (DASHBOARD / UPLOAD OTA)
# ============================================================

def page_admin_dashboard():
    """Render halaman admin dengan navigasi sidebar internal."""
    inject_css()

    # --- Sidebar: Branding + Menu Admin + Logout ---
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding: 1rem 0;">
            <span style="font-size:2.5rem;">🏨</span>
            <h2 style="margin:0; font-size:1.2rem; font-weight:700;">Kampung Sumber Alam</h2>
            <p style="margin:0; font-size:0.8rem; opacity:0.7;">Panel Admin</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # Menu navigasi admin
        admin_menu = st.radio(
            "📂 Menu Admin",
            ["📊 Dashboard Monitoring", "📤 Upload Data OTA"],
            label_visibility="collapsed",
            key="admin_menu",
        )

        st.markdown("---")

        if st.button("🚪 Logout", key="btn_logout", use_container_width=True):
            do_logout()
            st.rerun()

    # --- Routing halaman admin ---
    if admin_menu == "📊 Dashboard Monitoring":
        page_dashboard_monitoring()
    else:
        page_upload_ota()


# ============================================================
# MAIN — ROUTING DENGAN SESSION STATE
# ============================================================

def main():
    """Entry point aplikasi."""
    # Inisialisasi database
    init_database()

    # Routing berdasarkan session state
    current_page = st.session_state.page

    if current_page == "form":
        page_guest_form()

    elif current_page == "login":
        # Jika sudah login, langsung ke dashboard
        if st.session_state.logged_in:
            st.session_state.page = "admin_dashboard"
            st.rerun()
        else:
            page_login()

    elif current_page == "admin_dashboard":
        # Proteksi: harus sudah login
        if not st.session_state.logged_in:
            st.session_state.page = "login"
            st.rerun()
        else:
            page_admin_dashboard()

    else:
        # Fallback
        st.session_state.page = "form"
        st.rerun()


if __name__ == "__main__":
    main()
