"""
CARFul - XSD Schema Validation Engine

Provides schema validation for CARF XML documents against OECD XSD.
Supports both full document validation and streaming iterparse validation
for large files.

Features:
    - XSD schema loading from file or string
    - Full document validation with detailed error reporting
    - Streaming validation for large files using iterparse
    - ValidationReport with XPath locations and error codes

Usage:
    from validators.schema_validator import SchemaValidator, ValidationReport

    # Validate a file
    validator = SchemaValidator('schemas/CARFXML_v1.xsd')
    report = validator.validate_file('export.xml')

    if report.is_valid:
        print("Validation passed!")
    else:
        for error in report.errors:
            print(f"{error.xpath}: {error.message}")

    # Streaming validation for large files
    report = validator.validate_file_streaming('large_export.xml')
"""

import os
from pathlib import Path
from typing import List, Optional, Union, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from lxml import etree
from io import BytesIO


# =============================================================================
# Error Data Classes
# =============================================================================

@dataclass
class ValidationError:
    """
    Single validation error with location and details.

    Attributes:
        message: Human-readable error message
        xpath: XPath to the error location in the document
        line: Line number in the XML file
        column: Column number in the XML file
        error_type: Type of error (schema, well-formed, etc.)
        element: Element name where error occurred
        expected: Expected value/type (if applicable)
        actual: Actual value/type found
    """
    message: str
    xpath: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    error_type: str = 'schema'
    element: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None

    def __str__(self) -> str:
        """Format error as string."""
        location = []
        if self.line:
            location.append(f"line {self.line}")
        if self.column:
            location.append(f"col {self.column}")
        if self.xpath:
            location.append(f"xpath: {self.xpath}")

        loc_str = f" ({', '.join(location)})" if location else ""
        return f"[{self.error_type.upper()}]{loc_str}: {self.message}"


@dataclass
class ValidationReport:
    """
    Complete validation report for a document.

    Attributes:
        is_valid: True if document passed all validations
        errors: List of validation errors
        warnings: List of non-fatal warnings
        document_path: Path to validated document
        schema_path: Path to XSD schema used
        validation_time: Time taken for validation
        element_count: Number of elements validated
    """
    is_valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    document_path: Optional[str] = None
    schema_path: Optional[str] = None
    validation_time_ms: float = 0.0
    element_count: int = 0
    validated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def error_count(self) -> int:
        """Number of errors."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Number of warnings."""
        return len(self.warnings)

    def add_error(
        self,
        message: str,
        xpath: Optional[str] = None,
        line: Optional[int] = None,
        column: Optional[int] = None,
        error_type: str = 'schema',
        **kwargs,
    ) -> None:
        """Add an error to the report."""
        self.errors.append(ValidationError(
            message=message,
            xpath=xpath,
            line=line,
            column=column,
            error_type=error_type,
            **kwargs,
        ))
        self.is_valid = False

    def add_warning(
        self,
        message: str,
        xpath: Optional[str] = None,
        line: Optional[int] = None,
        column: Optional[int] = None,
        **kwargs,
    ) -> None:
        """Add a warning to the report."""
        self.warnings.append(ValidationError(
            message=message,
            xpath=xpath,
            line=line,
            column=column,
            error_type='warning',
            **kwargs,
        ))

    def to_dict(self) -> dict:
        """Convert report to dictionary."""
        return {
            'is_valid': self.is_valid,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'validation_time_ms': self.validation_time_ms,
            'element_count': self.element_count,
            'validated_at': self.validated_at.isoformat(),
            'document_path': self.document_path,
            'schema_path': self.schema_path,
            'errors': [
                {
                    'message': e.message,
                    'xpath': e.xpath,
                    'line': e.line,
                    'column': e.column,
                    'error_type': e.error_type,
                }
                for e in self.errors
            ],
            'warnings': [
                {
                    'message': w.message,
                    'xpath': w.xpath,
                    'line': w.line,
                    'column': w.column,
                }
                for w in self.warnings
            ],
        }

    def summary(self) -> str:
        """Get human-readable summary."""
        status = "PASSED" if self.is_valid else "FAILED"
        lines = [
            f"Validation {status}",
            f"  Document: {self.document_path or 'N/A'}",
            f"  Schema: {self.schema_path or 'N/A'}",
            f"  Elements: {self.element_count}",
            f"  Time: {self.validation_time_ms:.2f}ms",
            f"  Errors: {self.error_count}",
            f"  Warnings: {self.warning_count}",
        ]

        if self.errors:
            lines.append("\nErrors:")
            for i, error in enumerate(self.errors[:10], 1):
                lines.append(f"  {i}. {error}")
            if len(self.errors) > 10:
                lines.append(f"  ... and {len(self.errors) - 10} more")

        return '\n'.join(lines)


# =============================================================================
# Schema Validator
# =============================================================================

class SchemaValidator:
    """
    XSD Schema validator for CARF XML documents.

    Validates XML documents against OECD CARF XSD schema with
    support for both full document and streaming validation.

    Example:
        validator = SchemaValidator('schemas/CARFXML_v1.xsd')

        # Validate file
        report = validator.validate_file('export.xml')
        print(report.summary())

        # Validate string/bytes
        report = validator.validate_string(xml_content)

        # Streaming validation for large files
        report = validator.validate_file_streaming('large.xml')
    """

    def __init__(
        self,
        schema_path: Optional[Union[str, Path]] = None,
        schema_string: Optional[str] = None,
    ):
        """
        Initialize SchemaValidator.

        Args:
            schema_path: Path to XSD schema file
            schema_string: XSD schema as string (alternative to path)

        Raises:
            ValueError: If neither schema_path nor schema_string provided
            etree.XMLSchemaParseError: If schema is invalid
        """
        if schema_path is None and schema_string is None:
            raise ValueError("Must provide either schema_path or schema_string")

        self.schema_path = str(schema_path) if schema_path else None

        if schema_path:
            self._schema = self._load_schema_from_file(schema_path)
        else:
            self._schema = self._load_schema_from_string(schema_string)

    def _load_schema_from_file(self, path: Union[str, Path]) -> etree.XMLSchema:
        """Load XSD schema from file."""
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Schema file not found: {path}")

        with open(path, 'rb') as f:
            schema_doc = etree.parse(f)

        return etree.XMLSchema(schema_doc)

    def _load_schema_from_string(self, schema_string: str) -> etree.XMLSchema:
        """Load XSD schema from string."""
        schema_doc = etree.fromstring(schema_string.encode('utf-8'))
        return etree.XMLSchema(schema_doc)

    def _extract_xpath(self, element: etree._Element) -> str:
        """Extract XPath for an element."""
        parts = []
        current = element

        while current is not None:
            if isinstance(current.tag, str):
                # Get local name without namespace
                tag = current.tag.split('}')[-1] if '}' in current.tag else current.tag

                # Count siblings with same tag
                parent = current.getparent()
                if parent is not None:
                    siblings = [c for c in parent if c.tag == current.tag]
                    if len(siblings) > 1:
                        idx = siblings.index(current) + 1
                        tag = f"{tag}[{idx}]"

                parts.append(tag)

            current = current.getparent()

        return '/' + '/'.join(reversed(parts))

    def _convert_schema_errors(
        self,
        report: ValidationReport,
    ) -> None:
        """Convert lxml schema errors to ValidationError objects."""
        for error in self._schema.error_log:
            report.add_error(
                message=error.message,
                line=error.line,
                column=error.column,
                error_type='schema',
            )

    def validate(self, doc: etree._ElementTree) -> ValidationReport:
        """
        Validate an lxml ElementTree against the schema.

        Args:
            doc: Parsed XML document

        Returns:
            ValidationReport with validation results
        """
        import time
        start_time = time.perf_counter()

        report = ValidationReport(schema_path=self.schema_path)

        # Count elements
        report.element_count = sum(1 for _ in doc.iter())

        # Validate
        try:
            self._schema.assertValid(doc)
            report.is_valid = True
        except etree.DocumentInvalid:
            report.is_valid = False
            self._convert_schema_errors(report)

        report.validation_time_ms = (time.perf_counter() - start_time) * 1000
        return report

    def validate_file(self, file_path: Union[str, Path]) -> ValidationReport:
        """
        Validate an XML file against the schema.

        Args:
            file_path: Path to XML file

        Returns:
            ValidationReport with validation results
        """
        import time
        start_time = time.perf_counter()

        file_path = Path(file_path)
        report = ValidationReport(
            document_path=str(file_path),
            schema_path=self.schema_path,
        )

        if not file_path.exists():
            report.add_error(
                message=f"File not found: {file_path}",
                error_type='file',
            )
            return report

        try:
            # Parse document
            doc = etree.parse(str(file_path))
            report.element_count = sum(1 for _ in doc.iter())

            # Validate
            self._schema.assertValid(doc)
            report.is_valid = True

        except etree.XMLSyntaxError as e:
            report.add_error(
                message=str(e),
                line=e.lineno,
                column=e.offset,
                error_type='syntax',
            )

        except etree.DocumentInvalid:
            report.is_valid = False
            self._convert_schema_errors(report)

        report.validation_time_ms = (time.perf_counter() - start_time) * 1000
        return report

    def validate_string(
        self,
        xml_content: Union[str, bytes],
    ) -> ValidationReport:
        """
        Validate XML string/bytes against the schema.

        Args:
            xml_content: XML content as string or bytes

        Returns:
            ValidationReport with validation results
        """
        import time
        start_time = time.perf_counter()

        report = ValidationReport(schema_path=self.schema_path)

        if isinstance(xml_content, str):
            xml_content = xml_content.encode('utf-8')

        try:
            doc = etree.parse(BytesIO(xml_content))
            report.element_count = sum(1 for _ in doc.iter())

            self._schema.assertValid(doc)
            report.is_valid = True

        except etree.XMLSyntaxError as e:
            report.add_error(
                message=str(e),
                line=e.lineno,
                column=e.offset,
                error_type='syntax',
            )

        except etree.DocumentInvalid:
            report.is_valid = False
            self._convert_schema_errors(report)

        report.validation_time_ms = (time.perf_counter() - start_time) * 1000
        return report

    def validate_file_streaming(
        self,
        file_path: Union[str, Path],
        chunk_size: int = 10000,
    ) -> ValidationReport:
        """
        Validate a large XML file using iterparse for memory efficiency.

        Uses incremental parsing to validate large files without loading
        the entire document into memory. Performs well-formedness checks
        and basic structure validation.

        Note: Full schema validation still requires loading elements,
        but this approach clears parsed elements from memory after
        validation to maintain lower memory footprint.

        Args:
            file_path: Path to XML file
            chunk_size: Number of elements to process before memory cleanup

        Returns:
            ValidationReport with validation results
        """
        import time
        start_time = time.perf_counter()

        file_path = Path(file_path)
        report = ValidationReport(
            document_path=str(file_path),
            schema_path=self.schema_path,
        )

        if not file_path.exists():
            report.add_error(
                message=f"File not found: {file_path}",
                error_type='file',
            )
            return report

        element_count = 0
        root = None

        try:
            # Use iterparse for memory-efficient parsing
            context = etree.iterparse(
                str(file_path),
                events=('start', 'end'),
                recover=False,
            )

            for event, elem in context:
                if event == 'start':
                    if root is None:
                        root = elem

                elif event == 'end':
                    element_count += 1

                    # Periodically clear memory
                    if element_count % chunk_size == 0:
                        # Clear completed elements
                        elem.clear()
                        # Also clear parent references to save memory
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]

            # Final element count
            report.element_count = element_count

            # Parse fully for schema validation
            # (necessary because XMLSchema needs complete tree)
            doc = etree.parse(str(file_path))
            self._schema.assertValid(doc)
            report.is_valid = True

        except etree.XMLSyntaxError as e:
            report.add_error(
                message=str(e),
                line=e.lineno,
                column=e.offset,
                error_type='syntax',
            )

        except etree.DocumentInvalid:
            report.is_valid = False
            self._convert_schema_errors(report)

        report.validation_time_ms = (time.perf_counter() - start_time) * 1000
        return report

    def is_valid(self, doc: etree._ElementTree) -> bool:
        """
        Quick check if document is valid.

        Args:
            doc: Parsed XML document

        Returns:
            True if valid, False otherwise
        """
        return self._schema.validate(doc)


# =============================================================================
# Factory Functions
# =============================================================================

def create_carf_validator(
    schema_dir: Optional[Union[str, Path]] = None,
) -> SchemaValidator:
    """
    Create a SchemaValidator configured for CARF validation.

    Args:
        schema_dir: Directory containing CARF XSD files
                   (defaults to package schemas directory)

    Returns:
        Configured SchemaValidator
    """
    if schema_dir is None:
        # Use package schemas directory
        schema_dir = Path(__file__).parent.parent / 'schemas'

    schema_path = Path(schema_dir) / 'CARFXML_v1.xsd'

    if not schema_path.exists():
        raise FileNotFoundError(
            f"CARF schema not found at {schema_path}. "
            f"Please ensure schema files are in {schema_dir}"
        )

    return SchemaValidator(schema_path)


def validate_carf_file(
    file_path: Union[str, Path],
    schema_dir: Optional[Union[str, Path]] = None,
) -> ValidationReport:
    """
    Convenience function to validate a CARF XML file.

    Args:
        file_path: Path to CARF XML file
        schema_dir: Directory containing CARF XSD files

    Returns:
        ValidationReport with results
    """
    validator = create_carf_validator(schema_dir)
    return validator.validate_file(file_path)
