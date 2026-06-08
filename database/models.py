from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    TEACHER = "teacher"
    SECRETARY = "secretary"

class VacationStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    vacation_days_total = Column(Integer, default=24)
    vacation_days_used = Column(Integer, default=0)
    pml_subscribed = Column(Integer, default=0)  # 0 = not subscribed, 1 = subscribed
    created_at = Column(DateTime, default=datetime.utcnow)

    vacations = relationship("Vacation", back_populates="user")
    orders = relationship("Order", back_populates="user")

    @property
    def vacation_days_remaining(self):
        return self.vacation_days_total - self.vacation_days_used

class Vacation(Base):
    __tablename__ = "vacations"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    days_count = Column(Integer, nullable=False)
    status = Column(Enum(VacationStatus), default=VacationStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="vacations")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    order_type = Column(String(100), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    template_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)
    variables = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="orders")


class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"

    id = Column(Integer, primary_key=True)
    message_text = Column(Text, nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_count = Column(Integer, default=0)
