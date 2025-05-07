from sqlalchemy import Column, Integer, BigInteger, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from .base import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True)
    is_restaurant_owner = Column(Boolean, default=False)
    current_restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    restaurant = relationship("Restaurant", back_populates="owner", foreign_keys="Restaurant.owner_id", uselist=False)
    connected_restaurant = relationship("Restaurant", foreign_keys=[current_restaurant_id], backref="connected_users")
    donations = relationship("Donation", back_populates="user")
    orders = relationship("Order", back_populates="user")

class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), unique=True)
    invite_code = Column(String(10), unique=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    owner = relationship("User", back_populates="restaurant", foreign_keys=[owner_id])
    menu_items = relationship("MenuItem", back_populates="restaurant", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="restaurant")

class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"))
    name = Column(String(20), nullable=False)
    photo = Column(String)
    description = Column(Text)
    duration = Column(Integer)  # in minutes
    price_kisses = Column(Integer)
    price_hugs = Column(Integer)  # in minutes
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    restaurant = relationship("Restaurant", back_populates="menu_items")
    order_items = relationship("OrderItem", back_populates="menu_item")

class Donation(Base):
    __tablename__ = "donations"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer, nullable=False)  # количество звезд
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="donations")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"))
    status = Column(String(20), default="pending")  # pending, completed, cancelled
    total_kisses = Column(Integer, default=0)
    total_hugs = Column(Integer, default=0)
    total_duration = Column(Integer, default=0)  # in minutes
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="orders")
    restaurant = relationship("Restaurant", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"))
    quantity = Column(Integer, default=1)
    price_kisses = Column(Integer, default=0)
    price_hugs = Column(Integer, default=0)
    
    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem", back_populates="order_items")

class Broadcast(Base):
    __tablename__ = "broadcasts"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # Название рассылки
    text = Column(Text, nullable=False)  # Текст сообщения
    photo = Column(String)  # ID фото в Telegram (опционально)
    button_text = Column(String(100))  # Текст кнопки (опционально)
    button_url = Column(String(255))  # URL кнопки (опционально)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    scheduled_at = Column(DateTime, nullable=True)  # Время запланированной отправки
    sent_at = Column(DateTime, nullable=True)  # Время фактической отправки
    status = Column(String(20), default="created")  # created, sending, completed, failed
    total_users = Column(Integer, default=0)  # Общее количество пользователей
    received_count = Column(Integer, default=0)  # Количество пользователей, получивших сообщение

class BroadcastRecipient(Base):
    __tablename__ = "broadcast_recipients"

    id = Column(Integer, primary_key=True)
    broadcast_id = Column(Integer, ForeignKey("broadcasts.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    received = Column(Boolean, default=False)  # Получил ли пользователь сообщение
    received_at = Column(DateTime, nullable=True)  # Время получения

    broadcast = relationship("Broadcast")
    user = relationship("User") 