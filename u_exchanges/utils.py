import logging

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))

if logger.hasHandlers():
    logger.handlers.clear()
logger.propagate = False
logger.addHandler(handler)


def chunks(array, n):
    """Yield successive n-sized chunks from lst."""
    counter = 0
    while counter < len(array):
        yield array[counter:counter + n]
        counter += n
