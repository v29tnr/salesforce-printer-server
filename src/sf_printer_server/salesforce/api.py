from simple_salesforce import Salesforce
import json

class SalesforceAPI:
    def __init__(self, username, password, security_token):
        self.sf = Salesforce(username=username, password=password, security_token=security_token)

    def create_printer(self, printer_data):
        return self.sf.Printer__c.create(printer_data)

    def create_print_job(self, print_job_data):
        return self.sf.Print_Job__c.create(print_job_data)

    def get_printer(self, printer_id):
        return self.sf.Printer__c.get(printer_id)

    def get_print_job(self, print_job_id):
        return self.sf.Print_Job__c.get(print_job_id)

    def update_printer(self, printer_id, printer_data):
        return self.sf.Printer__c.update(printer_id, printer_data)

    def update_print_job(self, print_job_id, print_job_data):
        return self.sf.Print_Job__c.update(print_job_id, print_job_data)

    def delete_printer(self, printer_id):
        return self.sf.Printer__c.delete(printer_id)

    def delete_print_job(self, print_job_id):
        return self.sf.Print_Job__c.delete(print_job_id)

    def query(self, soql):
        return self.sf.query(soql)

    def get_printers(self):
        return self.query("SELECT Id, Name FROM Printer__c")

    def get_print_jobs(self):
        return self.query("SELECT Id, Name FROM Print_Job__c")