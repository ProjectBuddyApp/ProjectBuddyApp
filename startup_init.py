"""
Startup initialization module for loading vector data once at application startup.
This module should be imported at the top level to ensure data is loaded before any chat sessions start.
"""
import logging
from rag_model import load_all_teams_data

logger = logging.getLogger(__name__)

def initialize_vector_data():
    """
    Initialize vector data for all teams at application startup.
    This function should be called once when the application starts.
    """
    logger.info("Initializing vector data at application startup...")
    try:
        load_all_teams_data()
        logger.info("Vector data initialization complete")
    except Exception as e:
        logger.error(f"Error during vector data initialization: {e}")
        raise

# Auto-initialize when module is imported
logger.info("Running startup initialization...")
initialize_vector_data()

# Made with Bob
