import json
from logging import getLogger
from logging.config import dictConfig
from os import path, mkdir

# Configure logging
with open('config/log_settings_pytest.json') as log_settings_in:
    log_settings = json.load(log_settings_in)
    assert('handlers' in log_settings)
    handlers = log_settings.get('handlers', [])
    for handler in handlers.values():
        if not 'filename' in handler:
            continue
        filepath = handler['filename']
        dirpath = path.dirname(filepath)
        if not path.exists(dirpath):
            try:
                mkdir(dirpath)
            except OSError as e:
                print("Error preparing logging directories.\n" + dirpath + ": " + str(e))
    dictConfig(log_settings)

pytest_log = getLogger('tests')
pytest_log.info("%s Pytest session started. %s", "="*20, "="*20)