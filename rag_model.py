import os
import time
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
import pandas as pd

# Load environment variables
load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Initialize embeddings and LLM
embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},  # or "cuda" if you have a GPU
        encode_kwargs={"normalize_embeddings": True},
    )
llm = ChatGroq(groq_api_key=groq_api_key, model_name="Llama3-8b-8192")

# Define prompt
prompt = ChatPromptTemplate.from_template(
    """
    You are an onboarding assistant helping new employees.

    Answer the user's question in a clear, direct, and professional manner using only the information provided in the following context.
    If the context does not contain the exact answer, use your best judgment to provide a helpful and relevant response.

    Always be confident and supportive. Do not mention that the information came from the context. 
    Do not say "based on the context" or "the document says".
    
    <context>
    {context}
    <context>
    Question:{input}
    """
)


# Function to create vector embeddings from pdf
def create_or_load_vector_embedding(persist_directory="vector_store"):


    if os.path.exists(persist_directory):
        print("Loading existing vector database...")
        vectors = FAISS.load_local(persist_directory, embedding_model, allow_dangerous_deserialization=True)
    else:
        print("Creating new vector database from documents...")
        loader = PyPDFDirectoryLoader(persist_directory)  # Folder must exist
        docs = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        final_documents = text_splitter.split_documents(docs[:50])
        vectors = FAISS.from_documents(final_documents, embedding_model)
        vectors.save_local(persist_directory)
        print("Vector database created and saved locally.")
    
    return vectors

def load_excel_documents(file_path):
    df = pd.read_excel(file_path)

    # Create one Document per row, combining all columns into one text blob
    documents = []
    for idx, row in df.iterrows():
        content = "\n".join([f"{col}: {row[col]}" for col in df.columns])
        documents.append(Document(page_content=content))
    return documents

# Function to create vector embeddings from excel
def create_or_load_vector_embedding_for_excel(filepath_excel, persist_directory="vector_store_excel"):
    

    if os.path.exists(persist_directory):
        print("Loading existing vector database...")
        vectors = FAISS.load_local(persist_directory, embedding_model, allow_dangerous_deserialization=True)
    else:
        print("Creating new vector database from Excel file...")
        documents = load_excel_documents(filepath_excel)  # <-- Your Excel file path

        # Optional: split long documents
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        final_documents = text_splitter.split_documents(documents)

        vectors = FAISS.from_documents(final_documents, embedding_model)
        vectors.save_local(persist_directory)
        print("Vector database created and saved locally.")
    
    return vectors

if __name__ == "__main__":
    print("Building vector database from documents...")
    onboarding_filepath = './onboarding_template.xlsx'
    vectors = create_or_load_vector_embedding_for_excel(onboarding_filepath)
    print("Vector Database is ready.\n")

    user_prompt = input("Enter your query: ")

    if user_prompt:
        document_chain = create_stuff_documents_chain(llm, prompt)
        retriever = vectors.as_retriever()
        retrieval_chain = create_retrieval_chain(retriever, document_chain)

        start = time.process_time()
        response = retrieval_chain.invoke({'input': user_prompt})
        print(f"\nResponse time: {time.process_time() - start:.2f} seconds\n")

        print("Answer:")
        print(response['answer'])
