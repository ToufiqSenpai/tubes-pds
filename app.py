import streamlit as st
import math
import dotenv
import folium
import pandas as pd
from streamlit_folium import st_folium
from data.dataset import get_books, get_store_locations, get_available_books_on_stores, get_book_categories

dotenv.load_dotenv()

def maps_link(address):
    base_url = "https://www.google.com/maps/search/?api=1&query="
    return base_url + address.replace(" ", "+")

st.set_page_config(
    page_title="Gramedia Book Collections",
    layout="wide"
)

ITEMS_PER_PAGE = 20

if "page" not in st.session_state:
    st.session_state.page = "list"

if "selected_book" not in st.session_state:
    st.session_state.selected_book = None

books = get_books()
categories = get_book_categories()

# Merge books with categories to get category titles
books = books.merge(categories[['slug', 'title']], left_on='category_slug', right_on='slug', how='left', suffixes=('', '_category'))
books = books.rename(columns={'title_category': 'category_title'})

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
        st.write(f"🏷️ **Kategori:** {book.get('category_title', book['category_slug'])}")
        st.write(f"💰 **Harga:** Rp {book['final_price']:,}")
        st.markdown("---")
        st.write("🗺️ Toko yang Menjual Buku Ini")
        
        # Get book slug
        book_slug = book.get('slug')
        
        if book_slug:
            # Get stores that have this book available
            available_stores_df = get_available_books_on_stores(book_slug)
            
            if not available_stores_df.empty:
                # Load all store locations to get coordinates
                all_stores = get_store_locations()
                
                # Merge to get coordinates for available stores
                stores = available_stores_df.merge(
                    all_stores,
                    on='name',
                    how='inner'
                )
                
                if not stores.empty:
                    # Calculate center point from available stores
                    avg_lat = stores['latitude'].mean()
                    avg_lon = stores['longitude'].mean()
                    
                    # Create folium map centered on average location of available stores
                    m = folium.Map(
                        location=[avg_lat, avg_lon],
                        zoom_start=5,
                        tiles="OpenStreetMap"
                    )
                    
                    # Add marker for each store that has the book
                    for _, store in stores.iterrows():
                        if pd.notna(store['latitude']) and pd.notna(store['longitude']):
                            availability = "Offline saja" if store.get('is_only_available_offline') else "Online & Offline"
                            folium.Marker(
                                [store['latitude'], store['longitude']],
                                popup=f"<b>{store['name']}</b><br>{store['address']}<br><i>Ketersediaan: {availability}</i>",
                                tooltip=f"{store['name']} - {availability}",
                                icon=folium.Icon(
                                    color="red" if store.get('is_only_available_offline') else "blue",
                                    icon="book",
                                    prefix="fa"
                                )
                            ).add_to(m)
                    
                    # Display map
                    st_folium(m, width=700, height=400)
                    st.caption(f"📍 Buku tersedia di {len(stores)} toko (Merah: Offline saja | Biru: Online & Offline)")
                else:
                    st.info("Tidak dapat menemukan koordinat toko yang menjual buku ini.")
            else:
                st.warning("Buku ini saat ini tidak tersedia di toko manapun.")
        else:
            st.error("Slug buku tidak ditemukan.")
        
        st.markdown("---")

def list_page():
    st.title("📚 Gramedia Book Collections")

    col1, col2, col3 = st.columns(3)

    with col1:
        search_query = st.text_input("Cari buku berdasarkan judul")

    with col2:
        category_options = ["All"] + sorted([cat for cat in books["category_title"].dropna().unique() if cat])
        selected_category = st.selectbox("Filter kategori", category_options)

    with col3:
        sort_option = st.selectbox(
            "Urutkan berdasarkan",
            ["Judul (A-Z)", "Harga Termurah", "Harga Termahal"]
        )

    filtered_books = books.copy()

    if search_query:
        filtered_books = filtered_books[
            filtered_books["title"].str.contains(search_query, case=False, na=False)
        ]

    if selected_category != "All":
        filtered_books = filtered_books[
            filtered_books["category_title"] == selected_category
        ]

    if sort_option == "Judul (A-Z)":
        filtered_books = filtered_books.sort_values(by="title")
    elif sort_option == "Harga Termurah":
        filtered_books = filtered_books.sort_values(by="final_price")
    elif sort_option == "Harga Termahal":
        filtered_books = filtered_books.sort_values(by="final_price", ascending=False)

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

    cols = st.columns(4)

    for idx, (_, book) in enumerate(books_to_show.iterrows()):
        with cols[idx % 4]:
            with st.container(border=True):
                st.image(book["image"])

                st.subheader(book["title"])
                st.caption(book["author"])

                st.markdown(f"**Rp {book['final_price']:,}**")
                st.caption(f"🏷️ {book.get('category_title', book['category_slug'])}")

                if st.button("📖 Lihat Detail", key=f"detail_{book['id']}"):
                    st.session_state.selected_book = book
                    st.session_state.page = "detail"
                    st.rerun()

    st.caption(f"Menampilkan halaman {page} dari {total_pages}")

if st.session_state.page == "detail" and st.session_state.selected_book is not None:
    detail_page(st.session_state.selected_book)
else:
    list_page()

