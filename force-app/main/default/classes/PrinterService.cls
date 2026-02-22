/**
 * PrinterService
 *
 * Reusable service for firing SF_Printer_Event__e platform events.
 * Looks up the Printer__c record to build connection details and ZPL config.
 *
 * ── SIMPLE USAGE (PDF from Salesforce File) ──────────────────────────────────────
 * Just provide Printer ID and Content Document ID — the service does the rest:
 *
 *   PrinterService.PrintRequest req = new PrinterService.PrintRequest();
 *   req.printerId         = myRecord.Printer__c;
 *   req.contentDocumentId = cvId;   // ContentDocument Id
 *   req.jobTitle          = 'Invoice ' + myRecord.Name;
 *   PrinterService.send(new List<PrinterService.PrintRequest>{ req });
 *
 * ── ZPL / RAW USAGE ───────────────────────────────────────────────────────
 *   req.printerId   = myRecord.Printer__c;
 *   req.contentType = 'raw_base64';
 *   req.content     = EncodingUtil.base64Encode(Blob.valueOf(zplString));
 *
 * ── FLOW USAGE ─────────────────────────────────────────────────────────────
 *   Action type: Apex → PrinterService → Send Print Job
 *   Required:  Printer ID + (Content Document ID  OR  Content Type + Content)
 *   Optional:  Job Title, Source, Qty, Options JSON
 */
public with sharing class PrinterService {

    // Update this when you upgrade your org's API version
    // (Setup → Apex Classes → API Version, or check your sfdx-project.json sourceApiVersion)
    private static final String API_VERSION = 'v65.0';

    // -------------------------------------------------------------------------
    // Input class — each property is a Flow input variable
    // -------------------------------------------------------------------------

    public class PrintRequest {

        // ── Required: identify the printer ──────────────────────────────────────
        @InvocableVariable(label='Printer ID' description='Id of the Printer__c record' required=true)
        public Id printerId;

        // ── Option A: Salesforce File (easiest for admins) ──────────────────────
        @InvocableVariable(
            label='Content Document ID'
            description='Id of a ContentDocument (Salesforce File). The service automatically fetches the latest version and sends it to the printer. Use this OR Content Type + Content — not both.'
        )
        public Id contentDocumentId;

        // ── Option B: Manual content (ZPL, external PDF, etc.) ───────────────
        @InvocableVariable(
            label='Content Type'
            description='pdf_uri | pdf_base64 | raw_uri | raw_base64. Not needed when using Content Document ID.'
        )
        public String contentType;

        @InvocableVariable(
            label='Content'
            description='Base64 payload or URL. Not needed when using Content Document ID.'
        )
        public String content;

        // ── Optional metadata ───────────────────────────────────────────────
        @InvocableVariable(label='Job Title' description='Label shown in the print queue')
        public String jobTitle;

        @InvocableVariable(label='Source' description='Free text — identifies the originating process, flow or object')
        public String source;

        @InvocableVariable(label='Qty' description='Number of copies. ZPL/RAW only — PDF uses Options JSON.')
        public Integer qty;

        @InvocableVariable(label='Options JSON' description='PDF print options. e.g. {"copies":2,"duplex":"long-edge","paper":"A4"}')
        public String optionsJson;

        @InvocableVariable(label='Correlation ID' description='Unique job ID for idempotency. Leave blank to auto-generate.')
        public String correlationId;

        @InvocableVariable(label='Expire After (seconds)' description='Discard job if not delivered within this many seconds.')
        public Integer expireAfter;

        @InvocableVariable(label='Auth Config JSON' description='Only needed for external *_uri URLs requiring auth. Leave blank for Salesforce files — the server handles auth automatically.')
        public String authConfig;
    }

    // -------------------------------------------------------------------------
    // Invocable entry point — called by Flow or Apex
    // -------------------------------------------------------------------------

    @InvocableMethod(
        label='Send Print Job'
        description='Send a print job to a printer. Provide a Printer ID and either a Content Document ID (Salesforce File) or Content Type + Content (ZPL/raw/external PDF).'
        category='Printing'
    )
    public static void send(List<PrintRequest> requests) {
        if (requests == null || requests.isEmpty()) return;

        // ── Resolve Content Document IDs in one SOQL query ─────────────────────
        Set<Id> docIds = new Set<Id>();
        for (PrintRequest r : requests) {
            if (r.contentDocumentId != null) docIds.add(r.contentDocumentId);
        }
        Map<Id, ContentVersion> latestVersionByDocId = new Map<Id, ContentVersion>();
        if (!docIds.isEmpty()) {
            for (ContentVersion cv : [
                SELECT Id, ContentDocumentId, Title, FileExtension
                FROM ContentVersion
                WHERE ContentDocumentId IN :docIds AND IsLatest = true
            ]) {
                latestVersionByDocId.put(cv.ContentDocumentId, cv);
            }
        }

        // ── Resolve Printer records in one SOQL query ──────────────────────────
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

        String orgUrl = System.URL.getOrgDomainURL().toExternalForm();
        List<SF_Printer_Event__e> events = new List<SF_Printer_Event__e>();

        for (PrintRequest req : requests) {
            Printer__c printer = printers.get(req.printerId);

            if (printer == null) {
                throw new PrinterServiceException('Printer not found: ' + req.printerId);
            }
            if (printer.Enabled__c == false) {
                throw new PrinterServiceException(
                    'Printer \'' + printer.Name + '\' is disabled. '
                    + 'Enable it on the Printer record before sending jobs.'
                );
            }

            // ── Resolve content from ContentDocument if provided ────────────────
            String resolvedContentType = req.contentType;
            String resolvedContent     = req.content;

            if (req.contentDocumentId != null) {
                ContentVersion cv = latestVersionByDocId.get(req.contentDocumentId);
                if (cv == null) {
                    throw new PrinterServiceException(
                        'No ContentVersion found for ContentDocument: ' + req.contentDocumentId
                    );
                }
                resolvedContent     = orgUrl + '/services/data/' + API_VERSION + '/sobjects/ContentVersion/' + cv.Id + '/VersionData';
                resolvedContentType = 'pdf_uri';
                if (String.isBlank(req.jobTitle)) {
                    req.jobTitle = cv.Title + (String.isNotBlank(cv.FileExtension) ? '.' + cv.FileExtension : '');
                }
            }

            if (String.isBlank(resolvedContent)) {
                throw new PrinterServiceException(
                    'No content provided. Supply Content Document ID or Content Type + Content.'
                );
            }
            if (String.isBlank(resolvedContentType)) {
                throw new PrinterServiceException('Content Type is required when not using Content Document ID.');
            }

            SF_Printer_Event__e evt = new SF_Printer_Event__e();
            evt.Type__c           = 'print_job';
            evt.Printer_Host__c   = printer.Host__c;
            evt.Printer_Port__c   = printer.Port__c != null ? printer.Port__c : 9100;
            evt.Printer_Type__c   = printer.Type__c;
            evt.Content_Type__c   = resolvedContentType;
            evt.Content__c        = resolvedContent;
            evt.Correlation_Id__c = String.isNotBlank(req.correlationId) ? req.correlationId : generateUUID();
            evt.Job_Title__c      = req.jobTitle;
            evt.Source__c         = req.source;
            evt.Qty__c            = req.qty != null ? req.qty : 1;
            evt.Options__c        = req.optionsJson;
            evt.Expire_After__c   = req.expireAfter;
            evt.Auth_Config__c    = req.authConfig;
            evt.ZPL_Config__c     = buildZplConfig(printer);

            events.add(evt);
        }

        if (!events.isEmpty()) {
            List<Database.SaveResult> results = EventBus.publish(events);
            for (Integer i = 0; i < results.size(); i++) {
                if (!results[i].isSuccess()) {
                    for (Database.Error e : results[i].getErrors()) {
                        System.debug(LoggingLevel.ERROR, 'PrinterService: ' + e.getMessage());
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
