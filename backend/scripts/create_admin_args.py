"""
Uso: python scripts/create_admin_args.py "Nome" "email@exemplo.com" "senha"
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models
import bcrypt


def main():
    if len(sys.argv) != 4:
        print("Uso: python scripts/create_admin_args.py \"Nome\" \"email\" \"senha\"")
        sys.exit(1)

    name, email, password = sys.argv[1], sys.argv[2], sys.argv[3]
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db = SessionLocal()
    existing = db.query(models.AdminUser).filter(models.AdminUser.email == email).first()
    if existing:
        print(f"E-mail já cadastrado: {email}")
        db.close()
        sys.exit(1)

    admin = models.AdminUser(name=name, email=email, password_hash=password_hash, role="geral")
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f"Admin geral criado: {admin.name} (id={admin.id})")
    db.close()


if __name__ == "__main__":
    main()
