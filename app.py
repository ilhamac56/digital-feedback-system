"""
Digital Feedback System & Monitoring Dashboard
Kampung Sumber Alam Resort
=============================================
MAIN — Entry point aplikasi.
Berisi: Konfigurasi, Navigasi, dan Routing.

Kode terpisah menjadi beberapa modul:
- core_utils.py    → CORE: Database & Utilities (CSS, Nav)
- process_nlp.py   → PROCESS: Analisis NLP & sentimen
- input_form.py    → INPUT: Form tamu, login, upload OTA
- output_dashboard.py → OUTPUT: Dashboard monitoring

Jalankan: streamlit run app.py
"""

import streamlit as st
from core_utils import init_database, inject_css, do_logout

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
# IMPORT MODUL INPUT-PROCESS-OUTPUT
# ============================================================
from input_form import page_guest_form, page_login, page_upload_ota
from output_dashboard import page_dashboard_monitoring


# ============================================================
# HALAMAN ADMIN: ROUTING INTERNAL (DASHBOARD / UPLOAD OTA)
# ============================================================

def page_admin_dashboard():
    """Render halaman admin dengan navigasi sidebar internal."""
    inject_css()

    # --- Sidebar: Branding + Menu Admin + Logout ---
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding: 1.2rem 0;">
            <div style="font-size:2.8rem; animation: float 3s ease-in-out infinite;">🏨</div>
            <h2 style="margin:0; font-size:1.15rem; font-weight:800; background:linear-gradient(135deg,#34d399,#10b981); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">Kampung Sumber Alam</h2>
            <p style="margin:4px 0 0; font-size:0.75rem; font-weight:500; color:#6ee7b7 !important; letter-spacing:1px; text-transform:uppercase;">Panel Admin</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # Menu navigasi admin
        admin_menu = st.radio(
            "📂 Menu Admin",
            ["📊 Dashboard Monitoring", "📤 Upload Data (Excel)"],
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
