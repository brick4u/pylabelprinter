"""
Exception-Hierarchie für pylabelprinter.
"""


class LabelprinterError(Exception):
    """Basis-Exception für alle pylabelprinter-Fehler."""
    pass


class PrinterNotFoundError(LabelprinterError):
    """Kein passender Drucker gefunden."""
    pass


class PrinterConnectionError(LabelprinterError):
    """Verbindungsfehler zum Drucker."""
    pass


class UnsupportedFeatureError(LabelprinterError):
    """Feature wird vom Drucker nicht unterstützt."""
    pass


class PrintError(LabelprinterError):
    """Fehler beim Drucken."""
    pass


class NoPaperError(PrintError):
    """Kein Papier eingelegt."""
    pass


class CoverOpenError(PrintError):
    """Druckerabdeckung offen."""
    pass


class PermissionDeniedError(PrinterConnectionError):
    """Keine Berechtigung für Drucker-Zugriff."""
    pass


class PrinterStandbyError(PrinterConnectionError):
    """Drucker ist im Standby und antwortet nicht."""
    pass
