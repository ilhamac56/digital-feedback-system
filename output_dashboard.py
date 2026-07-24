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
# KNOWLEDGE BASE DSS RULE-BASED — ANALISIS FISHBONE / 6M (FITUR 4)
# ============================================================
# Key harus PERSIS sama dengan field "name" di ABSA_CATEGORIES (process_nlp.py)
# Setiap entry = list of dict {"faktor", "penyebab", "rekomendasi"}
# Faktor mengacu pada Fishbone 6M: Man, Method, Machine/Tool, Material, Mother Nature, Measurement
DSS_KNOWLEDGE_BASE = {
    "Tidak ada AC": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada target kuantitatif & timeline pemerataan instalasi AC",
            "rekomendasi": "Susun Master Schedule & target anggaran kuantitatif bulanan yang mengikat",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Unit AC belum tersedia merata di seluruh kamar",
            "rekomendasi": "Prioritaskan pengadaan bertahap berdasarkan keluhan tertinggi",
        },
        {
            "faktor": "Measurement",
            "penyebab": "Belum ada pemetaan data prioritas kamar dengan keluhan suhu tertinggi",
            "rekomendasi": "Susun peta prioritas kamar berdasarkan frekuensi keluhan panas dari data DFS",
        },
    ],
    "Fasilitas kamar tidak memadai": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada jadwal peremajaan aset (preventive replacement)",
            "rekomendasi": "Buat logbook umur ekonomis aset & jadwal peremajaan sebelum aset aus",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Tidak ada logbook pelaporan kerusakan fasilitas",
            "rekomendasi": "Sediakan logbook digital pelaporan kerusakan terintegrasi dengan tim Engineering",
        },
        {
            "faktor": "Man",
            "penyebab": "Staf tidak terbiasa melaporkan kerusakan kecil sebelum menjadi besar",
            "rekomendasi": "Bangun budaya pelaporan dini melalui briefing rutin dan insentif kepatuhan",
        },
    ],
    "Serangga dan hewan pengganggu": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada jadwal pest control rutin",
            "rekomendasi": "Terapkan jadwal fumigasi/pest control berkala",
        },
        {
            "faktor": "Mother Nature",
            "penyebab": "Lokasi resor berada di area terbuka dekat vegetasi alami",
            "rekomendasi": "Pasang penghalang fisik (kasa nyamuk, penutup celah) pada unit kamar",
        },
        {
            "faktor": "Material",
            "penyebab": "Celah pada material bangunan (bilik bambu/kayu) memudahkan serangga masuk",
            "rekomendasi": "Tutup celah struktural pada dinding bilik bambu/kayu secara berkala",
        },
    ],
    "Variasi dan rasa makanan kurang": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada kontrol kualitas rasa dan rotasi menu berkala",
            "rekomendasi": "Terapkan uji rasa (taste test) rutin dan evaluasi menu berkala",
        },
        {
            "faktor": "Material",
            "penyebab": "Variasi bahan baku terbatas",
            "rekomendasi": "Evaluasi pemasok dan tambah variasi bahan baku musiman",
        },
        {
            "faktor": "Man",
            "penyebab": "Keterbatasan keterampilan juru masak dalam variasi resep",
            "rekomendasi": "Adakan pelatihan kuliner/upskilling bagi staf dapur secara berkala",
        },
    ],
    "Kamar mandi/toilet kurang bersih": [
        {
            "faktor": "Method",
            "penyebab": "Lemahnya prosedur deep cleaning & cross-check supervisor",
            "rekomendasi": "Perbarui SOP deep cleaning & wajibkan cross-check kebersihan",
        },
        {
            "faktor": "Man",
            "penyebab": "Kurangnya supervisi pada titik yang sering terlewat (sudut, celah)",
            "rekomendasi": "Latih staf pada titik kritis kebersihan, spot-check berkala",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Peralatan pembersih saluran air tidak memadai",
            "rekomendasi": "Sediakan alat pembersih saluran (drain snake/vacuum saluran) khusus",
        },
    ],
    "Kebersihan kamar kurang": [
        {
            "faktor": "Man",
            "penyebab": "Staf housekeeping terburu-buru saat jam sibuk",
            "rekomendasi": "Evaluasi beban kerja staf, tambah personel saat peak hours",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada SOP inspeksi silang sebelum status kamar \"Ready\"",
            "rekomendasi": "Terapkan cross-check wajib oleh supervisor sebelum kamar dijual",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Update status kamar hanya via radio (HT), tanpa verifikasi digital",
            "rekomendasi": "Bangun sistem checklist digital terhubung status kamar",
        },
    ],
    "Sanitasi kolam ikan kurang terjaga": [
        {
            "faktor": "Method",
            "penyebab": "Tidak ada checklist & jadwal rutin pembersihan area air",
            "rekomendasi": "Terapkan checklist inspeksi harian area air sebelum jam operasional",
        },
        {
            "faktor": "Man",
            "penyebab": "Kurang jelasnya PIC kebersihan area kolam",
            "rekomendasi": "Tetapkan PIC (Gardening/Public Area) dengan jadwal kerja jelas",
        },
        {
            "faktor": "Machine/Tool",
            "penyebab": "Tidak ada sistem filter/sirkulasi air otomatis",
            "rekomendasi": "Pasang sistem filtrasi/sirkulasi air untuk menjaga kualitas air secara berkelanjutan",
        },
    ],
    "Kualitas pelayanan staf kurang": [
        {
            "faktor": "Man",
            "penyebab": "Standar pelayanan belum konsisten antarstaf",
            "rekomendasi": "Pelatihan ulang SOP pelayanan dan roleplay penanganan tamu",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada evaluasi kinerja pelayanan berkala",
            "rekomendasi": "Terapkan evaluasi kinerja pelayanan secara rutin",
        },
        {
            "faktor": "Measurement",
            "penyebab": "Belum ada indikator/KPI kinerja layanan yang terukur",
            "rekomendasi": "Susun KPI pelayanan (mis. skor kepuasan per staf) sebagai dasar evaluasi",
        },
    ],
    "Kebersihan lingkungan resort kurang": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada jadwal kebersihan area luar kamar yang terjadwal jelas",
            "rekomendasi": "Susun jadwal kebersihan area publik dengan PIC yang jelas",
        },
        {
            "faktor": "Man",
            "penyebab": "Jumlah tenaga kebersihan area publik tidak memadai",
            "rekomendasi": "Evaluasi rasio staf kebersihan terhadap luas area publik, tambah personel bila perlu",
        },
    ],
    "Penerangan kamar dan lingkungan kurang": [
        {
            "faktor": "Machine/Tool",
            "penyebab": "Titik lampu belum memadai di beberapa area",
            "rekomendasi": "Audit titik penerangan dan tambah lampu di area minim cahaya",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada jadwal penggantian lampu berkala",
            "rekomendasi": "Terapkan jadwal pemeriksaan & penggantian lampu rutin",
        },
        {
            "faktor": "Man",
            "penyebab": "Tidak ada petugas patroli rutin yang mengecek lampu mati",
            "rekomendasi": "Tugaskan petugas maintenance untuk patroli & pelaporan lampu mati harian",
        },
    ],
    "Gangguan lingkungan": [
        {
            "faktor": "Material",
            "penyebab": "Material bangunan (bilik bambu/kayu) tidak kedap suara tinggi",
            "rekomendasi": "Pertimbangkan peredam suara tambahan pada unit bungalow",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada kebijakan jam tenang (quiet hours) yang dikomunikasikan",
            "rekomendasi": "Tetapkan dan komunikasikan aturan quiet hours saat check-in",
        },
        {
            "faktor": "Mother Nature",
            "penyebab": "Lokasi terbuka dekat vegetasi memungkinkan gangguan alami",
            "rekomendasi": "Pasang jaring/pelindung atap pada titik rawan gangguan alam",
        },
        {
            "faktor": "Man",
            "penyebab": "Kurangnya pengawasan aktif petugas keamanan pada malam hari",
            "rekomendasi": "Tingkatkan intensitas patroli keamanan malam di area bungalow",
        },
    ],
    "Koneksi WiFi tidak stabil": [
        {
            "faktor": "Machine/Tool",
            "penyebab": "Kapasitas bandwidth/titik akses tidak memadai",
            "rekomendasi": "Evaluasi kapasitas dan tambah access point di titik lemah sinyal",
        },
        {
            "faktor": "Method",
            "penyebab": "Tidak ada monitoring rutin kualitas jaringan",
            "rekomendasi": "Terapkan pemantauan kualitas sinyal berkala sebelum tamu mengeluh",
        },
    ],
    "Kolam rendam kurang panas": [
        {
            "faktor": "Machine/Tool",
            "penyebab": "Sistem pemanas air kolam tidak optimal",
            "rekomendasi": "Evaluasi kapasitas pemanas dan lakukan perawatan berkala",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada pengecekan suhu rutin sebelum jam operasional",
            "rekomendasi": "Terapkan pengecekan suhu kolam terjadwal setiap pagi",
        },
    ],
    "Lantai kamar berbunyi saat dipijak": [
        {
            "faktor": "Material",
            "penyebab": "Struktur lantai kayu/panggung sudah mulai longgar",
            "rekomendasi": "Lakukan pemeriksaan dan perbaikan struktur lantai secara berkala",
        },
        {
            "faktor": "Method",
            "penyebab": "Tidak ada jadwal inspeksi struktur bangunan berkala",
            "rekomendasi": "Masukkan pemeriksaan struktur lantai ke jadwal preventive maintenance bangunan",
        },
    ],
    "Jarak akses pintu masuk ke unit jauh": [
        {
            "faktor": "Machine/Tool",
            "penyebab": "Belum tersedia sarana transportasi internal (buggy/shuttle)",
            "rekomendasi": "Sediakan layanan antar-jemput/buggy internal untuk unit yang jauh",
        },
        {
            "faktor": "Method",
            "penyebab": "Tata letak unit belum mempertimbangkan kemudahan akses sejak perencanaan",
            "rekomendasi": "Evaluasi tata letak unit pada perencanaan pembangunan berikutnya",
        },
    ],
    "Desain kamar kurang ergonomis": [
        {
            "faktor": "Method",
            "penyebab": "Tata letak furnitur belum mempertimbangkan kenyamanan pengguna",
            "rekomendasi": "Evaluasi ulang tata letak furnitur kamar berdasarkan masukan tamu",
        },
        {
            "faktor": "Measurement",
            "penyebab": "Belum ada survei ergonomi/kenyamanan tamu terhadap tata letak furnitur",
            "rekomendasi": "Lakukan survei kenyamanan ergonomis sebagai dasar evaluasi ulang",
        },
    ],
    "Sirkulasi udara kamar kurang": [
        {
            "faktor": "Machine/Tool",
            "penyebab": "Ventilasi/exhaust fan tidak memadai",
            "rekomendasi": "Evaluasi dan tambah ventilasi/exhaust pada kamar bermasalah",
        },
        {
            "faktor": "Material",
            "penyebab": "Desain bangunan/material menghambat sirkulasi udara alami",
            "rekomendasi": "Evaluasi desain bukaan/material dinding untuk mendukung sirkulasi alami",
        },
    ],
    "Keamanan kolam kurang terjamin": [
        {
            "faktor": "Machine/Tool",
            "penyebab": "Tidak ada pagar pembatas di area kolam",
            "rekomendasi": "Pasang pagar pengaman di sekitar area kolam",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada rambu peringatan keselamatan",
            "rekomendasi": "Pasang rambu peringatan dan papan kedalaman kolam",
        },
    ],
    "Kebersihan tempat makan/restoran kurang": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada checklist kebersihan area makan",
            "rekomendasi": "Terapkan checklist kebersihan restoran sebelum jam operasional",
        },
        {
            "faktor": "Man",
            "penyebab": "Kurangnya pengawasan konsisten terhadap kebersihan area makan",
            "rekomendasi": "Tugaskan PIC kebersihan restoran dengan jadwal spot-check rutin",
        },
    ],
    "Restoran terlalu kecil": [
        {
            "faktor": "Machine/Tool",
            "penyebab": "Kapasitas fisik restoran tidak dirancang untuk kondisi ramai/peak season",
            "rekomendasi": "Terapkan sistem reservasi meja/jam makan bergilir saat ramai",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada sistem manajemen kapasitas/reservasi meja",
            "rekomendasi": "Bangun sistem reservasi meja digital untuk mengatur alur tamu",
        },
    ],
    "Parkir kurang memadai": [
        {
            "faktor": "Machine/Tool",
            "penyebab": "Kapasitas lahan parkir terbatas",
            "rekomendasi": "Evaluasi tata letak parkir dan pertimbangkan kerja sama lahan tambahan",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada sistem pengaturan/pengarahan parkir saat ramai",
            "rekomendasi": "Tugaskan petugas pengatur parkir pada jam kunjungan tinggi",
        },
    ],
    "Informasi fasilitas kurang jelas": [
        {
            "faktor": "Method",
            "penyebab": "Informasi fasilitas tidak disampaikan saat check-in",
            "rekomendasi": "Sampaikan info fasilitas secara lisan & tercetak di welcome card",
        },
        {
            "faktor": "Man",
            "penyebab": "Staf tidak proaktif menyampaikan informasi fasilitas ke tamu",
            "rekomendasi": "Latih staf Front Office untuk selalu menyampaikan info fasilitas saat registrasi",
        },
    ],
    "Perlengkapan kamar (toiletries) kurang lengkap": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada standar baku kelengkapan toiletries per kamar",
            "rekomendasi": "Tetapkan checklist kelengkapan toiletries standar per kamar",
        },
        {
            "faktor": "Man",
            "penyebab": "Staf housekeeping tidak mengecek kelengkapan sebelum kamar dijual",
            "rekomendasi": "Integrasikan pengecekan toiletries ke dalam checklist cross-check kamar (terkait Temuan #6)",
        },
    ],
    "Fasilitas belanja sekitar resort tidak tersedia": [
        {
            "faktor": "Mother Nature",
            "penyebab": "Lokasi resor yang relatif terpencil dari pusat perbelanjaan",
            "rekomendasi": "Jalin kerja sama dengan UMKM lokal untuk sediakan area/etalase belanja kecil",
        },
        {
            "faktor": "Method",
            "penyebab": "Belum ada kerja sama formal dengan pelaku usaha lokal sekitar",
            "rekomendasi": "Susun perjanjian kerja sama resmi dengan UMKM sekitar sebagai mitra resor",
        },
    ],
    "Kamar panas": [
        {
            "faktor": "Method",
            "penyebab": "Belum ada target kuantitatif & timeline pemerataan instalasi AC",
            "rekomendasi": "Prioritaskan kamar dengan keluhan \"panas\" pada tahap awal pengadaan AC",
        },
        {
            "faktor": "Material",
            "penyebab": "Insulasi atap/dinding kamar kurang optimal menahan panas",
            "rekomendasi": "Evaluasi material atap/dinding untuk kamar dengan keluhan berulang",
        },
    ],
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
                    top_freq = top["frekuensi"]

                    # Lookup Knowledge Base (case-insensitive key matching)
                    kb_entries = DSS_KNOWLEDGE_BASE.get(top_kategori)
                    if not kb_entries:
                        # Coba case-insensitive fallback
                        kb_lower = {k.lower(): v for k, v in DSS_KNOWLEDGE_BASE.items()}
                        kb_entries = kb_lower.get(top_kategori.lower(), [
                            {
                                "faktor": "Unknown",
                                "penyebab": "Belum tersedia analisis akar masalah untuk kategori ini.",
                                "rekomendasi": "Lakukan investigasi lanjutan terhadap keluhan ini."
                            }
                        ])

                    # Build table HTML for Fishbone
                    table_html = """
                    <table style="width:100%; border-collapse: collapse; margin-top: 10px; font-size: 13px;">
                        <thead>
                            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); text-align: left;">
                                <th style="padding: 8px 4px; color: #94a3b8; font-weight: 600;">Faktor (6M)</th>
                                <th style="padding: 8px 4px; color: #94a3b8; font-weight: 600;">Kemungkinan Penyebab</th>
                                <th style="padding: 8px 4px; color: #94a3b8; font-weight: 600;">Rekomendasi Tindakan</th>
                            </tr>
                        </thead>
                        <tbody>
                    """
                    for entry in kb_entries:
                        table_html += f"""
                            <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                                <td style="padding: 8px 4px; color: #38bdf8; font-weight: 500; vertical-align: top;">{entry['faktor']}</td>
                                <td style="padding: 8px 4px; color: #e2e8f0; vertical-align: top;">{entry['penyebab']}</td>
                                <td style="padding: 8px 4px; color: #34d399; vertical-align: top;">{entry['rekomendasi']}</td>
                            </tr>
                        """
                    table_html += """
                        </tbody>
                    </table>
                    """

                    # DSS Recommendation Card — premium styling
                    st.markdown(f"""
                    <div class="dss-card">
                        <span class="dss-badge">⚡ PRIORITAS UTAMA</span>
                        <div class="dss-dim-name">📌 {top_kategori}</div>
                        <div class="dss-score">Temuan Terbanyak: <strong>{top_freq}</strong> keluhan</div>
                        <div class="dss-separator"></div>
                        <div class="dss-label">🔍 Analisis Fishbone & Rekomendasi Tindakan (DSS):</div>
                        {table_html}
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
                # Urutkan ascending agar bar terbesar di atas
                df_findings = df_findings.sort_values("frekuensi", ascending=True)

                fig_findings = px.bar(
                    df_findings,
                    x="frekuensi",
                    y="frasa",
                    orientation="h",
                    text=df_findings.apply(
                        lambda row: f"{row['frekuensi']}x ({row['persentase']}%)", axis=1
                    ),
                    color_discrete_sequence=["#34d399"],
                )
                fig_findings.update_layout(
                    height=max(300, len(df_findings) * 50),
                    xaxis_title="Frekuensi Kemunculan",
                    yaxis_title="",
                    showlegend=False,
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
                    daftar_ulasan = finding.get("ulasan", [])
                    jumlah = finding["frekuensi"]

                    with st.expander(
                        f"📋 {kategori_nama} — {jumlah} ulasan",
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
