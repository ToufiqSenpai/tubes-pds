import asyncio
import nest_asyncio
import httpx
import pandas as pd
import streamlit as st

# Allow nested event loops
nest_asyncio.apply()

PAGE_SIZE = 20

# Configure client with limits and timeouts to prevent overwhelming the server
limits = httpx.Limits(max_keepalive_connections=5, max_connections=20)
timeout = httpx.Timeout(120.0, connect=60.0, pool=None)
http = httpx.AsyncClient(limits=limits, timeout=timeout)

async def get_book_categories() -> pd.DataFrame:
    response = await http.get("https://api-service.gramedia.com/api/v2/public/subcategory?parent_category=buku")
    categories = response.json()["data"]
    
    def flatten_subcategories(category: dict, parent_slug: str = None, depth: int = 0) -> list[dict]:
        flattened = []
        
        flattened.append({
            "title": category["title"],
            "slug": category["slug"],
            "image": category["image"],
            "parent_slug": parent_slug,
            "depth": depth,
        })
        
        if category.get("subcategory"):
            for subcat in category["subcategory"]:
                flattened.extend(
                    flatten_subcategories(subcat, parent_slug=category["slug"], depth=depth + 1)
                )
        
        return flattened
    
    all_categories = []
    for cat in categories:
        all_categories.extend(flatten_subcategories(cat))
    
    df = pd.DataFrame(all_categories)
    dtype_map = {
        "title": "string",
        "slug": "string",
        "image": "string",
        "parent_slug": "string",
        "depth": "int64",
    }
    valid_dtypes = {col: dtype for col, dtype in dtype_map.items() if col in df.columns}
    if valid_dtypes:
        df = df.astype(valid_dtypes)
    return df

async def get_books() -> pd.DataFrame:
    async def fetch_books_for_category(category_slug: str) -> list[dict]:
        """Fetch all books for a specific category with pagination."""
        response = await http.get(
            f"https://api-service.gramedia.com/api/v2/public/products?is_available_only=false&page=1&size={PAGE_SIZE}&slug={category_slug}"
        )
        data = response.json()
        total_pages = data["meta"]["total_page"]
        books = list(data["data"])

        if total_pages > 1:
            tasks = [
                http.get(
                    f"https://api-service.gramedia.com/api/v2/public/products?is_available_only=false&page={page}&size={PAGE_SIZE}&slug={category_slug}"
                )
                for page in range(2, total_pages + 1)
            ]
            responses = await asyncio.gather(*tasks)
            for resp in responses:
                books.extend(resp.json()["data"])

        # Add category_slug to each book
        for book in books:
            book["category_slug"] = category_slug

        return books

    # Get all book categories first
    categories_df = await get_book_categories()
    category_slugs = categories_df["slug"].tolist()

    # Fetch books for all categories in parallel
    all_books_tasks = [fetch_books_for_category(slug) for slug in category_slugs]
    all_books_lists = await asyncio.gather(*all_books_tasks)

    # Flatten all books into one list
    all_books = []
    for books in all_books_lists:
        all_books.extend(books)

    df = pd.DataFrame(all_books)
    
    # Rename columns
    df = df.rename(columns={"product_meta_id": "id"})
    
    dtype_map = {
        "id": "int64",
        "title": "string",
        "image": "string",
        "slug": "string",
        "author": "string",
        "final_price": "int64",
        "slice_price": "int64",
        "discount": "int64",
        "is_oos": "bool",
        "sku": "string",
        "category_slug": "string",
        "format": "string",
        "applied_promo_slug": "string",
        "store_name": "string",
        "isbn": "string",
        "warehouse_slug": "string",
        "warehouse_id": "int64",
        "lang": "category",
    }
    valid_dtypes = {col: dtype for col, dtype in dtype_map.items() if col in df.columns}
    if valid_dtypes:
        df = df.astype(valid_dtypes)
    return df

async def get_store_locations() -> pd.DataFrame:
    async def fetch_all(is_online: bool) -> list[dict]:
        response = await http.get(
            f"https://api-service.gramedia.com/api/v2/public/stores?is_online={str(is_online).lower()}&page=1&size={PAGE_SIZE}"
        )
        data = response.json()
        total_pages = data["meta"]["total_page"]
        stores = list(data["data"])

        if total_pages > 1:
            tasks = [
                http.get(
                    f"https://api-service.gramedia.com/api/v2/public/stores?is_online={str(is_online).lower()}&page={page}&size={PAGE_SIZE}"
                )
                for page in range(2, total_pages + 1)
            ]
            responses = await asyncio.gather(*tasks)
            for resp in responses:
                stores.extend(resp.json()["data"])

        return stores

    online_stores, offline_stores = await asyncio.gather(
        fetch_all(True),
        fetch_all(False),
    )

    df = pd.DataFrame(online_stores + offline_stores)
    dtype_map = {
        "name": "string",
        "address": "string",
        "latitude": "float64",
        "longitude": "float64",
        "open_schedule": "string",
        "slug": "string",
        "type": "category",
    }
    valid_dtypes = {col: dtype for col, dtype in dtype_map.items() if col in df.columns}
    if valid_dtypes:
        df = df.astype(valid_dtypes)
    return df

@st.cache_data()
def get_book_categories_cached() -> pd.DataFrame:
    return asyncio.run(get_book_categories())

@st.cache_data()
def get_books_cached() -> pd.DataFrame:
    return asyncio.run(get_books())

@st.cache_data()
def get_store_locations_cached() -> pd.DataFrame:
    return asyncio.run(get_store_locations())
    
if __name__ == "__main__":
    df_categories = asyncio.run(get_book_categories())
    print(f"Total categories fetched: {len(df_categories)}")
    print(df_categories.info())
    
    # df_stores = asyncio.run(get_store_locations())
    # print(f"Total stores fetched: {len(df_stores)}")
    # print(df_stores.head())