"""
Core Utilities & Database Connections
======================================
Berisi: Konfigurasi Database, Operasi Database, CSS Helper, dan Navigasi.
Dipisahkan dari app.py untuk menghindari Circular Import.
"""

import streamlit as st
import mysql.connector
import pandas as pd
import os

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
        if hasattr(st, "secrets"):
            # Coba dari section [database] dulu
            if "database" in st.secrets:
                sec = st.secrets["database"]
                if key in sec:
                    return str(sec[key])
                # Coba key lowercase (misal: host, port, user, dll.)
                key_lower = key.replace("DB_", "").lower()
                if key_lower in sec:
                    return str(sec[key_lower])
            # Coba langsung dari root secrets (tanpa section [database])
            if key in st.secrets:
                return str(st.secrets[key])
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
                q1_reliability TINYINT NOT NULL CHECK(q1_reliability BETWEEN 1 AND 5),
                q2_assurance TINYINT NOT NULL CHECK(q2_assurance BETWEEN 1 AND 5),
                q3_tangibles TINYINT NOT NULL CHECK(q3_tangibles BETWEEN 1 AND 5),
                q4_empathy TINYINT NOT NULL CHECK(q4_empathy BETWEEN 1 AND 5),
                q5_responsiveness TINYINT NOT NULL CHECK(q5_responsiveness BETWEEN 1 AND 5),
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
             q1_reliability, q2_assurance, q3_tangibles,
             q4_empathy, q5_responsiveness, teks_ulasan,
             dimensi_terdeteksi, sentimen_akhir)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data["tanggal"],
            data["nama_tamu"],
            data["rating_bintang"],
            data["q1_reliability"],
            data["q2_assurance"],
            data["q3_tangibles"],
            data["q4_empathy"],
            data["q5_responsiveness"],
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
                     q1_reliability, q2_assurance, q3_tangibles,
                     q4_empathy, q5_responsiveness, teks_ulasan,
                     dimensi_terdeteksi, sentimen_akhir)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    data["tanggal"],
                    data["nama_tamu"],
                    data["rating_bintang"],
                    data["q1_reliability"],
                    data["q2_assurance"],
                    data["q3_tangibles"],
                    data["q4_empathy"],
                    data["q5_responsiveness"],
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

