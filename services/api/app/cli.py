"""Administrative CLI for secure bootstrap operations."""

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.services.security import hash_password


def create_user(role: UserRole) -> int:
    username = input("Login: ").strip().lower()
    if len(username) < 3:
        print("O login precisa ter ao menos 3 caracteres.", file=sys.stderr)
        return 2
    password = getpass.getpass("Senha (mínimo 12 caracteres): ")
    confirmation = getpass.getpass("Confirme a senha: ")
    if password != confirmation:
        print("As senhas não coincidem.", file=sys.stderr)
        return 2
    if len(password) < 12:
        print("A senha precisa ter ao menos 12 caracteres.", file=sys.stderr)
        return 2

    with SessionLocal.begin() as db:
        if db.scalar(select(User.id).where(User.username == username)) is not None:
            print("Esse login já existe.", file=sys.stderr)
            return 1
        user = User(username=username, password_hash=hash_password(password), role=role)
        db.add(user)
    print(f"Usuário {username!r} criado com papel {role.value!r}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create-user", help="Cria uma conta local")
    create.add_argument("--role", choices=[role.value for role in UserRole], default="viewer")
    args = parser.parse_args()
    if args.command == "create-user":
        return create_user(UserRole(args.role))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
