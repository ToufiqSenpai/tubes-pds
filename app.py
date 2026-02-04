import streamlit as st
import math
import dotenv
from data.dataset import get_books

dotenv.load_dotenv()

# =============================
# HELPER GOOGLE MAPS
# =============================
def maps_link(address):
    base_url = "https://www.google.com/maps/search/?api=1&query="
    return base_url + address.replace(" ", "+")

# =============================
# CONFIG
# =============================
st.set_page_config(
    page_title="Gramedia Book Collections",
    layout="wide"
)

ITEMS_PER_PAGE = 4

# =============================
# SESSION STATE
# =============================
if "page" not in st.session_state:
    st.session_state.page = "list"

if "selected_book" not in st.session_state:
    st.session_state.selected_book = None

# =============================
# LOAD DATA
# =============================
books = get_books()

# =============================
# HALAMAN DETAIL
# =============================
def detail_page(book):
    if st.button("⬅ Kembali"):
        st.session_state.page = "list"
        st.session_state.selected_book = None
        st.rerun()

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("---")
        st.image(book["image"])
        st.markdown("---")
        st.write("Buku Tersedia Di Gramedia")

    with col2:
        st.markdown("---")
        st.title(book["title"])
        st.write(f"✍️ **Penulis:** {book['author']}")
        st.write(f"🏷️ **Kategori:** {book['category_slug']}")
        st.write(f"💰 **Harga:** Rp {book['final_price']:,}")
        st.markdown("---")
        location = books.get("location", "Gramedia Indonesia")
        maps_url = maps_link(location)
        st.write("🗺️ Peta Lokasi Toko")
        st.markdown(
            f"""
            <iframe
                width="100%"
                height="225"
                style="border:0"
                loading="lazy"
                allowfullscreen
                src="https://www.google.com/maps?q={location.replace(" ", "+")}&output=embed">
            </iframe>
            """,
            unsafe_allow_html=True
        )
        st.markdown("---")

# =============================
# HALAMAN LIST
# =============================
def list_page():
    st.title("📚 Gramedia Book Collections")

    # ---------- FILTER & SEARCH ----------
    col1, col2, col3 = st.columns(3)

    with col1:
        search_query = st.text_input("Cari buku berdasarkan judul")

    with col2:
        categories = ["All"] + sorted(list(books["category_slug"].unique()))
        selected_category = st.selectbox("Filter kategori", categories)

    with col3:
        sort_option = st.selectbox(
            "Urutkan berdasarkan",
            ["Judul (A-Z)", "Harga Termurah", "Harga Termahal"]
        )

    # ---------- FILTER LOGIC ----------
    filtered_books = books.copy()

    if search_query:
        filtered_books = filtered_books[
            filtered_books["title"].str.contains(search_query, case=False, na=False)
        ]

    if selected_category != "All":
        filtered_books = filtered_books[
            filtered_books["category_slug"] == selected_category
        ]

    # ---------- SORTING ----------
    if sort_option == "Judul (A-Z)":
        filtered_books = filtered_books.sort_values(by="title")
    elif sort_option == "Harga Termurah":
        filtered_books = filtered_books.sort_values(by="final_price")
    elif sort_option == "Harga Termahal":
        filtered_books = filtered_books.sort_values(by="final_price", ascending=False)

    # ---------- PAGINATION ----------
    total_items = len(filtered_books)
    total_pages = max(1, math.ceil(total_items / ITEMS_PER_PAGE))

    page = st.number_input(
        "Halaman",
        min_value=1,
        max_value=total_pages,
        step=1
    )

    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    books_to_show = filtered_books.iloc[start:end]

    # ---------- CARD LIST ----------
    cols = st.columns(4)

    for idx, (_, book) in enumerate(books_to_show.iterrows()):
        with cols[idx % 4]:
            with st.container(border=True):
                st.image(book["image"])

                st.subheader(book["title"])
                st.caption(book["author"])

                st.markdown(f"**Rp {book['final_price']:,}**")
                st.caption(f"🏷️ {book['category_slug']}")

                if st.button("📖 Lihat Detail", key=f"detail_{book['id']}"):
                    st.session_state.selected_book = book
                    st.session_state.page = "detail"
                    st.rerun()

    st.caption(f"Menampilkan halaman {page} dari {total_pages}")

# =============================
# ROUTER
# =============================
if st.session_state.page == "detail" and st.session_state.selected_book is not None:
    detail_page(st.session_state.selected_book)
else:
    list_page()

