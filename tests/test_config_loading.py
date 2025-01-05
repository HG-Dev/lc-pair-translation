"""
Tests the functionality of configuration model loading and saving.
"""
import unittest
from tests import pytest_log
from os.path import exists
from os import remove
from langchain_pairtranslation.config import Config

class ConfigTests(unittest.TestCase):
    CONFIG_FILEPATH = "tests/resources/config.json"

    def tearDown(self):
        if exists(ConfigTests.CONFIG_FILEPATH):
            remove(ConfigTests.CONFIG_FILEPATH)

    def test_create_default(self):
        pytest_log.debug("Testing creation of default config...")
        config = Config.load(ConfigTests.CONFIG_FILEPATH)
        self.assertTrue(config)
        self.assertTrue(exists(ConfigTests.CONFIG_FILEPATH))

    def test_alter_languages(self):
        pytest_log.debug("Testing the alteration of languages in config...")
        config = Config.load(ConfigTests.CONFIG_FILEPATH)
        assert(config.user.target_language != "French")
        config.user.target_language = "French"
        assert(config.user.source_language != "German")
        config.user.source_language = "German"
        config.save(ConfigTests.CONFIG_FILEPATH)

        new_config = Config.load(ConfigTests.CONFIG_FILEPATH)
        self.assertEqual(new_config.user.target_language, "French")
        self.assertEqual(new_config.user.source_language, "German")
