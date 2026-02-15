"""
Print job processor that handles incoming print jobs from Salesforce platform events.
Downloads content documents, processes ZPL, and sends jobs to appropriate printers.
"""

import logging
import base64
from typing import Dict, Any, Optional
from sf_printer_server.jobs.models import PrintJob
from sf_printer_server.printers.drivers import get_printer_driver
from sf_printer_server.printers.zpl import validate_zpl
from sf_printer_server.salesforce.api import SalesforceAPI

logger = logging.getLogger(__name__)


class PrintJobProcessor:
    """Processes print jobs from Salesforce platform events."""
    
    def __init__(self, sf_api: SalesforceAPI, printer_configs: Dict[str, Dict[str, Any]]):
        """
        Initialize the print job processor.
        
        Args:
            sf_api: Salesforce API client for downloading documents
            printer_configs: Dictionary mapping printer IDs to printer configurations
        """
        self.sf_api = sf_api
        self.printer_configs = printer_configs
        self.printer_drivers = {}
        
        # Initialize printer drivers
        self._initialize_printers()
        
    def _initialize_printers(self):
        """Initialize printer drivers from configuration."""
        for printer_id, config in self.printer_configs.items():
            try:
                driver = get_printer_driver(config)
                self.printer_drivers[printer_id] = driver
                logger.info(f"Initialized printer: {config.get('name', printer_id)}")
            except Exception as e:
                logger.error(f"Failed to initialize printer {printer_id}: {e}")
                
    def process_job(self, job: PrintJob) -> bool:
        """
        Process a print job.
        
        Args:
            job: PrintJob instance
            
        Returns:
            True if job was processed successfully
        """
        try:
            logger.info(f"Processing print job {job.id} for printer {job.printer_id}")
            
            # Get printer driver
            driver = self.printer_drivers.get(job.printer_id)
            if not driver:
                logger.error(f"No driver found for printer {job.printer_id}")
                self._update_job_status(job.id, 'Error', f'Printer {job.printer_id} not configured')
                return False
            
            # Get print content
            content = self._get_print_content(job)
            if not content:
                logger.error(f"Failed to get content for job {job.id}")
                self._update_job_status(job.id, 'Error', 'Failed to retrieve print content')
                return False
            
            # Validate ZPL if applicable
            if job.is_zpl:
                content_str = content.decode('utf-8') if isinstance(content, bytes) else content
                if not validate_zpl(content_str):
                    logger.warning(f"Invalid ZPL content for job {job.id}")
                    # Continue anyway, printer might handle it
            
            # Send to printer
            success = driver.print(content)
            
            if success:
                logger.info(f"Successfully printed job {job.id}")
                self._update_job_status(job.id, 'Completed', 'Print job completed successfully')
                return True
            else:
                logger.error(f"Failed to print job {job.id}")
                self._update_job_status(job.id, 'Error', 'Failed to send to printer')
                return False
                
        except Exception as e:
            logger.error(f"Error processing job {job.id}: {e}", exc_info=True)
            self._update_job_status(job.id, 'Error', f'Processing error: {str(e)}')
            return False
    
    def _get_print_content(self, job: PrintJob) -> Optional[bytes]:
        """
        Get print content from job (either ZPL string or download from ContentDocument).
        
        Args:
            job: PrintJob instance
            
        Returns:
            Print content as bytes or None if failed
        """
        if job.is_zpl and job.zpl_content:
            # Direct ZPL content
            if isinstance(job.zpl_content, str):
                return job.zpl_content.encode('utf-8')
            return job.zpl_content
            
        elif job.content_document_id:
            # Download from Salesforce
            try:
                logger.info(f"Downloading ContentDocument {job.content_document_id}")
                content = self.sf_api.download_content_document(job.content_document_id)
                return content
            except Exception as e:
                logger.error(f"Failed to download ContentDocument {job.content_document_id}: {e}")
                return None
        else:
            logger.error(f"Job {job.id} has no content source")
            return None
    
    def _update_job_status(self, job_id: str, status: str, message: str):
        """
        Update print job status in Salesforce.
        
        Args:
            job_id: Print job record ID
            status: New status (Processing, Completed, Error)
            message: Status message
        """
        try:
            self.sf_api.update_print_job(job_id, {
                'Status__c': status,
                'Status_Message__c': message
            })
            logger.debug(f"Updated job {job_id} status to {status}")
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")
    
    def handle_platform_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle incoming platform event from CometD.
        
        Args:
            event_data: Platform event data
            
        Returns:
            True if event was processed successfully
        """
        try:
            logger.info(f"Received platform event: {event_data.get('event', {}).get('replayId')}")
            
            # Parse event into PrintJob
            job = PrintJob.from_platform_event(event_data)
            
            # Process the job
            return self.process_job(job)
            
        except Exception as e:
            logger.error(f"Error handling platform event: {e}", exc_info=True)
            return False
    
    def test_printer(self, printer_id: str) -> bool:
        """
        Test a printer connection.
        
        Args:
            printer_id: Printer ID
            
        Returns:
            True if printer is reachable
        """
        driver = self.printer_drivers.get(printer_id)
        if not driver:
            logger.error(f"Printer {printer_id} not found")
            return False
            
        try:
            result = driver.test_connection()
            if result:
                logger.info(f"Printer {printer_id} connection test: OK")
            else:
                logger.warning(f"Printer {printer_id} connection test: FAILED")
            return result
        except Exception as e:
            logger.error(f"Error testing printer {printer_id}: {e}")
            return False
    
    def reload_printer_config(self, printer_configs: Dict[str, Dict[str, Any]]):
        """
        Reload printer configurations.
        
        Args:
            printer_configs: New printer configurations
        """
        logger.info("Reloading printer configurations")
        self.printer_configs = printer_configs
        self.printer_drivers.clear()
        self._initialize_printers()