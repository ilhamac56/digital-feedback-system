"""
OUTPUT — Modul Dashboard Monitoring & Visualisasi
==================================================
Berisi halaman dashboard admin untuk menampilkan:
- KPI Cards (total ulasan, sentimen negatif, rata-rata rating, rata-rata SERVPERF)
- Grafik bar rata-rata skor per dimensi SERVPERF
- Donut chart distribusi sentimen
- Tabel data ulasan tamu dengan filter
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta, datetime, timezone

from core_utils import load_all_feedback

# Timezone WIB (UTC+7) — agar filter tanggal sesuai waktu lokal Indonesia
_WIB = timezone(timedelta(hours=7))


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

    # Terapkan filter
    df_filtered = df.copy()

    if filter_sentimen != "Semua":
        df_filtered = df_filtered[df_filtered["sentimen_akhir"] == filter_sentimen]
    if filter_dimensi != "Semua":
        df_filtered = df_filtered[
            df_filtered["dimensi_terdeteksi"].str.contains(filter_dimensi, na=False)
        ]

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

    # --- Bar Chart: Rata-rata Skor Dimensi ---
    with chart_col1:
        st.markdown('<p class="section-header">📊 Rata-rata Skor per Dimensi SERVPERF</p>',
                    unsafe_allow_html=True)

        dim_means = pd.DataFrame({
            "Dimensi": ["Q1 Reliability", "Q2 Assurance", "Q3 Tangibles",
                         "Q4 Empathy", "Q5 Responsiveness"],
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
        },
    )
