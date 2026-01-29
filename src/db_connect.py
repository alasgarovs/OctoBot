from sqlalchemy import create_engine, Boolean,Column, Integer, String,DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import pytz 
from datetime import datetime

Base = declarative_base()

class Pool(Base):
    __tablename__ = 'Pool'
    
    id = Column(Integer, primary_key=True)
    number = Column(String(50), unique=True, nullable=False)
    whatsapp_status = Column(Boolean, default=False)
    created_date = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Baku')))
    updated_date = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Baku')), 
                                onupdate=lambda: datetime.now(pytz.timezone('Asia/Baku')))

class TempNumbers(Base):
    __tablename__ = 'TempNumbers'
    
    id = Column(Integer, primary_key=True)
    number = Column(String(50), nullable=False)


class Message(Base):
    __tablename__ = 'Message'
    
    id = Column(Integer, primary_key=True)
    message = Column(String(10000), nullable=False)


# Create a SQLite database
engine = create_engine('sqlite:///local.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
