# app/database/connection.py
import asyncpg
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manager para conexiones a la base de datos"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Crear pool de conexiones"""
        try:
            self.pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=settings.db_pool_min_size,
                max_size=settings.db_pool_max_size,
                command_timeout=settings.db_command_timeout
            )
            logger.info("✅ Pool de conexiones a DB establecido")
            
            # Verificar conexión
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            logger.info("✅ Conexión a DB verificada")
            
        except Exception as e:
            logger.error(f"❌ Error conectando a la base de datos: {e}")
            raise
    
    async def disconnect(self):
        """Cerrar pool de conexiones"""
        if self.pool:
            await self.pool.close()
            logger.info("🔌 Pool de conexiones cerrado")
    
    async def execute_query(self, query: str, *args):
        """Ejecutar query que retorna múltiples filas"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetch(query, *args)
        except Exception as e:
            logger.error(f"Error ejecutando query: {e}")
            raise
    
    async def execute_single(self, query: str, *args):
        """Ejecutar query que retorna una sola fila"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchrow(query, *args)
        except Exception as e:
            logger.error(f"Error ejecutando query single: {e}")
            raise
    
    async def execute_command(self, query: str, *args):
        """Ejecutar comando que no retorna datos"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        try:
            async with self.pool.acquire() as conn:
                return await conn.execute(query, *args)
        except Exception as e:
            logger.error(f"Error ejecutando comando: {e}")
            raise
    
    async def execute_transaction(self, queries: list):
        """Ejecutar múltiples queries en una transacción"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    results = []
                    for query, args in queries:
                        result = await conn.fetchrow(query, *args)
                        results.append(result)
                    return results
        except Exception as e:
            logger.error(f"Error en transacción: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Verificar estado de la conexión"""
        try:
            if not self.pool:
                return False
            
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Health check falló: {e}")
            return False

# Instancia global del manager
db_manager = DatabaseManager()

# Dependency para FastAPI
async def get_database() -> DatabaseManager:
    """Dependency injection para obtener el database manager"""
    if not db_manager.pool:
        raise RuntimeError("Database not initialized")
    return db_manager