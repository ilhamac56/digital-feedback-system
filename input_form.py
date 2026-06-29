"""
INPUT — Modul Halaman Input / Pengumpulan Data
===============================================
Berisi semua halaman yang mengumpulkan data dari pengguna:
- Form ulasan tamu (page_guest_form)
- Login admin (page_login)
- Upload data OTA dari Excel (page_upload_ota)
"""

import streamlit as st
import pandas as pd
from datetime import date

from process_nlp import analyze_feedback
from app import inject_css, go_to, insert_feedback, insert_feedback_batch


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

        st.markdown("""
        <div style="text-align: center; margin-bottom: 1rem; color: #1e8449; font-size: 0.85rem; line-height: 1.5;">
            <strong style="font-size: 1rem; color: #145a32;">Bantu Kami Menjadi Lebih Baik</strong><br><br>
            Kepuasan pengunjung adalah prioritas utama di Kampung Sumber Alam. Kami mengundang Anda untuk membagikan kesan dan pesan selama berada di resor kami. Jawaban jujur yang Anda berikan akan langsung kami jadikan acuan untuk meningkatkan standar kualitas layanan kami. Terima kasih atas partisipasi Anda.
        </div>
        """, unsafe_allow_html=True)
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
                "q2_reliability": (
                    "Kenyamanan Kamar & Kualitas Tidur",
                    "Kenyamanan kamar dan kualitas tidur yang saya rasakan di resor ini sangat baik dan sesuai dengan janji pelayanan/ekspektasi."
                ),
                "q4_assurance": (
                    "Kesopanan, Kompetensi & Keamanan Pelayanan",
                    "Kesopanan dan kompetensi staf, serta jaminan keamanan di resor ini membuat saya merasa sangat nyaman dan terlindungi."
                ),
                "q1_tangibles": (
                    "Kebersihan & Kelengkapan Fasilitas Fisik",
                    "Estetika bangunan, kebersihan, serta kelengkapan fasilitas fisik di resor ini sangat terawat dan berfungsi dengan baik."
                ),
                "q5_empathy": (
                    "Kepedulian & Perhatian Personal Staf",
                    "Staf resor menunjukkan kepedulian yang tinggi dan memberikan perhatian personal untuk memahami kebutuhan saya."
                ),
                "q3_responsiveness": (
                    "Kecepatan & Kesigapan Respons Staf",
                    "Staf resor sangat cepat dan sigap dalam merespons serta melayani setiap permintaan saya."
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
        <code>Tanggal | Nama | Rating | X1 | X2 | X3 | X4 | X5 | Ulasan</code><br><br>
        <strong>Keterangan:</strong><br>
        • <strong>Tanggal</strong> — Format tanggal (YYYY-MM-DD atau DD/MM/YYYY)<br>
        • <strong>Nama</strong> — Nama tamu (teks)<br>
        • <strong>Rating</strong> — Rating bintang (angka 1–5)<br>
        • <strong>X1–X5</strong> — Skor dimensi Reliability, Assurance, Tangibles, Empathy, Responsiveness (angka 1–5)<br>
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
                f"(Tanggal, Nama, Rating, X1, X2, X3, X4, X5, Ulasan). "
                f"File Anda memiliki {df_upload.shape[1]} kolom."
            )
            return

        # Normalisasi nama kolom — ambil 9 kolom pertama
        df_upload = df_upload.iloc[:, :9]
        expected_cols = ["Tanggal", "Nama", "Rating", "X1", "X2", "X3", "X4", "X5", "Ulasan"]
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

                    x1 = int(row["X1"]) if pd.notna(row["X1"]) else 3
                    x2 = int(row["X2"]) if pd.notna(row["X2"]) else 3
                    x3 = int(row["X3"]) if pd.notna(row["X3"]) else 3
                    x4 = int(row["X4"]) if pd.notna(row["X4"]) else 3
                    x5 = int(row["X5"]) if pd.notna(row["X5"]) else 3

                    # Clamp X1-X5 ke rentang 1-5
                    x1, x2, x3, x4, x5 = [max(1, min(5, x)) for x in [x1, x2, x3, x4, x5]]

                    ulasan_val = str(row["Ulasan"]).strip() if pd.notna(row["Ulasan"]) else ""

                    # Jalankan fungsi NLP modular
                    dimensi, sentimen = analyze_feedback(ulasan_val, rating_val)

                    rows_to_insert.append({
                        "tanggal": tanggal_str,
                        "nama_tamu": nama_val,
                        "rating_bintang": rating_val,
                        "q1_tangibles": x3,
                        "q2_reliability": x1,
                        "q3_responsiveness": x5,
                        "q4_assurance": x2,
                        "q5_empathy": x4,
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
