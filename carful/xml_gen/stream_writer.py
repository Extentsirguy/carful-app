"""
CARFul - Streaming XML Writer

Provides a high-performance streaming XML writer using lxml.etree.xmlfile.
Maintains O(1) memory footprint regardless of document size by writing
elements directly to the output stream and clearing them from memory.

Features:
    - UTF-8 encoding with XML declaration
    - Streaming element writes (no full document buffering)
    - Automatic memory cleanup after element writes
    - Context manager support for nested elements
    - Progress callback support for large documents

Usage:
    from xml_gen.stream_writer import CARFStreamWriter

    with CARFStreamWriter('output.xml') as writer:
        with writer.element('CARF', version='1.5'):
            with writer.element('MessageHeader'):
                writer.write_text_element('TransmittingCountry', 'US')
                writer.write_text_element('ReceivingCountry', 'GB')
"""

import io
import gc
from typing import (
    Any,
    BinaryIO,
    Callable,
    Dict,
    Generator,
    Optional,
    Union,
)
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from .namespaces import (
    XMLNamespaceManager,
    CARF_NS,
    get_default_namespace_manager,
)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class StreamWriterConfig:
    """Configuration for CARFStreamWriter."""

    # XML declaration settings
    encoding: str = 'UTF-8'
    standalone: bool = True
    include_xml_declaration: bool = True

    # Memory management
    gc_interval: int = 1000  # Force GC every N elements
    clear_after_write: bool = True  # Clear element after xf.write()

    # Formatting (for debugging only - impacts performance)
    pretty_print: bool = False  # Only for small documents
    indent_spaces: int = 2

    # Progress reporting
    report_interval: int = 10000  # Report progress every N elements


@dataclass
class WriteStats:
    """Statistics for streaming write operations."""
    elements_written: int = 0
    bytes_written: int = 0
    gc_collections: int = 0

    def reset(self) -> None:
        """Reset all statistics."""
        self.elements_written = 0
        self.bytes_written = 0
        self.gc_collections = 0


# =============================================================================
# Streaming XML Writer
# =============================================================================

class CARFStreamWriter:
    """
    Streaming XML writer for CARF documents using lxml.etree.xmlfile.

    Writes XML elements directly to an output stream without buffering
    the entire document in memory. This enables generation of gigabyte-scale
    XML files with constant memory usage.

    Attributes:
        config: Writer configuration
        stats: Write statistics
        nsm: Namespace manager

    Example:
        # Write to file
        with CARFStreamWriter('report.xml') as writer:
            with writer.root_element():
                writer.write_element(header_element)

        # Write to BytesIO
        buffer = io.BytesIO()
        with CARFStreamWriter(buffer) as writer:
            ...
    """

    def __init__(
        self,
        output: Union[str, Path, BinaryIO],
        config: Optional[StreamWriterConfig] = None,
        namespace_manager: Optional[XMLNamespaceManager] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
    ):
        """
        Initialize streaming writer.

        Args:
            output: Output path or file-like object
            config: Writer configuration
            namespace_manager: Namespace manager for element creation
            progress_callback: Called with element count during writes
        """
        self.config = config or StreamWriterConfig()
        self.nsm = namespace_manager or get_default_namespace_manager()
        self.stats = WriteStats()
        self._progress_callback = progress_callback

        # Handle output destination
        if isinstance(output, (str, Path)):
            self._output_path = Path(output)
            self._output_file: Optional[BinaryIO] = None
            self._owns_file = True
        else:
            self._output_path = None
            self._output_file = output
            self._owns_file = False

        # XML file context
        self._xf: Optional[etree.xmlfile] = None
        self._xf_context: Optional[Any] = None
        self._element_stack: list = []

    def __enter__(self) -> 'CARFStreamWriter':
        """Enter context manager - open file and xmlfile context."""
        if self._output_path:
            self._output_file = open(self._output_path, 'wb')

        # Create xmlfile context
        self._xf = etree.xmlfile(
            self._output_file,
            encoding=self.config.encoding,
        )
        self._xf_context = self._xf.__enter__()

        # Write XML declaration if configured
        if self.config.include_xml_declaration:
            self._write_xml_declaration()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager - close file and cleanup."""
        # Close xmlfile context
        if self._xf is not None:
            self._xf.__exit__(exc_type, exc_val, exc_tb)
            self._xf = None
            self._xf_context = None

        # Close file if we own it
        if self._owns_file and self._output_file is not None:
            self._output_file.close()
            self._output_file = None

        # Final garbage collection
        gc.collect()

    def _write_xml_declaration(self) -> None:
        """Write XML declaration to output."""
        standalone = 'yes' if self.config.standalone else 'no'
        declaration = f'<?xml version="1.0" encoding="{self.config.encoding}" standalone="{standalone}"?>\n'
        self._output_file.write(declaration.encode(self.config.encoding))

    def _check_memory(self) -> None:
        """Check if garbage collection should be triggered."""
        if (
            self.config.clear_after_write
            and self.stats.elements_written % self.config.gc_interval == 0
        ):
            gc.collect()
            self.stats.gc_collections += 1

    def _report_progress(self) -> None:
        """Report progress if callback is configured."""
        if (
            self._progress_callback
            and self.stats.elements_written % self.config.report_interval == 0
        ):
            self._progress_callback(self.stats.elements_written)

    @contextmanager
    def element(
        self,
        tag: str,
        namespace: Optional[str] = None,
        attrib: Optional[Dict[str, str]] = None,
        nsmap: Optional[Dict[Optional[str], str]] = None,
    ) -> Generator[None, None, None]:
        """
        Context manager for writing an XML element with children.

        Opens an element tag, yields for child content, then closes the tag.
        Use for container elements that will have children.

        Args:
            tag: Element tag name
            namespace: Element namespace (uses default if None)
            attrib: Element attributes
            nsmap: Namespace map (for root element)

        Yields:
            None (write children in the context)

        Example:
            with writer.element('CARFBody'):
                with writer.element('ReportingGroup'):
                    writer.write_text_element('Name', 'Acme Corp')
        """
        qname = self.nsm.qname(tag, namespace)

        with self._xf_context.element(qname, attrib=attrib, nsmap=nsmap):
            self.stats.elements_written += 1
            self._element_stack.append(tag)
            yield
            self._element_stack.pop()

        self._check_memory()
        self._report_progress()

    @property
    def ns_manager(self) -> XMLNamespaceManager:
        """Return the namespace manager for external use."""
        return self.nsm

    @contextmanager
    def carf_document(
        self,
        version: str = '1.5',
        include_schema_location: bool = True,
    ) -> Generator[None, None, None]:
        """
        Context manager for the root CARF document element.

        Alias for root_element() with semantic naming for CARF documents.

        Args:
            version: Schema version
            include_schema_location: Whether to add xsi:schemaLocation

        Yields:
            None (write children in the context)

        Example:
            with writer.carf_document():
                writer.write_element(header_element)
                with writer.element('CARFBody'):
                    ...
        """
        with self.root_element('CARF', version, include_schema_location):
            yield

    @contextmanager
    def root_element(
        self,
        tag: str = 'CARF',
        version: str = '1.5',
        include_schema_location: bool = True,
    ) -> Generator[None, None, None]:
        """
        Context manager for the root CARF element.

        Writes the root element with all namespace declarations
        and optional schema location attribute.

        Args:
            tag: Root element name (default: 'CARF')
            version: Schema version
            include_schema_location: Whether to add xsi:schemaLocation

        Yields:
            None (write children in the context)

        Example:
            with writer.root_element():
                # Write MessageHeader and CARFBody elements
        """
        attrib = {'version': version}

        if include_schema_location:
            xsi_schema_loc = self.nsm.qname('schemaLocation', 'http://www.w3.org/2001/XMLSchema-instance')
            attrib[xsi_schema_loc] = f'{CARF_NS} CARFXML_v1.xsd'

        with self.element(tag, nsmap=self.nsm.nsmap, attrib=attrib):
            yield

    def write_element(
        self,
        element: etree._Element,
        clear: bool = True,
    ) -> None:
        """
        Write a complete lxml Element to the stream.

        The element and its subtree are written and optionally cleared
        from memory to maintain O(1) memory usage.

        Args:
            element: lxml Element to write
            clear: Whether to clear element from memory after write

        Example:
            header = nsm.create_element('MessageHeader')
            # ... build header ...
            writer.write_element(header)
        """
        self._xf_context.write(element)
        self.stats.elements_written += 1

        if clear and self.config.clear_after_write:
            # Clear element and its children from memory
            element.clear()

        self._check_memory()
        self._report_progress()

    def write_text_element(
        self,
        tag: str,
        text: str,
        namespace: Optional[str] = None,
        attrib: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Write a simple text element directly to the stream.

        Convenience method for writing elements with only text content.

        Args:
            tag: Element tag name
            text: Text content
            namespace: Element namespace
            attrib: Element attributes

        Example:
            writer.write_text_element('TransmittingCountry', 'US')
            writer.write_text_element('Amount', '1.5', attrib={'currCode': 'USD'})
        """
        element = self.nsm.create_element(tag, namespace, text=text, attrib=attrib)
        self.write_element(element)

    def write_raw(self, content: str) -> None:
        """
        Write raw string content to the output stream.

        Use sparingly - primarily for whitespace/formatting.
        Content is NOT XML-escaped.

        Args:
            content: Raw string to write
        """
        self._output_file.write(content.encode(self.config.encoding))

    def flush(self) -> None:
        """Flush the output stream."""
        if self._output_file:
            self._output_file.flush()


# =============================================================================
# Convenience Functions
# =============================================================================

def write_carf_document(
    output: Union[str, Path, BinaryIO],
    header_element: etree._Element,
    body_elements: Generator[etree._Element, None, None],
    config: Optional[StreamWriterConfig] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> WriteStats:
    """
    Write a complete CARF document with streaming body elements.

    Args:
        output: Output file path or file-like object
        header_element: MessageHeader element
        body_elements: Generator yielding CARFBody elements
        config: Writer configuration
        progress_callback: Progress callback function

    Returns:
        WriteStats with document statistics

    Example:
        def generate_bodies():
            for batch in user_batches:
                yield build_body_element(batch)

        stats = write_carf_document(
            'report.xml',
            header,
            generate_bodies(),
        )
        print(f"Wrote {stats.elements_written} elements")
    """
    with CARFStreamWriter(output, config, progress_callback=progress_callback) as writer:
        with writer.root_element():
            # Write header
            writer.write_element(header_element)

            # Stream body elements
            for body in body_elements:
                writer.write_element(body)

        return writer.stats


def create_memory_writer(
    config: Optional[StreamWriterConfig] = None,
) -> tuple[CARFStreamWriter, io.BytesIO]:
    """
    Create a streaming writer that writes to memory.

    Useful for testing or when output needs further processing.

    Args:
        config: Writer configuration

    Returns:
        Tuple of (writer, BytesIO buffer)

    Example:
        writer, buffer = create_memory_writer()
        with writer:
            with writer.root_element():
                ...
        xml_content = buffer.getvalue()
    """
    buffer = io.BytesIO()
    writer = CARFStreamWriter(buffer, config)
    return writer, buffer


def clear_element_tree(element: etree._Element) -> None:
    """
    Explicitly clear an lxml Element and all its children from memory.

    This function recursively clears all child elements before clearing
    the parent, ensuring complete memory release. Use after writing
    elements to the stream to maintain O(1) memory usage.

    Args:
        element: lxml Element to clear

    Example:
        header = build_header_element()
        writer.write_element(header, clear=False)  # Don't auto-clear
        clear_element_tree(header)  # Explicit clear with logging
    """
    # Clear children first (depth-first)
    for child in element:
        clear_element_tree(child)

    # Clear this element
    element.clear()


def force_memory_cleanup() -> int:
    """
    Force immediate garbage collection and return bytes freed.

    Use periodically during large document generation to ensure
    memory is released promptly.

    Returns:
        Number of unreachable objects found and collected

    Example:
        # After processing a batch of users
        freed = force_memory_cleanup()
        logger.debug(f"GC freed {freed} objects")
    """
    # Run full collection on all generations
    return gc.collect()
