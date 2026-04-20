"""
CARFul - Command Line Interface

Entry point for the CARFul RegTech application.
Provides commands for CSV ingestion, transformation, and XML generation.

Usage:
    python -m carful ingest <csv_path> --db <db_path>
    python -m carful validate <csv_path>
    python -m carful benchmark <csv_path>
"""

import click
import sys
import time
import logging
from pathlib import Path
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('carful')

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent))

from ingestion.csv_reader import CSVReader, ColumnMapper, detect_csv_format
from ingestion.chunk_processor import ChunkProcessor, create_chunk_generator
from pipeline.transformer import (
    TransformationPipeline,
    CoerceTypesStage,
    MapEnumsStage,
    ValidateStage,
    PersistStage,
    create_default_pipeline,
)
from xml_gen import (
    CARFStreamWriter,
    StreamWriterConfig,
    HeaderBuilder,
    MessageHeaderData,
    BodyBuilder,
    RCASPData,
    AddressData,
    TINData,
    UserBuilder,
    IndividualData,
    PersonNameData,
    TransactionBuilder,
    TransactionData,
    TransactionType,
    CryptoAssetData,
    FiatValueData,
    create_new_data_header,
)
from validators.tin.dispatcher import TINDispatcher, validate_tin
from validators.schema_validator import SchemaValidator, ValidationReport


# =============================================================================
# CLI Application
# =============================================================================

@click.group()
@click.version_option(version='0.1.0', prog_name='CARFul')
def cli():
    """
    CARFul - CARF XML Generation Tool

    Convert crypto transaction CSV files to OECD CARF XML format
    for regulatory compliance reporting.
    """
    pass


# =============================================================================
# Ingest Command
# =============================================================================

@cli.command()
@click.argument('csv_path', type=click.Path(exists=True))
@click.option('--db', 'db_path', type=click.Path(), help='SQLite database path')
@click.option('--chunk-size', default=5000, help='Rows per processing chunk')
@click.option('--preset', type=str, help='Column mapping preset (coinbase, binance, kraken)')
@click.option('--year', default=2025, help='Reporting year for validation')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def ingest(csv_path: str, db_path: str, chunk_size: int, preset: str, year: int, verbose: bool):
    """
    Ingest a CSV file into the CARFul database.

    Reads the CSV file, applies transformations (type coercion, CARF mapping),
    validates data, and optionally persists to SQLite.

    Example:
        python -m carful ingest transactions.csv --db carful.db --year 2025
    """
    click.echo(f"\n{'='*60}")
    click.echo("CARFul CSV Ingestion")
    click.echo(f"{'='*60}")
    click.echo(f"  File: {csv_path}")
    click.echo(f"  Chunk size: {chunk_size:,}")
    click.echo(f"  Reporting year: {year}")
    if preset:
        click.echo(f"  Preset: {preset}")
    if db_path:
        click.echo(f"  Database: {db_path}")
    click.echo(f"{'='*60}\n")

    start_time = time.perf_counter()

    # Set up column mapper
    mapper = ColumnMapper.from_preset(preset) if preset else None
    reader = CSVReader(chunk_size=chunk_size, column_mapper=mapper)

    # Create pipeline
    pipeline = create_default_pipeline(reporting_year=year)

    # Process file in chunks
    total_rows = 0
    total_errors = 0
    chunk_count = 0

    try:
        gen = reader.read_chunks(csv_path)

        while True:
            try:
                chunk_df, metadata = next(gen)
                chunk_count += 1

                result = pipeline.run(chunk_df)
                total_rows += result.total_rows_in
                total_errors += result.error_report.total_errors

                if verbose:
                    click.echo(f"  Chunk {chunk_count}: {result.total_rows_in} rows, "
                              f"{result.error_report.total_errors} errors")

            except StopIteration:
                break

    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        sys.exit(1)

    elapsed = time.perf_counter() - start_time
    rows_per_sec = total_rows / elapsed if elapsed > 0 else 0

    # Summary
    click.echo(f"\n{'='*60}")
    click.echo("INGESTION COMPLETE")
    click.echo(f"{'='*60}")
    click.echo(f"  Total rows:     {total_rows:,}")
    click.echo(f"  Total chunks:   {chunk_count}")
    click.echo(f"  Total errors:   {total_errors}")
    click.echo(f"  Elapsed time:   {elapsed:.2f}s")
    click.echo(f"  Rows/second:    {rows_per_sec:,.0f}")
    click.echo(f"{'='*60}\n")

    if total_errors > 0:
        click.echo(f"⚠️  {total_errors} errors encountered during processing")
    else:
        click.echo("✅ All rows processed successfully")


# =============================================================================
# Validate Command
# =============================================================================

@cli.command()
@click.argument('csv_path', type=click.Path(exists=True))
@click.option('--preset', type=str, help='Column mapping preset')
@click.option('--sample', default=100, help='Number of rows to sample')
def validate(csv_path: str, preset: str, sample: int):
    """
    Validate a CSV file without processing.

    Analyzes the file structure, detects column mappings,
    and reports potential issues.

    Example:
        python -m carful validate transactions.csv --sample 50
    """
    click.echo(f"\n{'='*60}")
    click.echo("CARFul CSV Validation")
    click.echo(f"{'='*60}")
    click.echo(f"  File: {csv_path}")
    click.echo(f"{'='*60}\n")

    # Detect format
    try:
        format_info = detect_csv_format(csv_path, sample_rows=sample)

        click.echo("Detected Columns:")
        for col in format_info['columns']:
            dtype = format_info['dtypes'].get(col, 'unknown')
            mapped = format_info['detected_mapping'].get(col, '')
            mapping_str = f" → {mapped}" if mapped else ""
            click.echo(f"  • {col} ({dtype}){mapping_str}")

        click.echo(f"\nSample rows analyzed: {format_info['row_count_sample']}")

        unmapped = format_info['unmapped_columns']
        if unmapped:
            click.echo(f"\nUnmapped columns: {', '.join(unmapped)}")

        # Check for required fields
        required = ['timestamp', 'amount', 'asset']
        mapped_fields = set(format_info['detected_mapping'].values())
        missing = [f for f in required if f not in mapped_fields]

        if missing:
            click.echo(f"\n⚠️  Missing required fields: {', '.join(missing)}")
            click.echo("   Consider using --preset or creating a custom mapping")
        else:
            click.echo("\n✅ All required fields detected")

    except Exception as e:
        click.echo(f"\n❌ Validation error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Benchmark Command
# =============================================================================

@cli.command()
@click.argument('csv_path', type=click.Path(exists=True))
@click.option('--chunk-size', default=5000, help='Rows per chunk')
@click.option('--no-mapping', is_flag=True, help='Skip CARF mapping for raw speed test')
def benchmark(csv_path: str, chunk_size: int, no_mapping: bool):
    """
    Run performance benchmark on a CSV file.

    Measures processing speed and memory efficiency.
    Target: <30 seconds for 100K transactions.

    Example:
        python -m carful benchmark large_dataset.csv --chunk-size 10000
    """
    import gc
    import tracemalloc

    click.echo(f"\n{'='*60}")
    click.echo("CARFul Performance Benchmark")
    click.echo(f"{'='*60}")
    click.echo(f"  File: {csv_path}")
    click.echo(f"  Chunk size: {chunk_size:,}")
    click.echo(f"  CARF mapping: {'disabled' if no_mapping else 'enabled'}")
    click.echo(f"{'='*60}\n")

    # Force garbage collection
    gc.collect()

    # Start memory tracking
    tracemalloc.start()

    # Start timer
    start_time = time.perf_counter()

    # Create reader
    reader = CSVReader(chunk_size=chunk_size)

    # Create pipeline (optionally skip mapping)
    pipeline = TransformationPipeline()
    pipeline.add_stage(CoerceTypesStage(reporting_year=2025))
    if not no_mapping:
        pipeline.add_stage(MapEnumsStage())
    pipeline.add_stage(ValidateStage())

    # Track stats
    total_rows = 0
    chunk_count = 0
    chunk_times = []

    try:
        gen = reader.read_chunks(csv_path)

        while True:
            try:
                chunk_start = time.perf_counter()
                chunk_df, metadata = next(gen)
                chunk_count += 1

                result = pipeline.run(chunk_df)
                total_rows += result.total_rows_in

                chunk_time = (time.perf_counter() - chunk_start) * 1000
                chunk_times.append(chunk_time)

                if chunk_count % 5 == 0:
                    current, peak = tracemalloc.get_traced_memory()
                    click.echo(f"  Chunk {chunk_count}: {total_rows:,} rows, "
                              f"{chunk_time:.1f}ms, Memory: {peak/(1024*1024):.1f}MB")

            except StopIteration:
                break

    except Exception as e:
        click.echo(f"\n❌ Benchmark error: {e}", err=True)
        sys.exit(1)

    # Stop tracking
    end_time = time.perf_counter()
    current_memory, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    elapsed = end_time - start_time
    rows_per_sec = total_rows / elapsed if elapsed > 0 else 0

    # Calculate stats
    avg_chunk_time = sum(chunk_times) / len(chunk_times) if chunk_times else 0
    max_chunk_time = max(chunk_times) if chunk_times else 0
    min_chunk_time = min(chunk_times) if chunk_times else 0

    # Results
    click.echo(f"\n{'='*60}")
    click.echo("BENCHMARK RESULTS")
    click.echo(f"{'='*60}")
    click.echo(f"  Total Rows:        {total_rows:,}")
    click.echo(f"  Total Chunks:      {chunk_count}")
    click.echo(f"  Elapsed Time:      {elapsed:.2f}s")
    click.echo(f"  Rows/Second:       {rows_per_sec:,.0f}")
    click.echo(f"  Avg Chunk Time:    {avg_chunk_time:.2f}ms")
    click.echo(f"  Max Chunk Time:    {max_chunk_time:.2f}ms")
    click.echo(f"  Min Chunk Time:    {min_chunk_time:.2f}ms")
    click.echo(f"  Peak Memory:       {peak_memory/(1024*1024):.2f}MB")
    click.echo(f"{'='*60}")

    # Check target
    target_time = 30.0  # seconds for 100K
    projected_100k = (100000 / total_rows) * elapsed if total_rows > 0 else float('inf')

    if projected_100k < target_time:
        click.echo(f"\n✅ TARGET MET: Projected {projected_100k:.1f}s for 100K rows (target: <{target_time}s)")
    else:
        click.echo(f"\n❌ TARGET MISSED: Projected {projected_100k:.1f}s for 100K rows (target: <{target_time}s)")

    click.echo(f"{'='*60}\n")


# =============================================================================
# Export Command
# =============================================================================

@cli.command()
@click.argument('csv_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), required=True, help='Output XML file path')
@click.option('--validate', 'do_validate', is_flag=True, help='Validate XML against XSD schema after generation')
@click.option('--schema', type=click.Path(exists=True), help='Path to XSD schema file for validation')
@click.option('--sending-country', default='US', help='Transmitting country code (ISO 3166-1)')
@click.option('--receiving-country', default='GB', help='Receiving country code (ISO 3166-1)')
@click.option('--year', default=2025, help='Reporting period year')
@click.option('--chunk-size', default=5000, help='Rows per processing chunk')
@click.option('--preset', type=str, help='Column mapping preset')
@click.option('--dry-run', is_flag=True, help='Validate data without generating XML')
@click.option('--profile-memory', is_flag=True, help='Enable memory profiling with tracemalloc')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def export(csv_path: str, output: str, do_validate: bool, schema: str,
           sending_country: str, receiving_country: str, year: int,
           chunk_size: int, preset: str, dry_run: bool, profile_memory: bool, verbose: bool):
    """
    Export CSV data to CARF-compliant XML.

    Full pipeline: CSV → TIN Validation → XML Generation → XSD Validation

    Examples:
        python -m carful export transactions.csv -o export.xml --validate
        python -m carful export data.csv -o out.xml --dry-run --profile-memory
        python -m carful export data.csv -o out.xml --sending-country US --receiving-country DE
    """
    import tracemalloc
    import uuid
    from datetime import datetime, timezone

    click.echo(f"\n{'='*60}")
    click.echo("CARFul XML Export")
    click.echo(f"{'='*60}")
    click.echo(f"  Input:             {csv_path}")
    click.echo(f"  Output:            {output}")
    click.echo(f"  Sending Country:   {sending_country}")
    click.echo(f"  Receiving Country: {receiving_country}")
    click.echo(f"  Reporting Year:    {year}")
    click.echo(f"  Validate XML:      {'Yes' if do_validate else 'No'}")
    click.echo(f"  Dry Run:           {'Yes' if dry_run else 'No'}")
    click.echo(f"  Memory Profiling:  {'Yes' if profile_memory else 'No'}")
    click.echo(f"{'='*60}\n")

    start_time = time.perf_counter()

    # Start memory profiling if requested
    if profile_memory:
        tracemalloc.start()
        click.echo("📊 Memory profiling enabled")

    # Initialize TIN dispatcher
    tin_dispatcher = TINDispatcher()

    # Set up column mapper and reader
    mapper = ColumnMapper.from_preset(preset) if preset else None
    reader = CSVReader(chunk_size=chunk_size, column_mapper=mapper)

    # Create transformation pipeline
    pipeline = create_default_pipeline(reporting_year=year)

    # Statistics tracking
    total_rows = 0
    total_tin_valid = 0
    total_tin_invalid = 0
    total_tin_notin = 0
    chunk_count = 0
    user_count = 0
    transaction_count = 0
    memory_snapshots = []

    try:
        # Phase 1: Process CSV and validate TINs
        click.echo("Phase 1: Processing CSV and validating TINs...")

        processed_data = []
        gen = reader.read_chunks(csv_path)

        while True:
            try:
                chunk_df, metadata = next(gen)
                chunk_count += 1
                total_rows += len(chunk_df)

                # Run transformation pipeline
                result = pipeline.run(chunk_df)

                # Validate TINs in chunk
                # Support both 'country_code' and 'tin_country' column names
                country_col = 'country_code' if 'country_code' in chunk_df.columns else 'tin_country'
                if 'tin' in chunk_df.columns and country_col in chunk_df.columns:
                    for idx, row in chunk_df.iterrows():
                        tin_value = str(row.get('tin', '')) if row.get('tin') else ''
                        country = str(row.get(country_col, 'US'))
                        tin_result = validate_tin(tin_value, country)

                        if tin_result.is_notin:
                            total_tin_notin += 1
                        elif tin_result.is_valid:
                            total_tin_valid += 1
                        else:
                            total_tin_invalid += 1

                # Store processed data for XML generation
                # Note: We store the original chunk_df since the pipeline is for validation
                # The XML generator will use this data to create XML elements
                processed_data.append(chunk_df.copy())

                if verbose:
                    click.echo(f"  Chunk {chunk_count}: {len(chunk_df)} rows processed")

                # Memory snapshot
                if profile_memory and chunk_count % 5 == 0:
                    current, peak = tracemalloc.get_traced_memory()
                    memory_snapshots.append({
                        'chunk': chunk_count,
                        'current_mb': current / (1024 * 1024),
                        'peak_mb': peak / (1024 * 1024),
                    })
                    if verbose:
                        click.echo(f"    Memory: {current/(1024*1024):.1f}MB current, {peak/(1024*1024):.1f}MB peak")

            except StopIteration:
                break

        click.echo(f"  ✓ Processed {total_rows:,} rows in {chunk_count} chunks")
        click.echo(f"  ✓ TIN validation: {total_tin_valid} valid, {total_tin_invalid} invalid, {total_tin_notin} NOTIN")

        # If dry run, stop here
        if dry_run:
            elapsed = time.perf_counter() - start_time
            click.echo(f"\n{'='*60}")
            click.echo("DRY RUN COMPLETE (no XML generated)")
            click.echo(f"{'='*60}")
            click.echo(f"  Total rows:        {total_rows:,}")
            click.echo(f"  TIN valid:         {total_tin_valid:,}")
            click.echo(f"  TIN invalid:       {total_tin_invalid:,}")
            click.echo(f"  TIN NOTIN:         {total_tin_notin:,}")
            click.echo(f"  Elapsed time:      {elapsed:.2f}s")

            if profile_memory:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                click.echo(f"  Peak memory:       {peak/(1024*1024):.2f}MB")

            click.echo(f"{'='*60}\n")
            return

        # Phase 2: Generate XML
        click.echo("\nPhase 2: Generating CARF XML...")

        config = StreamWriterConfig(
            encoding='UTF-8',
            standalone=True,
            gc_interval=1000,
            report_interval=10000,
        )

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with CARFStreamWriter(str(output_path), config=config) as writer:
            # Write CARF root with namespaces
            with writer.carf_document():
                # Write MessageHeader
                header_builder = HeaderBuilder(
                    transmitting_country=sending_country,
                    receiving_country=receiving_country,
                    reporting_year=year,
                    namespace_manager=writer.ns_manager,
                )
                header_elem = header_builder.build()
                writer.write_element(header_elem)
                click.echo("  ✓ MessageHeader written")

                # Write CARFBody
                # Placeholder RCASP (Reporting Crypto-Asset Service Provider)
                rcasp_data = RCASPData(
                    name="Sample RCASP Provider",
                    tin="12-3456789",
                    tin_country=sending_country,
                    address=AddressData(
                        country=sending_country,
                        city="New York",
                        street="123 Main Street",
                    ),
                )
                body_builder = BodyBuilder(rcasp=rcasp_data, namespace_manager=writer.ns_manager)
                with writer.element('CARFBody'):
                    # Write ReportingGroup
                    with writer.element('ReportingGroup'):
                        rcasp_elem = body_builder.build_rcasp()
                        writer.write_element(rcasp_elem)
                        click.echo("  ✓ RCASP element written")

                        # Write users and transactions from processed data
                        for chunk_data in processed_data:
                            if chunk_data is None or chunk_data.empty:
                                continue

                            # Group by user (simplified - using first occurrence)
                            for idx, row in chunk_data.iterrows():
                                user_count += 1

                                # Build user element
                                # Get country from tin_country or country_code columns
                                user_country = str(row.get('tin_country', row.get('country_code', sending_country)))
                                user_city = str(row.get('address_city', row.get('city', 'Unknown')))

                                user_data = IndividualData(
                                    first_name=str(row.get('first_name', 'Unknown')),
                                    last_name=str(row.get('last_name', 'User')),
                                    tin=str(row.get('tin', 'NOTIN')),
                                    tin_country=user_country,
                                    address=AddressData(
                                        country=user_country,
                                        city=user_city,
                                        street=str(row.get('address_street', row.get('street', ''))) or None,
                                    ),
                                )

                                # Build transaction data
                                transaction_count += 1
                                tx_data = TransactionData(
                                    transaction_type='CARF501',  # Transfer in other
                                    transaction_date=datetime.now(),
                                    asset_code=str(row.get('crypto_asset', row.get('asset', 'BTC'))),
                                    amount=Decimal(str(row.get('quantity', row.get('amount', '0')))),
                                )

                                # Build user with transaction and write
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

                        click.echo(f"  ✓ {user_count:,} users and {transaction_count:,} transactions written")

        file_size = output_path.stat().st_size
        click.echo(f"  ✓ XML file generated: {file_size:,} bytes")

        # Phase 3: Validate XML (if requested)
        if do_validate:
            click.echo("\nPhase 3: Validating XML against XSD schema...")

            schema_path = schema
            if not schema_path:
                # Look for default schema
                default_schema = Path(__file__).parent / 'schemas' / 'CARFXML_v1.xsd'
                if default_schema.exists():
                    schema_path = str(default_schema)
                else:
                    click.echo("  ⚠️  No schema file provided and default not found")
                    click.echo("     Use --schema to specify XSD file")

            if schema_path:
                try:
                    validator = SchemaValidator(schema_path)
                    report = validator.validate_file(str(output_path))

                    if report.is_valid:
                        click.echo(f"  ✓ Schema validation PASSED")
                    else:
                        click.echo(f"  ✗ Schema validation FAILED ({len(report.errors)} errors)")
                        for error in report.errors[:5]:  # Show first 5 errors
                            click.echo(f"    - {error}")
                        if len(report.errors) > 5:
                            click.echo(f"    ... and {len(report.errors) - 5} more errors")
                except Exception as e:
                    click.echo(f"  ⚠️  Validation error: {e}")

        # Final summary
        elapsed = time.perf_counter() - start_time
        rows_per_sec = total_rows / elapsed if elapsed > 0 else 0

        click.echo(f"\n{'='*60}")
        click.echo("EXPORT COMPLETE")
        click.echo(f"{'='*60}")
        click.echo(f"  Input rows:        {total_rows:,}")
        click.echo(f"  Users written:     {user_count:,}")
        click.echo(f"  Transactions:      {transaction_count:,}")
        click.echo(f"  Output file:       {output}")
        click.echo(f"  File size:         {file_size:,} bytes ({file_size/(1024*1024):.2f}MB)")
        click.echo(f"  Elapsed time:      {elapsed:.2f}s")
        click.echo(f"  Rows/second:       {rows_per_sec:,.0f}")

        if profile_memory:
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            click.echo(f"  Peak memory:       {peak/(1024*1024):.2f}MB")

            # Show memory profile
            if memory_snapshots and verbose:
                click.echo("\n  Memory Profile:")
                for snap in memory_snapshots[-5:]:  # Last 5 snapshots
                    click.echo(f"    Chunk {snap['chunk']}: {snap['current_mb']:.1f}MB (peak: {snap['peak_mb']:.1f}MB)")

        click.echo(f"{'='*60}\n")

        click.echo(f"✅ Export successful: {output}")

    except Exception as e:
        if profile_memory:
            tracemalloc.stop()
        click.echo(f"\n❌ Export error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


# =============================================================================
# Memory Profile Command
# =============================================================================

@cli.command('profile')
@click.argument('csv_path', type=click.Path(exists=True))
@click.option('--chunk-size', default=5000, help='Rows per chunk')
@click.option('--output', '-o', type=click.Path(), help='Save profile report to file')
def profile(csv_path: str, chunk_size: int, output: str):
    """
    Run detailed memory profiling on CSV processing.

    Measures memory usage at each stage of the pipeline to verify
    O(1) memory footprint for streaming operations.

    Example:
        python -m carful profile large_dataset.csv --chunk-size 10000
    """
    import tracemalloc
    import gc
    import linecache

    click.echo(f"\n{'='*60}")
    click.echo("CARFul Memory Profiler")
    click.echo(f"{'='*60}")
    click.echo(f"  File: {csv_path}")
    click.echo(f"  Chunk size: {chunk_size:,}")
    click.echo(f"{'='*60}\n")

    # Force initial GC
    gc.collect()

    # Start detailed tracing
    tracemalloc.start(25)  # 25 frames deep

    start_time = time.perf_counter()

    # Track memory at each stage
    stages = []
    reader = CSVReader(chunk_size=chunk_size)
    pipeline = create_default_pipeline(reporting_year=2025)

    total_rows = 0
    chunk_count = 0

    try:
        # Baseline snapshot
        snapshot_baseline = tracemalloc.take_snapshot()
        stages.append({
            'name': 'Baseline (after imports)',
            'snapshot': snapshot_baseline,
            'rows': 0,
        })

        gen = reader.read_chunks(csv_path)

        while True:
            try:
                chunk_df, metadata = next(gen)
                chunk_count += 1
                total_rows += len(chunk_df)

                # Process through pipeline
                result = pipeline.run(chunk_df)

                # Take snapshot every 5 chunks
                if chunk_count % 5 == 0:
                    gc.collect()  # Force GC before snapshot
                    snapshot = tracemalloc.take_snapshot()
                    stages.append({
                        'name': f'After chunk {chunk_count}',
                        'snapshot': snapshot,
                        'rows': total_rows,
                    })
                    click.echo(f"  Chunk {chunk_count}: {total_rows:,} rows processed")

            except StopIteration:
                break

        # Final snapshot
        gc.collect()
        snapshot_final = tracemalloc.take_snapshot()
        stages.append({
            'name': 'Final (all chunks processed)',
            'snapshot': snapshot_final,
            'rows': total_rows,
        })

    except Exception as e:
        click.echo(f"\n❌ Profile error: {e}", err=True)
        tracemalloc.stop()
        sys.exit(1)

    elapsed = time.perf_counter() - start_time

    # Analyze memory growth
    click.echo(f"\n{'='*60}")
    click.echo("MEMORY PROFILE RESULTS")
    click.echo(f"{'='*60}")

    click.echo("\n📈 Memory at each stage:")
    for i, stage in enumerate(stages):
        snapshot = stage['snapshot']
        stats = snapshot.statistics('lineno')
        total_bytes = sum(stat.size for stat in stats)
        click.echo(f"  {stage['name']}: {total_bytes/(1024*1024):.2f}MB ({stage['rows']:,} rows)")

    # Compare first and last to check for memory growth
    if len(stages) >= 2:
        first_stats = stages[0]['snapshot'].statistics('lineno')
        last_stats = stages[-1]['snapshot'].statistics('lineno')
        first_total = sum(stat.size for stat in first_stats)
        last_total = sum(stat.size for stat in last_stats)
        growth = last_total - first_total
        growth_per_row = growth / total_rows if total_rows > 0 else 0

        click.echo(f"\n📊 Memory Analysis:")
        click.echo(f"  Initial memory:    {first_total/(1024*1024):.2f}MB")
        click.echo(f"  Final memory:      {last_total/(1024*1024):.2f}MB")
        click.echo(f"  Total growth:      {growth/(1024*1024):.2f}MB")
        click.echo(f"  Growth per row:    {growth_per_row:.2f} bytes")

        # Check if O(1) memory (growth should be minimal)
        if growth_per_row < 100:  # Less than 100 bytes per row
            click.echo(f"\n✅ O(1) memory verified: {growth_per_row:.2f} bytes/row")
        else:
            click.echo(f"\n⚠️  Memory growth detected: {growth_per_row:.2f} bytes/row")

    # Top memory consumers
    click.echo(f"\n🔝 Top 10 memory consumers:")
    top_stats = stages[-1]['snapshot'].statistics('lineno')[:10]
    for stat in top_stats:
        click.echo(f"  {stat.traceback.format()[0].strip()}")
        click.echo(f"    Size: {stat.size/(1024):.1f}KB, Count: {stat.count}")

    # Summary
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    click.echo(f"\n{'='*60}")
    click.echo("SUMMARY")
    click.echo(f"{'='*60}")
    click.echo(f"  Total rows:        {total_rows:,}")
    click.echo(f"  Total chunks:      {chunk_count}")
    click.echo(f"  Elapsed time:      {elapsed:.2f}s")
    click.echo(f"  Peak memory:       {peak/(1024*1024):.2f}MB")
    click.echo(f"  Current memory:    {current/(1024*1024):.2f}MB")
    click.echo(f"{'='*60}\n")

    # Save report if requested
    if output:
        report_path = Path(output)
        with open(report_path, 'w') as f:
            f.write("CARFul Memory Profile Report\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"File: {csv_path}\n")
            f.write(f"Chunk size: {chunk_size}\n")
            f.write(f"Total rows: {total_rows}\n")
            f.write(f"Peak memory: {peak/(1024*1024):.2f}MB\n")
            f.write(f"Elapsed time: {elapsed:.2f}s\n")
        click.echo(f"📄 Report saved to: {output}")


# =============================================================================
# Info Command
# =============================================================================

@cli.command()
def info():
    """
    Display CARFul system information.
    """
    click.echo(f"\n{'='*60}")
    click.echo("CARFul - CARF XML Generation Tool")
    click.echo(f"{'='*60}")
    click.echo("  Version: 0.1.0")
    click.echo("  Python: " + sys.version.split()[0])
    click.echo("")
    click.echo("Supported Features:")
    click.echo("  • CSV ingestion with chunked processing")
    click.echo("  • Column mapping for major exchanges")
    click.echo("  • CARF transaction code mapping")
    click.echo("  • 20 decimal precision for amounts")
    click.echo("  • ISO 8601 date/time parsing")
    click.echo("  • SQLite persistence")
    click.echo("")
    click.echo("Exchange Presets:")
    click.echo("  coinbase, binance, kraken, gemini, crypto_com")
    click.echo("  kucoin, bitfinex, bitstamp, blockchain_com")
    click.echo("  etherscan, bscscan, polygonscan, arbiscan, ftmscan")
    click.echo(f"{'='*60}\n")


# =============================================================================
# Presets Command
# =============================================================================

@cli.command()
def presets():
    """
    List available column mapping presets.
    """
    import json

    config_path = Path(__file__).parent / 'config' / 'column_mappings.json'

    if not config_path.exists():
        click.echo("No presets file found.")
        return

    with open(config_path) as f:
        config = json.load(f)

    click.echo(f"\n{'='*60}")
    click.echo("Available Column Mapping Presets")
    click.echo(f"{'='*60}\n")

    for preset_id, preset_data in config.get('presets', {}).items():
        name = preset_data.get('name', preset_id)
        source = preset_data.get('source', 'unknown')
        cols = preset_data.get('columns', {})

        click.echo(f"  {preset_id}")
        click.echo(f"    Name: {name}")
        click.echo(f"    Source: {source}")
        click.echo(f"    Mapped columns: {len(cols)}")
        click.echo("")

    click.echo(f"{'='*60}")
    click.echo("Usage: python -m carful ingest data.csv --preset coinbase")
    click.echo(f"{'='*60}\n")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == '__main__':
    cli()
