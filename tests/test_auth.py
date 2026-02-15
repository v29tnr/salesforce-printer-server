import unittest
from sf_printer_server.auth.oauth import OAuth

class TestAuth(unittest.TestCase):

    def setUp(self):
        self.oauth = OAuth(client_id='test_client_id', client_secret='test_client_secret')

    def test_token_generation(self):
        token = self.oauth.get_token()
        self.assertIsNotNone(token)
        self.assertIn('access_token', token)

    def test_token_expiration(self):
        self.oauth.get_token()
        self.assertTrue(self.oauth.is_token_valid())

    def test_invalid_credentials(self):
        invalid_oauth = OAuth(client_id='invalid_id', client_secret='invalid_secret')
        with self.assertRaises(Exception):
            invalid_oauth.get_token()

if __name__ == '__main__':
    unittest.main()