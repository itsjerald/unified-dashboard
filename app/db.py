from sqlmodel import SQLModel, create_engine, Session
import os

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///./gpay.db')
engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    print(f"Using database: {DATABASE_URL}")
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
