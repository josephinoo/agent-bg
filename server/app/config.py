# app/config.py
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Configuración de la aplicación"""
    
    # API Configuration
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "Agente de Leads Bancario"
    api_version: str = "1.0.0"
    
    # Database Configuration
    database_url: str = Field(alias="SUPABASE_DATABASE_URL")
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20
    db_command_timeout: int = 60
    
    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 500
    
    # BuilderBot
    builderbot_url: str = "http://localhost:3008"
    builderbot_timeout: int = 10
    
    # Logging
    log_level: str = "INFO"
    
    # Agent Configuration
    session_timeout_minutes: int = 30
    max_conversation_messages: int = 50
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"  # This allows extra fields to be ignored
    }

# Instancia global de configuración
settings = Settings()

# Validaciones de configuración requerida
def validate_config():
    """Valida que la configuración requerida esté presente"""
    required_fields = [
        ('database_url', 'DATABASE_URL or SUPABASE_DATABASE_URL'),
        ('openai_api_key', 'OPENAI_API_KEY')
    ]
    
    missing = []
    for field, env_var in required_fields:
        if not getattr(settings, field, None):
            missing.append(env_var)
    
    if missing:
        raise ValueError(f"Variables de entorno requeridas: {', '.join(missing)}")

# Ejecutar validación al importar
validate_config()