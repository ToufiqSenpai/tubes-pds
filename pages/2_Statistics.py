import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from data.dataset import get_books

# ==========================================
# KONFIGURASI TEMA: UNIVERSAL (KARTU PUTIH)
# ==========================================
# Kita reset ke default agar teks kembali hitam
plt.style.use('default') 

# Konfigurasi halaman
st.set_page_config(page_title="Dashboard Gramedia", layout="wide")

# Load Data
df_books = get_books()

# ==========================================
# JUDUL & KPI METRICS
# ==========================================
st.title("📚 Dashboard Analisis Buku Gramedia")
st.markdown("---")

# Hitung Metrik
total_books = len(df_books)
avg_price = df_books["final_price"].mean()
discounted_books = len(df_books[df_books["discount"] > 0])

col1, col2, col3 = st.columns(3)
col1.metric("📦 Total Buku", f"{total_books:,}")
col2.metric("🏷️ Rata-rata Harga", f"Rp {avg_price:,.0f}")
col3.metric("💸 Buku Diskon", f"{discounted_books:,}", f"{discounted_books/total_books:.1%}")

st.markdown("---")

# ==========================================
# FUNGSI BANTUAN UNTUK MEMBUAT "KARTU PUTIH"
# ==========================================
def format_white_card(fig, ax):
    """Membuat grafik memiliki background putih bersih (seperti kartu)"""
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    # Grid tipis agar mudah dibaca
    ax.grid(axis='y', linestyle='--', alpha=0.3, color='gray')
    
    # Hapus garis pinggir atas & kanan
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Pastikan warna text hitam/abu tua
    ax.xaxis.label.set_color('#333333')
    ax.yaxis.label.set_color('#333333')
    ax.tick_params(colors='#333333')
    ax.title.set_color('#333333')

# ==========================================
# BARIS 1: STOK & BAHASA
# ==========================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Status Stok")
    stock_counts = df_books["is_oos"].value_counts()
    
    fig1, ax1 = plt.subplots(figsize=(6, 4))
    
    ax1.pie(stock_counts.values, 
            labels=["Tersedia", "Habis (OOS)"], 
            autopct="%1.1f%%", 
            startangle=90,
            colors=['#4CAF50', '#F44336'], # Hijau & Merah Standard
            explode=[0.05, 0])
    
    # Set background putih
    fig1.patch.set_facecolor('white')
    st.pyplot(fig1)

with col2:
    st.subheader("🌍 Komposisi Bahasa")
    lang_counts = df_books["lang"].value_counts()
    
    fig2, ax2 = plt.subplots(figsize=(6, 4))
    bars = ax2.bar(lang_counts.index, lang_counts.values, color=['#2196F3', '#FFC107'])
    
    ax2.bar_label(bars, padding=3, color='black') # Text label hitam
    ax2.set_ylabel("Jumlah Buku")
    
    # Terapkan gaya kartu putih
    format_white_card(fig2, ax2)
    st.pyplot(fig2)

# ==========================================
# BARIS 2: TOP 10 PENULIS
# ==========================================
st.subheader("✍️ Top 10 Penulis Paling Produktif")

df_authors = df_books.copy()
df_authors["author"] = df_authors["author"].replace("-", "(Penulis Tidak Diketahui)")
df_authors["author"] = df_authors["author"].fillna("(Penulis Tidak Diketahui)")

top_authors = df_authors["author"].value_counts().head(10).sort_values(ascending=True)

fig3, ax3 = plt.subplots(figsize=(12, 6))
colors = ['#B0BEC5'] * (len(top_authors) - 1) + ['#E91E63'] # Abu & Pink

bars = ax3.barh(top_authors.index, top_authors.values, color=colors)
ax3.bar_label(bars, padding=5, fontweight='bold', color='black')

ax3.set_xlabel("Jumlah Buku")
ax3.set_xlim(right=max(top_authors.values) * 1.1)

format_white_card(fig3, ax3)
ax3.grid(axis='x', linestyle='--', alpha=0.3) # Grid X khusus bar horizontal

st.pyplot(fig3)

# ==========================================
# BARIS 3: HARGA & DISKON
# ==========================================
col3, col4 = st.columns(2)

with col3:
    st.subheader("💰 Distribusi Harga (Max 500rb)")
    harga_wajar = df_books[df_books["final_price"] < 500000]["final_price"]
    
    if not harga_wajar.empty:
        fig4, ax4 = plt.subplots()
        ax4.hist(harga_wajar, bins=25, color='#009688', edgecolor='white', alpha=0.9)
        
        ax4.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: format(int(x), ',')))
        plt.xticks(rotation=30)
        
        ax4.set_xlabel("Harga (Rp)")
        ax4.set_ylabel("Frekuensi")
        
        format_white_card(fig4, ax4)
        st.pyplot(fig4)

with col4:
    st.subheader("🏷️ Sebaran Diskon (%)")
    diskon_ada = df_books[df_books["discount"] > 0]["discount"]
    
    if not diskon_ada.empty:
        fig5, ax5 = plt.subplots()
        ax5.hist(diskon_ada, bins=20, color='#FF9800', edgecolor='white', alpha=0.9)
        
        ax5.set_xlabel("Besar Diskon (%)")
        ax5.set_ylabel("Jumlah Buku")
        
        format_white_card(fig5, ax5)
        st.pyplot(fig5)

# ==========================================
# BARIS 4: BOXPLOT HARGA
# ==========================================
st.subheader("📦 Perbandingan Harga per Kategori (Top 5)")

top5_cat = df_books["category_slug"].value_counts().head(5).index
filtered_cat = df_books[df_books["category_slug"].isin(top5_cat)]

fig6, ax6 = plt.subplots(figsize=(10, 5))
data_boxplot = [filtered_cat[filtered_cat["category_slug"] == c]["final_price"].dropna() for c in top5_cat]

# Properti Boxplot standard (Hitam/Putih aman)
ax6.boxplot(data_boxplot, labels=top5_cat)

ax6.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: format(int(x), ',')))
ax6.set_ylabel("Harga (Rp)")

format_white_card(fig6, ax6)
st.pyplot(fig6)