import unittest
from sf_printer_server.cli import main

class TestCLI(unittest.TestCase):

    def test_help_command(self):
        """Test the help command output"""
        with self.assertLogs(level='INFO') as log:
            main(['--help'])
        self.assertIn('Usage:', log.output[0])

    def test_update_config_command(self):
        """Test the update config command"""
        # Assuming there's a function to update config in the CLI
        result = main(['update-config', '--client-id', 'new_client_id', '--client-secret', 'new_client_secret'])
        self.assertEqual(result, 0)  # Assuming 0 indicates success

    def test_invalid_command(self):
        """Test handling of invalid commands"""
        with self.assertRaises(SystemExit) as cm:
            main(['invalid-command'])
        self.assertEqual(cm.exception.code, 1)  # Assuming 1 indicates an error

if __name__ == '__main__':
    unittest.main()