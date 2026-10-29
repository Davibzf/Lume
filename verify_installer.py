"""Confere estrutura do MSI e, opcionalmente, os arquivos instalados."""
import argparse
import hashlib
from pathlib import Path
import warnings
from version import VERSION

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import msilib


def rows(db, table, fields):
    view = db.OpenView('SELECT ' + ','.join('`' + field + '`' for field in fields) + ' FROM `' + table + '`')
    view.Execute(None)
    result = []
    while (record := view.Fetch()) is not None:
        result.append(tuple(record.GetString(i + 1) for i in range(len(fields))))
    view.Close()
    return result


def verify(package, source, installed=None):
    db = msilib.OpenDatabase(str(package.resolve()), msilib.MSIDBOPEN_READONLY)
    properties = dict(rows(db, 'Property', ['Property', 'Value']))
    assert properties['ProductName'] == 'Lume — Transcrição Local'
    assert properties['ProductLanguage'] == '1046'
    assert properties['ProductVersion'] == VERSION
    upgrades = rows(db, 'Upgrade', ['ActionProperty', 'Attributes'])
    assert ('OLDPRODUCTS', '1') in upgrades and ('NEWERPRODUCTS', '258') in upgrades
    for table in ('InstallUISequence', 'InstallExecuteSequence'):
        actions = dict(rows(db, table, ['Action', 'Sequence']))
        assert int(actions['FindRelatedProducts']) < int(actions['LaunchConditions'])
        if table == 'InstallUISequence':
            assert int(actions['LaunchConditions']) < int(actions['InstallDlg']) < int(actions['CostInitialize'])
            assert int(actions['RemoveDlg']) < int(actions['CostInitialize'])
            assert int(actions['ProgressDlg']) < int(actions['CostInitialize'])
    assert properties.get('ALLUSERS', '') == '', 'O instalador deve ser por usuário.'
    assert db.GetSummaryInformation(0).GetProperty(msilib.PID_TEMPLATE) == b'x64;1046'
    files = rows(db, 'File', ['File', 'Component_', 'Sequence'])
    originals = sorted(p for p in source.rglob('*') if p.is_file())
    assert len(files) == len(originals), (len(files), len(originals))
    assert sorted(int(row[2]) for row in files) == list(range(1, len(files) + 1))
    components = {row[0] for row in rows(db, 'Component', ['Component'])}
    assert all(row[1] in components for row in files)
    assert len(rows(db, 'Shortcut', ['Shortcut'])) == 3
    assert ('UninstallLink', '/x "[ProductCode]"') in rows(db, 'Shortcut', ['Shortcut', 'Arguments'])
    assert {'Lume', 'DESINS~1|Desinstalar Lume'} == {row[0] for row in rows(db, 'Shortcut', ['Name'])}
    dialogs = {row[0] for row in rows(db, 'Dialog', ['Dialog'])}
    assert {'InstallDlg', 'RemoveDlg', 'ProgressDlg', 'ExitDialog', 'FatalError', 'UserExit'} <= dialogs
    assert ('InstallDlg', 'Cancel') in rows(db, 'Dialog', ['Dialog', 'Control_Cancel'])
    assert ('ProgressDlg', 'Progress', 'Progress', 'Progress') in rows(db, 'EventMapping', ['Dialog_', 'Control_', 'Event', 'Attribute'])
    events = rows(db, 'ControlEvent', ['Dialog_', 'Control_', 'Event', 'Argument', 'Ordering'])
    assert ('RemoveDlg', 'Remove', '[REMOVE]', 'ALL', '1') in events
    assert ('RemoveDlg', 'Remove', 'EndDialog', 'Return', '2') in events
    assert not rows(db, 'CustomAction', ['Action']), 'Não deve haver execução de scripts no instalador.'
    assert not rows(db, 'RemoveRegistry', ['RemoveRegistry'])
    assert all(not filename for _, filename in rows(db, 'RemoveFile', ['FileKey', 'FileName']))
    assert not any('large-v3' in row[0] for row in files), 'Modelos são dados separados e preservados.'
    if installed:
        for original in originals:
            target = installed / original.relative_to(source)
            assert target.is_file(), f'Arquivo ausente: {target}'
            with original.open('rb') as first, target.open('rb') as second:
                assert hashlib.file_digest(first, 'sha256').digest() == hashlib.file_digest(second, 'sha256').digest(), f'Arquivo diferente: {target}'
    print(f'MSI validado: {len(files)} arquivos, x64, português, por usuário, três atalhos e desinstalação personalizada sem apagar modelos.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, default=Path('output/Lume-Windows-x64.msi'))
    parser.add_argument('--source', type=Path, default=Path('output/Lume/TranscreveLocal'))
    parser.add_argument('--installed', type=Path)
    args = parser.parse_args()
    verify(args.package, args.source, args.installed)
