"""
VAT Lookup Service — stub for NIS2 standalone app.
Returns a minimal result so supply chain routes don't crash
if VIES verification is not configured.
Extend this with real VIES API calls if needed.
"""


class VatLookupResult:
    def __init__(self, valid=None, company_name=None, address=None, error=None):
        self.valid = valid
        self.company_name = company_name
        self.address = address
        self.error = error


class VatLookupService:
    def lookup(self, vat_number: str, country_code: str = '') -> VatLookupResult:
        """
        Stub implementation — returns unknown result.
        Replace with real VIES/EU VAT API call as needed.
        """
        return VatLookupResult(valid=None, error='VAT-Prüfung nicht konfiguriert')
