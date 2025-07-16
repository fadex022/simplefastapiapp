from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from sqlalchemy import text
from configuration.config import get_db_settings, get_app_settings

# Load settings
db_settings = get_db_settings()
app_settings = get_app_settings()

# Define the connection string for async PostgreSQL
connection_string = f"postgresql+asyncpg://{db_settings.DB_USER}:{db_settings.DB_PASSWORD}@" \
                    f"{db_settings.DB_HOST}:{db_settings.DB_PORT}/{db_settings.DB_NAME}"

# Configure database db_engine based on environment
if app_settings.ENVIRONMENT == "production":
    # Production configuration with optimal pool settings
    engine = create_async_engine(
        connection_string,
        echo=False,  # Disable SQL echoing in production
        pool_size=10,  # Number of connections to keep open
        max_overflow=20,  # Max extra connections when pool is full
        pool_timeout=30,  # Wait time for connection (seconds)
        pool_recycle=1800,  # Recycle connections after 30 min
        pool_pre_ping=True,  # Verify connections before use
    )
else:
    # Development/testing configuration
    engine = create_async_engine(
        connection_string,
        echo=app_settings.DEBUG,  # Only echo SQL in debug mode
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )

# Define the Base class for the ORM
Base = declarative_base()

# Create a session factory for async sessions
AsyncSessionFactory = sessionmaker(
    bind=engine,
    class_=AsyncSession,  # Use the async session class
    expire_on_commit=False  # Avoid expiring objects after commit
)

# Dependency for async database sessions
async def sess_db():
    async with AsyncSessionFactory() as session:
        try:
            # Set session timeout to prevent long-running queries
            await session.execute(text("SET statement_timeout = 10000"))  # 10 seconds
            yield session
        except Exception as e:
            # Rollback transaction in case of error
            await session.rollback()
            raise e
        finally:
            await session.close()

async def create_tables(db_engine: AsyncEngine):
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)