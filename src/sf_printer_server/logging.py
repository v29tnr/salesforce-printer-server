import logging

def setup_logging(log_level=logging.INFO):
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('printer_server.log')
        ]
    )

def get_logger(name):
    return logging.getLogger(name)