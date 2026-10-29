"""Gera MSI x64 por usuário usando o Windows Installer e Python 3.11."""
import argparse
import hashlib
from pathlib import Path
import uuid
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import msilib
    from msilib import schema, sequence

from version import VERSION

PRODUCT_CODE = '{4931F68D-B147-4966-BF38-07FA6E8F8AC8}'
UPGRADE_CODE = '{062FF886-6795-43E5-A7D5-BB0E74242392}'
NAMESPACE = uuid.UUID(UPGRADE_CODE.strip('{}'))


def identifier(prefix, value):
    return prefix + hashlib.sha256(value.encode('utf-8')).hexdigest()[:24]


def guid(value):
    return '{' + str(uuid.uuid5(NAMESPACE, value)).upper() + '}'


def dialogs(db):
    msilib.add_data(db, 'Binary', [('InstallerBackdrop', msilib.Binary(str(Path(__file__).parent / 'assets/installer/backdrop.bmp')))])
    msilib.add_data(db, 'TextStyle', [
        ('Body', 'Segoe UI', 10, 0x39352F, 0), ('Muted', 'Segoe UI', 9, 0x726C65, 0),
        ('Heading', 'Georgia', 23, 0x242322, 0), ('Eyebrow', 'Segoe UI', 9, 0x436BA8, 1),
        ('Button', 'Segoe UI', 10, 0x242322, 0),
    ])

    def page(name, first, modal=True, cancel=None):
        dialog = msilib.Dialog(db, name, 50, 50, 560, 360, 3 if modal else 1,
                               'Lume — Transcrição Local', first, first if modal else None, (cancel or first) if modal else None)
        dialog.bitmap('Backdrop', 0, 0, 560, 360, 'InstallerBackdrop')
        dialog.text('Eyebrow', 195, 30, 330, 16, 65539, r'{\Eyebrow}LUME  /  TRANSCRIÇÃO LOCAL  /  ' + VERSION)
        dialog.text('Footer', 195, 292, 330, 16, 65539, r'{\Muted}Feito para suas palavras. No seu computador.')
        return dialog

    def copy(dialog, title, body, prefix='', condition=None):
        for name, y, height, text in [('Title', 58, 78, r'{\Heading}' + title),
                                      ('Description', 148, 120, r'{\Body}' + body)]:
            control = dialog.text(prefix + name, 195, y, 330, height, 65539, text)
            if condition:
                control.condition('Show', condition)
                control.condition('Hide', 'NOT (' + condition + ')')

    welcome = page('InstallDlg', 'Install', cancel='Cancel')
    copy(welcome, 'Dê espaço às\nsuas palavras.',
         'Vídeos e áudios viram texto, com tudo acontecendo no seu PC.\n\n'
         'Instalação para sua conta, com atalhos prontos para usar. '
         'Seus modelos atuais serão mantidos.\n\nO primeiro uso pode exigir o download de um modelo.')
    welcome.pushbutton('Cancel', 323, 319, 92, 24, 3, r'{\Button}Cancelar', 'Install').event('EndDialog', 'Exit')
    welcome.pushbutton('Install', 427, 319, 98, 24, 3, r'{\Button}Instalar', 'Cancel').event('EndDialog', 'Return')
    remove = page('RemoveDlg', 'Cancel')
    copy(remove, 'Até a próxima.', 'Deseja desinstalar o Lume?\n\n'
         'O aplicativo e seus atalhos serão removidos desta conta.\n\n'
         'Seus modelos baixados, transcrições exportadas e arquivos originais serão preservados.')
    remove.pushbutton('Cancel', 323, 319, 92, 24, 3, r'{\Button}Manter aplicativo', 'Remove').event('EndDialog', 'Exit')
    button = remove.pushbutton('Remove', 427, 319, 98, 24, 3, r'{\Button}Desinstalar', 'Cancel')
    button.event('[REMOVE]', 'ALL', ordering=1)
    button.event('EndDialog', 'Return', ordering=2)
    progress = page('ProgressDlg', 'Cancel', modal=False)
    copy(progress, 'Preparando\nseu aplicativo.',
         'Instalando o aplicativo. Seus modelos e arquivos permanecem seguros.', condition='NOT REMOVE="ALL"')
    copy(progress, 'Encerrando\neste capítulo.',
         'Removendo o aplicativo e seus atalhos. Seus modelos e transcrições serão mantidos.',
         prefix='Remove', condition='REMOVE="ALL"')
    progress.control('Progress', 'ProgressBar', 195, 233, 330, 12, 65539, None, None, None, None).mapping('Progress', 'Progress')
    progress.text('Action', 195, 254, 330, 28, 65539, r'{\Muted}Preparando…').mapping('ActionText', 'Text')
    progress.pushbutton('Cancel', 427, 319, 98, 24, 3, r'{\Button}Cancelar', None).event('SpawnDialog', 'CancelConfirm')
    confirm = page('CancelConfirm', 'Keep')
    copy(confirm, 'Deseja\ncancelar?', 'O Windows interromperá a operação e desfará as alterações desta instalação.\n\nSeus modelos e arquivos pessoais serão preservados.')
    confirm.pushbutton('Keep', 303, 319, 112, 24, 3, r'{\Button}Continuar operação', 'Stop').event('EndDialog', 'Return')
    confirm.pushbutton('Stop', 427, 319, 98, 24, 3, r'{\Button}Cancelar operação', 'Keep').event('EndDialog', 'Exit')
    for name, title, body in [
        ('ExitDialog', 'Seu espaço\nestá pronto.', 'Instalação concluída.\n\nAbra o Lume pelo menu Iniciar ou pelo atalho da área de trabalho.'),
        ('FatalError', 'Não foi possível\nconcluir.', 'O Windows encontrou um problema.\n\nFeche o aplicativo, confira o espaço disponível e tente novamente. Seus modelos e transcrições permanecem na pasta de dados.'),
        ('UserExit', 'Tudo bem.\nFica para depois.', 'Operação cancelada.\n\nVocê pode executar o instalador novamente quando quiser. Seus arquivos pessoais não são removidos.'),
    ]:
        dialog = page(name, 'Finish')
        copy(dialog, title, body, condition='NOT REMOVE="ALL"' if name == 'ExitDialog' else None)
        if name == 'ExitDialog':
            copy(dialog, 'Até a próxima.', 'Desinstalação concluída.\n\nO aplicativo e seus atalhos foram removidos. Seus modelos, transcrições exportadas e arquivos originais continuam com você.',
                 prefix='Remove', condition='REMOVE="ALL"')
        dialog.pushbutton('Finish', 427, 319, 98, 24, 3, r'{\Button}Concluir', None).event('EndDialog', 'Return')
    # Mostrar a confirmação antes de calcular/verificar os arquivos instalados.
    msilib.add_data(db, 'InstallUISequence', [('InstallDlg', 'NOT Installed', 270), ('RemoveDlg', 'Installed', 270), ('ProgressDlg', None, 280)])


def build(source, output):
    if not msilib.AMD64:
        raise RuntimeError('Use Python 3.11 de 64 bits para gerar o instalador.')
    source, output = source.resolve(), output.resolve()
    if not (source / 'TranscreveLocal.exe').is_file() or not (source / '_internal').is_dir():
        raise ValueError('A pasta deve conter o executável e _internal do aplicativo completo.')
    output.parent.mkdir(parents=True, exist_ok=True)
    db = msilib.init_database(str(output), schema, 'Lume — Transcrição Local', PRODUCT_CODE, VERSION, 'Lume')
    msilib.add_tables(db, sequence)
    msilib.add_data(db, 'Property', [
        ('UpgradeCode', UPGRADE_CODE), ('DefaultUIFont', 'Body'), ('INSTALLLEVEL', '1'),
        ('ARPCOMMENTS', 'Transcrição privada e local de vídeos e áudios.'), ('ARPNOMODIFY', '1'), ('ARPNOREPAIR', '1'),
        ('REBOOT', 'ReallySuppress'), ('DiskPrompt', 'Lume'),
        ('SecureCustomProperties', 'OLDPRODUCTS;NEWERPRODUCTS'),
        ('MSIRESTARTMANAGERCONTROL', 'Disable'),
    ])
    msilib.add_data(db, 'Upgrade', [
        (UPGRADE_CODE, None, VERSION, None, 1, None, 'OLDPRODUCTS'),
        (UPGRADE_CODE, VERSION, None, None, 258, None, 'NEWERPRODUCTS'),
    ])
    msilib.add_data(db, 'LaunchCondition', [('Installed OR NOT NEWERPRODUCTS', 'Uma versão igual ou mais recente já está instalada.')])
    for table in ('InstallUISequence', 'InstallExecuteSequence'):
        view = db.OpenView(f"UPDATE `{table}` SET `Sequence` = 250 WHERE `Action` = 'LaunchConditions'")
        view.Execute(None)
    view = db.OpenView("UPDATE `Property` SET `Value` = '1046' WHERE `Property` = 'ProductLanguage'")
    view.Execute(None)
    summary = db.GetSummaryInformation(20)
    summary.SetProperty(msilib.PID_TEMPLATE, 'x64;1046')
    summary.SetProperty(msilib.PID_PAGECOUNT, 500)
    summary.SetProperty(msilib.PID_CODEPAGE, 1252)
    summary.SetProperty(msilib.PID_WORDCOUNT, 10)  # Comprimido, nomes longos, sem elevação.
    summary.Persist()
    msilib.add_data(db, 'LaunchCondition', [('VersionNT64', 'Este aplicativo requer Windows de 64 bits.')])
    cab = msilib.CAB('payload.cab')
    feature = msilib.Feature(db, 'Application', 'Lume', 'Aplicativo completo', 1)
    feature.set_current()
    root = msilib.Directory(db, cab, None, str(source), 'TARGETDIR', 'SourceDir', 0)
    local = msilib.Directory(db, cab, root, '', 'LocalAppDataFolder', '.', 0)
    programs = msilib.Directory(db, cab, local, '', 'UserPrograms', 'Programs', 0)
    install = msilib.Directory(db, cab, programs, '', 'INSTALLDIR', 'TranscreveLocal', 0)
    directories = {Path('.'): install}
    for folder in sorted((p for p in source.rglob('*') if p.is_dir()), key=lambda p: (len(p.parts), str(p))):
        relative = folder.relative_to(source)
        parent = directories[relative.parent]
        directories[relative] = msilib.Directory(db, cab, parent, folder.name, identifier('D', relative.as_posix()), parent.make_short(folder.name) + '|' + folder.name, 0)
    files = sorted(p for p in source.rglob('*') if p.is_file())
    for file in files:
        relative = file.relative_to(source)
        directory = directories[relative.parent]
        component = identifier('C', relative.as_posix())
        directory.start_component(component, feature, 0, keyfile=file.name, uuid=guid(relative.as_posix()))
        directory.add_file(file.name)
    msilib.add_data(db, 'Directory', [('DesktopFolder', 'TARGETDIR', '.'), ('ProgramMenuFolder', 'TARGETDIR', '.'), ('AppMenu', 'ProgramMenuFolder', 'Lume')])
    msilib.add_data(db, 'Component', [('Shortcuts', guid('shortcuts-lume'), 'INSTALLDIR', 260, 'NOT NO_SHORTCUTS', 'InstallMarker')])
    msilib.add_data(db, 'FeatureComponents', [('Application', 'Shortcuts')])
    msilib.add_data(db, 'Registry', [('InstallMarker', 1, r'Software\TranscreveLocal\Installer', 'LumeInstalled', '#1', 'Shortcuts')])
    msilib.add_data(db, 'Icon', [('AppIcon', msilib.Binary(str(source / '_internal/assets/transcreve.ico')))])
    msilib.add_data(db, 'Property', [('ARPPRODUCTICON', 'AppIcon')])
    msilib.add_data(db, 'Shortcut', [(name, directory, 'Lume', 'Shortcuts', '[INSTALLDIR]TranscreveLocal.exe', None, 'Lume — transcrição local de vídeos e áudios', None, 'AppIcon', 0, 1, 'INSTALLDIR') for name, directory in [('DesktopLink', 'DesktopFolder'), ('MenuLink', 'AppMenu')]])
    msilib.add_data(db, 'Directory', [('System64Folder', 'TARGETDIR', '.')])
    msilib.add_data(db, 'Shortcut', [('UninstallLink', 'AppMenu', 'DESINS~1|Desinstalar Lume', 'Shortcuts', '[System64Folder]msiexec.exe', '/x "[ProductCode]"', 'Desinstalar preservando modelos e arquivos pessoais', None, 'AppIcon', 0, 1, 'INSTALLDIR')])
    msilib.add_data(db, 'RemoveFile', [('RemoveAppMenu', 'Shortcuts', None, 'AppMenu', 2)])
    dialogs(db)
    cab.commit(db)
    db.Commit()
    print(f'Instalador gerado: {output}\nArquivos incorporados: {len(files)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path('output/Lume/TranscreveLocal'))
    parser.add_argument('--output', type=Path, default=Path('output/Lume-Windows-x64.msi'))
    args = parser.parse_args()
    build(args.source, args.output)
