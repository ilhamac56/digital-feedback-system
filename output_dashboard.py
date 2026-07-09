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
from datetime import date, timedelta, datetime, timezone

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
# REKOMENDASI DSS RULE-BASED (FITUR 4)
# ============================================================
DSS_RECOMMENDATIONS = {
    "Tangibles": (
        "Fokuskan pengawasan minggu ini pada **perbaikan fasilitas fisik dan kebersihan kamar**. "
        "Lakukan inspeksi rutin terhadap kondisi kamar, toilet, dan area publik."
    ),
    "Reliability": (
        "Tingkatkan **konsistensi layanan** agar sesuai dengan janji dan ekspektasi tamu. "
        "Pastikan proses check-in/check-out, reservasi, dan informasi harga akurat."
    ),
    "Responsiveness": (
        "Evaluasi **kecepatan pelayanan staf front-office** dalam menangani keluhan. "
        "Terapkan SOP waktu respons maksimal untuk setiap permintaan tamu."
    ),
    "Assurance": (
        "Adakan **pelatihan tambahan** untuk meningkatkan kompetensi dan kesopanan staf. "
        "Pastikan keamanan area hotel dan keramahan pelayanan terjaga."
    ),
    "Empathy": (
        "Dorong staf untuk lebih **proaktif memahami dan memenuhi kebutuhan personal tamu**. "
        "Latih kemampuan komunikasi empatik dan perhatian terhadap detail."
    ),
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

        sentimen_counts = df_filtered["sentimen_akhir"].value_counts().reset_index()
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
    # BARIS BARU: Donut Reservasi + Rekomendasi DSS (FITUR 3 & 4)
    # ----------------------------------------------------------------
    dss_col1, dss_col2 = st.columns([2, 3], gap="large")

    # --- Donut Chart: Proporsi Metode Reservasi (FITUR 3) ---
    with dss_col1:
        st.markdown('<p class="section-header">🏷️ Proporsi Metode Reservasi</p>',
                    unsafe_allow_html=True)

        reservasi_counts = df_filtered["jenis_reservasi"].value_counts().reset_index()
        reservasi_counts.columns = ["Metode", "Jumlah"]

        reservasi_color_map = {
            "Aplikasi Online (OTA)": "#3498db",
            "Walk-in": "#e67e22",
            "Tidak Diketahui": "#95a5a6",
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
            height=400,
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", size=12),
            margin=dict(t=30, b=30, l=40, r=40),
            annotations=[
                dict(
                    text=f"<b>{total_ulasan}</b><br>Tamu",
                    x=0.5, y=0.5,
                    font_size=14,
                    showarrow=False,
                    font=dict(family="Inter", color="#1e293b"),
                )
            ],
        )
        st.plotly_chart(fig_reservasi, use_container_width=True)

    # --- Rekomendasi Prioritas DSS (FITUR 4) ---
    with dss_col2:
        st.markdown('<p class="section-header">💡 Rekomendasi Prioritas (DSS)</p>',
                    unsafe_allow_html=True)

        if total_ulasan > 0:
            # Hitung rata-rata per dimensi (backend variable names)
            dim_scores = {
                "Tangibles": df_filtered["q3_tangibles"].mean(),
                "Reliability": df_filtered["q1_reliability"].mean(),
                "Responsiveness": df_filtered["q5_responsiveness"].mean(),
                "Assurance": df_filtered["q2_assurance"].mean(),
                "Empathy": df_filtered["q4_empathy"].mean(),
            }

            # Cari dimensi dengan skor terendah
            lowest_dim = min(dim_scores, key=dim_scores.get)
            lowest_score = dim_scores[lowest_dim]
            lowest_label = DIMENSION_LABEL_MAP[lowest_dim]
            recommendation = DSS_RECOMMENDATIONS[lowest_dim]

            st.warning(
                f"**Dimensi Terendah: {lowest_label}** (Skor rata-rata: **{lowest_score:.2f}**/5)\n\n"
                f"{recommendation}",
                icon="💡",
            )

            # Tampilkan ringkasan skor semua dimensi untuk konteks
            st.markdown("**📋 Ringkasan Skor Seluruh Dimensi:**")
            for dim_key, score in sorted(dim_scores.items(), key=lambda x: x[1]):
                label = DIMENSION_LABEL_MAP[dim_key]
                bar_fill = int(score / 5 * 100)
                indicator = "🔴" if score < 3.0 else "🟡" if score < 4.0 else "🟢"
                st.markdown(
                    f"{indicator} **{label}**: {score:.2f}/5",
                )
        else:
            st.info("Tidak cukup data untuk menghasilkan rekomendasi.")

    # ----------------------------------------------------------------
    # LOG TEMUAN KRITIS — EKSTRAKSI FRASA NEGATIF ASPECT-BASED (FITUR 5)
    # ----------------------------------------------------------------
    st.markdown('<p class="section-header">\u26a0\ufe0f Log Temuan Kritis (Aspect-Based)</p>',
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
                color="frekuensi",
                color_continuous_scale=["#f5b7b1", "#e74c3c", "#922b21"],
            )
            fig_findings.update_layout(
                height=max(300, len(df_findings) * 45),
                xaxis_title="Frekuensi Kemunculan",
                yaxis_title="",
                showlegend=False,
                coloraxis_showscale=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", size=13),
                margin=dict(t=20, b=40, l=200, r=30),
            )
            fig_findings.update_traces(
                textposition="outside",
                marker_line_width=0,
                marker_cornerradius=6,
            )
            st.plotly_chart(fig_findings, use_container_width=True)

            st.caption(
                f"Berdasarkan **{len(ulasan_negatif_list)}** ulasan bersentimen Negatif "
                f"(dari {total_ulasan} ulasan terfilter). "
                f"Frasa diekstrak secara otomatis dari konteks kalimat (kata benda + kata sifat negatif)."
            )

            # --- Tabel detail temuan ---
            with st.expander("\ud83d\udccb Lihat Detail Tabel Temuan Kritis", expanded=False):
                df_table = pd.DataFrame(findings)
                df_table["frasa"] = df_table["frasa"].str.capitalize()
                df_table.columns = ["Frasa Temuan", "Frekuensi", "Proporsi (%)"]
                df_table.index = range(1, len(df_table) + 1)
                df_table.index.name = "No"
                st.dataframe(
                    df_table,
                    use_container_width=True,
                    column_config={
                        "Frasa Temuan": st.column_config.TextColumn(width="large"),
                        "Frekuensi": st.column_config.NumberColumn(format="%d"),
                        "Proporsi (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    },
                )
        else:
            st.info("Tidak ditemukan frasa temuan negatif yang cocok dengan kamus leksikon.")
    else:
        st.success("\ud83c\udf89 Tidak ada ulasan bersentimen Negatif pada data yang terfilter.")

    # ----------------------------------------------------------------
    # TABEL DATA — termasuk kolom X1–X5 dan Jenis Reservasi
    # ----------------------------------------------------------------
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
            "X1 Reliability": st.column_config.NumberColumn(format="%d"),
            "X2 Assurance": st.column_config.NumberColumn(format="%d"),
            "X3 Tangibles": st.column_config.NumberColumn(format="%d"),
            "X4 Empathy": st.column_config.NumberColumn(format="%d"),
            "X5 Responsiveness": st.column_config.NumberColumn(format="%d"),
            "Sentimen": st.column_config.TextColumn(width="small"),
            "Jenis Reservasi": st.column_config.TextColumn(width="medium"),
        },
    )
