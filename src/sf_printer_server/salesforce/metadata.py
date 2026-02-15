from sqlalchemy import create_engine, Column, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Printer(Base):
    __tablename__ = 'printers'

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    model = Column(String, nullable=False)
    location = Column(String)

class PrintJob(Base):
    __tablename__ = 'print_jobs'

    id = Column(String, primary_key=True)
    printer_id = Column(String, ForeignKey('printers.id'), nullable=False)
    content_document = Column(String)
    zpl = Column(Boolean, default=False)

    printer = relationship("Printer")