from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

load_dotenv()

# Prioridade: DATABASE_URL → MYSQL_URL (Railway MySQL plugin) → variáveis individuais
DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("MYSQL_URL")
    or (
        f"mysql+pymysql://{os.getenv('MYSQLUSER') or os.getenv('DB_USER')}"
        f":{os.getenv('MYSQLPASSWORD') or os.getenv('DB_PASS')}"
        f"@{os.getenv('MYSQLHOST') or os.getenv('DB_HOST')}"
        f"/{os.getenv('MYSQLDATABASE') or os.getenv('DB_NAME')}"
    )
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
