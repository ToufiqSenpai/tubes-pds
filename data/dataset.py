import asyncio
import nest_asyncio
import httpx
import huggingface_hub as hf_hub
import pandas as pd
import os
import streamlit as st
import tempfile
from abc import ABC, abstractmethod
from typing import Optional

# Allow nested event loops
nest_asyncio.apply()

PAGE_SIZE = 20

# Configure client with limits and timeouts to prevent overwhelming the server
limits = httpx.Limits(max_keepalive_connections=5, max_connections=20)
timeout = httpx.Timeout(120.0, connect=60.0, pool=None)
http = httpx.AsyncClient(limits=limits, timeout=timeout)

hf_login = False
REPOSITORY_ID = "mhmtaufiq/gramedia-datasets"

class Dataset(ABC):
    """Abstract base class for managing datasets."""
    
    def __init__(self, filename: str):
        self._filename = filename
    
    @abstractmethod
    async def _fetch_dataset(self) -> pd.DataFrame:
        """Fetch dataset from the API."""
        pass
    
    def _load_local(self) -> Optional[pd.DataFrame]:
        """Load dataset from local storage if it exists."""
        file_path = self._get_dataset_path()
        if os.path.exists(file_path):
            df = pd.read_parquet(file_path)
            return df
        return None
    
    def _save_local(self, df: pd.DataFrame):
        """Save dataset to local storage."""
        file_path = self._get_dataset_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.to_parquet(file_path, index=False)
        
    def _get_dataset_dir(self) -> str:
        base_dir = tempfile.gettempdir()
        return os.path.join(base_dir, "gramedia_datasets")

    def _get_dataset_path(self) -> str:
        return os.path.join(self._get_dataset_dir(), self._filename)
    
    def _check_exists_on_hf(self) -> bool:
        """Check if dataset exists on HuggingFace Hub."""
        try:
            hf_hub.hf_hub_download(
                repo_id=REPOSITORY_ID,
                filename=self._filename,
                repo_type="dataset",
                local_files_only=False,
            )
            return True
        except Exception:
            return False
    
    def _download_from_hf(self) -> pd.DataFrame:
        """Download dataset from HuggingFace Hub."""
        try:
            file_path = hf_hub.hf_hub_download(
                repo_id=REPOSITORY_ID,
                filename=self._filename,
                repo_type="dataset",
            )
            df = pd.read_parquet(file_path)
            return df
        except Exception as e:
            print(f"Error downloading {self._filename}: {e}")
            raise
    
    def _upload_to_hf(self):
        """Upload dataset to HuggingFace Hub."""
        global hf_login
        
        if not hf_login:
            token = os.environ.get("OPENAI_API_KEY")
                
            if token:
                hf_hub.login(token=token)
                hf_login = True
            else:
                print("Please login to HuggingFace Hub...")
                hf_hub.login()
                hf_login = True
                    
        try:
            hf_hub.create_repo(repo_id=REPOSITORY_ID, repo_type="dataset", exist_ok=True)
            hf_hub.upload_file(
                path_or_fileobj=self._get_dataset_path(),
                path_in_repo=self._filename,
                repo_id=REPOSITORY_ID,
                repo_type="dataset",
            )
        except Exception as e:
            print(f"Error uploading {self._filename}: {e}")
            raise
    
    async def get(self) -> pd.DataFrame:
        """
        Get dataset with priority: local -> HuggingFace -> API.
        
        Args:
            force_fetch: If True, always fetch from API
            
        Returns:
            DataFrame with dataset
        """
        # Check local storage first
        df = self._load_local()
        if df is not None:
            return df
    
        # Check HuggingFace
        if self._check_exists_on_hf():
            df = self._download_from_hf()
            self._save_local(df)
            return df
        
        # Fetch from API
        df = await self._fetch_dataset()
        
        # Save locally and upload to HuggingFace
        self._save_local(df)
        self._upload_to_hf()

        return df


class BookCategoriesDataset(Dataset):
    """Manages book categories dataset."""
    
    def __init__(self):
        super().__init__("book_categories.parquet")
    
    async def _fetch_dataset(self) -> pd.DataFrame:
        """Fetch book categories from API."""
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


class BooksDataset(Dataset):
    """Manages books dataset."""
    
    def __init__(self):
        super().__init__("books.parquet")
    
    async def _fetch_dataset(self) -> pd.DataFrame:
        """Fetch books from API."""
        description_semaphore = asyncio.Semaphore(10)  # Limit concurrent description fetches
        
        async def fetch_description(slug: str) -> Optional[str]:
            async with description_semaphore:
                try:
                    res = await http.get(f"https://www.gramedia.com/_next/data/ey4L3i4wZwf5ANxjLrGrb/products/{slug}.json?productDetailSlug={slug}")
                    data = res.json()
                    
                    return data["pageProps"]["productDetailMeta"]["description"]
                except Exception as e:
                    print(f"Error fetching description for slug {slug}: {e}")
                    
                    return None
                
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

            for book in books:
                # Add category_slug to each book
                book["category_slug"] = category_slug

            # Fetch descriptions in parallel
            description_tasks = [fetch_description(book["slug"]) for book in books]
            descriptions = await asyncio.gather(*description_tasks)
            for book, description in zip(books, descriptions):
                book["description"] = description
                
            return books

        # Get all book categories first
        categories_manager = BookCategoriesDataset(self.repo_id)
        categories_df = await categories_manager.get()
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
            "description": "string",
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


class StoreLocationsDataset(Dataset):
    """Manages store locations dataset."""
    def __init__(self):
        super().__init__("store_locations.parquet")
    
    async def _fetch_dataset(self) -> pd.DataFrame:
        """Fetch store locations from API."""
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
    
@st.cache_data
def get_books() -> pd.DataFrame:
    return asyncio.run(BooksDataset().get())

@st.cache_data
def get_book_categories() -> pd.DataFrame:
    return asyncio.run(BookCategoriesDataset().get())

@st.cache_data
def get_store_locations() -> pd.DataFrame:
    return asyncio.run(StoreLocationsDataset().get())
