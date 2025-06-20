import logging

logger = logging.getLogger(__name__)

def arxiv_client_retry(client, func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error: {e}. Retrying without SSL verification.")
            client._session.verify = False
            return func(*args, **kwargs)
    return wrapper
