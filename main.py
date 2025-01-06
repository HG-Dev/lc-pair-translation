from langchain_pairtranslation import run

import json
from logging import getLogger
from logging.config import dictConfig
from os import path, mkdir

from langchain_pairtranslation.config import Config

if __name__ == '__main__':
    # Configure logging for application
    with open('config/log_settings.json') as log_settings_in:
        log_settings = json.load(log_settings_in)
        assert('handlers' in log_settings)
        handlers = log_settings.get('handlers', [])
        for handler in handlers.values():
            if not 'filename' in handler:
                continue
            filepath = handler['filename']
            dirpath = path.dirname(filepath)
            print(dirpath)
            if not path.exists(dirpath):
                try:
                    mkdir(dirpath)
                except OSError as e:
                    print("Error preparing logging directories.\n" + dirpath + ": " + str(e))
        dictConfig(log_settings)

    app_settings = Config.load('config/app_settings.json')

    # Run the application
    getLogger('app').info("Application started.")
    run(app_settings)
