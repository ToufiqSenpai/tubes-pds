import streamlit as st
from data.dataset import get_books
from data.rag import RAG
from langchain.agents import create_agent
from langchain.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import MessagesState
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, Field
from streamlit_chat import message as chat_message
from typing import Literal

@st.cache_resource
def get_rag_instance() -> tuple[RAG]:
    rag_books = RAG("books", get_books(), ["title", "description", "author", "category_slug"])
    
    return rag_books

rag_books = get_rag_instance()

class BookInput(BaseModel):
    query: str = Field(default=None, description="The search query for books by title, author, or category.")
    limit: int = Field(default=5, description="The maximum number of books to return.")

@tool("get_books", args_schema=BookInput, description="Get books from the book store dataset based on a search query.")
def get_books_tool(query: str = None, limit: int = 5) -> str:
    global rag_books
    
    results = rag_books.search(query, limit)
    
    if results.empty:
        return "No books found for the given query."
    
    print(results)
    
    return results.to_json(orient="records")

class State(MessagesState):
    pass

@st.cache_resource
def make_agent():
    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        max_tokens=None, 
        temperature=1.0, 
        max_retries=2
    )
    
    return create_agent(
        model=model,
        system_prompt=SystemMessage(content="You are a helpful assistant."),
        checkpointer=InMemorySaver(),
        tools=[get_books_tool],
    )

st.title("Assistant")
    
agent = make_agent()

if "messages" not in st.session_state:
    st.session_state.messages = [SystemMessage(
    """
    Kamu adalah asisten katalog buku Gramedia. Tugasmu membantu pengguna menemukan buku dari dataset yang tersedia. Selalu gunakan tool pencarian buku ketika pengguna menanyakan rekomendasi, judul, penulis, kategori, atau permintaan terkait stok/produk. Jika hasil kosong, jelaskan bahwa data tidak ditemukan dan tawarkan kata kunci lain. Jawaban harus ringkas, ramah, dan berbasis data. Jangan mengarang judul/penulis di luar dataset. Jika pengguna meminta rekomendasi, tampilkan beberapa opsi singkat (judul, penulis, kategori, harga bila tersedia) dan minta preferensi lanjutan.
    """
    )]

for idx, msg in enumerate(st.session_state.messages):
    if isinstance(msg, HumanMessage):
        chat_message(msg.content, is_user=True, key=f"user-{idx}")
    elif isinstance(msg, AIMessage):
        chat_message(msg.content, key=f"assistant-{idx}")
    else:
        continue

if prompt := st.chat_input("Ask me anything about the book store data!"):
    user_message = HumanMessage(content=prompt)
    st.session_state.messages.append(user_message)
    chat_message(prompt, is_user=True, key=f"user-{len(st.session_state.messages) - 1}")

    message_placeholder = st.empty()
    full_response = ""
    
    try:
        state = State(messages=user_message)
        config = {"configurable": {"thread_id": "thread"}}
        
        # invoke the agent, streaming tokens from any llm calls directly
        for chunk, metadata in agent.stream(state, config=config, stream_mode="messages"):
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
        message_placeholder.empty()
        chat_message(full_response, key=f"assistant-{len(st.session_state.messages)}")

        # Add the complete message to session state
        st.session_state.messages.append(AIMessage(content=full_response))
    except Exception as e:
        st.error(e)
        print(e)
