import sys

from werkzeug.security import generate_password_hash

from app import db, User


def main():
    if len(sys.argv) < 3:
        print("Usage: python reset_password.py <username> <new_password>")
        sys.exit(1)
    username = sys.argv[1].strip()
    new_password = sys.argv[2]
    if not username or not new_password:
        print("Username and password are required.")
        sys.exit(1)
    user = User.query.filter_by(username=username).first()
    if not user:
        print(f"User '{username}' not found.")
        sys.exit(1)
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    print(f"Password updated for '{username}'.")


if __name__ == "__main__":
    main()
