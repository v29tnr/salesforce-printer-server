import unittest
from unittest.mock import patch, MagicMock
from sf_printer_server.salesforce.cometd import CometDClient

class TestCometDClient(unittest.TestCase):

    @patch('sf_printer_server.salesforce.cometd.CometDClient.connect')
    def test_connect(self, mock_connect):
        client = CometDClient()
        client.connect()
        mock_connect.assert_called_once()

    @patch('sf_printer_server.salesforce.cometd.CometDClient.subscribe')
    def test_subscribe_to_event(self, mock_subscribe):
        client = CometDClient()
        event_name = 'PrintJobEvent'
        client.subscribe(event_name)
        mock_subscribe.assert_called_once_with(event_name)

    @patch('sf_printer_server.salesforce.cometd.CometDClient.on_event')
    def test_on_event(self, mock_on_event):
        client = CometDClient()
        event_data = {'printerId': '123', 'jobId': '456', 'content': 'Sample ZPL'}
        client.on_event(event_data)
        mock_on_event.assert_called_once_with(event_data)

    @patch('sf_printer_server.salesforce.cometd.CometDClient.disconnect')
    def test_disconnect(self, mock_disconnect):
        client = CometDClient()
        client.disconnect()
        mock_disconnect.assert_called_once()

if __name__ == '__main__':
    unittest.main()