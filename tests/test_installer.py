"""Fluxo dos diálogos sem instalar ou remover o aplicativo do usuário."""
import tempfile
import unittest
from pathlib import Path

import build_installer as installer
from verify_installer import rows


class InstallerDialogTests(unittest.TestCase):
    def test_branded_install_remove_progress_and_terminal_dialogs(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
            db = installer.msilib.init_database(str(Path(folder) / 'ui.msi'), installer.schema,
                                               'Teste', installer.PRODUCT_CODE, installer.VERSION, 'Teste')
            installer.msilib.add_tables(db, installer.sequence)
            installer.dialogs(db)
            dialogs = rows(db, 'Dialog', ['Dialog', 'Control_Default', 'Control_Cancel'])
            self.assertIn(('InstallDlg', 'Install', 'Cancel'), dialogs)
            controls = rows(db, 'Control', ['Dialog_', 'Control', 'Type', 'Text'])
            self.assertIn(('RemoveDlg', 'Remove', 'PushButton', r'{\Button}Desinstalar'), controls)
            self.assertIn(('ProgressDlg', 'Progress', 'ProgressBar', ''), controls)
            mappings = rows(db, 'EventMapping', ['Dialog_', 'Control_', 'Event', 'Attribute'])
            self.assertIn(('ProgressDlg', 'Progress', 'Progress', 'Progress'), mappings)
            events = rows(db, 'ControlEvent', ['Dialog_', 'Control_', 'Event', 'Argument', 'Ordering'])
            self.assertIn(('RemoveDlg', 'Remove', '[REMOVE]', 'ALL', '1'), events)
            self.assertIn(('RemoveDlg', 'Remove', 'EndDialog', 'Return', '2'), events)
            self.assertIn(('ProgressDlg', 'Cancel', 'SpawnDialog', 'CancelConfirm', ''), events)
            self.assertIn(('CancelConfirm', 'Keep', 'EndDialog', 'Return', ''), events)
            self.assertIn(('CancelConfirm', 'Stop', 'EndDialog', 'Exit', ''), events)
            sequence = rows(db, 'InstallUISequence', ['Action', 'Condition', 'Sequence'])
            self.assertIn(('RemoveDlg', 'Installed', '270'), sequence)
            actions = {name: int(order) for name, _, order in sequence}
            self.assertLess(actions['InstallDlg'], actions['CostInitialize'])
            self.assertLess(actions['RemoveDlg'], actions['CostInitialize'])
            self.assertLess(actions['ProgressDlg'], actions['CostInitialize'])
            for name, code in [('ExitDialog', '-1'), ('UserExit', '-2'), ('FatalError', '-3')]:
                self.assertIn((name, '', code), sequence)
            self.assertEqual(len(rows(db, 'Binary', ['Name'])), 1)
            conditions = rows(db, 'ControlCondition', ['Dialog_', 'Control_', 'Action', 'Condition'])
            self.assertIn(('ExitDialog', 'RemoveTitle', 'Show', 'REMOVE="ALL"'), conditions)
            db = None


if __name__ == '__main__':
    unittest.main()
