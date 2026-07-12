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
                
                # Pemetaan khusus untuk DB_NAME -> database
                if key == "DB_NAME" and "database" in sec:
                    return str(sec["database"])
                    
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
                sentimen_akhir ENUM('Positif', 'Netral', 'Negatif'),
                jenis_reservasi VARCHAR(50) DEFAULT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        # Backward-compatible: tambahkan kolom jika tabel sudah ada tapi kolom belum
        try:
            cursor.execute("""
                ALTER TABLE guest_feedback
                ADD COLUMN jenis_reservasi VARCHAR(50) DEFAULT NULL
            """)
        except mysql.connector.Error:
            pass  # Kolom sudah ada, abaikan error
        conn.commit()
        conn.close()
    except Exception as e:
        config_host = DB_CONFIG.get('host', 'unknown')
        st.error(f"⚠️ **Gagal terhubung ke Database MySQL (Host: {config_host})!**\n\nDetail Error: `{e}`\n\nPastikan pengaturan Secrets di Streamlit Cloud sudah benar.")
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
             dimensi_terdeteksi, sentimen_akhir, jenis_reservasi)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            data.get("jenis_reservasi"),
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
                     dimensi_terdeteksi, sentimen_akhir, jenis_reservasi)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    data.get("jenis_reservasi"),
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
    """Mengambil seluruh data feedback dari database."""
    try:
        conn = get_connection()
        query = "SELECT * FROM guest_feedback ORDER BY id DESC"
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except mysql.connector.Error as e:
        st.error(f"Gagal memuat data: {e}")
        return pd.DataFrame()


# ============================================================
# CUSTOM CSS — PREMIUM STYLING
# ============================================================

def inject_css():
    """Menyuntikkan CSS kustom untuk tampilan premium dark-mode."""
    st.markdown("""
    <style>
    /* ============================================================
       PREMIUM DARK-MODE DESIGN SYSTEM
       Kampung Sumber Alam — Digital Feedback System
       ============================================================ */

    /* ---------- Google Font ---------- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    /* ---------- Keyframe Animations ---------- */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
    }
    @keyframes shimmer {
        0%   { background-position: -200% center; }
        100% { background-position: 200% center; }
    }
    @keyframes pulse-glow {
        0%, 100% { box-shadow: 0 0 15px rgba(16,185,129,0.15); }
        50%      { box-shadow: 0 0 30px rgba(16,185,129,0.3); }
    }
    @keyframes float {
        0%, 100% { transform: translateY(0); }
        50%      { transform: translateY(-6px); }
    }
    @keyframes gradient-shift {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    @keyframes slide-in-left {
        from { opacity: 0; transform: translateX(-30px); }
        to   { opacity: 1; transform: translateX(0); }
    }

    /* ---------- Base ---------- */
    html, body, [class*="st-"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    /* ---------- Custom Scrollbar ---------- */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #1a1d29; }
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #10b981, #059669);
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb:hover { background: #34d399; }

    /* ---------- Sidebar — Dark Emerald Gradient ---------- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0c1a12 0%, #0f2b1a 40%, #134a2a 100%) !important;
        border-right: 1px solid rgba(16,185,129,0.15) !important;
    }
    section[data-testid="stSidebar"] * {
        color: #c8e6d5 !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stRadio label span {
        font-size: 1rem;
        font-weight: 500;
        letter-spacing: 0.2px;
    }
    /* Dropdown list text — gelap di popup */
    div[data-baseweb="popover"] li,
    div[data-baseweb="popover"] [role="option"],
    div[data-baseweb="popover"] [data-baseweb="menu"] * {
        color: #1e293b !important;
    }

    /* ---------- KPI Card — Base Style ---------- */
    .kpi-card {
        border-radius: 18px;
        padding: 26px 20px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.06);
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        transition: all 0.35s cubic-bezier(0.25, 0.8, 0.25, 1);
        animation: fadeInUp 0.6s ease-out both;
        position: relative;
        overflow: hidden;
    }
    .kpi-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        border-radius: 18px 18px 0 0;
    }
    .kpi-card:hover {
        transform: translateY(-6px) scale(1.02);
        box-shadow: 0 16px 48px rgba(0,0,0,0.4);
    }
    .kpi-icon {
        font-size: 2.2rem;
        margin-bottom: 8px;
        animation: float 3s ease-in-out infinite;
    }
    .kpi-value {
        font-size: 2.4rem;
        font-weight: 900;
        line-height: 1.2;
        letter-spacing: -0.5px;
    }
    .kpi-label {
        font-size: 0.78rem;
        font-weight: 600;
        margin-top: 6px;
        text-transform: uppercase;
        letter-spacing: 1.2px;
    }

    /* --- KPI Variant 1: Emerald (Total Ulasan) --- */
    .kpi-card.kpi-emerald {
        background: linear-gradient(145deg, #0d3320 0%, #14532d 50%, #166534 100%);
    }
    .kpi-card.kpi-emerald::before {
        background: linear-gradient(90deg, #10b981, #34d399, #6ee7b7);
    }
    .kpi-card.kpi-emerald .kpi-value {
        background: linear-gradient(135deg, #34d399, #6ee7b7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .kpi-card.kpi-emerald .kpi-label { color: #86efac; }
    .kpi-card.kpi-emerald:hover {
        box-shadow: 0 16px 48px rgba(16,185,129,0.25);
    }

    /* --- KPI Variant 2: Rose (Sentimen Negatif) --- */
    .kpi-card.kpi-rose {
        background: linear-gradient(145deg, #3b0d15 0%, #5c1a28 50%, #7f1d2e 100%);
    }
    .kpi-card.kpi-rose::before {
        background: linear-gradient(90deg, #f43f5e, #fb7185, #fda4af);
    }
    .kpi-card.kpi-rose .kpi-value {
        background: linear-gradient(135deg, #fb7185, #fda4af);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .kpi-card.kpi-rose .kpi-label { color: #fda4af; }
    .kpi-card.kpi-rose:hover {
        box-shadow: 0 16px 48px rgba(244,63,94,0.25);
    }

    /* --- KPI Variant 3: Amber (Rata-rata Rating) --- */
    .kpi-card.kpi-amber {
        background: linear-gradient(145deg, #3b2506 0%, #5c3a0e 50%, #78490e 100%);
    }
    .kpi-card.kpi-amber::before {
        background: linear-gradient(90deg, #f59e0b, #fbbf24, #fcd34d);
    }
    .kpi-card.kpi-amber .kpi-value {
        background: linear-gradient(135deg, #fbbf24, #fcd34d);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .kpi-card.kpi-amber .kpi-label { color: #fcd34d; }
    .kpi-card.kpi-amber:hover {
        box-shadow: 0 16px 48px rgba(245,158,11,0.25);
    }

    /* --- KPI Variant 4: Violet (SERVPERF) --- */
    .kpi-card.kpi-violet {
        background: linear-gradient(145deg, #2e0e4a 0%, #4c1d72 50%, #5b21b6 100%);
    }
    .kpi-card.kpi-violet::before {
        background: linear-gradient(90deg, #8b5cf6, #a78bfa, #c4b5fd);
    }
    .kpi-card.kpi-violet .kpi-value {
        background: linear-gradient(135deg, #a78bfa, #c4b5fd);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .kpi-card.kpi-violet .kpi-label { color: #c4b5fd; }
    .kpi-card.kpi-violet:hover {
        box-shadow: 0 16px 48px rgba(139,92,246,0.25);
    }

    /* --- KPI animation stagger --- */
    .kpi-card:nth-child(1) { animation-delay: 0.1s; }
    .kpi-card:nth-child(2) { animation-delay: 0.2s; }
    .kpi-card:nth-child(3) { animation-delay: 0.3s; }
    .kpi-card:nth-child(4) { animation-delay: 0.4s; }

    /* ---------- Section Header ---------- */
    .section-header {
        font-size: 1.25rem;
        font-weight: 700;
        color: #e2e8f0;
        margin: 2rem 0 1rem;
        padding-bottom: 10px;
        border-bottom: 2px solid transparent;
        border-image: linear-gradient(90deg, #10b981, #059669, transparent) 1;
        display: inline-block;
        letter-spacing: 0.3px;
    }

    /* ---------- Form Header — Hero Style ---------- */
    .form-hero {
        text-align: center;
        padding: 2rem 1rem 1.5rem;
        background: linear-gradient(135deg, rgba(16,185,129,0.08) 0%, rgba(6,78,59,0.12) 100%);
        border-radius: 20px;
        border: 1px solid rgba(16,185,129,0.15);
        margin-bottom: 1.5rem;
        animation: fadeIn 0.8s ease-out;
    }
    .form-hero .hero-icon {
        font-size: 3.2rem;
        display: block;
        margin-bottom: 8px;
        animation: float 4s ease-in-out infinite;
    }
    .form-hero h1 {
        font-size: 1.7rem;
        font-weight: 900;
        background: linear-gradient(135deg, #34d399, #10b981, #fbbf24);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: gradient-shift 4s ease infinite;
        margin: 0 0 4px;
        letter-spacing: -0.3px;
    }
    .form-hero .hero-subtitle {
        color: #94a3b8;
        font-size: 0.88rem;
        font-weight: 400;
        margin: 0;
    }
    .form-hero .hero-badge {
        display: inline-block;
        background: rgba(16,185,129,0.15);
        color: #34d399;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 4px 14px;
        border-radius: 50px;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-top: 10px;
        border: 1px solid rgba(16,185,129,0.2);
    }

    /* ---------- Form Header (legacy compat) ---------- */
    .form-header {
        text-align: center;
        padding: 1.5rem 0.5rem 0.5rem;
    }
    .form-header h1 {
        font-size: 1.6rem;
        font-weight: 800;
        background: linear-gradient(135deg, #34d399, #10b981);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .form-header p {
        color: #94a3b8;
        font-size: 0.9rem;
        margin-top: 4px;
    }

    /* ---------- Form Intro Text ---------- */
    .form-intro {
        text-align: center;
        margin-bottom: 1.2rem;
        padding: 16px 20px;
        background: rgba(16,185,129,0.05);
        border-radius: 14px;
        border: 1px solid rgba(16,185,129,0.1);
    }
    .form-intro strong {
        color: #34d399;
        font-size: 1rem;
    }
    .form-intro p {
        color: #94a3b8;
        font-size: 0.85rem;
        line-height: 1.7;
        margin: 8px 0 0;
    }

    /* ---------- Success Box ---------- */
    .success-box {
        background: linear-gradient(135deg, rgba(16,185,129,0.15), rgba(6,78,59,0.2));
        border-left: 4px solid #10b981;
        border-radius: 14px;
        padding: 24px;
        margin: 20px 0;
        text-align: center;
        animation: fadeInUp 0.5s ease-out;
        border: 1px solid rgba(16,185,129,0.2);
    }
    .success-box h3 {
        color: #34d399;
        margin: 0;
        font-size: 1.2rem;
        font-weight: 700;
    }
    .success-box p {
        color: #a7f3d0;
        margin: 6px 0 0;
        font-size: 0.92rem;
    }

    /* ---------- Star Rating ---------- */
    .star-rating-display {
        display: flex;
        gap: 6px;
        justify-content: center;
        font-size: 2.2rem;
        margin: 10px 0;
    }
    .star-filled {
        color: #fbbf24;
        filter: drop-shadow(0 0 6px rgba(251,191,36,0.4));
        transition: transform 0.2s;
    }
    .star-filled:hover { transform: scale(1.2); }
    .star-empty {
        color: #374151;
    }

    /* ---------- Likert Card ---------- */
    .likert-statement {
        background: rgba(16,185,129,0.06);
        border-left: 4px solid #10b981;
        padding: 14px 18px;
        border-radius: 0 12px 12px 0;
        margin-bottom: 10px;
        font-size: 0.88rem;
        color: #cbd5e1;
        line-height: 1.6;
        transition: all 0.3s ease;
        border: 1px solid rgba(16,185,129,0.08);
        border-left: 4px solid #10b981;
    }
    .likert-statement:hover {
        background: rgba(16,185,129,0.1);
        border-left-color: #34d399;
    }
    .likert-statement strong {
        color: #34d399;
    }

    /* ---------- Dashboard Title ---------- */
    .dash-title {
        font-size: 1.7rem;
        font-weight: 900;
        background: linear-gradient(135deg, #e2e8f0, #f8fafc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
        letter-spacing: -0.3px;
    }
    .dash-subtitle {
        color: #64748b;
        font-size: 0.88rem;
        margin-bottom: 1.5rem;
        font-weight: 400;
    }

    /* ---------- Login Card — Glassmorphism ---------- */
    .login-card {
        max-width: 440px;
        margin: 2.5rem auto;
        background: rgba(26,29,41,0.8);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-radius: 24px;
        padding: 2.5rem 2rem;
        border: 1px solid rgba(16,185,129,0.15);
        box-shadow: 0 16px 64px rgba(0,0,0,0.4), 0 0 30px rgba(16,185,129,0.08);
        text-align: center;
        animation: fadeInUp 0.6s ease-out;
    }
    .login-card h2 {
        font-size: 1.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #34d399, #10b981);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .login-card p {
        color: #94a3b8;
        font-size: 0.88rem;
        margin-bottom: 1.5rem;
    }

    /* ---------- Upload Info Box ---------- */
    .upload-info {
        background: rgba(16,185,129,0.06);
        border-left: 4px solid #10b981;
        padding: 16px 20px;
        border-radius: 0 14px 14px 0;
        margin-bottom: 18px;
        font-size: 0.88rem;
        color: #a7f3d0;
        line-height: 1.7;
        border: 1px solid rgba(16,185,129,0.1);
        border-left: 4px solid #10b981;
    }
    .upload-info code {
        background: rgba(16,185,129,0.15);
        padding: 2px 8px;
        border-radius: 6px;
        color: #34d399;
        font-size: 0.82rem;
    }

    /* ---------- Primary Buttons ---------- */
    .stButton > button {
        background: linear-gradient(135deg, #059669, #10b981) !important;
        color: white !important;
        border: none !important;
        border-radius: 14px !important;
        padding: 0.65rem 2rem !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        letter-spacing: 0.3px !important;
        transition: all 0.35s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
        width: 100%;
        box-shadow: 0 4px 16px rgba(16,185,129,0.3) !important;
    }
    .stButton > button:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 8px 30px rgba(16,185,129,0.45) !important;
        background: linear-gradient(135deg, #047857, #059669) !important;
    }
    .stButton > button:active {
        transform: translateY(-1px) !important;
    }

    /* ---------- Admin nav button (top-right) ---------- */
    .admin-nav-btn button {
        background: transparent !important;
        color: #34d399 !important;
        border: 1.5px solid rgba(16,185,129,0.4) !important;
        border-radius: 12px !important;
        padding: 0.4rem 1.2rem !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        width: auto !important;
        box-shadow: none !important;
        letter-spacing: 0.3px !important;
    }
    .admin-nav-btn button:hover {
        background: linear-gradient(135deg, #059669, #10b981) !important;
        color: white !important;
        transform: none !important;
        box-shadow: 0 4px 16px rgba(16,185,129,0.3) !important;
        border-color: transparent !important;
    }

    /* Hide Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }

    /* ---------- Dashboard Section Card (st.container with border) ---------- */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(26,29,41,0.6) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(16,185,129,0.12) !important;
        border-radius: 20px !important;
        padding: 20px 24px !important;
        margin: 16px 0 !important;
        box-shadow: 0 8px 32px rgba(0,0,0,0.25) !important;
        transition: border-color 0.3s ease !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: rgba(16,185,129,0.25) !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] > div,
    div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] {
        background: transparent !important;
    }

    /* ---------- DSS Recommendation Card ---------- */
    .dss-card {
        background: linear-gradient(135deg, rgba(245,158,11,0.08), rgba(217,119,6,0.12));
        border: 1px solid rgba(245,158,11,0.2);
        border-radius: 16px;
        padding: 20px 24px;
        margin: 8px 0;
        animation: slide-in-left 0.5s ease-out;
    }
    .dss-card .dss-badge {
        display: inline-block;
        background: rgba(245,158,11,0.2);
        color: #fbbf24;
        font-size: 0.7rem;
        font-weight: 700;
        padding: 3px 12px;
        border-radius: 50px;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-bottom: 10px;
    }
    .dss-card .dss-dim-name {
        font-size: 1.1rem;
        font-weight: 700;
        color: #fbbf24;
        margin-bottom: 6px;
    }
    .dss-card .dss-score {
        font-size: 0.85rem;
        color: #fcd34d;
        margin-bottom: 10px;
    }
    .dss-card .dss-text {
        font-size: 0.88rem;
        color: #e2e8f0;
        line-height: 1.6;
    }

    /* ---------- Score Indicator Row ---------- */
    .score-row {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 6px 0;
        font-size: 0.82rem;
        color: #cbd5e1;
    }
    .score-bar-track {
        flex: 1;
        height: 8px;
        background: rgba(255,255,255,0.06);
        border-radius: 10px;
        overflow: hidden;
    }
    .score-bar-fill {
        height: 100%;
        border-radius: 10px;
        transition: width 0.8s cubic-bezier(0.25, 0.8, 0.25, 1);
    }

    /* ---------- Divider Decoration ---------- */
    .section-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(16,185,129,0.3), transparent);
        margin: 2rem 0;
        border: none;
    }

    /* ---------- Form field labels (dark mode) ---------- */
    .stTextInput label, .stTextArea label, .stDateInput label,
    .stRadio label, .stSelectbox label, .stFileUploader label {
        color: #e2e8f0 !important;
        font-weight: 600 !important;
    }
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

