from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Argon2id with secure default params from argon2-cffi
_password_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(hashed_password: str, plain_password: str) -> bool:
    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
