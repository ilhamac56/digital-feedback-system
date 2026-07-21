"""
OUTPUT — Modul Dashboard Monitoring & Visualisasi
==================================================
Berisi halaman dashboard admin untuk menampilkan:
- KPI Cards (total ulasan, sentimen negatif, rata-rata rating, rata-rata SERVPERF)
- Grafik bar rata-rata skor per dimensi SERVPERF
- Donut chart distribusi sentimen
- Donut chart proporsi metode reservasi
- Rekomendasi Prioritas DSS (rule-based)
- Horizontal bar chart Top 5 kata kunci keluhan negatif
- Tabel data ulasan tamu dengan filter
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta, datetime, timezone

from core_utils import load_all_feedback
from process_nlp import extract_negative_findings

# Timezone WIB (UTC+7) — agar filter tanggal sesuai waktu lokal Indonesia
_WIB = timezone(timedelta(hours=7))

# ============================================================
# MAPPING LABEL DIMENSI MANAJERIAL (FITUR 2)
# ============================================================
DIMENSION_LABEL_MAP = {
    "Tangibles": "Fasilitas Fisik & Kebersihan",
    "Reliability": "Keandalan & Ketepatan Layanan",
    "Responsiveness": "Kecepatan & Kesigapan Staf",
    "Assurance": "Keamanan & Kompetensi Staf",
    "Empathy": "Kepedulian & Perhatian Personal",
}

# ============================================================
# KNOWLEDGE BASE DSS RULE-BASED — ANALISIS 5 WHY (FITUR 4)
# ============================================================
# Key harus PERSIS sama dengan field "name" di ABSA_CATEGORIES (process_nlp.py)
DSS_KNOWLEDGE_BASE = {
    # --- TANGIBLES ---
    "Kebersihan Kamar Kurang": {
        "akar_masalah": (
            "Kemungkinan standar kebersihan kamar belum terjaga secara konsisten, "
            "bisa disebabkan oleh beban kerja housekeeping yang tinggi atau kurangnya pengawasan."
        ),
        "rekomendasi": (
            "Terapkan inspeksi silang (cross-check) oleh supervisor sebelum status kamar "
            "diubah menjadi siap huni, serta evaluasi beban kerja staf housekeeping."
        ),
    },
    "Kamar Mandi / Toilet Kotor": {
        "akar_masalah": (
            "Kemungkinan pembersihan area basah (toilet, wastafel, shower) belum dilakukan "
            "secara menyeluruh atau belum ada checklist khusus untuk area kamar mandi."
        ),
        "rekomendasi": (
            "Terapkan checklist deep cleaning kamar mandi yang wajib diisi setiap pembersihan "
            "dan diverifikasi oleh supervisor sebelum kamar diserahkan ke tamu."
        ),
    },
    "Fasilitas Kamar Rusak": {
        "akar_masalah": (
            "Kemungkinan belum ada sistem pemeliharaan preventif yang teratur, "
            "sehingga kerusakan baru terdeteksi setelah ada keluhan dari tamu."
        ),
        "rekomendasi": (
            "Buat jadwal pemeliharaan berkala untuk seluruh fasilitas kamar "
            "dan sediakan logbook pelaporan kerusakan yang mudah diakses staf."
        ),
    },
    "AC Tidak Dingin / Bermasalah": {
        "akar_masalah": (
            "Kemungkinan unit AC kurang mendapat perawatan rutin seperti pembersihan filter "
            "atau servis berkala, sehingga performanya menurun seiring waktu."
        ),
        "rekomendasi": (
            "Jadwalkan servis AC secara berkala (minimal sebulan sekali), "
            "dan pastikan ada mekanisme pelaporan cepat dari tamu ke tim engineering."
        ),
    },
    "Air Panas Tidak Tersedia / Bermasalah": {
        "akar_masalah": (
            "Kemungkinan kapasitas water heater tidak memadai untuk seluruh kamar "
            "atau ada kendala teknis pada instalasi pipa air panas."
        ),
        "rekomendasi": (
            "Lakukan pengecekan rutin pada water heater dan instalasi pipa, "
            "serta pertimbangkan penambahan kapasitas jika sering terjadi keluhan."
        ),
    },
    "Kolam / Area Publik Kurang Terawat": {
        "akar_masalah": (
            "Kemungkinan frekuensi pembersihan area publik (kolam, taman, lobby) "
            "belum memadai atau belum ada jadwal perawatan yang ketat."
        ),
        "rekomendasi": (
            "Terapkan checklist inspeksi harian khusus area publik yang harus diselesaikan "
            "sebelum jam operasional dimulai, dan evaluasi jadwal perawatan secara berkala."
        ),
    },
    "Kualitas Makanan / Sarapan Kurang": {
        "akar_masalah": (
            "Kemungkinan variasi menu terbatas atau kontrol kualitas bahan baku "
            "dan proses penyajian belum cukup ketat."
        ),
        "rekomendasi": (
            "Evaluasi rotasi menu secara berkala, lakukan uji rasa (taste test) "
            "sebelum penyajian, dan minta feedback langsung dari tamu terkait menu."
        ),
    },
    # --- RELIABILITY ---
    "Koneksi WiFi Buruk": {
        "akar_masalah": (
            "Kemungkinan kapasitas jaringan belum sebanding dengan jumlah pengguna, "
            "atau ada kendala teknis pada infrastruktur access point."
        ),
        "rekomendasi": (
            "Evaluasi kapasitas bandwidth dan jumlah access point, "
            "pertimbangkan upgrade infrastruktur jaringan jika sering terjadi keluhan."
        ),
    },
    "Check-in / Check-out Lambat": {
        "akar_masalah": (
            "Kemungkinan proses administrasi check-in/check-out masih manual "
            "atau jumlah staf front desk belum memadai saat jam sibuk."
        ),
        "rekomendasi": (
            "Evaluasi efisiensi proses registrasi, pertimbangkan sistem express check-in, "
            "dan tambah personel front desk pada jam-jam puncak kedatangan tamu."
        ),
    },
    "Harga Tidak Sebanding": {
        "akar_masalah": (
            "Kemungkinan ekspektasi tamu terhadap kualitas layanan tidak sesuai "
            "dengan harga yang dibayarkan, atau kurangnya nilai tambah yang dirasakan."
        ),
        "rekomendasi": (
            "Evaluasi value proposition hotel, pertimbangkan penambahan benefit atau amenities "
            "kecil yang meningkatkan persepsi nilai, dan pastikan deskripsi promosi akurat."
        ),
    },
    "Deskripsi / Promosi Tidak Sesuai Kenyataan": {
        "akar_masalah": (
            "Kemungkinan materi promosi (foto, deskripsi di OTA atau website) sudah tidak "
            "diperbarui sesuai kondisi terkini, atau terdapat perbedaan antara ekspektasi "
            "yang dibangun oleh promosi dengan pengalaman aktual tamu."
        ),
        "rekomendasi": (
            "Audit seluruh materi promosi di website dan platform OTA, pastikan foto dan "
            "deskripsi mencerminkan kondisi terkini, dan terapkan kebijakan update konten "
            "promosi secara berkala setiap ada renovasi atau perubahan fasilitas."
        ),
    },
    "Jam Operasional Fasilitas Tidak Jelas": {
        "akar_masalah": (
            "Kemungkinan informasi jam operasional fasilitas (kolam renang, spa, sarapan, dll) "
            "belum dikomunikasikan secara jelas kepada tamu saat check-in atau melalui media "
            "informasi di kamar, sehingga tamu datang saat fasilitas sudah tutup."
        ),
        "rekomendasi": (
            "Pasang papan informasi jam operasional yang jelas di setiap fasilitas, "
            "sertakan informasi tersebut di welcome card kamar dan sampaikan saat check-in, "
            "serta update informasi di website dan platform OTA."
        ),
    },
    # --- RESPONSIVENESS ---
    "Pelayanan Staf Kurang Memuaskan": {
        "akar_masalah": (
            "Kemungkinan belum ada standar pelayanan yang konsisten "
            "atau staf memerlukan pelatihan tambahan dalam menangani tamu."
        ),
        "rekomendasi": (
            "Lakukan pelatihan ulang SOP pelayanan dan roleplay penanganan keluhan "
            "bagi seluruh staf, serta terapkan sistem evaluasi pelayanan berkala."
        ),
    },
    "Room Service / Housekeeping Lambat": {
        "akar_masalah": (
            "Kemungkinan jumlah staf housekeeping tidak sebanding dengan jumlah kamar "
            "yang harus dilayani, atau belum ada sistem prioritas dan tracking permintaan "
            "tamu yang efisien."
        ),
        "rekomendasi": (
            "Evaluasi rasio staf housekeeping terhadap jumlah kamar, terapkan sistem "
            "tracking permintaan tamu (digital atau manual), dan tetapkan standar waktu "
            "respons maksimal untuk setiap jenis permintaan."
        ),
    },
    "Keluhan Tidak Ditindaklanjuti": {
        "akar_masalah": (
            "Kemungkinan belum ada prosedur eskalasi keluhan yang jelas atau sistem "
            "pencatatan keluhan belum terdigitalisasi, sehingga keluhan tamu terlewat "
            "atau tidak sampai ke pihak yang berwenang menyelesaikannya."
        ),
        "rekomendasi": (
            "Terapkan sistem pencatatan keluhan terpusat dengan mekanisme eskalasi "
            "berjenjang, tetapkan batas waktu penyelesaian (SLA) untuk setiap jenis "
            "keluhan, dan pastikan tamu menerima konfirmasi bahwa keluhannya sedang diproses."
        ),
    },
    "Waktu Tunggu Pelayanan Lama": {
        "akar_masalah": (
            "Kemungkinan alur kerja pelayanan belum efisien atau jumlah staf yang "
            "bertugas tidak memadai pada jam-jam sibuk, menyebabkan antrian dan "
            "waktu tunggu yang lama bagi tamu."
        ),
        "rekomendasi": (
            "Analisis jam-jam puncak pelayanan dan sesuaikan penjadwalan staf, "
            "optimalkan alur kerja pelayanan, dan pertimbangkan sistem antrian atau "
            "notifikasi agar tamu tidak perlu menunggu di tempat."
        ),
    },
    # --- ASSURANCE ---
    "Suasana Berisik / Kurang Nyaman": {
        "akar_masalah": (
            "Kemungkinan isolasi suara antar-kamar atau dari area publik "
            "belum memadai, atau belum ada aturan ketenangan yang jelas."
        ),
        "rekomendasi": (
            "Pertimbangkan pemasangan peredam suara, terapkan kebijakan quiet hours "
            "yang dikomunikasikan kepada tamu saat check-in."
        ),
    },
    "Keamanan Kurang Terjamin": {
        "akar_masalah": (
            "Kemungkinan sistem keamanan (CCTV, kunci, petugas) belum optimal "
            "atau tamu merasa kurang aman karena minimnya visibilitas petugas keamanan."
        ),
        "rekomendasi": (
            "Evaluasi dan tingkatkan sistem keamanan area hotel, pastikan CCTV berfungsi, "
            "dan tambah frekuensi patroli keamanan terutama pada malam hari."
        ),
    },
    "Parkir Kurang Memadai": {
        "akar_masalah": (
            "Kemungkinan kapasitas lahan parkir terbatas dibandingkan jumlah tamu, "
            "atau tata letak parkir belum optimal."
        ),
        "rekomendasi": (
            "Evaluasi kapasitas dan tata letak area parkir, pertimbangkan penggunaan "
            "valet parking atau kerjasama dengan lahan parkir terdekat sebagai solusi alternatif."
        ),
    },
    "Akses Lokasi Sulit / Petunjuk Kurang": {
        "akar_masalah": (
            "Kemungkinan petunjuk arah menuju resor belum memadai, titik lokasi di "
            "Google Maps belum akurat, atau kondisi jalan akses kurang terawat, "
            "sehingga tamu kesulitan menemukan atau menjangkau lokasi."
        ),
        "rekomendasi": (
            "Pastikan titik lokasi di Google Maps akurat dan terkini, pasang papan "
            "petunjuk arah di persimpangan kunci, sediakan panduan arah di konfirmasi "
            "booking, dan koordinasi dengan pemerintah daerah untuk perbaikan jalan akses."
        ),
    },
    "Privasi Tamu Kurang Terjaga": {
        "akar_masalah": (
            "Kemungkinan desain kamar atau area penginapan kurang memperhatikan aspek "
            "privasi, seperti sekat yang tipis, gorden yang tidak rapat, atau jarak "
            "antar-kamar yang terlalu dekat."
        ),
        "rekomendasi": (
            "Evaluasi dan perbaiki elemen privasi kamar (gorden, sekat, kunci), pastikan "
            "jendela dan pintu tertutup rapat, dan pertimbangkan pemasangan kaca film "
            "atau tirai tambahan pada kamar yang menghadap area publik."
        ),
    },
    # --- EMPATHY ---
    "Staf Kurang Peduli / Cuek": {
        "akar_masalah": (
            "Kemungkinan belum ada budaya pelayanan yang menekankan empati, "
            "atau staf kurang termotivasi untuk memberikan perhatian personal kepada tamu."
        ),
        "rekomendasi": (
            "Adakan pelatihan komunikasi empatik secara berkala dan pertimbangkan "
            "program apresiasi staf berbasis kepuasan tamu untuk meningkatkan motivasi."
        ),
    },
    "Komunikasi / Informasi Kurang Jelas": {
        "akar_masalah": (
            "Kemungkinan staf belum terbiasa menyampaikan informasi secara proaktif "
            "dan jelas kepada tamu, atau belum ada standar komunikasi yang baku "
            "untuk informasi penting seperti aturan, prosedur, dan fasilitas."
        ),
        "rekomendasi": (
            "Buat panduan komunikasi standar (script) untuk informasi yang sering "
            "ditanyakan tamu, sediakan brosur atau kartu informasi di kamar, dan "
            "latih staf untuk menyampaikan informasi penting secara proaktif saat check-in."
        ),
    },
    "Kurang Ramah Terhadap Anak / Keluarga": {
        "akar_masalah": (
            "Kemungkinan fasilitas dan layanan resor belum dirancang dengan "
            "mempertimbangkan kebutuhan keluarga dengan anak kecil, seperti area bermain "
            "yang aman, menu anak, atau perlengkapan bayi."
        ),
        "rekomendasi": (
            "Sediakan fasilitas ramah anak (playground aman, kids corner, menu anak), "
            "tawarkan perlengkapan bayi (baby cot, high chair) sebagai layanan tambahan, "
            "dan latih staf untuk memberikan perhatian khusus kepada tamu keluarga."
        ),
    },
    "Kebutuhan Khusus Tidak Diakomodasi": {
        "akar_masalah": (
            "Kemungkinan resor belum memiliki fasilitas aksesibilitas yang memadai "
            "untuk tamu berkebutuhan khusus (disabilitas, lansia, alergi makanan), "
            "atau staf belum terlatih menangani permintaan khusus."
        ),
        "rekomendasi": (
            "Evaluasi aksesibilitas fasilitas untuk tamu disabilitas dan lansia, "
            "sediakan opsi menu untuk alergi dan diet khusus, latih staf mengenali "
            "dan merespons kebutuhan khusus tamu, dan komunikasikan ketersediaan "
            "layanan ini di platform booking."
        ),
    },
}



# ============================================================
# HALAMAN ADMIN: DASHBOARD MONITORING
# ============================================================

def page_dashboard_monitoring():
    """Render halaman dashboard monitoring (KPI, grafik, tabel)."""

    # --- Judul Dashboard ---
    st.markdown('<p class="dash-title">📊 Dashboard Monitoring Ulasan</p>', unsafe_allow_html=True)
    st.markdown('<p class="dash-subtitle">Kampung Sumber Alam — Analisis Real-time Feedback Tamu</p>',
                unsafe_allow_html=True)
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # Muat data
    df = load_all_feedback()

    if df.empty:
        st.info("📭 Belum ada data ulasan. Silakan isi form ulasan atau upload data OTA terlebih dahulu.")
        return

    # Pastikan kolom tanggal bertipe datetime untuk filtering
    # Normalisasi ke date-only (tanpa waktu) agar perbandingan konsisten
    df["tanggal"] = pd.to_datetime(df["tanggal"], errors="coerce")
    df["tanggal"] = df["tanggal"].dt.normalize()  # Set waktu ke 00:00:00

    # Normalisasi kolom jenis_reservasi (backward-compatible jika NULL)
    if "jenis_reservasi" not in df.columns:
        df["jenis_reservasi"] = "Tidak Diketahui"
    else:
        df["jenis_reservasi"] = df["jenis_reservasi"].fillna("Tidak Diketahui")

    # ----------------------------------------------------------------
    # SIDEBAR: FILTER (ditambahkan ke sidebar yang sudah ada)
    # ----------------------------------------------------------------
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🔍 Filter Data")

        # Filter Rentang Waktu — radio agar semua opsi terlihat tanpa dropdown
        filter_terbaru = st.radio(
            "🕐 Rentang Waktu",
            ["Semua Waktu", "Hari Ini", "7 Hari Terakhir", "30 Hari Terakhir", "90 Hari Terakhir"],
            key="filter_terbaru",
        )

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

        # Filter Jenis Reservasi (FITUR 3)
        filter_reservasi = st.selectbox(
            "🏷️ Jenis Reservasi",
            ["Semua", "Aplikasi Online (OTA)", "Walk-in"],
            key="filter_reservasi",
        )

    # Terapkan filter
    df_filtered = df.copy()

    if filter_sentimen != "Semua":
        df_filtered = df_filtered[df_filtered["sentimen_akhir"] == filter_sentimen]
    if filter_dimensi != "Semua":
        df_filtered = df_filtered[
            df_filtered["dimensi_terdeteksi"].str.contains(filter_dimensi, na=False)
        ]
    if filter_reservasi != "Semua":
        df_filtered = df_filtered[df_filtered["jenis_reservasi"] == filter_reservasi]

    # Filter berdasarkan waktu — gunakan WIB (UTC+7) dan batasi sampai hari ini
    today = pd.Timestamp(datetime.now(_WIB).date())
    if filter_terbaru == "Hari Ini":
        df_filtered = df_filtered[df_filtered["tanggal"] == today]
    elif filter_terbaru == "7 Hari Terakhir":
        start = today - timedelta(days=7)
        df_filtered = df_filtered[(df_filtered["tanggal"] >= start) & (df_filtered["tanggal"] <= today)]
    elif filter_terbaru == "30 Hari Terakhir":
        start = today - timedelta(days=30)
        df_filtered = df_filtered[(df_filtered["tanggal"] >= start) & (df_filtered["tanggal"] <= today)]
    elif filter_terbaru == "90 Hari Terakhir":
        start = today - timedelta(days=90)
        df_filtered = df_filtered[(df_filtered["tanggal"] >= start) & (df_filtered["tanggal"] <= today)]

    # ----------------------------------------------------------------
    # KPI CARDS — menggunakan data yang sudah difilter
    # ----------------------------------------------------------------
    st.markdown('<p class="section-header">📈 Key Performance Indicators</p>', unsafe_allow_html=True)

    total_ulasan = len(df_filtered)
    pct_negatif = (
        (df_filtered["sentimen_akhir"] == "Negatif").sum() / total_ulasan * 100
        if total_ulasan > 0 else 0
    )
    avg_rating = df_filtered["rating_bintang"].mean() if total_ulasan > 0 else 0
    avg_servperf = (
        df_filtered[["q1_reliability", "q2_assurance", "q3_tangibles",
            "q4_empathy", "q5_responsiveness"]].mean().mean()
        if total_ulasan > 0 else 0
    )

    k1, k2, k3, k4 = st.columns(4)

    with k1:
        st.markdown(f"""
        <div class="kpi-card kpi-emerald">
            <div class="kpi-icon">📝</div>
            <div class="kpi-value">{total_ulasan}</div>
            <div class="kpi-label">Total Ulasan</div>
        </div>
        """, unsafe_allow_html=True)

    with k2:
        st.markdown(f"""
        <div class="kpi-card kpi-rose">
            <div class="kpi-icon">⚠️</div>
            <div class="kpi-value">{pct_negatif:.1f}%</div>
            <div class="kpi-label">Sentimen Negatif</div>
        </div>
        """, unsafe_allow_html=True)

    with k3:
        st.markdown(f"""
        <div class="kpi-card kpi-amber">
            <div class="kpi-icon">⭐</div>
            <div class="kpi-value">{avg_rating:.2f}</div>
            <div class="kpi-label">Rata-rata Rating</div>
        </div>
        """, unsafe_allow_html=True)

    with k4:
        st.markdown(f"""
        <div class="kpi-card kpi-violet">
            <div class="kpi-icon">📊</div>
            <div class="kpi-value">{avg_servperf:.2f}</div>
            <div class="kpi-label">Rata-rata SERVPERF</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # ----------------------------------------------------------------
    # GRAFIK — berdampingan [3, 2] agar bar chart lebih lebar
    # ----------------------------------------------------------------
    with st.container(border=True):
        chart_col1, chart_col2 = st.columns([3, 2], gap="large")

        # --- Bar Chart: Rata-rata Skor Dimensi (FITUR 2 — label manajerial) ---
        with chart_col1:
            st.markdown('<p class="section-header">📊 Rata-rata Skor per Dimensi SERVPERF</p>',
                        unsafe_allow_html=True)

            # Variabel backend tetap q1_reliability dst, label diganti
            dim_means = pd.DataFrame({
                "Dimensi": [
                    DIMENSION_LABEL_MAP["Reliability"],
                    DIMENSION_LABEL_MAP["Assurance"],
                    DIMENSION_LABEL_MAP["Tangibles"],
                    DIMENSION_LABEL_MAP["Empathy"],
                    DIMENSION_LABEL_MAP["Responsiveness"],
                ],
                "Rata-rata": [
                    df_filtered["q1_reliability"].mean(),
                    df_filtered["q2_assurance"].mean(),
                    df_filtered["q3_tangibles"].mean(),
                    df_filtered["q4_empathy"].mean(),
                    df_filtered["q5_responsiveness"].mean(),
                ]
            })

            colors = ["#10b981", "#34d399", "#6ee7b7", "#a7f3d0", "#059669"]
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
                font=dict(family="Inter", size=13, color="#94a3b8"),
                margin=dict(t=30, b=60, l=50, r=30),
                bargap=0.3,
                xaxis=dict(gridcolor="rgba(255,255,255,0.05)", linecolor="rgba(255,255,255,0.1)"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)", linecolor="rgba(255,255,255,0.1)"),
            )
            fig_bar.update_traces(
                textposition="outside",
                textfont=dict(color="#e2e8f0", size=13),
                marker_line_width=0,
                marker_cornerradius=10,
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # --- Donut Chart: Distribusi Sentimen ---
        with chart_col2:
            st.markdown('<p class="section-header">🎯 Distribusi Sentimen</p>', unsafe_allow_html=True)

            sentimen_counts = df_filtered["sentimen_akhir"].value_counts().reset_index()
            sentimen_counts.columns = ["Sentimen", "Jumlah"]

            color_map = {"Positif": "#10b981", "Netral": "#f59e0b", "Negatif": "#f43f5e"}
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
                font=dict(family="Inter", size=12, color="#94a3b8"),
                margin=dict(t=30, b=30, l=60, r=40),
                annotations=[
                    dict(
                        text=f"<b>{total_ulasan}</b><br>Ulasan",
                        x=0.5, y=0.5,
                        font_size=15,
                        showarrow=False,
                        font=dict(family="Inter", color="#e2e8f0"),
                    )
                ],
            )
            st.plotly_chart(fig_donut, use_container_width=True)

    # ----------------------------------------------------------------
    # BARIS BARU: Donut Reservasi + Rekomendasi DSS (FITUR 3 & 4)
    # ----------------------------------------------------------------
    with st.container(border=True):
        dss_col1, dss_col2 = st.columns([2, 3], gap="large")

        # --- Donut Chart: Proporsi Metode Reservasi (FITUR 3) ---
        with dss_col1:
            st.markdown('<p class="section-header">🏷️ Proporsi Metode Reservasi</p>',
                        unsafe_allow_html=True)

            reservasi_counts = df_filtered["jenis_reservasi"].value_counts().reset_index()
            reservasi_counts.columns = ["Metode", "Jumlah"]

            reservasi_color_map = {
                "Aplikasi Online (OTA)": "#3b82f6",
                "Walk-in": "#f59e0b",
                "Tidak Diketahui": "#6b7280",
            }
            fig_reservasi = px.pie(
                reservasi_counts,
                names="Metode",
                values="Jumlah",
                hole=0.55,
                color="Metode",
                color_discrete_map=reservasi_color_map,
            )
            fig_reservasi.update_traces(
                textinfo="label+percent",
                textposition="outside",
                textfont_size=12,
                pull=[0.03] * len(reservasi_counts),
            )
            fig_reservasi.update_layout(
                height=260,
                showlegend=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", size=12, color="#94a3b8"),
                margin=dict(t=10, b=10, l=10, r=10),
                annotations=[
                    dict(
                        text=f"<b>{total_ulasan}</b><br>Tamu",
                        x=0.5, y=0.5,
                        font_size=14,
                        showarrow=False,
                        font=dict(family="Inter", color="#e2e8f0"),
                    )
                ],
            )
            st.plotly_chart(fig_reservasi, use_container_width=True)

        # --- Rekomendasi Prioritas DSS (FITUR 4 — Knowledge Base) ---
        with dss_col2:
            st.markdown('<p class="section-header">💡 Rekomendasi Prioritas (DSS)</p>',
                        unsafe_allow_html=True)

            # Ambil ulasan bersentimen Negatif dari data terfilter
            df_neg_dss = df_filtered[df_filtered["sentimen_akhir"] == "Negatif"]
            ulasan_neg_dss = df_neg_dss["teks_ulasan"].dropna().tolist()

            if ulasan_neg_dss:
                # Hitung Top 1 kategori keluhan ABSA
                top_findings = extract_negative_findings(ulasan_neg_dss, top_n=1)

                if top_findings:
                    top = top_findings[0]
                    top_kategori = top["frasa"]          # nama kategori ABSA
                    top_dimensi = top.get("dimensi", "")
                    top_freq = top["frekuensi"]

                    # Lookup Knowledge Base (case-insensitive key matching)
                    kb_entry = DSS_KNOWLEDGE_BASE.get(top_kategori)
                    if not kb_entry:
                        # Coba case-insensitive fallback
                        kb_lower = {k.lower(): v for k, v in DSS_KNOWLEDGE_BASE.items()}
                        kb_entry = kb_lower.get(top_kategori.lower(), {
                            "akar_masalah": "Belum tersedia analisis akar masalah untuk kategori ini.",
                            "rekomendasi": "Lakukan investigasi lanjutan terhadap keluhan ini.",
                        })

                    akar = kb_entry["akar_masalah"]
                    rekom = kb_entry["rekomendasi"]
                    dim_label = DIMENSION_LABEL_MAP.get(top_dimensi, top_dimensi)

                    # DSS Recommendation Card — premium styling
                    st.markdown(f"""
                    <div class="dss-card">
                        <span class="dss-badge">⚡ PRIORITAS UTAMA</span>
                        <div class="dss-dim-name">📌 {top_kategori}</div>
                        <div class="dss-score">Dimensi: <strong>{dim_label}</strong> · Temuan Terbanyak: <strong>{top_freq}</strong> keluhan</div>
                        <div class="dss-separator"></div>
                        <div class="dss-label">🔍 Akar Masalah Historis:</div>
                        <div class="dss-text">{akar}</div>
                        <div class="dss-label">💊 Rekomendasi Tindakan (DSS):</div>
                        <div class="dss-text">{rekom}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.success(
                        "✅ Tidak ada temuan kritis pada periode ini. "
                        "Pertahankan kualitas pelayanan!"
                    )
            else:
                st.success(
                    "✅ Tidak ada temuan kritis pada periode ini. "
                    "Pertahankan kualitas pelayanan!"
                )

    # ----------------------------------------------------------------
    # LOG TEMUAN KRITIS — EKSTRAKSI FRASA NEGATIF ASPECT-BASED (FITUR 5)
    # ----------------------------------------------------------------
    with st.container(border=True):
        st.markdown('<p class="section-header">⚠️ Log Temuan Kritis (Aspect-Based)</p>',
                    unsafe_allow_html=True)

        # Ambil ulasan yang bersentimen Negatif dari data terfilter
        df_negatif = df_filtered[df_filtered["sentimen_akhir"] == "Negatif"]
        ulasan_negatif_list = df_negatif["teks_ulasan"].dropna().tolist()

        if ulasan_negatif_list:
            findings = extract_negative_findings(ulasan_negatif_list, top_n=3)

            if findings:
                # --- Horizontal Bar Chart: Top frasa temuan negatif ---
                df_findings = pd.DataFrame(findings)
                # Capitalize frasa untuk tampilan
                df_findings["frasa"] = df_findings["frasa"].str.capitalize()
                # Tambahkan label dimensi
                df_findings["frasa_display"] = "[" + df_findings["dimensi"] + "] " + df_findings["frasa"]
                # Urutkan ascending agar bar terbesar di atas
                df_findings = df_findings.sort_values("frekuensi", ascending=True)

                fig_findings = px.bar(
                    df_findings,
                    x="frekuensi",
                    y="frasa_display",
                    orientation="h",
                    text=df_findings.apply(
                        lambda row: f"{row['frekuensi']}x ({row['persentase']}%)", axis=1
                    ),
                    color="dimensi",
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                )
                fig_findings.update_layout(
                    height=max(300, len(df_findings) * 45),
                    xaxis_title="Frekuensi Kemunculan",
                    yaxis_title="",
                    showlegend=True,
                    legend_title="Dimensi SERVPERF",
                    coloraxis_showscale=False,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter", size=13, color="#94a3b8"),
                    margin=dict(t=20, b=40, l=250, r=30),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                )
                fig_findings.update_traces(
                    textposition="outside",
                    textfont=dict(color="#e2e8f0"),
                    marker_line_width=0,
                    marker_cornerradius=8,
                )
                st.plotly_chart(fig_findings, use_container_width=True)

                st.caption(
                    f"Berdasarkan **{len(ulasan_negatif_list)}** ulasan bersentimen Negatif "
                    f"(dari {total_ulasan} ulasan terfilter). "
                    f"Frasa diekstrak secara otomatis dari konteks kalimat (kata benda + kata sifat negatif)."
                )

                # --- Detail ulasan asli per kategori ---
                for finding in findings:
                    kategori_nama = finding["frasa"].capitalize()
                    dimensi = finding.get("dimensi", "Unknown")
                    daftar_ulasan = finding.get("ulasan", [])
                    jumlah = finding["frekuensi"]

                    with st.expander(
                        f"📋 [{dimensi}] {kategori_nama} — {jumlah} ulasan",
                        expanded=False,
                    ):
                        if daftar_ulasan:
                            for idx, ulasan_teks in enumerate(daftar_ulasan, 1):
                                st.markdown(
                                    f"**{idx}.** {ulasan_teks}",
                                )
                            st.caption(f"Menampilkan {len(daftar_ulasan)} ulasan asli tamu.")
                        else:
                            st.info("Tidak ada data ulasan asli yang tersedia.")
            else:
                st.info("Tidak ditemukan frasa temuan negatif yang cocok dengan kamus leksikon.")
        else:
            st.success("🎉 Tidak ada ulasan bersentimen Negatif pada data yang terfilter.")

    # ----------------------------------------------------------------
    # TABEL DATA — termasuk kolom X1–X5 dan Jenis Reservasi
    # ----------------------------------------------------------------
    with st.container(border=True):
        st.markdown('<p class="section-header">📋 Data Ulasan Tamu</p>', unsafe_allow_html=True)

        active_filters = []
        if filter_sentimen != "Semua":
            active_filters.append(f"Sentimen={filter_sentimen}")
        if filter_dimensi != "Semua":
            active_filters.append(f"Dimensi={filter_dimensi}")
        if filter_terbaru != "Semua Waktu":
            active_filters.append(f"Waktu={filter_terbaru}")
        if filter_reservasi != "Semua":
            active_filters.append(f"Reservasi={filter_reservasi}")

        total_semua = len(df)
        if active_filters:
            st.caption(
                f"🔎 Menampilkan {len(df_filtered)} dari {total_semua} ulasan "
                f"(Filter: {', '.join(active_filters)})"
            )
        else:
            st.caption(f"Menampilkan seluruh {total_semua} ulasan")

        # Pilih & rename kolom untuk tampilan
        display_cols = {
            "tanggal": "Tanggal",
            "nama_tamu": "Nama Tamu",
            "jenis_reservasi": "Jenis Reservasi",
            "rating_bintang": "Rating Bintang",
            "q1_reliability": "Q1 Reliability",
            "q2_assurance": "Q2 Assurance",
            "q3_tangibles": "Q3 Tangibles",
            "q4_empathy": "Q4 Empathy",
            "q5_responsiveness": "Q5 Responsiveness",
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
                "Q1 Reliability": st.column_config.NumberColumn(format="%d"),
                "Q2 Assurance": st.column_config.NumberColumn(format="%d"),
                "Q3 Tangibles": st.column_config.NumberColumn(format="%d"),
                "Q4 Empathy": st.column_config.NumberColumn(format="%d"),
                "Q5 Responsiveness": st.column_config.NumberColumn(format="%d"),
                "Sentimen": st.column_config.TextColumn(width="small"),
                "Jenis Reservasi": st.column_config.TextColumn(width="medium"),
            },
        )

        # --- Tombol Ekspor ke Excel ---
        import os
        import tempfile

        df_export = df_display.copy()
        # Konversi kolom Tanggal ke string
        if "Tanggal" in df_export.columns:
            df_export["Tanggal"] = pd.to_datetime(
                df_export["Tanggal"], errors="coerce"
            ).dt.strftime("%Y-%m-%d")

        # Simpan ke file sementara di disk (cara yang terbukti berhasil)
        tmp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, "_feedback_export_temp.xlsx")
        df_export.to_excel(tmp_path, index=False, engine="openpyxl", sheet_name="Feedback")

        # Baca bytes dari file yang sudah tersimpan
        with open(tmp_path, "rb") as f:
            excel_bytes = f.read()

        # Hapus file sementara
        try:
            os.remove(tmp_path)
        except OSError:
            pass

        timestamp_file = datetime.now(_WIB).strftime("%Y%m%d_%H%M%S")
        filename = f"feedback_data_{timestamp_file}.xlsx"

        st.download_button(
            label="📥 Ekspor ke Excel",
            data=excel_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_export_excel",
            use_container_width=True,
        )
