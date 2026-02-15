import unittest
from sf_printer_server.jobs.processor import PrintJobProcessor
from sf_printer_server.jobs.models import PrintJob, Printer

class TestPrintJobProcessor(unittest.TestCase):

    def setUp(self):
        self.printer = Printer(id='printer1', name='Test Printer')
        self.print_job = PrintJob(id='job1', printer=self.printer, content='Test content', is_zpl=False)
        self.processor = PrintJobProcessor()

    def test_process_print_job(self):
        result = self.processor.process(self.print_job)
        self.assertTrue(result)
        # Add more assertions based on expected behavior

    def test_process_zpl_print_job(self):
        self.print_job.is_zpl = True
        result = self.processor.process(self.print_job)
        self.assertTrue(result)
        # Add more assertions based on expected behavior

    def test_invalid_print_job(self):
        invalid_job = PrintJob(id='job2', printer=None, content='', is_zpl=False)
        with self.assertRaises(ValueError):
            self.processor.process(invalid_job)

if __name__ == '__main__':
    unittest.main()