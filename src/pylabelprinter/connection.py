"""
Verbindungs-Abstraktion für verschiedene Schnittstellen.
"""

import os
import time
from abc import ABC, abstractmethod
from typing import Optional


class Connection(ABC):
    """Abstrakte Basis-Klasse für Drucker-Verbindungen."""
    
    @abstractmethod
    def open(self) -> None:
        """Öffne die Verbindung."""
        ...
    
    @abstractmethod
    def close(self) -> None:
        """Schließe die Verbindung."""
        ...
    
    @abstractmethod
    def write(self, data: bytes) -> int:
        """Sende Daten an den Drucker.
        
        Args:
            data: Zu sendende Bytes
            
        Returns:
            Anzahl gesendeter Bytes
        """
        ...
    
    @abstractmethod
    def read(self, size: int, timeout: float = 1.0) -> bytes:
        """Lese Daten vom Drucker.
        
        Args:
            size: Maximale Anzahl zu lesender Bytes
            timeout: Timeout in Sekunden
            
        Returns:
            Gelesene Bytes
        """
        ...
    
    def flush_input(self) -> None:
        """Leere den Eingabe-Buffer."""
        while True:
            data = self.read(1024, timeout=0.01)
            if not data:
                break
    
    def query(self, command: bytes, response_size: int = 64, timeout: float = 0.5) -> bytes:
        """Sende Befehl und lese Antwort.
        
        Args:
            command: Zu sendender Befehl
            response_size: Erwartete Antwortgröße
            timeout: Timeout in Sekunden
            
        Returns:
            Antwort-Bytes
        """
        self.flush_input()  # Alte Daten verwerfen
        self.write(command)
        time.sleep(0.1)  # Warten auf Antwort
        return self.read(response_size, timeout)
    
    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Prüfe ob Verbindung offen."""
        ...


class UsbConnection(Connection):
    """USB-Verbindung über /dev/usb/lpX.
    
    USB-Drucker haben keinen automatischen Flow Control wie Bluetooth RFCOMM.
    Große Datenblöcke werden daher automatisch in Chunks aufgeteilt, um
    Pufferüberläufe im Drucker zu vermeiden.
    """
    
    # Konservative Standardwerte für kleine USB-Druckerpuffer.
    # Schnellere Geräte können diese Werte instanzspezifisch überschreiben.
    WRITE_CHUNK_SIZE = 256
    WRITE_CHUNK_DELAY = 0.01
    WRITE_RETRY_DELAY = 0.01
    
    def __init__(
        self,
        device_path: str,
        write_chunk_size: Optional[int] = None,
        write_chunk_delay: Optional[float] = None,
        write_retry_delay: Optional[float] = None,
    ):
        """Initialisiere USB-Verbindung.
        
        Args:
            device_path: Pfad zum USB-Gerät (z.B. '/dev/usb/lp0')
            write_chunk_size: Optionale Chunk-Größe pro Write
            write_chunk_delay: Optionale Pause zwischen Chunks
            write_retry_delay: Optionale Pause bei vollem USB-Puffer
        """
        self._device_path = device_path
        self._fd: Optional[int] = None
        self._write_chunk_size = write_chunk_size or self.WRITE_CHUNK_SIZE
        self._write_chunk_delay = (
            self.WRITE_CHUNK_DELAY if write_chunk_delay is None else write_chunk_delay
        )
        self._write_retry_delay = (
            self.WRITE_RETRY_DELAY if write_retry_delay is None else write_retry_delay
        )
    
    @property
    def device_path(self) -> str:
        """Geräte-Pfad."""
        return self._device_path
    
    @property
    def is_open(self) -> bool:
        """Prüfe ob Verbindung offen."""
        return self._fd is not None
    
    def open(self) -> None:
        """Öffne USB-Gerät."""
        from .exceptions import PermissionDeniedError
        
        if self._fd is not None:
            return  # Bereits offen
        
        try:
            self._fd = os.open(
                self._device_path,
                os.O_RDWR | os.O_NONBLOCK
            )
        except PermissionError:
            raise PermissionDeniedError(
                f"Keine Berechtigung für {self._device_path}. "
                f"Versuche: sudo usermod -a -G lp $USER (und neu einloggen) "
                f"oder mit sudo ausführen."
            )
    
    def close(self) -> None:
        """Schließe USB-Gerät."""
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
    
    def write(self, data: bytes) -> int:
        """Sende Daten an USB-Gerät.
        
        Große Datenblöcke werden automatisch in Chunks aufgeteilt,
        um den Empfangspuffer des Druckers nicht zu überlaufen.
        USB hat (im Gegensatz zu Bluetooth RFCOMM) kein automatisches
        Flow Control.
        
        Achtung: Bei O_NONBLOCK kann os.write() BlockingIOError (EAGAIN)
        werfen wenn der USB-Puffer voll ist. In dem Fall wird mit Delay
        retried.
        """
        if self._fd is None:
            raise RuntimeError("Connection not open")
        
        total_written = 0
        offset = 0
        
        while offset < len(data):
            chunk = data[offset:offset + self._write_chunk_size]
            try:
                written = os.write(self._fd, chunk)
            except BlockingIOError:
                # USB-Puffer voll – kurz warten und wiederholen
                time.sleep(self._write_retry_delay)
                continue
            total_written += written
            offset += written  # written, nicht len(chunk)!
            
            if offset < len(data) and self._write_chunk_delay > 0:
                time.sleep(self._write_chunk_delay)
        
        return total_written
    
    def read(self, size: int, timeout: float = 1.0) -> bytes:
        """Lese Daten von USB-Gerät mit Timeout."""
        if self._fd is None:
            raise RuntimeError("Connection not open")
        
        end_time = time.time() + timeout
        
        while time.time() < end_time:
            try:
                data = os.read(self._fd, size)
                if data:
                    return data
            except BlockingIOError:
                time.sleep(0.01)
        
        return b""
    
    def __repr__(self) -> str:
        status = "open" if self.is_open else "closed"
        return f"UsbConnection({self._device_path!r}, {status})"
