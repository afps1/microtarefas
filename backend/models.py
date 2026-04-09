from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Condominium(Base):
    __tablename__ = "condominiums"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    address = Column(String(300))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    residents = relationship("Resident", back_populates="condominium")
    runners = relationship("Runner", back_populates="condominium")


class Resident(Base):
    __tablename__ = "residents"

    id = Column(Integer, primary_key=True)
    condominium_id = Column(Integer, ForeignKey("condominiums.id"), nullable=False)
    name = Column(String(200), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    apartment = Column(String(20), nullable=False)
    email = Column(String(200))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    condominium = relationship("Condominium", back_populates="residents")
    tasks = relationship("Task", back_populates="resident")


class Runner(Base):
    __tablename__ = "runners"

    id = Column(Integer, primary_key=True)
    condominium_id = Column(Integer, ForeignKey("condominiums.id"), nullable=False)
    name = Column(String(200), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    pix_key = Column(String(200))
    photo_url = Column(String(500))
    status = Column(Enum("pending", "approved", "blocked"), default="pending")
    available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    condominium = relationship("Condominium", back_populates="runners")
    tasks = relationship("Task", back_populates="runner")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(Enum("geral", "condominio"), nullable=False, default="condominio")
    condominium_id = Column(Integer, ForeignKey("condominiums.id"), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    condominium = relationship("Condominium", foreign_keys=[condominium_id])


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    condominium_id = Column(Integer, ForeignKey("condominiums.id"), nullable=False)
    resident_id = Column(Integer, ForeignKey("residents.id"), nullable=False)
    runner_id = Column(Integer, ForeignKey("runners.id"), nullable=True)
    service_type_id = Column(Integer, ForeignKey("service_types.id"), nullable=True)
    type = Column(String(100), nullable=False)
    price = Column(Integer, nullable=True)  # centavos, snapshot no momento da criação
    description = Column(Text)
    status = Column(
        Enum("solicitado", "aceito", "em_execucao", "concluido", "recebido", "cancelado"),
        default="solicitado",
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resident = relationship("Resident", back_populates="tasks")
    runner = relationship("Runner", back_populates="tasks")
    service_type = relationship("ServiceType", foreign_keys=[service_type_id])
    magic_links = relationship("MagicLink", back_populates="task")


class MagicLink(Base):
    __tablename__ = "magic_links"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    runner_id = Column(Integer, ForeignKey("runners.id"), nullable=False)
    token = Column(String(100), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="magic_links")


class ServiceType(Base):
    __tablename__ = "service_types"

    id = Column(Integer, primary_key=True)
    condominium_id = Column(Integer, ForeignKey("condominiums.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(String(500))
    price = Column(Integer, nullable=False)  # centavos
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    condominium = relationship("Condominium", foreign_keys=[condominium_id])


class PendingRequest(Base):
    __tablename__ = "pending_requests"

    id = Column(Integer, primary_key=True)
    resident_id = Column(Integer, ForeignKey("residents.id"), nullable=False, unique=True)
    task_type = Column(String(100), nullable=False)
    service_type_id = Column(Integer, ForeignKey("service_types.id"), nullable=True)
    description = Column(Text, nullable=True)
    awaiting_observation = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    resident = relationship("Resident", foreign_keys=[resident_id])
    service_type = relationship("ServiceType", foreign_keys=[service_type_id])


class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, unique=True)
    runner_id = Column(Integer, ForeignKey("runners.id"), nullable=False)
    resident_id = Column(Integer, ForeignKey("residents.id"), nullable=False)
    score = Column(Integer, nullable=False)  # 1-5
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", foreign_keys=[task_id])
    runner = relationship("Runner", foreign_keys=[runner_id])
    resident = relationship("Resident", foreign_keys=[resident_id])


class TaskMessage(Base):
    __tablename__ = "task_messages"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    sender = Column(Enum("parceiro", "morador"), nullable=False)
    type = Column(Enum("text", "image"), default="text")
    content = Column(Text, nullable=False)  # texto ou media_id
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", foreign_keys=[task_id])


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True)
    runner_id = Column(Integer, ForeignKey("runners.id"), nullable=False, unique=True)
    endpoint = Column(Text, nullable=False)
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    runner = relationship("Runner", foreign_keys=[runner_id])


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True)
    email = Column(String(200), nullable=False)
    code = Column(String(10), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
