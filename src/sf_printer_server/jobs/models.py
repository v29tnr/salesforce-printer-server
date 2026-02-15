from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Printer(Base):
    __tablename__ = 'printers'

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String)
    model = Column(String)

    def __repr__(self):
        return f"<Printer(id={self.id}, name={self.name}, location={self.location}, model={self.model})>"

class PrintJob(Base):
    __tablename__ = 'print_jobs'

    id = Column(String, primary_key=True)
    printer_id = Column(String, ForeignKey('printers.id'), nullable=False)
    content_document = Column(String)
    zpl = Column(Boolean, default=False)

    printer = relationship("Printer", back_populates="print_jobs")

    def __repr__(self):
        return f"<PrintJob(id={self.id}, printer_id={self.printer_id}, zpl={self.zpl})>"

Printer.print_jobs = relationship("PrintJob", order_by=PrintJob.id, back_populates="printer")