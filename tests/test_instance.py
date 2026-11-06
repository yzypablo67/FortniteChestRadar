import unittest,sys,subprocess,tempfile,os
from pathlib import Path

@unittest.skipUnless(os.name=='nt','Windows mutex integration')
class InstanceTests(unittest.TestCase):
    def test_two_processes_cannot_acquire_same_folder(self):
        project=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=project/"tests") as folder:
            code='from single_instance import acquire;import sys,time;print(acquire(sys.argv[1]),flush=True);time.sleep(10)'
            first=subprocess.Popen([sys.executable,'-u','-c',code,folder],cwd=project,stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(first.stdout.readline().strip(),'True')
                second=subprocess.run([sys.executable,'-c','from single_instance import acquire;import sys;print(acquire(sys.argv[1]))',folder],cwd=project,capture_output=True,text=True,timeout=5)
                self.assertEqual(second.returncode,0)
                self.assertEqual(second.stdout.strip(),'False')
            finally:
                first.terminate();first.wait(timeout=5);first.stdout.close()
