# PrinterService — Manual Test Scripts

Run these in **Developer Console → Execute Anonymous** (or Setup → Apex → Execute Anonymous).

---

## 1. PDF via Salesforce File (ContentDocument ID — recommended)

The easiest path for admins.  
Uploads a minimal PDF as a Salesforce File, then sends it using `contentDocumentId`.  
The server fetches the file itself — no URL or auth config needed.

```apex
// ── 1. Create a test file ────────────────────────────────────────────────────
ContentVersion cv = new ContentVersion();
cv.Title          = 'Test PDF Print';
cv.PathOnClient   = 'test-print.pdf';
cv.VersionData    = Blob.valueOf(
    '%PDF-1.4\n'
    + '1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj '
    + '2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj '
    + '3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n'
    + 'xref\n0 4\n'
    + '0000000000 65535 f\n'
    + '0000000009 00000 n\n'
    + '0000000058 00000 n\n'
    + '0000000115 00000 n\n'
    + 'trailer<</Size 4/Root 1 0 R>>\n'
    + 'startxref\n190\n%%EOF'
);
cv.IsMajorVersion = true;
insert cv;

ContentVersion saved = [SELECT Id, ContentDocumentId FROM ContentVersion WHERE Id = :cv.Id];

// ── 2. Look up a ZPL printer (change Type__c filter if using a PDF printer) ──
Printer__c printer = [
    SELECT Id, Name
    FROM   Printer__c
    WHERE  Type__c = 'zpl'
    AND    Enabled__c = true
    LIMIT  1
];
System.debug('Using printer: ' + printer.Name + ' (' + printer.Id + ')');

// ── 3. Fire the job ──────────────────────────────────────────────────────────
PrinterService.PrintRequest req = new PrinterService.PrintRequest();
req.printerId         = printer.Id;
req.contentDocumentId = saved.ContentDocumentId;   // service handles everything else
req.jobTitle          = 'ContentDocument PDF Test';
req.source            = 'Execute Anonymous';

PrinterService.send(new List<PrinterService.PrintRequest>{ req });
System.debug('Job sent.');
```

---

## 2. PDF via Download URL (`pdf_uri`)

Useful when the file already exists in Salesforce and you want to build the URL manually,
or when sending a PDF hosted outside Salesforce (swap `downloadUrl` for any HTTPS URL and
set `req.authConfig` if the endpoint requires credentials).

```apex
// ── 1. Create a test file ────────────────────────────────────────────────────
ContentVersion cv = new ContentVersion();
cv.Title          = 'Test PDF URI';
cv.PathOnClient   = 'test-uri.pdf';
cv.VersionData    = Blob.valueOf(
    '%PDF-1.4\n'
    + '1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj '
    + '2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj '
    + '3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n'
    + 'xref\n0 4\n'
    + '0000000000 65535 f\n'
    + '0000000009 00000 n\n'
    + '0000000058 00000 n\n'
    + '0000000115 00000 n\n'
    + 'trailer<</Size 4/Root 1 0 R>>\n'
    + 'startxref\n190\n%%EOF'
);
cv.IsMajorVersion = true;
insert cv;

ContentVersion saved = [SELECT Id FROM ContentVersion WHERE Id = :cv.Id];

// Match this to the API_VERSION constant in PrinterService.cls
String apiVersion  = 'v65.0';
String downloadUrl = System.URL.getOrgDomainURL().toExternalForm()
    + '/services/data/' + apiVersion + '/sobjects/ContentVersion/'
    + saved.Id + '/VersionData';

// ── 2. Look up a ZPL printer ─────────────────────────────────────────────────
Printer__c printer = [
    SELECT Id, Name
    FROM   Printer__c
    WHERE  Type__c = 'zpl'
    AND    Enabled__c = true
    LIMIT  1
];
System.debug('Using printer: ' + printer.Name + ' (' + printer.Id + ')');

// ── 3. Fire the job ──────────────────────────────────────────────────────────
PrinterService.PrintRequest req = new PrinterService.PrintRequest();
req.printerId   = printer.Id;
req.contentType = 'pdf_uri';
req.content     = downloadUrl;
// no authConfig needed — server injects Bearer automatically for Salesforce URLs
req.jobTitle    = 'PDF URI Test';
req.source      = 'Execute Anonymous';

PrinterService.send(new List<PrinterService.PrintRequest>{ req });
System.debug('Job sent. URL: ' + downloadUrl);
```

---

## 3. ZPL via base64 (`raw_base64`)

Sends a raw ZPL label to a `zpl` printer.  
The server auto-queries the Zebra for DPI/width/darkness and prepends the config block.

```apex
// ── Build a simple ZPL label ─────────────────────────────────────────────────
String zpl = '^XA'
    + '^FO50,50^ADN,36,20^FDHello from Salesforce^FS'
    + '^FO50,120^BY3^BCN,100,Y,N,N^FD123456789^FS'
    + '^XZ';

String zplBase64 = EncodingUtil.base64Encode(Blob.valueOf(zpl));

// ── Look up a ZPL printer ────────────────────────────────────────────────────
Printer__c printer = [
    SELECT Id, Name
    FROM   Printer__c
    WHERE  Type__c = 'zpl'
    AND    Enabled__c = true
    LIMIT  1
];
System.debug('Using printer: ' + printer.Name + ' (' + printer.Id + ')');

// ── Fire the job ─────────────────────────────────────────────────────────────
PrinterService.PrintRequest req = new PrinterService.PrintRequest();
req.printerId   = printer.Id;
req.contentType = 'raw_base64';
req.content     = zplBase64;
req.jobTitle    = 'ZPL Base64 Test';
req.source      = 'Execute Anonymous';
req.qty         = 1;

PrinterService.send(new List<PrinterService.PrintRequest>{ req });
System.debug('ZPL job sent.');
```

---

## 4. Raw bytes via base64 (`raw_base64`) — RAW printer

Same as ZPL but targets a `raw` printer (e.g. receipt / ESC/POS).

```apex
// ── ESC/POS snippet: init + text + feed + cut ────────────────────────────────
String escpos = '\u001B\u0040'          // ESC @ — initialize
    + 'Hello from Salesforce\n\n\n'
    + '\u001Bd\u0003'                   // feed 3 lines
    + '\u001Bm';                        // cut

String rawBase64 = EncodingUtil.base64Encode(Blob.valueOf(escpos));

// ── Look up a RAW printer ────────────────────────────────────────────────────
Printer__c printer = [
    SELECT Id, Name
    FROM   Printer__c
    WHERE  Type__c = 'raw'
    AND    Enabled__c = true
    LIMIT  1
];
System.debug('Using printer: ' + printer.Name + ' (' + printer.Id + ')');

// ── Fire the job ─────────────────────────────────────────────────────────────
PrinterService.PrintRequest req = new PrinterService.PrintRequest();
req.printerId   = printer.Id;
req.contentType = 'raw_base64';
req.content     = rawBase64;
req.jobTitle    = 'ESC/POS Receipt Test';
req.source      = 'Execute Anonymous';

PrinterService.send(new List<PrinterService.PrintRequest>{ req });
System.debug('RAW job sent.');
```

---

## Tips

| Scenario | `contentType` | `content` |
|---|---|---|
| Salesforce File | *(leave blank)* | *(leave blank)* — use `contentDocumentId` |
| PDF hosted externally | `pdf_uri` | HTTPS URL |
| PDF as base64 | `pdf_base64` | `EncodingUtil.base64Encode(pdfBlob)` |
| ZPL string | `raw_base64` | `EncodingUtil.base64Encode(Blob.valueOf(zpl))` |
| ESC/POS / raw bytes | `raw_base64` | `EncodingUtil.base64Encode(rawBlob)` |
| Raw file URL | `raw_uri` | HTTPS URL |

- **Bearer auth** for Salesforce URLs is injected automatically by the server — never set `authConfig` for Salesforce files.
- The server caches Zebra printer config (DPI, width, darkness) after the first job. Call `clear_printer_cache()` on the server if you change printer settings.
- Use a different `correlationId` per test run to avoid idempotency skips.
