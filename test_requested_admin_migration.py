import unittest
import core

class RequestedAdminMigrationTests(unittest.TestCase):
    def test_8068123777_promotes_once_and_is_protected(self):
        db=core.connect(':memory:')
        try:
            db.execute("INSERT INTO users(id,role,name) VALUES(8068123777,'agent','Абдувохид')")
            core._promote_8068123777_to_admin_once(db)
            row=db.execute("SELECT role FROM users WHERE id=8068123777").fetchone()
            self.assertEqual(row['role'],'admin')
            self.assertEqual(db.execute("SELECT value FROM meta WHERE key='secondary_admin:8068123777'").fetchone()[0],'1')
            core._promote_8068123777_to_admin_once(db)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM meta WHERE key='role_migration:8068123777:agent_to_admin:20260925'").fetchone()[0],1)
        finally:
            db.close()

    def test_open_shift_blocks_migration(self):
        db=core.connect(':memory:')
        try:
            db.execute("INSERT INTO users(id,role,name) VALUES(8068123777,'agent','Абдувохид')")
            db.execute("INSERT INTO shifts(agent,start) VALUES(8068123777,1)")
            with self.assertRaisesRegex(RuntimeError,'open shift'):
                core._promote_8068123777_to_admin_once(db)
            self.assertEqual(db.execute("SELECT role FROM users WHERE id=8068123777").fetchone()[0],'agent')
        finally:
            db.close()

if __name__=='__main__':
    unittest.main()
