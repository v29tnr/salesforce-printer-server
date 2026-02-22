/**
 * PrinterService
 *
 * Reusable service for firing SF_Printer_Event__e platform events.
 * Looks up the Printer__c record to build connection details and ZPL config.
 *
 * Usage — from Apex:
 *   PrinterService.PrintRequest req = new PrinterService.PrintRequest();
 *   req.printerId    = '001xx...';
 *   req.contentType  = 'raw_base64';
 *   req.content      = EncodingUtil.base64Encode(Blob.valueOf(zplString));
 *   req.correlationId = 'order-' + recordId;
 *   PrinterService.send(new List<PrinterService.PrintRequest>{ req });
 *
 * Usage — from Flow:
 *   Action type: Apex  →  PrinterService
 *   Required inputs: Printer_Id, Content_Type, Content
 *   Optional inputs: Correlation_Id, Job_Title, Source, Qty, Options_JSON
 */
public with sharing class PrinterService {

    // -------------------------------------------------------------------------
    // Invocable input class — each property maps to a Flow input variable
    // -------------------------------------------------------------------------

    public class PrintRequest {
        @InvocableVariable(label='Printer ID' description='Id of the Printer__c record' required=true)
        public Id printerId;

        @InvocableVariable(label='Content Type' description='pdf_uri | pdf_base64 | raw_uri | raw_base64' required=true)
        public String contentType;

        @InvocableVariable(label='Content' description='Base64 payload or URL depending on Content Type' required=true)
        public String content;

        @InvocableVariable(label='Correlation ID' description='Unique ID for idempotency. Use a UUID or record Id + timestamp.')
        public String correlationId;

        @InvocableVariable(label='Job Title' description='Label shown in the print queue')
        public String jobTitle;

        @InvocableVariable(label='Source' description='Free text — identifies the originating process or record type')
        public String source;

        @InvocableVariable(label='Qty' description='Number of copies. RAW/ZPL only — PDF uses Options JSON.')
        public Integer qty;

        @InvocableVariable(label='Options JSON' description='PDF options JSON blob. e.g. {"copies":2,"duplex":"long-edge"}')
        public String optionsJson;

        @InvocableVariable(label='Expire After (seconds)' description='Discard job if not delivered within this many seconds')
        public Integer expireAfter;

        @InvocableVariable(label='Auth Config JSON' description='HTTP auth for downloading *_uri content. e.g. {"type":"BearerToken","token":"<session>"} or {"type":"BasicAuth","user":"u","pass":"p"}')
        public String authConfig;
    }

    // -------------------------------------------------------------------------
    // Invocable entry point — called by Flow
    // -------------------------------------------------------------------------

    @InvocableMethod(
        label='Send Print Job'
        description='Fires SF_Printer_Event__e to the printer server. Looks up Printer__c for connection details and ZPL config.'
        category='Printing'
    )
    public static void send(List<PrintRequest> requests) {
        if (requests == null || requests.isEmpty()) return;

        // Collect all Printer IDs for a single query
        Set<Id> printerIds = new Set<Id>();
        for (PrintRequest r : requests) {
            if (r.printerId != null) printerIds.add(r.printerId);
        }

        Map<Id, Printer__c> printers = new Map<Id, Printer__c>([
            SELECT Id, Name, Host__c, Port__c, Type__c, Enabled__c,
                   DPI__c, Label_Width_mm__c, Label_Height_mm__c,
                   Darkness__c, ZPL_Prefix__c
            FROM Printer__c
            WHERE Id IN :printerIds
        ]);

        List<SF_Printer_Event__e> events = new List<SF_Printer_Event__e>();

        for (PrintRequest req : requests) {
            Printer__c printer = printers.get(req.printerId);

            if (printer == null) {
                throw new PrinterServiceException('Printer not found: ' + req.printerId);
            }
            if (printer.Enabled__c == false) {
                throw new PrinterServiceException('Printer \'' + printer.Name + '\' is disabled. Enable it on the Printer record before sending jobs.');
            }

            SF_Printer_Event__e evt = new SF_Printer_Event__e();
            evt.Type__c         = 'print_job';
            evt.Printer_Host__c = printer.Host__c;
            evt.Printer_Port__c = printer.Port__c != null ? printer.Port__c : 9100;
            evt.Printer_Type__c = printer.Type__c;
            evt.Content_Type__c = req.contentType;
            evt.Content__c      = req.content;
            evt.Correlation_Id__c = String.isNotBlank(req.correlationId)
                ? req.correlationId
                : generateUUID();
            evt.Job_Title__c    = req.jobTitle;
            evt.Source__c       = req.source;
            evt.Qty__c          = req.qty != null ? req.qty : 1;
            evt.Options__c      = req.optionsJson;
            evt.Expire_After__c = req.expireAfter;
            evt.Auth_Config__c  = req.authConfig;
            evt.ZPL_Config__c   = buildZplConfig(printer);

            events.add(evt);
        }

        if (!events.isEmpty()) {
            List<Database.SaveResult> results = EventBus.publish(events);
            for (Integer i = 0; i < results.size(); i++) {
                if (!results[i].isSuccess()) {
                    for (Database.Error err : results[i].getErrors()) {
                        System.debug(LoggingLevel.ERROR,
                            'PrinterService: Failed to publish event for printer '
                            + requests[i].printerId + ': ' + err.getMessage());
                    }
                }
            }
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /**
     * Build the ZPL_Config__c JSON from Printer__c fields.
     * Returns null if no ZPL-relevant fields are populated (server will auto-detect).
     */
    private static String buildZplConfig(Printer__c printer) {
        // Only build config for ZPL/RAW printer types
        String pType = (printer.Type__c != null ? printer.Type__c : '').toLowerCase();
        if (pType != 'zpl' && pType != 'raw') return null;

        Map<String, Object> cfg = new Map<String, Object>();

        if (printer.DPI__c != null) {
            cfg.put('dpi', (Integer) printer.DPI__c);
        }

        Decimal dpi = printer.DPI__c != null ? printer.DPI__c : 203;

        if (printer.Label_Width_mm__c != null) {
            cfg.put('width_dots', (Integer)(printer.Label_Width_mm__c / 25.4 * dpi).round());
        }
        if (printer.Label_Height_mm__c != null) {
            cfg.put('height_dots', (Integer)(printer.Label_Height_mm__c / 25.4 * dpi).round());
        }
        if (printer.Darkness__c != null) {
            cfg.put('darkness', (Integer) printer.Darkness__c);
        }
        if (String.isNotBlank(printer.ZPL_Prefix__c)) {
            cfg.put('prefix', printer.ZPL_Prefix__c);
        }

        return cfg.isEmpty() ? null : JSON.serialize(cfg);
    }

    /**
     * Generate a random UUID v4-format correlation ID.
     * Uses 128-bit crypto-random bytes — unique across all users and orgs.
     * Format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
     */
    private static String generateUUID() {
        Blob b = Crypto.generateAesKey(128);
        String h = EncodingUtil.convertToHex(b);  // 32 hex chars
        return h.substring(0, 8)  + '-' +
               h.substring(8, 12) + '-' +
               '4' + h.substring(13, 16) + '-' +
               h.substring(16, 20) + '-' +
               h.substring(20, 32);
    }

    public class PrinterServiceException extends Exception {}
}
