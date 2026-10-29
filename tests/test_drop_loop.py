import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(os.name == 'nt', 'Integração nativa do Windows')
class DropLoopTests(unittest.TestCase):
    def test_posted_drop_survives_real_tk_mainloop(self):
        probe = Path(__file__).with_name('drop_probe.py')
        result = subprocess.run([sys.executable, '-X', 'faulthandler', str(probe)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"success": true', result.stdout)
