#!/usr/bin/env python3
"""
CARFul/CARFul - JSON-RPC Server

This module implements a JSON-RPC 2.0 server that communicates with the
Electron frontend via stdin/stdout. It exposes the CARFul functionality
as RPC methods.

Protocol:
- Reads JSON-RPC requests from stdin (one per line)
- Writes JSON-RPC responses to stdout (one per line)
- Supports notifications (no id) for progress updates

Usage:
    python -m carful.rpc_server
    python carful/rpc_server.py
"""

import json
import sys
import traceback
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional
import logging

# Configure logging to stderr (not stdout, which is for RPC responses)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger('rpc_server')


# JSON-RPC 2.0 error codes
class RPCErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR = -32000


class RPCError(Exception):
    """RPC error with code and message."""
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal and datetime objects."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


class RPCServer:
    """JSON-RPC 2.0 server for CARFul operations."""

    def __init__(self):
        self.methods = {}
        self._register_methods()
        self._running = True

    def _register_methods(self):
        """Register all available RPC methods."""
        self.methods = {
            # Database operations
            'db.stats': self._db_stats,

            # CSV operations
            'csv.import': self._csv_import,
            'csv.preview': self._csv_preview,

            # TIN validation
            'tin.validate': self._tin_validate,
            'tin.validate_single': self._tin_validate_single,

            # XML export
            'xml.export': self._xml_export,

            # Health check
            'health.check': self._health_check,

            # PDF report
            'report.pdf': self._report_pdf,

            # System
            'ping': self._ping,
            'version': self._version,
            'shutdown': self._shutdown,
        }

    def _send_response(self, id: Optional[int], result: Any = None, error: Dict = None):
        """Send a JSON-RPC response to stdout."""
        response = {'jsonrpc': '2.0'}

        if id is not None:
            response['id'] = id

        if error:
            response['error'] = error
        else:
            response['result'] = result

        try:
            json_str = json.dumps(response, cls=DecimalEncoder)
            print(json_str, flush=True)
        except Exception as e:
            logger.error(f"Failed to serialize response: {e}")
            error_response = {
                'jsonrpc': '2.0',
                'id': id,
                'error': {
                    'code': RPCErrorCode.INTERNAL_ERROR,
                    'message': f'Serialization error: {str(e)}'
                }
            }
            print(json.dumps(error_response), flush=True)

    def _send_notification(self, method: str, params: Dict):
        """Send a notification (no id) for progress updates."""
        notification = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params
        }
        print(json.dumps(notification, cls=DecimalEncoder), flush=True)

    def _send_progress(self, percent: float, message: str):
        """Send a progress update notification."""
        self._send_notification('progress', {
            'percent': percent,
            'message': message
        })

    # ================================================================
    # RPC Method Implementations
    # ================================================================

    def _ping(self, params: Dict) -> Dict:
        """Simple ping to check if server is alive."""
        return {'pong': True, 'timestamp': datetime.now().isoformat()}

    def _version(self, params: Dict) -> Dict:
        """Get server version info."""
        return {
            'version': '1.0.0',
            'python_version': sys.version,
            'platform': sys.platform
        }

    def _shutdown(self, params: Dict) -> Dict:
        """Gracefully shutdown the server."""
        self._running = False
        return {'status': 'shutting_down'}

    def _db_stats(self, params: Dict) -> Dict:
        """Get database statistics."""
        # Import here to avoid circular imports
        from carful.db.user_generator import get_database_stats

        db_path = params.get('db_path')
        if not db_path:
            raise RPCError(RPCErrorCode.INVALID_PARAMS, 'db_path is required')

        try:
            stats = get_database_stats(db_path)
            return stats
        except Exception as e:
            logger.error(f"db.stats error: {e}")
            raise RPCError(RPCErrorCode.SERVER_ERROR, str(e))

    def _csv_import(self, params: Dict) -> Dict:
        """Import CSV file into database."""
        from carful.ingestion.csv_reader import CSVReader
        from carful.pipeline.transformer import create_default_pipeline

        csv_path = params.get('csv_path')
        db_path = params.get('db_path')
        chunk_size = params.get('chunk_size', 5000)

        if not csv_path:
            raise RPCError(RPCErrorCode.INVALID_PARAMS, 'csv_path is required')

        try:
            reader = CSVReader(chunk_size=chunk_size)
            pipeline = create_default_pipeline()

            total_rows = 0
            errors = []

            gen = reader.read_chunks(csv_path)
            chunk_num = 0

            while True:
                try:
                    chunk_df, metadata = next(gen)
                    chunk_num += 1
                    total_rows += len(chunk_df)

                    # Send progress update
                    self._send_progress(
                        percent=min(chunk_num * 10, 90),
                        message=f'Processing chunk {chunk_num}...'
                    )

                    # Run pipeline
                    result = pipeline.run(chunk_df)
                    if not result.success:
                        errors.extend([str(e) for e in result.error_report.errors])

                except StopIteration:
                    break

            self._send_progress(100, 'Import complete')

            return {
                'rows': total_rows,
                'chunks': chunk_num,
                'errors': errors[:50]  # Limit errors returned
            }
        except Exception as e:
            logger.error(f"csv.import error: {e}")
            raise RPCError(RPCErrorCode.SERVER_ERROR, str(e))

    def _csv_preview(self, params: Dict) -> Dict:
        """Preview first N rows of CSV file."""
        import pandas as pd

        csv_path = params.get('csv_path')
        num_rows = params.get('rows', 5)

        if not csv_path:
            raise RPCError(RPCErrorCode.INVALID_PARAMS, 'csv_path is required')

        try:
            # Count total rows (subtract header)
            total_rows = sum(1 for _ in open(csv_path)) - 1
            df = pd.read_csv(csv_path, nrows=num_rows)
            return {
                'headers': list(df.columns),
                'rows': df.fillna('').values.tolist(),
                'total_rows': max(total_rows, 0),
            }
        except Exception as e:
            logger.error(f"csv.preview error: {e}")
            raise RPCError(RPCErrorCode.SERVER_ERROR, str(e))

    def _tin_validate(self, params: Dict) -> Dict:
        """Validate all TINs in database."""
        from carful.validators.tin.dispatcher import TINDispatcher, validate_tin

        db_path = params.get('db_path')
        csv_path = params.get('csv_path')

        # Can validate from either DB or CSV
        if not db_path and not csv_path:
            raise RPCError(RPCErrorCode.INVALID_PARAMS, 'db_path or csv_path is required')

        try:
            valid_count = 0
            invalid_count = 0
            notin_count = 0
            errors = []

            if csv_path:
                import pandas as pd
                df = pd.read_csv(csv_path)

                # Find TIN and country columns
                tin_col = None
                country_col = None
                for col in df.columns:
                    if 'tin' in col.lower() and 'country' not in col.lower():
                        tin_col = col
                    if 'country' in col.lower() and 'tin' in col.lower():
                        country_col = col
                    elif 'country_code' in col.lower():
                        country_col = col

                if tin_col:
                    for idx, row in df.iterrows():
                        tin_value = str(row.get(tin_col, '')) if pd.notna(row.get(tin_col)) else ''
                        country = str(row.get(country_col, 'US')) if country_col and pd.notna(row.get(country_col)) else 'US'

                        result = validate_tin(tin_value, country)

                        if result.is_notin:
                            notin_count += 1
                        elif result.is_valid:
                            valid_count += 1
                        else:
                            invalid_count += 1
                            if len(errors) < 50:
                                errors.append({
                                    'row': idx + 2,  # 1-indexed + header
                                    'tin': tin_value,
                                    'country': country,
                                    'message': result.error or 'Invalid TIN'
                                })

            return {
                'valid': valid_count,
                'invalid': invalid_count,
                'notin': notin_count,
                'errors': errors
            }
        except Exception as e:
            logger.error(f"tin.validate error: {e}")
            raise RPCError(RPCErrorCode.SERVER_ERROR, str(e))

    def _tin_validate_single(self, params: Dict) -> Dict:
        """Validate a single TIN."""
        from carful.validators.tin.dispatcher import validate_tin

        tin = params.get('tin', '')
        country = params.get('country', 'US')

        result = validate_tin(tin, country)

        return {
            'valid': result.is_valid,
            'is_notin': result.is_notin,
            'error': result.error,
            'tin_type': result.tin_type.value if result.tin_type else None,
        }

    def _xml_export(self, params: Dict) -> Dict:
        """Export data to CARF XML."""
        import time
        from pathlib import Path

        csv_path = params.get('csv_path')
        db_path = params.get('db_path')
        output = params.get('output')
        config = params.get('config', {})

        if not output:
            raise RPCError(RPCErrorCode.INVALID_PARAMS, 'output is required')
        if not csv_path and not db_path:
            raise RPCError(RPCErrorCode.INVALID_PARAMS, 'csv_path or db_path is required')

        try:
            start_time = time.perf_counter()

            # Use CLI export functionality
            from carful.xml_gen.stream_writer import CARFStreamWriter, StreamWriterConfig
            from carful.xml_gen.header_builder import HeaderBuilder
            from carful.xml_gen.body_builder import BodyBuilder, RCASPData, AddressData

            sending_country = config.get('sending_country', 'US')
            receiving_country = config.get('receiving_country', 'GB')
            year = config.get('reporting_year', config.get('year', 2025))

            # Extract RCASP config (frontend sends nested rcasp object)
            rcasp_config = config.get('rcasp', {})

            output_path = Path(output)

            writer_config = StreamWriterConfig(
                encoding='UTF-8',
                standalone=True,
            )

            with CARFStreamWriter(str(output_path), config=writer_config) as writer:
                with writer.carf_document():
                    # Write header
                    header_builder = HeaderBuilder(
                        transmitting_country=sending_country,
                        receiving_country=receiving_country,
                        reporting_year=year,
                        namespace_manager=writer.ns_manager,
                    )
                    header_elem = header_builder.build()
                    writer.write_element(header_elem)

                    self._send_progress(20, 'Header written')

                    # Write body with RCASP
                    rcasp_data = RCASPData(
                        name=rcasp_config.get('name', 'RCASP Provider'),
                        tin=rcasp_config.get('tin', '12-3456789'),
                        tin_country=rcasp_config.get('country', sending_country),
                        address=AddressData(
                            country=rcasp_config.get('country', sending_country),
                            city=rcasp_config.get('city', 'New York'),
                            street=rcasp_config.get('street', '123 Main St'),
                        ),
                    )

                    body_builder = BodyBuilder(
                        rcasp=rcasp_data,
                        namespace_manager=writer.ns_manager,
                    )

                    with writer.element('CARFBody'):
                        with writer.element('ReportingGroup'):
                            rcasp_elem = body_builder.build_rcasp()
                            writer.write_element(rcasp_elem)

                            self._send_progress(40, 'RCASP written')

                            # Process CSV if provided
                            if csv_path:
                                import pandas as pd
                                from carful.xml_gen.user_builder import UserBuilder, IndividualData
                                from carful.xml_gen.transaction_builder import TransactionBuilder, TransactionData
                                from carful.xml_gen.body_builder import AddressData

                                df = pd.read_csv(csv_path)
                                total = len(df)

                                for idx, row in df.iterrows():
                                    if idx % 100 == 0:
                                        progress = 40 + (idx / total * 50)
                                        self._send_progress(progress, f'Processing row {idx}/{total}')

                                    # Build user
                                    user_country = str(row.get('tin_country', row.get('country_code', sending_country)))
                                    user_city = str(row.get('address_city', row.get('city', 'Unknown')))

                                    user_data = IndividualData(
                                        first_name=str(row.get('first_name', 'Unknown')),
                                        last_name=str(row.get('last_name', 'User')),
                                        tin=str(row.get('tin', 'NOTIN')) if pd.notna(row.get('tin')) else 'NOTIN',
                                        tin_country=user_country,
                                        address=AddressData(
                                            country=user_country,
                                            city=user_city,
                                            street=str(row.get('address_street', '')) or None,
                                        ),
                                    )

                                    # Build transaction
                                    tx_data = TransactionData(
                                        transaction_type='CARF501',
                                        transaction_date=datetime.now(),
                                        asset_code=str(row.get('crypto_asset', row.get('asset', 'BTC'))),
                                        amount=Decimal(str(row.get('quantity', row.get('amount', '0')))),
                                    )

                                    user_builder = UserBuilder(
                                        individual=user_data,
                                        namespace_manager=writer.ns_manager,
                                    )
                                    tx_builder = TransactionBuilder(
                                        data=tx_data,
                                        namespace_manager=writer.ns_manager,
                                    )

                                    tx_elem = tx_builder.build()
                                    user_elem = user_builder.build([tx_elem])
                                    writer.write_element(user_elem)

            elapsed = time.perf_counter() - start_time
            file_size = output_path.stat().st_size

            self._send_progress(100, 'Export complete')

            return {
                'file': str(output_path),
                'size': file_size,
                'duration': elapsed
            }
        except Exception as e:
            logger.error(f"xml.export error: {e}\n{traceback.format_exc()}")
            raise RPCError(RPCErrorCode.SERVER_ERROR, str(e))

    def _health_check(self, params: Dict) -> Dict:
        """Run comprehensive health check on CSV file.

        Checks: required columns, TIN validation, transaction code mapping,
        data quality (missing fields, format errors, precision), and computes
        a weighted compliance score.
        """
        import os
        import time
        import pandas as pd
        from carful.validators.tin.dispatcher import validate_tin
        from carful.enumerations import is_valid_transaction_type
        from carful.transaction_mapper import map_transaction

        start_time = time.time()

        csv_path = params.get('csv_path')
        if not csv_path:
            raise RPCError(RPCErrorCode.INVALID_PARAMS, 'csv_path is required')

        try:
            file_size_bytes = os.path.getsize(csv_path)
            df = pd.read_csv(csv_path)
            total_rows = len(df)

            errors = []
            warnings = []
            suggestions = []

            # ----------------------------------------------------------
            # 1. Required columns check
            # ----------------------------------------------------------
            required_columns = ['transaction_id', 'user_id']
            optional_important = ['amount', 'timestamp', 'transaction_type', 'description']
            missing_required = []
            missing_optional = []

            for col in required_columns:
                if col not in df.columns:
                    missing_required.append(col)
                    errors.append({
                        'type': 'missing_column',
                        'column': col,
                        'message': f'Required column "{col}" is missing'
                    })

            for col in optional_important:
                if col not in df.columns:
                    missing_optional.append(col)

            if missing_optional:
                suggestions.append({
                    'type': 'missing_optional_columns',
                    'columns': missing_optional,
                    'message': f'Optional columns missing: {", ".join(missing_optional)}. '
                              'Adding these improves CARF compliance quality.'
                })

            # ----------------------------------------------------------
            # 2. Detect column names for TIN, country, transaction, amount
            # ----------------------------------------------------------
            tin_col = None
            country_col = None
            tx_type_col = None
            description_col = None
            amount_col = None
            timestamp_col = None

            for col in df.columns:
                col_lower = col.lower()
                if 'tin' in col_lower and 'country' not in col_lower and not tin_col:
                    tin_col = col
                if 'country' in col_lower and not country_col:
                    country_col = col
                if col_lower in ('transaction_type', 'tx_type', 'type') and not tx_type_col:
                    tx_type_col = col
                if col_lower in ('description', 'memo', 'note', 'notes') and not description_col:
                    description_col = col
                if col_lower in ('amount', 'value', 'total') and not amount_col:
                    amount_col = col
                if col_lower in ('timestamp', 'date', 'datetime', 'time', 'created_at') and not timestamp_col:
                    timestamp_col = col

            # ----------------------------------------------------------
            # 3. TIN Validation
            # ----------------------------------------------------------
            valid_tins = 0
            invalid_tins = 0
            notin_count = 0
            tin_errors = []
            tin_by_country = {}

            if tin_col:
                for idx, row in df.iterrows():
                    tin_value = str(row.get(tin_col, '')) if pd.notna(row.get(tin_col)) else ''
                    country = str(row.get(country_col, 'US')) if country_col and pd.notna(row.get(country_col)) else 'US'

                    result = validate_tin(tin_value, country)

                    # Country breakdown
                    if country not in tin_by_country:
                        tin_by_country[country] = {'valid': 0, 'invalid': 0, 'notin': 0}

                    if result.is_notin:
                        notin_count += 1
                        tin_by_country[country]['notin'] += 1
                    elif result.is_valid:
                        valid_tins += 1
                        tin_by_country[country]['valid'] += 1
                    else:
                        invalid_tins += 1
                        tin_by_country[country]['invalid'] += 1
                        if len(tin_errors) < 50:
                            tin_errors.append({
                                'type': 'invalid_tin',
                                'row': idx + 2,
                                'tin': tin_value,
                                'country': country,
                                'message': result.error or 'Invalid TIN' or 'Invalid TIN format'
                            })
            else:
                errors.append({
                    'type': 'missing_column',
                    'column': 'tin',
                    'message': 'No TIN column detected. TIN validation requires a column containing "tin" in its name.'
                })

            # ----------------------------------------------------------
            # 4. Transaction Code Mapping Quality
            # ----------------------------------------------------------
            mapped_codes = 0
            unmapped_codes = 0
            code_distribution = {}
            unmapped_descriptions = []

            if tx_type_col or description_col:
                for idx, row in df.iterrows():
                    tx_type = str(row.get(tx_type_col, '')) if tx_type_col and pd.notna(row.get(tx_type_col)) else ''
                    desc = str(row.get(description_col, '')) if description_col and pd.notna(row.get(description_col)) else ''

                    # Check if tx_type is already a valid CARF code
                    if tx_type and is_valid_transaction_type(tx_type):
                        mapped_codes += 1
                        code_distribution[tx_type] = code_distribution.get(tx_type, 0) + 1
                    elif desc:
                        # Try keyword-based mapping
                        mapping_result = map_transaction(desc)
                        if mapping_result.transaction_type and mapping_result.confidence.value != 'unknown':
                            mapped_codes += 1
                            code_distribution[mapping_result.transaction_type] = code_distribution.get(mapping_result.transaction_type, 0) + 1
                        else:
                            unmapped_codes += 1
                            if len(unmapped_descriptions) < 10:
                                unmapped_descriptions.append({
                                    'row': idx + 2,
                                    'description': desc[:60],
                                    'message': 'Could not map to CARF transaction code'
                                })
                    else:
                        unmapped_codes += 1

                total_tx = mapped_codes + unmapped_codes
                if unmapped_codes > 0:
                    warnings.append({
                        'type': 'unmapped_transactions',
                        'count': unmapped_codes,
                        'message': f'{unmapped_codes} of {total_tx} transactions could not be mapped to CARF codes',
                        'samples': unmapped_descriptions
                    })

            # ----------------------------------------------------------
            # 5. Data Quality Checks
            # ----------------------------------------------------------
            data_quality_issues = []

            # 5a. Missing required field values (not columns, but cell values)
            for col in ['transaction_id', 'user_id']:
                if col in df.columns:
                    null_count = df[col].isna().sum()
                    if null_count > 0:
                        data_quality_issues.append({
                            'type': 'missing_values',
                            'column': col,
                            'count': int(null_count),
                            'message': f'{null_count} rows have missing {col} values'
                        })

            # 5b. Amount precision check
            precision_issues = 0
            if amount_col and amount_col in df.columns:
                for idx, val in df[amount_col].items():
                    if pd.notna(val):
                        try:
                            str_val = str(val)
                            if '.' in str_val:
                                decimal_places = len(str_val.split('.')[1])
                                if decimal_places > 20:
                                    precision_issues += 1
                        except (ValueError, TypeError):
                            pass

                if precision_issues > 0:
                    data_quality_issues.append({
                        'type': 'precision_overflow',
                        'count': precision_issues,
                        'message': f'{precision_issues} amounts exceed 20 decimal places (CARF XSD max)'
                    })

            # 5c. Duplicate transaction IDs
            if 'transaction_id' in df.columns:
                dup_count = df['transaction_id'].duplicated().sum()
                if dup_count > 0:
                    data_quality_issues.append({
                        'type': 'duplicate_ids',
                        'count': int(dup_count),
                        'message': f'{dup_count} duplicate transaction_id values found'
                    })

            # 5d. Character encoding check (non-ASCII in key fields)
            encoding_issues = 0
            for col in [tin_col, 'transaction_id', 'user_id']:
                if col and col in df.columns:
                    for val in df[col].dropna():
                        try:
                            str(val).encode('ascii')
                        except UnicodeEncodeError:
                            encoding_issues += 1

            if encoding_issues > 0:
                data_quality_issues.append({
                    'type': 'encoding_issues',
                    'count': encoding_issues,
                    'message': f'{encoding_issues} values contain non-ASCII characters in ID/TIN fields'
                })

            if data_quality_issues:
                for issue in data_quality_issues:
                    if issue['type'] in ('missing_values', 'duplicate_ids'):
                        errors.append(issue)
                    else:
                        warnings.append(issue)

            # ----------------------------------------------------------
            # 6. Data Overview metrics
            # ----------------------------------------------------------
            unique_users = int(df['user_id'].nunique()) if 'user_id' in df.columns else 0

            date_range_start = None
            date_range_end = None
            if timestamp_col and timestamp_col in df.columns:
                try:
                    dates = pd.to_datetime(df[timestamp_col], errors='coerce').dropna()
                    if len(dates) > 0:
                        date_range_start = str(dates.min().date())
                        date_range_end = str(dates.max().date())
                except Exception:
                    pass

            processing_time = round(time.time() - start_time, 2)

            # ----------------------------------------------------------
            # 7. Weighted Compliance Score (0-100)
            # ----------------------------------------------------------
            # Weights: TIN validation 40%, tx code mapping 25%,
            #          required columns 15%, data quality 20%
            tin_total = valid_tins + invalid_tins + notin_count
            tin_score = (valid_tins / tin_total * 100) if tin_total > 0 else 0

            total_tx = mapped_codes + unmapped_codes
            mapping_score = (mapped_codes / total_tx * 100) if total_tx > 0 else 100

            column_score = 100 - (len(missing_required) * 50)
            column_score = max(0, column_score)

            total_quality_issues = sum(i.get('count', 0) for i in data_quality_issues)
            quality_score = max(0, 100 - (total_quality_issues / max(total_rows, 1) * 100))

            score = int(
                tin_score * 0.40 +
                mapping_score * 0.25 +
                column_score * 0.15 +
                quality_score * 0.20
            )
            score = max(0, min(100, score))

            # Grade
            if score >= 90:
                grade = 'A'
            elif score >= 80:
                grade = 'B'
            elif score >= 70:
                grade = 'C'
            elif score >= 60:
                grade = 'D'
            else:
                grade = 'F'

            # ----------------------------------------------------------
            # 8. Build response (aligned with PDF generator expectations)
            # ----------------------------------------------------------
            # Top-level 'score' for pdf_generator.py compatibility
            return {
                'score': score,
                'grade': grade,
                'errors': errors,
                'warnings': warnings,
                'suggestions': suggestions,
                'validation': {
                    'valid': valid_tins,
                    'invalid': invalid_tins,
                    'notin': notin_count,
                    'by_country': {k: v['valid'] for k, v in tin_by_country.items()},
                },
                'tin_errors': tin_errors,
                'transaction_analysis': {
                    'mapped': mapped_codes,
                    'unmapped': unmapped_codes,
                    'total': mapped_codes + unmapped_codes,
                    'mapped_pct': round(mapped_codes / max(mapped_codes + unmapped_codes, 1) * 100, 1),
                    'code_distribution': code_distribution,
                    'unmapped_samples': unmapped_descriptions,
                },
                'data_quality': {
                    'issues': data_quality_issues,
                    'total_issues': total_quality_issues,
                    'quality_score': round(quality_score, 1),
                },
                'summary': {
                    'total_records': total_rows,
                    'unique_users': unique_users,
                    'valid_tins': round(tin_score, 1),
                    'mapped_codes': round(mapping_score, 1),
                    'columns': list(df.columns),
                    'date_range_start': date_range_start,
                    'date_range_end': date_range_end,
                    'file_size': file_size_bytes,
                    'processing_time': processing_time,
                    'filing_ready': len(errors) == 0 and invalid_tins == 0,
                },
                'score_breakdown': {
                    'tin_validation': round(tin_score, 1),
                    'code_mapping': round(mapping_score, 1),
                    'required_columns': round(column_score, 1),
                    'data_quality': round(quality_score, 1),
                },
            }
        except Exception as e:
            logger.error(f"health.check error: {e}\n{traceback.format_exc()}")
            raise RPCError(RPCErrorCode.SERVER_ERROR, str(e))

    def _report_pdf(self, params: Dict) -> Dict:
        """Generate PDF health check report."""
        check_result = params.get('check_result')
        output = params.get('output')
        company_name = params.get('company_name')

        if not check_result:
            raise RPCError(RPCErrorCode.INVALID_PARAMS, 'check_result is required')
        if not output:
            raise RPCError(RPCErrorCode.INVALID_PARAMS, 'output is required')

        try:
            # Import PDF generator
            from carful.reports.pdf_generator import PDFHealthCheckReport

            generator = PDFHealthCheckReport(check_result, company_name=company_name)
            generator.generate(output)

            return {
                'file': output,
                'pages': generator.page_count
            }
        except ImportError:
            # PDF generator not yet implemented
            return {
                'file': output,
                'pages': 0,
                'error': 'PDF generator not yet implemented'
            }
        except Exception as e:
            logger.error(f"report.pdf error: {e}")
            raise RPCError(RPCErrorCode.SERVER_ERROR, str(e))

    # ================================================================
    # Main Loop
    # ================================================================

    def handle_request(self, request: Dict) -> None:
        """Handle a single RPC request."""
        request_id = request.get('id')

        # Validate request
        if request.get('jsonrpc') != '2.0':
            self._send_response(request_id, error={
                'code': RPCErrorCode.INVALID_REQUEST,
                'message': 'Invalid JSON-RPC version'
            })
            return

        method = request.get('method')
        if not method:
            self._send_response(request_id, error={
                'code': RPCErrorCode.INVALID_REQUEST,
                'message': 'Method is required'
            })
            return

        params = request.get('params', {})

        # Find and execute method
        handler = self.methods.get(method)
        if not handler:
            self._send_response(request_id, error={
                'code': RPCErrorCode.METHOD_NOT_FOUND,
                'message': f'Method not found: {method}'
            })
            return

        try:
            result = handler(params)
            self._send_response(request_id, result=result)
        except RPCError as e:
            self._send_response(request_id, error={
                'code': e.code,
                'message': e.message,
                'data': e.data
            })
        except Exception as e:
            logger.error(f"Unhandled error in {method}: {e}\n{traceback.format_exc()}")
            self._send_response(request_id, error={
                'code': RPCErrorCode.INTERNAL_ERROR,
                'message': str(e)
            })

    def run(self):
        """Main loop: read requests from stdin, process, write responses to stdout."""
        logger.info("RPC server starting...")

        # Signal readiness to the parent process (Electron)
        ready_signal = json.dumps({"jsonrpc": "2.0", "method": "ready", "params": {}})
        sys.stdout.write(ready_signal + "\n")
        sys.stdout.flush()
        logger.info("RPC server ready signal sent")

        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    # EOF - parent process closed stdin
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    self._send_response(None, error={
                        'code': RPCErrorCode.PARSE_ERROR,
                        'message': f'JSON parse error: {str(e)}'
                    })
                    continue

                self.handle_request(request)

            except KeyboardInterrupt:
                logger.info("Interrupted, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                continue

        logger.info("RPC server stopped")


def main():
    """Entry point for the RPC server."""
    server = RPCServer()
    server.run()


if __name__ == '__main__':
    main()
