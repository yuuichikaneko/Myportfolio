from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[int] = mapped_column(Integer)
    performance_score: Mapped[float] = mapped_column(Float)
    url: Mapped[str] = mapped_column(Text)
    
    # CPU
    socket: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Memory
    memory_standard: Mapped[str | None] = mapped_column(String(50), nullable=True)
    memory_capacity_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Storage
    storage_capacity_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # PSU
    wattage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Case
    form_factor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    supported_form_factors: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
