import os
from dotenv import load_dotenv

def load_config():
    load_dotenv()  # Cargar variables de entorno desde .env
    
    class Config:
        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    return Config()
