import httpx
import json
import os
import streamlit as st
from bs4 import BeautifulSoup
from data.dataset import get_books, get_store_locations, get_available_books_on_stores, get_book_description
from data.rag import RAG
from langchain.agents import create_agent
from langchain.messages import SystemMessage, HumanMessage, AIMessage
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, Field

@st.cache_resource
def get_rag_instance() -> tuple[RAG, RAG]:
    rag_books = RAG(
        "books", get_books(), ["title", "description", "author", "category_slug"]
    )
    rag_stores = RAG(
        "stores", get_store_locations(), ["name", "address"]
    )

    return rag_books, rag_stores


rag_books, rag_stores = get_rag_instance()

class BookInput(BaseModel):
    query: str = Field(
        default=None,
        description="The search query for books by title, author, or category.",
    )
    limit: int = Field(default=5, description="The maximum number of books to return.")


@tool(
    "get_books",
    args_schema=BookInput,
    description="Get books from the book store dataset based on a search query.",
)
def get_books_tool(query: str = None, limit: int = 5) -> str:
    global rag_books

    results = rag_books.search(query, limit)

    if results.empty:
        return "No books found for the given query."

    # Format as compact text
    output = []
    for idx, book in results.iterrows():
        output.append(
            f"{idx+1}. {book['title']} - {book['author']}\n"
            f"   Harga: Rp {book['final_price']:,} | Diskon: {book.get('discount', 0)}% | Kategori: {book['category_slug']}"
        )
    
    return "\n".join(output)


class BookDetailInput(BaseModel):
    query: str = Field(
        description="The search query for a specific book by title, ISBN, or slug. Should be as specific as possible.",
    )


@tool(
    "get_book_tool",
    args_schema=BookDetailInput,
    description="Get detailed information about a specific book including full description, ISBN, format, language, warehouse, and more. Use this when user asks for details about a specific book or wants to know more information beyond just title and price.",
)
def get_book_tool(query: str) -> str:
    global rag_books

    # Search for the most relevant book
    results = rag_books.search(query, limit=1)

    if results.empty:
        return "No book found for the given query."

    book = results.iloc[0]
    
    # Fetch detailed description from website using the new function
    description = book.get('description', 'Tidak ada deskripsi.')
    
    book_slug = book.get('slug')
    if book_slug:
        fetched_description = get_book_description(book_slug)
        if fetched_description:
            description = fetched_description
            print(f"Fetched description from website for: {book['title']}")
    
    # Format as readable text
    output = f"""
    DETAIL BUKU:
    Judul: {book['title']}
    Penulis: {book['author']}
    ISBN: {book.get('isbn', 'N/A')}
    Format: {book.get('format', 'N/A')}
    Bahasa: {book.get('lang', 'N/A')}
    Image: {book.get('image', '')}

    HARGA:
    Harga Normal: Rp {book.get('slice_price', 0):,}
    Harga Diskon: Rp {book['final_price']:,}
    Diskon: {book.get('discount', 0)}%

    KETERSEDIAAN:
    Status: {'Habis' if book.get('is_oos') else 'Tersedia'}
    Toko: {book.get('store_name', 'N/A')}
    Warehouse: {book.get('warehouse_slug', 'N/A')}

    DESKRIPSI:
    {description}

    INFO LAIN:
    Kategori: {book['category_slug']}
    SKU: {book.get('sku', 'N/A')}
    Slug: {book.get('slug', 'N/A')}
    """

    return output


class PriceFilterInput(BaseModel):
    query: str = Field(
        default=None,
        description="The search query for books by title, author, or category. Leave empty to search all books.",
    )
    price_min: int = Field(
        default=None,
        description="Minimum price in IDR. Use this to find books cheaper than a certain price.",
    )
    price_max: int = Field(
        default=None,
        description="Maximum price in IDR. Use this to find books more expensive than a certain price.",
    )
    limit: int = Field(default=10, description="The maximum number of books to return.")


@tool(
    "filter_books_by_price",
    args_schema=PriceFilterInput,
    description="Filter books by price range and search query. Use this when user asks for books cheaper than X, more expensive than Y, or within a price range. Supports combining price filters with search queries.",
)
def filter_books_by_price_tool(
    query: str = None, price_min: int = None, price_max: int = None, limit: int = 10
) -> str:
    global rag_books

    # If query is provided, use RAG search first
    if query:
        results = rag_books.search(query, limit=100)  # Get more results for filtering
    else:
        # If no query, get all books from dataset
        results = get_books()

    if results.empty:
        return "No books found for the given query."

    # Apply price filters
    if price_min is not None:
        results = results[results["final_price"] >= price_min]
    if price_max is not None:
        results = results[results["final_price"] <= price_max]

    if results.empty:
        return "No books found matching the price criteria."

    # Sort by price (ascending) and limit results
    results = results.sort_values("final_price").head(limit)

    # Format as compact text
    output = []
    for idx, book in results.iterrows():
        output.append(
            f"{len(output)+1}. {book['title']} - {book['author']}\n"
            f"   Harga: Rp {book['final_price']:,} | Diskon: {book.get('discount', 0)}% | Kategori: {book['category_slug']}"
        )
    
    return "\n".join(output)


class StoreInput(BaseModel):
    query: str = Field(
        default=None,
        description="The search query for stores by name or address.",
    )
    limit: int = Field(default=5, description="The maximum number of stores to return.")


@tool(
    "get_stores",
    args_schema=StoreInput,
    description="Search for Gramedia bookstores by store name or address. Returns store name, address, coordinates, type (online/offline), and opening hours. Use this when user asks about store locations, specific store names, or addresses.",
)
def get_stores_tool(query: str = None, limit: int = 5) -> str:
    global rag_stores

    results = rag_stores.search(query, limit)

    if results.empty:
        return "No stores found for the given query."

    # Format as compact text
    output = []
    for idx, store in results.iterrows():
        output.append(
            f"{len(output)+1}. {store['name']}\n"
            f"   Alamat: {store['address']}\n"
            f"   Tipe: {store['type']} | Jam Buka: {store.get('open_schedule', 'N/A')}"
        )
    
    return "\n".join(output)


class BookAvailabilityInput(BaseModel):
    book_query: str = Field(
        description="The search query for the book to check availability. Can be a title, author, or keyword.",
    )


@tool(
    "get_book_availability",
    args_schema=BookAvailabilityInput,
    description="Check which stores have a specific book available in stock. Use this when user asks where they can buy a specific book, which stores have it, or if a book is available at a certain store. Returns list of stores with the book in stock including store name, city, and availability type.",
)
def get_book_availability_tool(book_query: str) -> str:
    global rag_books

    # First find the book using RAG search
    results = rag_books.search(book_query, limit=1)

    if results.empty:
        return "No book found for the given query. Please try a more specific search."

    book = results.iloc[0]
    book_slug = book.get('slug')
    book_title = book.get('title')

    if not book_slug:
        print(f"Book slug not found for book: {book_title}")
        return f"Book '{book_title}' found but slug is missing."

    try:
        stores_df = get_available_books_on_stores(book_slug)
    except Exception as e:
        print(f"Error fetching availability: {e}")
        print(e)
        return f"Gagal mengecek ketersediaan buku '{book_title}'. Coba lagi nanti."

    if stores_df.empty:
        return f"Buku '{book_title}' saat ini tidak tersedia di toko manapun."

    # Format as compact text
    output = [f"Ketersediaan buku '{book_title}':"]
    for _, store in stores_df.iterrows():
        availability = "Offline saja" if store.get('is_only_available_offline') else "Online & Offline"
        output.append(
            f"{len(output)}. {store['name']} - {store['city']}\n"
            f"   Ketersediaan: {availability}"
        )
    
    output.append(f"\nTotal: {len(stores_df)} toko memiliki buku ini.")
    return "\n".join(output)

class State(MessagesState):
    pass


@st.cache_resource
def get_model():
    """Cache the LLM model to avoid recreating it."""
    return ChatOpenAI(
        model="openai/gpt-oss-120b:cheapest",
        temperature=1.0,
        max_retries=2,
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url="https://router.huggingface.co/v1"
    )


st.title("📚 Gramedia Assistant")

# Initialize checkpointer in session state
if "checkpointer" not in st.session_state:
    st.session_state.checkpointer = InMemorySaver()

# Initialize agent in session state
if "agent" not in st.session_state:
    model = get_model()
    system_prompt = """
Kamu adalah asisten katalog buku Gramedia. Tugasmu membantu pengguna menemukan buku dan toko Gramedia dari dataset yang tersedia.

**Untuk Pencarian Buku:**
- Gunakan tool get_books untuk pencarian umum dan menampilkan beberapa pilihan buku
- Gunakan tool get_book_tool ketika pengguna ingin detail lengkap dari buku tertentu (description, ISBN, format, dll)
- Gunakan tool filter_books_by_price ketika pengguna menyebut harga (lebih murah dari X, lebih mahal dari Y, atau range harga)
- Gunakan tool get_book_availability ketika pengguna bertanya di mana bisa beli buku tertentu, toko mana yang punya stok, atau ketersediaan buku
- Jika hasil kosong, jelaskan bahwa data tidak ditemukan dan tawarkan kata kunci lain
- Jangan mengarang judul/penulis di luar dataset
- Jika pengguna meminta rekomendasi, tampilkan beberapa opsi singkat (judul, penulis, kategori, harga bila tersedia)

**Format Tampilan Buku:**
- Ketika menampilkan informasi buku, SELALU sertakan gambar cover buku menggunakan markdown image syntax
- Data dari tool sudah include field 'image' yang berisi URL gambar
- Format gambar: ![Judul Buku](URL_gambar)
- Letakkan gambar di atas atau di samping informasi buku untuk visual yang menarik

**Untuk Pencarian Toko:**
- Gunakan tool get_stores ketika pengguna bertanya tentang lokasi toko, nama toko tertentu, atau alamat toko
- Tampilkan nama toko, alamat, tipe (online/offline), dan jam buka jika tersedia
- Jika user bertanya toko terdekat tanpa menyebut nama/alamat, sarankan mereka menyebutkan area/kota yang dimaksud

Jawaban harus ringkas, ramah, dan berbasis data. Format output dengan rapi menggunakan markdown.
"""
    st.session_state.agent = create_agent(
        model=model,
        system_prompt=SystemMessage(content=system_prompt),
        checkpointer=st.session_state.checkpointer,
        tools=[get_books_tool, get_book_tool, filter_books_by_price_tool, get_stores_tool, get_book_availability_tool],
    )

# Thread config for maintaining conversation
config = {"configurable": {"thread_id": "main_thread"}}

# Retrieve conversation history from checkpointer
try:
    state = st.session_state.agent.get_state(config)
    messages = state.values.get("messages", [])
except:
    messages = []

# Display conversation history
for idx, msg in enumerate(messages):
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.markdown(msg.content)
    elif isinstance(msg, AIMessage):
        # Skip tool call messages, only show final responses
        if msg.content and not msg.tool_calls:
            with st.chat_message("assistant"):
                st.markdown(msg.content)
    else:
        continue

if prompt := st.chat_input("💬 Ask about books or stores..."):
    user_message = HumanMessage(content=prompt)
    
    # Display user message immediately
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response with streaming
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        try:
            state = State(messages=user_message)

            # invoke the agent, streaming tokens from any llm calls directly
            for chunk, metadata in st.session_state.agent.stream(
                state, config=config, stream_mode="messages"
            ):
                if isinstance(chunk, AIMessage):
                    # Handle different content formats
                    if isinstance(chunk.content, str):
                        content_text = chunk.content
                    elif isinstance(chunk.content, list) and len(chunk.content) > 0:
                        if isinstance(chunk.content[0], dict):
                            content_text = chunk.content[0].get("text", "")
                        else:
                            content_text = str(chunk.content[0])
                    else:
                        content_text = ""

                    full_response = full_response + content_text
                    message_placeholder.markdown(full_response + "▌")

            # Once streaming is complete, display the final message without the cursor
            message_placeholder.markdown(full_response)
            
            # Rerun to update chat history from checkpointer
            st.rerun()
        except Exception as e:
            st.error(e)
            print(e)
