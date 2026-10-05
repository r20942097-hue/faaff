import hashlib,sys,tempfile,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from audit_product_archives import audit
from governance import Invalid
class ProductArchiveAuditTests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def fixture(self,extra=False):
        p=self.root/'product.zip'; payload=b'content'; digest=hashlib.sha256(payload).hexdigest()
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('package/data',payload);z.writestr('package/SHA256SUMS',digest+'  data\n')
            if extra:z.writestr('package/unlisted',b'extra')
        (self.root/'product.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  product.zip\n')
        return p
    def test_valid_archive(self):
        self.fixture();d=audit(self.root);self.assertEqual(d['archives'][0]['internal_hashes_verified'],1)
    def test_companion_hash_tamper(self):
        self.fixture();(self.root/'product.sha256').write_text('0'*64+'  product.zip\n')
        with self.assertRaises(Invalid):audit(self.root)
    def test_unlisted_member(self):
        self.fixture(True)
        with self.assertRaises(Invalid):audit(self.root)
    def test_missing_companion(self):
        p=self.fixture();(self.root/'product.sha256').rename(self.root/'not-a-checksum.txt')
        with self.assertRaises(Invalid):audit(self.root)
if __name__=='__main__':unittest.main()
