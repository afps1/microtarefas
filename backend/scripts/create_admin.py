"""
Utilitário para criar o primeiro admin.
Uso: python scripts/create_admin.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models
import bcrypt


def main():
    name = input("Nome: ")
    email = input("E-mail: ")
    password = input("Senha: ")

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db = SessionLocal()
    admin = models.AdminUser(name=name, email=email, password_hash=password_hash, role="geral")
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f"Admin criado: {admin.name} (id={admin.id})")
    db.close()


if __name__ == "__main__":
    main()
