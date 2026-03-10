import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import settings

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
env_path = os.path.join(project_root, ".env")

load_dotenv(env_path)

DB_USER = settings.get_db_user()
DB_PASSWORD = settings.get_db_password()
DB_HOST = settings.get_db_host()
DB_PORT = settings.get_db_port()
DB_NAME = settings.get_db_name()

DATABASE_URL = (
    f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@"
    f"{DB_HOST}:{int(DB_PORT)}/{DB_NAME}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,  # 배포 환경에서는 False 설정 (True로 설정시 TMDB 수집 후 프롬프트 창에 수집한 영화에 관한 상세 내용 출력)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
