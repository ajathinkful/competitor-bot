import logging
import os

from botocore.exceptions import ClientError

from app.services.aws import aws_service


def get_secret(secret_name: str, region: str = "us-east-2") -> str:
    """
    Gets a secret from AWS Secrets Manager using the given secret name.
    If not found, it falls back on local environment variables.

    This defaults to the secret_name using the standard
        `/opto/dev/t2/<SECRET_NAME>`

    :param secret_name:
    :param region:
    :return:
    """

    env = os.getenv("ENV", "dev")
    secret_full_name = f"/opto/{env}/t2/{secret_name}"

    try:
        value = os.environ[secret_name]
        if not value:  # Raises KeyError if value is empty string
            raise KeyError(f"Environment variable '{secret_name}' is empty")
        logging.info(f"[get_secret] Found '{secret_name}' in local env.")
        return value
    except KeyError:
        logging.warning(f"[get_secret] '{secret_name}' not in env or empty. Trying AWS Secrets Manager...")
        try:
            secret = aws_service.get_secret(secret_full_name, region)
            logging.info(f"[get_secret] Retrieved '{secret_name}' from AWS Secrets Manager.")
            return secret[secret_name]
        except (ClientError, KeyError) as e:
            logging.error(f"[get_secret] Failed to retrieve '{secret_name}' from AWS: {e}")
            raise RuntimeError(f"Secret '{secret_name}' not found in env or AWS.")
