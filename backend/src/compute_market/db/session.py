import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from compute_market.db.config import database_url

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://compute:compute@localhost:5432/compute"
)
engine = create_engine(database_url(DATABASE_URL), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session():
    with SessionLocal() as session:
        yield session
