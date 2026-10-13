"""Registered storage contracts for the new exact Sony platform profiles."""
import unittest

from tests.scalar_contract import ScalarContractTests
from tests.test_bladestorm_ps3 import fixture as bladestorm_fixture
from tests.test_pw3_ps3 import fixture as pw3_fixture
from tests.test_aot1_vita import fixture as aot1_fixture
from koei_editor.games.bladestorm_ps3 import parser as bladestorm
from koei_editor.games.pw3_ps3 import parser as pw3
from koei_editor.games.aot1_vita import parser as aot1


class BladestormRegisteredContract(ScalarContractTests, unittest.TestCase):
    game_id = 'bladestorm_ps3'

    def fixture_bytes(self):
        (self.folder / 'PARAM.SFO').write_bytes(bladestorm.identity_metadata('BLES00113PLAY0'))
        return bladestorm_fixture()


class PW3PS3RegisteredContract(ScalarContractTests, unittest.TestCase):
    game_id = 'pw3_ps3'

    def fixture_bytes(self):
        (self.folder / 'PARAM.SFO').write_bytes(pw3.identity_metadata('NPEB02211-00'))
        return pw3_fixture()


class AOT1VitaRegisteredContract(ScalarContractTests, unittest.TestCase):
    game_id = 'aot1_vita'

    def fixture_bytes(self):
        context = self.folder / 'sce_sys' / 'param.sfo'
        context.parent.mkdir()
        context.write_bytes(aot1.identity_metadata())
        return aot1_fixture()
