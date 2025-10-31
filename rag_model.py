import os
import time
import re
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import Embeddings
from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames as EmbedParams
from ibm_watsonx_ai.foundation_models.utils.enums import EmbeddingTypes
from langchain_groq import ChatGroq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_core.documents import Document
import pandas as pd
import logging
import ibm_cloud
from typing import List, Dict, Any
import shutil
import mongoclient

# Logging Configuration
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Prompt Template as Constant
PROMPT_TEMPLATE = """
You are an onboarding assistant helping new employees onboard.

Answer the user's question in a clear, direct, and professional manner using only the information provided in the following context.
If the context does not contain the exact answer, use your best judgment from your knowledge to provide a helpful and relevant response.

Always be confident and supportive. Do not mention that the information came from the context. 
Do not say "based on the context" or "the document says".

<context>
{context}
<context>
Question:{input}
"""
# IBM watsonx.ai credentials for embeddings
watsonx_api_key = os.getenv("WATSONX_API_KEY")
watsonx_project_id = os.getenv("WATSONX_PROJECT_ID")
watsonx_url = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

# Check if we have Watson credentials
if not watsonx_project_id:
    raise ValueError("WATSONX_PROJECT_ID must be set in environment variables")

if not watsonx_api_key:
    raise ValueError("WATSONX_API_KEY must be set in environment variables")

# Configure Watson embedding parameters
embed_params = {
    EmbedParams.TRUNCATE_INPUT_TOKENS: 512,
    EmbedParams.RETURN_OPTIONS: {
        'input_text': False
    }
}

# Initialize Watson Embeddings
logger.info("Initializing IBM Watson AI Embeddings...")
_watson_embeddings = Embeddings(
    model_id=EmbeddingTypes.IBM_SLATE_125M_ENG,
    params=embed_params,
    credentials=Credentials(
        api_key=watsonx_api_key,
        url=watsonx_url
    ),
    project_id=watsonx_project_id,
    batch_size=1000,
    concurrency_limit=5,
    persistent_connection=True
)
logger.info("Watson Embeddings initialized successfully")

# Create a wrapper class to make Watson Embeddings compatible with LangChain FAISS
class WatsonEmbeddingsWrapper:
    """Wrapper to make Watson Embeddings compatible with LangChain's FAISS"""
    
    def __init__(self, watson_embeddings):
        self.watson_embeddings = watson_embeddings
    
    def embed_documents(self, texts):
        """Embed a list of documents"""
        return self.watson_embeddings.embed_documents(texts)
    
    def embed_query(self, text):
        """Embed a single query"""
        return self.watson_embeddings.embed_query(text)
    
    def __call__(self, text):
        """Make the object callable for FAISS compatibility"""
        return self.embed_query(text)

# Create the wrapper instance
embedding_model = WatsonEmbeddingsWrapper(_watson_embeddings)

# Initialize Groq LLM
groq_api_key = os.getenv("GROQ_API_KEY")
llm = ChatGroq(groq_api_key=groq_api_key, model_name="llama-3.1-8b-instant")
prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
retrieval_chain = None

class MyBuddy:
    def __init__(self, file, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initializes the MyBuddy onboarding assistant.

        param file: Onboarding file.
        param chunk_size: Size of text chunks for embedding.
        param chunk_overlap: Overlap between text chunks.
        """
        self.onboarding_file = file
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.groq_api_key = groq_api_key
        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY is not set in environment variables.")


    def extract_links_from_text(self, text: str) -> List[str]:
        """
        Extract URLs from text using regex pattern.
        
        :param text: Text to extract URLs from
        :return: List of extracted URLs
        """
        # URL regex pattern
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
        return re.findall(url_pattern, str(text))
    
    def fetch_content_from_url(self, url: str) -> str:
        """
        Fetch content from a URL.
        
        :param url: URL to fetch content from
        :return: Extracted text content from the URL
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.extract()
                
            # Get text
            text = soup.get_text(separator='\n')
            
            # Break into lines and remove leading and trailing space on each
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # Remove blank lines
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return f"Content from {url}:\n{text}"
        except Exception as e:
            logger.error(f"Error fetching content from {url}: {e}")
            return f"Failed to fetch content from {url}: {str(e)}"
    
    def load_excel_documents(self) -> List[Document]:
        """
        Load documents from Excel file and extract content from any links found.
        
        :return: List of Document objects
        """
        df = pd.read_excel(self.onboarding_file)
        documents = []
        
        # Process each row in the Excel file
        for _, row in df.iterrows():
            # Create the base document from the row
            row_content = "\n".join([f"{col}: {row[col]}" for col in df.columns])
            documents.append(Document(page_content=row_content))
            
            # Extract links from each cell in the row
            for col in df.columns:
                cell_value = row[col]
                links = self.extract_links_from_text(cell_value)
                
                # Fetch content from each link and create a new document
                for link in links:
                    logger.info(f"Found link: {link}, fetching content...")
                    link_content = self.fetch_content_from_url(link)
                    if link_content:
                        documents.append(Document(
                            page_content=link_content,
                            metadata={"source": link, "related_to": f"{col}: {cell_value}"}
                        ))
        
        return documents

    def create_or_load_vector_embedding_for_excel(self,team_name):
        """
        Creates or loads vector embeddings from the Excel document.
        """
        logger.info("Creating new vector database from Excel file...")
        documents = self.load_excel_documents()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
        final_documents = text_splitter.split_documents(documents)

        vectors = FAISS.from_documents(final_documents, embedding_model)
        # Add save to bucket logic here
        vectors.save_local("./vector-db-local/")
        print("vector save to local")
        faiss_url,pkl_url = ibm_cloud.save_vector_data("./vector-db-local",team_name)
        print("vector save to cloud")
        mongoclient.save_vector_metadata_to_mongo(team_name,faiss_url,pkl_url)
        print("vector save to mongo")
        shutil.rmtree("./vector-db-local/")
        logger.info("Vector database created and saved locally.")


def load_all_teams_data():
    """
    Load vector data for all teams from MongoDB.
    This creates a combined retrieval chain with data from all teams.
    """
    global retrieval_chain
    
    logger.info("Loading data for all teams...")
    
    # Get all team names from MongoDB
    team_names = mongoclient.get_all_teams()
    
    if not team_names:
        logger.warning("No teams found in the database")
        return
    
    # Create a list to store all vector stores
    all_vectors = []
    
    # Load data for each team
    for team_name in team_names:
        try:
            logger.info(f"Loading data for team: {team_name}")
            
            # Fetch vector URLs for this team
            faiss_url, pkl_url = mongoclient.fetch_vector_urls(team_name)
            
            # Fetch files from cloud storage
            faiss_file = ibm_cloud.fetch_file_from_cos(faiss_url)
            pkl_file = ibm_cloud.fetch_file_from_cos(pkl_url)
            
            # Create a unique folder for this team
            local_folder = f"./vector-db-local/{team_name}"
            os.makedirs(local_folder, exist_ok=True)
            
            # Define file paths
            faiss_path = os.path.join(local_folder, "index.faiss")
            pkl_path = os.path.join(local_folder, "index.pkl")
            
            # Save FAISS file
            with open(faiss_path, "wb") as f:
                f.write(faiss_file.read())
            
            # Save PKL file
            with open(pkl_path, "wb") as f:
                f.write(pkl_file.read())
            
            # Load the vector store
            vectors = FAISS.load_local(local_folder, embedding_model, allow_dangerous_deserialization=True)
            all_vectors.append(vectors)
            
        except Exception as e:
            logger.error(f"Error loading data for team {team_name}: {e}")
    
    if not all_vectors:
        logger.error("No vector stores were loaded successfully")
        return
    
    # Combine all vector stores
    if len(all_vectors) == 1:
        combined_vectors = all_vectors[0]
    else:
        # Merge all vector stores
        combined_vectors = all_vectors[0]
        for vs in all_vectors[1:]:
            combined_vectors.merge_from(vs)
    
    # Create the retrieval chain
    document_chain = create_stuff_documents_chain(llm, prompt)
    retriever = combined_vectors.as_retriever()
    retrieval_chain = create_retrieval_chain(retriever, document_chain)
    
    logger.info("Successfully loaded data for all teams")

def AskQuestion(question: str) -> str:
    """
    Answers a user question using the document-based retrieval chain.

    :param question: The user's question as a string.
    :return: Answer string generated by the language model.
    """
    global retrieval_chain
    
    # Use the retrieval chain to answer the question
    response = retrieval_chain.invoke({'input': question})
    return response['answer']


def load_vector_db_for_selected_team(team_name):
    """
    Answers a user question using the document-based retrieval chain.

    :param question: The user's question as a string.
    :return: Answer string generated by the language model.
    """
    global retrieval_chain

    faiss_url,pkl_url = mongoclient.fetch_vector_urls(team_name)
    faiss_file = ibm_cloud.fetch_file_from_cos(faiss_url)
    pkl_file = ibm_cloud.fetch_file_from_cos(pkl_url)

    local_folder = "./vector-db-local/"
    os.makedirs(local_folder, exist_ok=True)  # Create folder if it doesn't exist

    # Define file paths
    faiss_path = os.path.join(local_folder, "index.faiss")
    pkl_path = os.path.join(local_folder, "index.pkl")

    # Save FAISS file
    with open(faiss_path, "wb") as f:
        f.write(faiss_file.read())

    # Save PKL file
    with open(pkl_path, "wb") as f:
        f.write(pkl_file.read())  

    vectors = FAISS.load_local(local_folder, embedding_model, allow_dangerous_deserialization=True)
    document_chain = create_stuff_documents_chain(llm, prompt)
    retriever = vectors.as_retriever()
    retrieval_chain = create_retrieval_chain(retriever, document_chain)
