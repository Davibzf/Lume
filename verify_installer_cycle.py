"""Integração explícita com MSI mínimo e identidade isolada; não altera o aplicativo real."""
import gc
import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import build_installer as installer


def run():
    result_dir = Path(__file__).parent / 'test-results'
    result_dir.mkdir(exist_ok=True)
    product = '{' + str(uuid.uuid4()).upper() + '}'
    upgrade = '{' + str(uuid.uuid4()).upper() + '}'
    with tempfile.TemporaryDirectory(prefix='transcreve-msi-test-') as folder:
        root = Path(folder)
        source = root / 'payload'
        assets = source / '_internal/assets'
        assets.mkdir(parents=True)
        (source / 'TranscreveLocal.exe').write_bytes(b'Arquivo inerte usado apenas para testar o instalador.')
        shutil.copyfile(Path(__file__).parent / 'assets/transcreve.ico', assets / 'transcreve.ico')
        package = root / 'isolated.msi'
        target = root / 'installed'
        preserved = root / 'user-data'
        preserved.mkdir()
        (preserved / 'model.bin').write_bytes(b'modelo de teste')
        (preserved / 'transcricao.txt').write_text('Texto preservado.', encoding='utf-8')
        before = {p.name: p.read_bytes() for p in preserved.iterdir()}
        with patch.object(installer, 'PRODUCT_CODE', product), patch.object(installer, 'UPGRADE_CODE', upgrade), patch.object(installer, 'NAMESPACE', uuid.UUID(upgrade.strip('{}'))):
            installer.build(source, package)
        # Identificação visível distinta e nenhum atalho/registro do aplicativo real.
        db = installer.msilib.OpenDatabase(str(package), installer.msilib.MSIDBOPEN_TRANSACT)
        view = db.OpenView("UPDATE `Property` SET `Value` = 'Transcreve Local - Teste isolado' WHERE `Property` = 'ProductName'")
        view.Execute(None)
        view.Close()
        db.Commit()
        view = None
        db = None
        gc.collect()
        executable = str(Path('C:/Windows/System32/msiexec.exe'))
        installed = False
        try:
            code = subprocess.run([executable, '/i', str(package), '/qn', '/norestart',
                                   f'INSTALLDIR={target}', 'NO_SHORTCUTS=1', '/l*v', str(result_dir / f'{installer.VERSION}-install-cycle.log')], timeout=120).returncode
            assert code in (0, 3010), f'Instalação retornou {code}'
            installed = True
            for original in source.rglob('*'):
                if original.is_file():
                    assert (target / original.relative_to(source)).read_bytes() == original.read_bytes()
            code = subprocess.run([executable, '/x', product, '/qn', '/norestart', '/l*v',
                                   str(result_dir / f'{installer.VERSION}-remove-cycle.log')], timeout=120).returncode
            assert code in (0, 3010), f'Desinstalação retornou {code}'
            installed = False
            assert not (target / 'TranscreveLocal.exe').exists()
            assert not (target / '_internal/assets/transcreve.ico').exists()
            assert before == {p.name: p.read_bytes() for p in preserved.iterdir()}
            report = {'success': True, 'product_code': product, 'install_exit': 0,
                      'remove_exit': code, 'payload_removed': True, 'user_data_preserved': True,
                      'isolated_identity': True, 'shortcuts_disabled': True}
            (result_dir / f'{installer.VERSION}-installer-cycle.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report, indent=2))
        finally:
            if installed:
                subprocess.run([executable, '/x', product, '/qn', '/norestart'], timeout=120, check=True)


if __name__ == '__main__':
    run()
