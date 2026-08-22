import os

MIN_JWT_SECRET_LENGTH = 32


def get_jwt_secret() -> str:
    """Retrieve and validate JWT_SECRET from environment.

    Raises RuntimeError if secret is missing or fewer than 32 characters long.
    """
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET environment variable is missing or empty.")

    if len(secret) < MIN_JWT_SECRET_LENGTH:
        raise RuntimeError(
            f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters long. "
            f"Current length is {len(secret)}."
        )

    return secret
