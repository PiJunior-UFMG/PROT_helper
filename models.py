from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, Boolean, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs
from pgvector.sqlalchemy import Vector  

# 1. Base declarativa moderna (SQLAlchemy 2.0)
class Base(AsyncAttrs, DeclarativeBase):
    pass

# 2. Modelos de Usuário e Admin
class User(Base):
    __tablename__ = "User"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_phone: Mapped[str] = mapped_column(String(30), unique=True)
    user_name: Mapped[str] = mapped_column(String(50))
    user_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True) #
    user_city: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    user_state: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    user_role: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    user_description: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    last_message: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    demanded_products: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) #

    # Relacionamentos
    companies: Mapped[List["Company"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    access_codes: Mapped[List["Access_Code"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    demands: Mapped[List["Demand"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    admin_demands: Mapped[List["Admin_Demand"]] = relationship(back_populates="user", foreign_keys="[Admin_Demand.user_id]")
    supplier_demands: Mapped[List["Supplier_Demand"]] = relationship(back_populates="supplier", foreign_keys="[Supplier_Demand.supplier_id]")


class Admin_User(Base):
    __tablename__ = "Admin_User"

    admin_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    admin_email: Mapped[str] = mapped_column(String(255))
    admin_password: Mapped[str] = mapped_column(String(255))
    admin_name: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relacionamentos
    admin_demands: Mapped[List["Admin_Demand"]] = relationship(back_populates="admin")


# 3. Modelos de Empresa e Produto
class Company(Base):
    __tablename__ = "Company"

    company_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("User.id"))
    company_cnpj: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    company_name: Mapped[str] = mapped_column(String(30))

    # Relacionamentos
    user: Mapped["User"] = relationship(back_populates="companies")
    products: Mapped[List["Product"]] = relationship(back_populates="company", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "Product"

    product_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("Company.company_id"))
    user_id: Mapped[int] = mapped_column(Integer)
    product_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    product_embedding: Mapped[Optional[list]] = mapped_column(Vector(768), nullable=True)

    # Relacionamentos
    company: Mapped["Company"] = relationship(back_populates="products")


# 4. Modelos de Demanda e Relacionamentos
class Demand(Base):
    __tablename__ = "Demand"

    demand_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("User.id"))
    location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    item: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[int] = mapped_column(Integer)
    fail_reason: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    item_embedding: Mapped[Optional[list]] = mapped_column(Vector(768), nullable=True)

    # Relacionamentos
    user: Mapped["User"] = relationship(back_populates="demands")
    supplier_demands: Mapped[List["Supplier_Demand"]] = relationship(back_populates="demand", cascade="all, delete-orphan")
    admin_demands: Mapped[List["Admin_Demand"]] = relationship(back_populates="demand", cascade="all, delete-orphan")


class Supplier_Demand(Base):
    __tablename__ = "Supplier_Demand"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, unique=True)
    demand_id: Mapped[int] = mapped_column(ForeignKey("Demand.demand_id"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("User.id"))
    status: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    # Relacionamentos
    demand: Mapped["Demand"] = relationship(back_populates="supplier_demands")
    supplier: Mapped["User"] = relationship(back_populates="supplier_demands", foreign_keys=[supplier_id])


class Admin_Demand(Base):
    __tablename__ = "Admin_Demand"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("User.id"))
    admin_id: Mapped[Optional[int]] = mapped_column(ForeignKey("Admin_User.admin_id"), nullable=True)
    demand_id: Mapped[int] = mapped_column(ForeignKey("Demand.demand_id"))
    fail_reason: Mapped[int] = mapped_column(Integer)
    context: Mapped[str] = mapped_column(Text)
    status: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relacionamentos
    user: Mapped["User"] = relationship(back_populates="admin_demands", foreign_keys=[user_id])
    admin: Mapped[Optional["Admin_User"]] = relationship(back_populates="admin_demands")
    demand: Mapped["Demand"] = relationship(back_populates="admin_demands")


# 5. Outros Modelos
class Access_Code(Base):
    __tablename__ = "Access_Code"

    code_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("User.id"))
    code: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean)

    # Relacionamentos
    user: Mapped["User"] = relationship(back_populates="access_codes")