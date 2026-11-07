"""Readonly transitions at native write boundaries must not add a second mutation."""
import unittest
import test_document_annotation_fonts as fonts
import test_document_display_options as display
import test_document_drafting_standard as standard


class WriteBoundaryTests(unittest.TestCase):
    def case(self, module, name, flip_at):
        case = getattr(module, name)()
        case.setUp()
        readonly = False
        calls = 0
        def dirty():
            nonlocal readonly, calls
            calls += 1
            if calls == flip_at: readonly = True
            return case.modified
        case.document.GetSaveFlag = dirty
        case.document.IsOpenedReadOnly = lambda: readonly
        return case

    def test_font_initial_live_assignment_is_refused_after_last_state_read_turns_readonly(self):
        case = self.case(fonts, 'DocumentAnnotationFontTests', 4)
        result = case.edit()
        self.assertFalse(result['ok'])
        self.assertEqual(result['mutation'], {'attempted': False, 'may_have_changed': False})
        case.assert_no_writes()

    def test_font_final_set_is_refused_after_property_state_read_turns_readonly(self):
        case = self.case(fonts, 'DocumentAnnotationFontTests', 6)
        result = case.edit()
        self.assertFalse(result['ok'])
        self.assertEqual(result['mutation'], {'attempted': True, 'may_have_changed': True})
        self.assertEqual(sum(len(item.writes) for item in case.objects), 1)
        case.extension.SetUserPreferenceTextFormat.assert_not_called()
        case.document.SetSaveFlag.assert_not_called()

    def test_scalar_initial_setters_are_refused_after_last_state_read_turns_readonly(self):
        for module, name in ((display, 'DocumentDisplayOptionsTests'), (standard, 'DocumentDraftingStandardTests')):
            with self.subTest(name=name):
                case = self.case(module, name, 4)
                if module is standard:
                    case.document.GetSaveFlag = lambda: case.modified
                    expected = case.expected()
                    case = self.case(module, name, 4)
                    result = case.edit(expected=expected)
                else:
                    result = case.edit()
                self.assertFalse(result['ok'])
                self.assertEqual(result['mutation'], {'attempted': False, 'may_have_changed': False})
                for family in ('Integer', 'Double', 'Toggle'):
                    getattr(case.extension, 'SetUserPreference' + family).assert_not_called()
                case.document.SetSaveFlag.assert_not_called()

    def test_dirty_marker_does_not_run_if_its_last_state_read_turns_readonly(self):
        for module, name, flip in ((fonts, 'DocumentAnnotationFontTests', 9),
                                  (display, 'DocumentDisplayOptionsTests', 7),
                                  (standard, 'DocumentDraftingStandardTests', 7)):
            with self.subTest(name=name):
                case = self.case(module, name, flip)
                # The standard helper reads the expected snapshot before edit;
                # capture that observation before arming the readonly trigger.
                if module is standard:
                    case.document.GetSaveFlag = lambda: case.modified
                    expected = case.expected()
                    case = self.case(module, name, flip)
                    result = case.edit(expected=expected)
                else:
                    result = case.edit()
                self.assertFalse(result['ok'])
                self.assertEqual(result['mutation'], {'attempted': True, 'may_have_changed': True})
                case.document.SetSaveFlag.assert_not_called()


if __name__ == '__main__': unittest.main()
