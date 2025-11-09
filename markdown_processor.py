"""
Markdown Template Processor for Vector Database Creation
Processes markdown files from GitHub templates and creates vector embeddings
Optimized to load common templates only once for all teams
"""

import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from typing import List
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
import ibm_cloud
import mongoclient
import shutil

logger = logging.getLogger(__name__)


def extract_links_from_text(text: str) -> List[str]:
    """
    Extract URLs from text using regex pattern.
    Filters out Slack and YourLearning URLs.
    
    :param text: Text to extract URLs from
    :return: List of extracted URLs (excluding Slack and YourLearning)
    """
    # URL regex pattern
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    all_urls = re.findall(url_pattern, str(text))
    
    # Filter out Slack and YourLearning URLs
    filtered_urls = []
    for url in all_urls:
        url_lower = url.lower()
        # Skip if URL contains slack or yourlearning domains
        if 'slack.com' in url_lower or 'yourlearning' in url_lower:
            logger.info(f"Skipping Slack/YourLearning URL: {url}")
            continue
        filtered_urls.append(url)
    
    return filtered_urls


def fetch_content_from_url(url: str) -> str:
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
        return ""


def load_markdown_documents(markdown_content: str, source_name: str) -> List[Document]:
    """
    Load documents from markdown content and extract content from any URLs found.
    
    :param markdown_content: The markdown content as string
    :param source_name: Name of the source file
    :return: List of Document objects
    """
    documents = []
    
    # Create document from markdown content
    doc = Document(
        page_content=markdown_content,
        metadata={"source": source_name, "type": "markdown"}
    )
    documents.append(doc)
    
    # Extract URLs from markdown content
    links = extract_links_from_text(markdown_content)
    
    # Fetch content from each URL and create additional documents
    for link in links:
        logger.info(f"Found link in {source_name}: {link}, fetching content...")
        link_content = fetch_content_from_url(link)
        if link_content:
            documents.append(Document(
                page_content=link_content,
                metadata={"source": link, "related_to": source_name, "type": "url_content"}
            ))
    
    return documents


def load_common_documents():
    """
    Load common documents once to be reused for all teams.
    
    :return: List of Document objects from common templates
    """
    try:
        logger.info("📚 Loading common templates (will be reused for all teams)...")
        
        # Get common templates
        common_templates = mongoclient.get_all_common_templates()
        
        if not common_templates:
            logger.warning("No common templates found")
            return []
        
        logger.info(f"Found {len(common_templates)} common templates")
        
        common_documents = []
        
        for template in common_templates:
            try:
                template_url = template.get('ibm_cloud_url')
                template_name = template.get('template_name', 'unknown')
                
                if not template_url:
                    logger.warning(f"No URL found for common template: {template_name}")
                    continue
                
                # Fetch markdown content from IBM Cloud
                logger.info(f"Fetching common template: {template_name}")
                markdown_file = ibm_cloud.fetch_file_from_cos(template_url)
                markdown_content = markdown_file.read().decode('utf-8')
                
                # Create documents from markdown
                docs = load_markdown_documents(markdown_content, f"common/{template_name}")
                common_documents.extend(docs)
                
            except Exception as e:
                logger.error(f"Error processing common template {template.get('template_name')}: {e}")
                continue
        
        logger.info(f"✅ Loaded {len(common_documents)} common documents")
        return common_documents
        
    except Exception as e:
        logger.error(f"Error loading common documents: {e}")
        return []


def create_vector_embeddings_for_team(team_name: str, team_type: str, embedding_model, common_documents=None, chunk_size: int = 1000, chunk_overlap: int = 200):
    """
    Create vector embeddings for a team from their markdown templates stored in IBM Cloud.
    Includes team-specific templates + common templates (passed as parameter to avoid re-fetching).
    
    :param team_name: Name of the team
    :param team_type: Type of team ('product' or 'teams')
    :param embedding_model: The embedding model to use
    :param common_documents: Pre-loaded common documents (to avoid re-fetching)
    :param chunk_size: Size of text chunks for embedding
    :param chunk_overlap: Overlap between text chunks
    :return: True if successful, False otherwise
    """
    try:
        logger.info(f"Creating vector embeddings for team: {team_name} (type: {team_type})")
        
        # Get team's specific template from MongoDB
        if team_type == "product":
            team_specific_templates = mongoclient.get_all_product_templates()
        else:
            team_specific_templates = mongoclient.get_all_team_templates()
        
        # Filter templates for this specific team
        team_templates = [t for t in team_specific_templates if t.get('template_name', '').replace('.md', '') == team_name]
        
        if not team_templates:
            logger.warning(f"No team-specific templates found for: {team_name}")
            return False
        
        logger.info(f"Found {len(team_templates)} team-specific templates for {team_name}")
        
        # Load team-specific documents
        team_documents = []
        
        for template in team_templates:
            try:
                template_url = template.get('ibm_cloud_url')
                template_name = template.get('template_name', 'unknown')
                
                if not template_url:
                    logger.warning(f"No URL found for template: {template_name}")
                    continue
                
                # Fetch markdown content from IBM Cloud
                logger.info(f"Fetching team template: {template_name}")
                markdown_file = ibm_cloud.fetch_file_from_cos(template_url)
                markdown_content = markdown_file.read().decode('utf-8')
                
                # Create documents from markdown
                docs = load_markdown_documents(markdown_content, f"{team_type}/{template_name}")
                team_documents.extend(docs)
                
            except Exception as e:
                logger.error(f"Error processing template {template.get('template_name')}: {e}")
                continue
        
        # Combine team-specific documents with common documents
        all_documents = team_documents + (common_documents if common_documents else [])
        
        if not all_documents:
            logger.error(f"No documents loaded for team: {team_name}")
            return False
        
        common_count = len(common_documents) if common_documents else 0
        logger.info(f"Total documents for {team_name}: {len(all_documents)} ({len(team_documents)} team-specific + {common_count} common)")
        
        # Split documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        final_documents = text_splitter.split_documents(all_documents)
        
        logger.info(f"Split into {len(final_documents)} chunks")
        
        # Create vector embeddings
        vectors = FAISS.from_documents(final_documents, embedding_model)
        
        # Save to local folder temporarily
        local_folder = f"./vector-db-local/{team_name}"
        os.makedirs(local_folder, exist_ok=True)
        vectors.save_local(local_folder)
        
        logger.info(f"Vector database saved locally for {team_name}")
        
        # Upload to IBM Cloud
        faiss_url, pkl_url = ibm_cloud.save_vector_data(local_folder, team_name)
        
        logger.info(f"Vector database uploaded to IBM Cloud for {team_name}")
        
        # Save metadata to MongoDB
        mongoclient.save_vector_metadata_to_mongo(team_name, faiss_url, pkl_url)
        
        logger.info(f"Vector metadata saved to MongoDB for {team_name}")
        
        # Clean up local folder
        shutil.rmtree(local_folder)
        
        logger.info(f"✅ Successfully created vector embeddings for team: {team_name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating vector embeddings for team {team_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_vectors_for_uploaded_teams(embedding_model, uploaded_teams):
    """
    Create vector embeddings ONLY for teams that were just uploaded.
    This is more efficient than recreating vectors for all teams.
    
    :param embedding_model: The embedding model to use
    :param uploaded_teams: Dictionary with 'product' and 'teams' lists of uploaded team names
    :return: Dictionary with success/failure counts
    """
    logger.info("🚀 Creating vector embeddings for uploaded teams only...")
    
    # Load common documents ONCE (will be reused for all teams)
    common_documents = load_common_documents()
    
    results = {
        "success": [],
        "failed": [],
        "total": 0
    }
    
    # Process uploaded product teams
    for team_name in uploaded_teams.get('product', []):
        results["total"] += 1
        logger.info(f"📦 Creating vectors for uploaded product team: {team_name}")
        if create_vector_embeddings_for_team(team_name, "product", embedding_model, common_documents):
            results["success"].append(f"{team_name} (product)")
        else:
            results["failed"].append(f"{team_name} (product)")
    
    # Process uploaded regular teams
    for team_name in uploaded_teams.get('teams', []):
        results["total"] += 1
        logger.info(f"📦 Creating vectors for uploaded team: {team_name}")
        if create_vector_embeddings_for_team(team_name, "teams", embedding_model, common_documents):
            results["success"].append(f"{team_name} (teams)")
        else:
            results["failed"].append(f"{team_name} (teams)")
    
    logger.info(f"✅ Vector creation complete: {len(results['success'])}/{results['total']} successful")
    
    if results['failed']:
        logger.warning(f"Failed teams: {', '.join(results['failed'])}")
    
    return results


def create_vectors_for_all_teams(embedding_model):
    """
    Create vector embeddings for all teams that have templates.
    Loads common templates once and reuses them for all teams (optimized).
    Use this for bulk operations or when you want to recreate all vectors.
    
    :param embedding_model: The embedding model to use
    :return: Dictionary with success/failure counts
    """
    logger.info("🚀 Creating vector embeddings for all teams...")
    
    # Load common documents ONCE (will be reused for all teams)
    common_documents = load_common_documents()
    
    # Get all team names from templates
    team_names_dict = mongoclient.get_all_team_names_from_templates()
    
    results = {
        "success": [],
        "failed": [],
        "total": 0
    }
    
    # Process product teams
    for team_name in team_names_dict.get('product', []):
        results["total"] += 1
        if create_vector_embeddings_for_team(team_name, "product", embedding_model, common_documents):
            results["success"].append(f"{team_name} (product)")
        else:
            results["failed"].append(f"{team_name} (product)")
    
    # Process regular teams
    for team_name in team_names_dict.get('teams', []):
        results["total"] += 1
        if create_vector_embeddings_for_team(team_name, "teams", embedding_model, common_documents):
            results["success"].append(f"{team_name} (teams)")
        else:
            results["failed"].append(f"{team_name} (teams)")
    
    logger.info(f"✅ Vector creation complete: {len(results['success'])}/{results['total']} successful")
    
    if results['failed']:
        logger.warning(f"Failed teams: {', '.join(results['failed'])}")
    
    return results
