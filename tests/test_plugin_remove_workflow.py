import copy
import tempfile
import unittest
from app.model import Application, validate_project
from app.ni_display import frame


class PluginRemoveWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.a = Application(self.temp.name)
        self.a.page = 'PLUGIN'
        self.fx = lambda uri: dict(uri=uri, kind='EFFECT', controls={}, bypass=False)

    def tearDown(self):
        self.temp.cleanup()

    def browse(self):
        self.a.button('SHIFT', True)
        self.a.button('BROWSE', True)
        self.a.button('BROWSE', False)
        self.a.button('SHIFT', False)

    def test_remove_selected_slot_on_every_bus_through_hardware_buttons(self):
        a = self.a
        for level in (0, 1, 2):
            with self.subTest(level=level):
                a.control_level = level
                a.page = 'PLUGIN'
                a.plugin_target()['plugins'] = [self.fx('urn:first'), self.fx('urn:remove'), self.fx('urn:last')]
                a.plugin_slot = 1
                bus = a.plugin_bus()
                self.browse()
                self.assertEqual((a.page, a.plugin_browser_index), ('PLUGIN BROWSE', -1))
                self.assertEqual(a.softkeys()[1], 'REMOVE')
                self.assertEqual(len(frame(a)), 8192)
                a.button('F2', True)
                self.assertEqual(a.page, 'CONFIRM')
                self.assertEqual(len(a.plugin_target()['plugins']), 3)
                a.button('F2', True)
                self.assertEqual(a.page, 'PLUGIN')
                self.assertEqual([p['uri'] for p in a.plugin_target()['plugins']], ['urn:first', 'urn:last'])
                self.assertEqual(a.actions[-1][0], 'plugins')
                self.assertEqual(a.actions[-1][1][0], bus)
                self.assertEqual(a.message, 'PLUGIN REMOVED')
                validate_project(a.project)

    def test_cancel_and_last_plugin_removal_preserve_sample(self):
        a = self.a
        a.track()['plugins'] = [self.fx('urn:tape')]
        before = copy.deepcopy(a.track())
        self.browse()
        a.button('F2', True)
        a.button('F1', True)
        self.assertEqual(a.track(), before)
        self.browse()
        a.button('ENTER', True)
        a.button('ENTER', True)
        self.assertEqual(a.track()['plugins'], [])
        self.assertEqual({k:v for k,v in a.track().items() if k!='plugins'}, {k:v for k,v in before.items() if k!='plugins'})
        a.undo_action()
        self.assertEqual(a.track()['plugins'], before['plugins'])

    def test_empty_slot_does_not_offer_remove_and_add_starts_on_plugin(self):
        a = self.a
        self.browse()
        self.assertEqual(a.plugin_browser_index, 0)
        a.rotate(-1)
        self.assertEqual(a.softkeys()[1], 'LOAD')
        a.button('F2', True)
        self.assertEqual(a.page, 'PLUGIN BROWSE')
        self.assertEqual(a.message, 'NO PLUGIN')
        a.page = 'PLUGIN'
        a.track()['plugins'] = [self.fx('urn:existing')]
        # F2 in the dedicated slot view retains its add/replace behavior.
        a.page = 'PLUGIN SLOTS'
        a.button('F2', True)
        self.assertEqual((a.page, a.plugin_browser_index), ('PLUGIN BROWSE', 0))
