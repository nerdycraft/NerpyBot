import logging
import sys


class LessThanFilter(logging.Filter):
    def __init__(self, exclusive_maximum, name=""):
        super(LessThanFilter, self).__init__(name)
        self.max_level = exclusive_maximum

    def filter(self, record):
        # non-zero return means we log this message
        return 1 if record.levelno < self.max_level else 0


def create_logger(verbosity: int = 0, level: str = "WARNING", name: str = None):
    """
    Set logging level at runtime

    :param verbosity: int
    :param level: str
    :param name: str

    :return: logging.Logger
    """
    switcher = {
        1: "WARNING",
        2: "INFO",
        3: "DEBUG",
    }
    if verbosity > 0:
        level = switcher.get(verbosity)

    fmt = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(module)s %(lineno)d: %(message)s",
        datefmt="[%d/%m/%Y %H:%M]",
    )

    # Root Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.NOTSET)

    # Logger
    _logger = get_logger(name)

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(fmt)
    stdout_handler.set_name("stdout")
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(LessThanFilter(logging.WARNING))

    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setFormatter(fmt)
    stderr_handler.set_name("stderr")
    stderr_handler.setLevel(logging.WARNING)

    _logger.addHandler(stdout_handler)
    _logger.addHandler(stderr_handler)
    _logger.setLevel(level.upper())
    _logger.log(logging.INFO, f"Setting loglevel to {level} for Logger {name}.")


def get_logger(name: str = None) -> logging.Logger:
    return logging.getLogger(name)
