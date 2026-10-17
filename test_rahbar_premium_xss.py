import os, re, shutil, subprocess, unittest

HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'miniapps', 'rahbar-premium', 'index.html')
EVIL = '<img src=x onerror=alert(1)>'


class RahbarPremiumEscapingTests(unittest.TestCase):
    """Mijoz/agent nomini agent kiritadi: rahbar panelida u HTML bo'lib bajarilmasligi kerak."""

    def setUp(self):
        with open(HTML, encoding='utf-8') as f:
            self.html = f.read()

    def test_no_raw_name_interpolation(self):
        for raw in ('<b>${c[0]}</b>', '<b>${a[0]}</b>', "'${c[0]}'", '${c[0][0]}</div>', '${a[0][0]}</div>'):
            self.assertNotIn(raw, self.html)

    @unittest.skipUnless(shutil.which('node'), 'node kerak')
    def test_rows_escape_names(self):
        defs = []
        for name in ('hx', 'cols', 'CL', 'AG', 'clRow', 'agRow'):
            m = re.search(r'^const ' + name + r'=.*$', self.html, re.M)
            self.assertIsNotNone(m, name)
            defs.append(m.group(0))
        script = '\n'.join(defs) + f'''
CL.splice(0,CL.length,[{EVIL!r},{EVIL!r},{EVIL!r},1,"5+ kun"]);
AG.splice(0,AG.length,[{EVIL!r},{EVIL!r},1,1,"Faol"]);
process.stdout.write(clRow(CL[0])+'\\n'+agRow(AG[0]));
'''
        out = subprocess.run(['node', '-e', script], capture_output=True, text=True, check=True).stdout
        self.assertNotIn('<img', out)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', out)
        self.assertIn("CL[0][0]", out)  # qo'ng'iroq tugmasi nomni JS satriga qo'ymaydi


if __name__ == '__main__':
    unittest.main()
