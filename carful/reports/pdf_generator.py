"""
CARFul - PDF Health Check Report Generator

Generates professional PDF reports for data health check results using reportlab.
Features:
- Cover page with branding
- Executive summary with compliance score gauge
- TIN validation breakdown by country
- Transaction analysis with charts
- Recommendations section
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import io

# ReportLab imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image,
    HRFlowable,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Circle, Wedge
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF

logger = logging.getLogger(__name__)

# Brand colors
CARFUL_BLUE = colors.HexColor('#0284c7')
CARFUL_DARK = colors.HexColor('#0c4a6e')
SUCCESS_GREEN = colors.HexColor('#22c55e')
WARNING_ORANGE = colors.HexColor('#f59e0b')
ERROR_RED = colors.HexColor('#ef4444')
GRAY_600 = colors.HexColor('#4b5563')
GRAY_400 = colors.HexColor('#9ca3af')
GRAY_200 = colors.HexColor('#e5e7eb')


class PDFHealthCheckReport:
    """
    Generate professional PDF health check reports.
    """

    def __init__(self, health_check_result: Dict[str, Any], company_name: Optional[str] = None):
        """
        Initialize the PDF generator with health check results.

        Args:
            health_check_result: Results from the health.check RPC method
            company_name: Optional company name for the report header
        """
        self.result = health_check_result
        self.company_name = company_name or "Your Company"
        self.page_count = 0
        self.styles = self._create_styles()

    def _create_styles(self) -> Dict[str, ParagraphStyle]:
        """Create custom paragraph styles for the report."""
        base_styles = getSampleStyleSheet()

        return {
            'title': ParagraphStyle(
                'CustomTitle',
                parent=base_styles['Heading1'],
                fontSize=28,
                textColor=CARFUL_DARK,
                spaceAfter=12,
                alignment=TA_CENTER,
            ),
            'subtitle': ParagraphStyle(
                'CustomSubtitle',
                parent=base_styles['Normal'],
                fontSize=14,
                textColor=GRAY_600,
                spaceAfter=24,
                alignment=TA_CENTER,
            ),
            'heading1': ParagraphStyle(
                'CustomH1',
                parent=base_styles['Heading1'],
                fontSize=18,
                textColor=CARFUL_DARK,
                spaceBefore=20,
                spaceAfter=12,
            ),
            'heading2': ParagraphStyle(
                'CustomH2',
                parent=base_styles['Heading2'],
                fontSize=14,
                textColor=CARFUL_BLUE,
                spaceBefore=16,
                spaceAfter=8,
            ),
            'body': ParagraphStyle(
                'CustomBody',
                parent=base_styles['Normal'],
                fontSize=10,
                textColor=GRAY_600,
                spaceAfter=8,
                leading=14,
            ),
            'body_bold': ParagraphStyle(
                'CustomBodyBold',
                parent=base_styles['Normal'],
                fontSize=10,
                textColor=colors.black,
                spaceAfter=8,
                leading=14,
                fontName='Helvetica-Bold',
            ),
            'footer': ParagraphStyle(
                'CustomFooter',
                parent=base_styles['Normal'],
                fontSize=8,
                textColor=GRAY_400,
                alignment=TA_CENTER,
            ),
            'score_large': ParagraphStyle(
                'ScoreLarge',
                parent=base_styles['Normal'],
                fontSize=48,
                textColor=CARFUL_BLUE,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
            ),
            'grade': ParagraphStyle(
                'Grade',
                parent=base_styles['Normal'],
                fontSize=72,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
            ),
        }

    def _create_score_gauge(self, score: int, width: float = 200, height: float = 120) -> Drawing:
        """Create a semi-circular gauge showing compliance score."""
        drawing = Drawing(width, height)

        # Determine color based on score
        if score >= 90:
            score_color = SUCCESS_GREEN
        elif score >= 70:
            score_color = WARNING_ORANGE
        else:
            score_color = ERROR_RED

        # Background arc (gray)
        cx, cy = width / 2, height - 20
        radius = 70

        # Draw background arc
        for i in range(180):
            angle = 180 - i
            x1 = cx + radius * 0.85 * __import__('math').cos(__import__('math').radians(angle))
            y1 = cy + radius * 0.85 * __import__('math').sin(__import__('math').radians(angle))
            x2 = cx + radius * __import__('math').cos(__import__('math').radians(angle))
            y2 = cy + radius * __import__('math').sin(__import__('math').radians(angle))

        # Simplified gauge - just show score text and colored bar
        # Background bar
        drawing.add(Rect(20, height - 40, width - 40, 20, fillColor=GRAY_200, strokeColor=None))

        # Score bar
        bar_width = (width - 40) * (score / 100)
        drawing.add(Rect(20, height - 40, bar_width, 20, fillColor=score_color, strokeColor=None))

        # Score text
        drawing.add(String(width / 2, 30, f"{score}%",
                          fontSize=24, fontName='Helvetica-Bold',
                          fillColor=score_color, textAnchor='middle'))

        return drawing

    def _create_pie_chart(self, data: List[tuple], width: float = 200, height: float = 150) -> Drawing:
        """Create a pie chart for data distribution."""
        drawing = Drawing(width, height)

        pie = Pie()
        pie.x = 50
        pie.y = 20
        pie.width = 100
        pie.height = 100
        pie.data = [d[1] for d in data if d[1] > 0]
        pie.labels = [d[0] for d in data if d[1] > 0]

        pie_colors = [SUCCESS_GREEN, WARNING_ORANGE, ERROR_RED, CARFUL_BLUE, GRAY_400]
        for i, _ in enumerate(pie.data):
            pie.slices[i].fillColor = pie_colors[i % len(pie_colors)]
            pie.slices[i].strokeColor = colors.white
            pie.slices[i].strokeWidth = 1

        drawing.add(pie)
        return drawing

    def _create_bar_chart(self, data: Dict[str, int], width: float = 400, height: float = 150) -> Drawing:
        """Create a bar chart for country breakdown."""
        drawing = Drawing(width, height)

        if not data:
            drawing.add(String(width / 2, height / 2, "No data available",
                              fontSize=10, fillColor=GRAY_400, textAnchor='middle'))
            return drawing

        bc = VerticalBarChart()
        bc.x = 50
        bc.y = 30
        bc.height = height - 60
        bc.width = width - 100
        bc.data = [list(data.values())]
        bc.categoryAxis.categoryNames = list(data.keys())
        bc.categoryAxis.labels.fontName = 'Helvetica'
        bc.categoryAxis.labels.fontSize = 8
        bc.valueAxis.valueMin = 0
        bc.valueAxis.labels.fontName = 'Helvetica'
        bc.valueAxis.labels.fontSize = 8
        bc.bars[0].fillColor = CARFUL_BLUE

        drawing.add(bc)
        return drawing

    def _build_cover_page(self) -> List:
        """Build the cover page elements."""
        elements = []

        # Add spacer for top margin
        elements.append(Spacer(1, 2 * inch))

        # Title
        elements.append(Paragraph("CARF Data Health Check", self.styles['title']))
        elements.append(Paragraph("Compliance Assessment Report", self.styles['subtitle']))

        elements.append(Spacer(1, 0.5 * inch))

        # Company name
        elements.append(Paragraph(
            f"<b>Prepared for:</b> {self.company_name}",
            self.styles['body']
        ))

        # Date
        elements.append(Paragraph(
            f"<b>Report Date:</b> {datetime.now().strftime('%B %d, %Y')}",
            self.styles['body']
        ))

        elements.append(Spacer(1, 1 * inch))

        # Compliance Score Box
        score = self.result.get('score', 0)
        grade = self._get_grade(score)

        # Create score display
        score_table_data = [
            [Paragraph("Compliance Score", self.styles['heading2'])],
            [Paragraph(f"{score}%", self.styles['score_large'])],
            [Paragraph(f"Grade: {grade}", self.styles['body_bold'])],
        ]

        score_table = Table(score_table_data, colWidths=[3 * inch])
        score_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 2, CARFUL_BLUE),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f9ff')),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))

        elements.append(score_table)

        elements.append(Spacer(1, 1.5 * inch))

        # Footer
        elements.append(HRFlowable(width="80%", thickness=1, color=GRAY_200))
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Paragraph(
            "Generated by CARFul - CARF Compliance Tool",
            self.styles['footer']
        ))
        elements.append(Paragraph(
            "All data processed locally • No cloud transmission",
            self.styles['footer']
        ))

        elements.append(PageBreak())
        return elements

    def _build_executive_summary(self) -> List:
        """Build the executive summary section."""
        elements = []

        elements.append(Paragraph("Executive Summary", self.styles['heading1']))
        elements.append(HRFlowable(width="100%", thickness=1, color=CARFUL_BLUE))
        elements.append(Spacer(1, 0.2 * inch))

        summary = self.result.get('summary', {})
        score = self.result.get('score', 0)
        errors = self.result.get('errors', [])
        warnings = self.result.get('warnings', [])

        # Score gauge
        gauge = self._create_score_gauge(score)
        elements.append(gauge)
        elements.append(Spacer(1, 0.3 * inch))

        # Status message
        if score >= 90:
            status_msg = "Your data is in excellent shape and ready for CARF filing."
            status_color = SUCCESS_GREEN
        elif score >= 70:
            status_msg = "Your data has some issues that should be addressed before filing."
            status_color = WARNING_ORANGE
        else:
            status_msg = "Significant issues found. Please review and correct before filing."
            status_color = ERROR_RED

        elements.append(Paragraph(
            f'<font color="#{status_color.hexval()[2:]}">{status_msg}</font>',
            self.styles['body_bold']
        ))

        elements.append(Spacer(1, 0.3 * inch))

        # Summary stats table
        stats_data = [
            ['Metric', 'Value'],
            ['Total Records', f"{summary.get('total_records', 0):,}"],
            ['Unique Users', f"{summary.get('unique_users', 0):,}"],
            ['Valid TINs', f"{summary.get('valid_tins', 0)}%"],
            ['Mapped Transaction Codes', f"{summary.get('mapped_codes', 0)}%"],
            ['Critical Issues', str(len(errors))],
            ['Warnings', str(len(warnings))],
        ]

        stats_table = Table(stats_data, colWidths=[2.5 * inch, 2 * inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), CARFUL_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, GRAY_200),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))

        elements.append(stats_table)
        elements.append(PageBreak())

        return elements

    def _build_tin_validation_section(self) -> List:
        """Build the TIN validation breakdown section."""
        elements = []

        elements.append(Paragraph("TIN Validation Results", self.styles['heading1']))
        elements.append(HRFlowable(width="100%", thickness=1, color=CARFUL_BLUE))
        elements.append(Spacer(1, 0.2 * inch))

        validation = self.result.get('validation', {})
        valid = validation.get('valid', 0)
        invalid = validation.get('invalid', 0)
        notin = validation.get('notin', 0)
        total = valid + invalid + notin

        # TIN summary pie chart
        if total > 0:
            pie_data = [
                ('Valid', valid),
                ('Invalid', invalid),
                ('NOTIN', notin),
            ]
            pie_chart = self._create_pie_chart(pie_data)
            elements.append(pie_chart)

        elements.append(Spacer(1, 0.2 * inch))

        # TIN breakdown table
        tin_data = [
            ['Status', 'Count', 'Percentage'],
            ['Valid TINs', f"{valid:,}", f"{(valid/total*100):.1f}%" if total > 0 else "0%"],
            ['Invalid TINs', f"{invalid:,}", f"{(invalid/total*100):.1f}%" if total > 0 else "0%"],
            ['NOTIN (Missing)', f"{notin:,}", f"{(notin/total*100):.1f}%" if total > 0 else "0%"],
            ['Total', f"{total:,}", "100%"],
        ]

        tin_table = Table(tin_data, colWidths=[2 * inch, 1.5 * inch, 1.5 * inch])
        tin_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), CARFUL_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, GRAY_200),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f9ff')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        elements.append(tin_table)
        elements.append(Spacer(1, 0.3 * inch))

        # Country breakdown
        country_breakdown = validation.get('by_country', {})
        if country_breakdown:
            elements.append(Paragraph("TIN Validation by Country", self.styles['heading2']))

            bar_chart = self._create_bar_chart(country_breakdown)
            elements.append(bar_chart)

        # Invalid TIN list (first 20)
        # Use dedicated tin_errors list from health check (preferred) or fall back
        tin_errors = self.result.get('tin_errors', [])[:20]
        if not tin_errors:
            all_errors = self.result.get('errors', [])
            tin_errors = [e for e in all_errors if 'tin' in e.get('type', '').lower()][:20]

        if tin_errors:
            elements.append(Paragraph("Invalid TINs (First 20)", self.styles['heading2']))

            error_data = [['Row', 'TIN', 'Country', 'Issue']]
            for err in tin_errors:
                error_data.append([
                    str(err.get('row', '-')),
                    err.get('tin', '-'),
                    err.get('country', '-'),
                    err.get('message', '-')[:40],
                ])

            error_table = Table(error_data, colWidths=[0.6 * inch, 1.2 * inch, 0.8 * inch, 2.5 * inch])
            error_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), ERROR_RED),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY_200),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fef2f2')]),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))

            elements.append(error_table)

        elements.append(PageBreak())
        return elements

    def _build_recommendations_section(self) -> List:
        """Build the recommendations section."""
        elements = []

        elements.append(Paragraph("Recommendations", self.styles['heading1']))
        elements.append(HRFlowable(width="100%", thickness=1, color=CARFUL_BLUE))
        elements.append(Spacer(1, 0.2 * inch))

        score = self.result.get('score', 0)
        errors = self.result.get('errors', [])
        warnings = self.result.get('warnings', [])

        recommendations = []

        # Priority recommendations based on issues found
        if any('tin' in str(e).lower() for e in errors):
            recommendations.append({
                'priority': 'High',
                'title': 'Fix Invalid TINs',
                'description': 'Review and correct Tax Identification Numbers that failed validation. '
                              'Ensure TIN formats match the expected pattern for each jurisdiction.',
            })

        validation = self.result.get('validation', {})
        if validation.get('notin', 0) > 0:
            recommendations.append({
                'priority': 'Medium',
                'title': 'Review NOTIN Entries',
                'description': 'Verify that all NOTIN (missing TIN) entries have valid reasons '
                              'documented. NOTIN should only be used when TIN is genuinely unavailable.',
            })

        if any('mapping' in str(w).lower() or 'code' in str(w).lower() for w in warnings):
            recommendations.append({
                'priority': 'Medium',
                'title': 'Review Transaction Mappings',
                'description': 'Some transactions could not be mapped to CARF codes. '
                              'Review your transaction type mappings and update as needed.',
            })

        # General recommendations
        recommendations.append({
            'priority': 'Low',
            'title': 'Regular Data Validation',
            'description': 'Run health checks regularly before filing deadlines to catch issues early.',
        })

        if score >= 90:
            recommendations.append({
                'priority': 'Info',
                'title': 'Ready for Filing',
                'description': 'Your data meets quality standards. Proceed with XML export when ready.',
            })

        # Build recommendations table
        priority_colors = {
            'High': ERROR_RED,
            'Medium': WARNING_ORANGE,
            'Low': CARFUL_BLUE,
            'Info': SUCCESS_GREEN,
        }

        for rec in recommendations:
            color = priority_colors.get(rec['priority'], GRAY_400)

            rec_data = [[
                Paragraph(f'<font color="#{color.hexval()[2:]}"><b>{rec["priority"]}</b></font>', self.styles['body']),
                Paragraph(f'<b>{rec["title"]}</b>', self.styles['body_bold']),
            ], [
                '',
                Paragraph(rec['description'], self.styles['body']),
            ]]

            rec_table = Table(rec_data, colWidths=[0.8 * inch, 5 * inch])
            rec_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (0, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))

            elements.append(rec_table)
            elements.append(Spacer(1, 0.1 * inch))

        return elements

    def _build_transaction_analysis_section(self) -> List:
        """Build the transaction code analysis section."""
        elements = []

        elements.append(Paragraph("Transaction Code Analysis", self.styles['heading1']))
        elements.append(HRFlowable(width="100%", thickness=1, color=CARFUL_BLUE))
        elements.append(Spacer(1, 0.2 * inch))

        tx = self.result.get('transaction_analysis', {})
        mapped = tx.get('mapped', 0)
        unmapped = tx.get('unmapped', 0)
        total = tx.get('total', mapped + unmapped)
        mapped_pct = tx.get('mapped_pct', 0)

        # Mapping summary
        elements.append(Paragraph(
            f"Of <b>{total:,}</b> transactions, <b>{mapped:,}</b> ({mapped_pct}%) were "
            f"successfully mapped to CARF codes and <b>{unmapped:,}</b> could not be mapped.",
            self.styles['body']
        ))
        elements.append(Spacer(1, 0.2 * inch))

        # Mapping pie chart
        if total > 0:
            pie_data = [
                ('Mapped', mapped),
                ('Unmapped', unmapped),
            ]
            pie_chart = self._create_pie_chart(pie_data)
            elements.append(pie_chart)
            elements.append(Spacer(1, 0.2 * inch))

        # CARF code distribution bar chart
        code_dist = tx.get('code_distribution', {})
        if code_dist:
            elements.append(Paragraph("CARF Code Distribution", self.styles['heading2']))

            # Limit to top 12 codes for readability
            sorted_codes = sorted(code_dist.items(), key=lambda x: x[1], reverse=True)[:12]
            top_codes = dict(sorted_codes)

            bar_chart = self._create_bar_chart(top_codes, width=450, height=160)
            elements.append(bar_chart)
            elements.append(Spacer(1, 0.2 * inch))

        # Unmapped transaction samples
        unmapped_samples = tx.get('unmapped_samples', [])
        if unmapped_samples:
            elements.append(Paragraph("Unmapped Transactions (Samples)", self.styles['heading2']))

            sample_data = [['Row', 'Description', 'Issue']]
            for sample in unmapped_samples[:10]:
                sample_data.append([
                    str(sample.get('row', '-')),
                    str(sample.get('description', '-'))[:45],
                    str(sample.get('message', '-'))[:35],
                ])

            sample_table = Table(sample_data, colWidths=[0.6 * inch, 3.2 * inch, 2.5 * inch])
            sample_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), WARNING_ORANGE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY_200),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fffbeb')]),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))

            elements.append(sample_table)

        elements.append(PageBreak())
        return elements

    def _build_data_quality_section(self) -> List:
        """Build the data quality issues section."""
        elements = []

        elements.append(Paragraph("Data Quality", self.styles['heading1']))
        elements.append(HRFlowable(width="100%", thickness=1, color=CARFUL_BLUE))
        elements.append(Spacer(1, 0.2 * inch))

        dq = self.result.get('data_quality', {})
        issues = dq.get('issues', [])
        quality_score = dq.get('quality_score', 100)

        # Quality score bar
        elements.append(Paragraph(
            f"Data Quality Score: <b>{quality_score}%</b>",
            self.styles['body_bold']
        ))

        gauge = self._create_score_gauge(int(quality_score), width=180, height=80)
        elements.append(gauge)
        elements.append(Spacer(1, 0.2 * inch))

        if not issues:
            elements.append(Paragraph(
                "No data quality issues detected. All fields pass format and completeness checks.",
                self.styles['body']
            ))
        else:
            elements.append(Paragraph(
                f"Found <b>{len(issues)}</b> data quality issue(s):",
                self.styles['body']
            ))
            elements.append(Spacer(1, 0.1 * inch))

            # Issues table
            issue_data = [['Type', 'Details', 'Count']]
            type_labels = {
                'missing_values': 'Missing Values',
                'precision_overflow': 'Precision Overflow',
                'duplicate_ids': 'Duplicate IDs',
                'encoding_issues': 'Encoding Issues',
            }

            for issue in issues:
                issue_type = type_labels.get(issue.get('type', ''), issue.get('type', 'Unknown'))
                issue_data.append([
                    issue_type,
                    str(issue.get('message', '-'))[:50],
                    str(issue.get('count', '-')),
                ])

            issue_table = Table(issue_data, colWidths=[1.5 * inch, 3.5 * inch, 1 * inch])
            issue_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), CARFUL_DARK),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY_200),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))

            elements.append(issue_table)

        elements.append(PageBreak())
        return elements

    def _build_data_overview_section(self) -> List:
        """Build the data overview section with key metrics."""
        elements = []

        elements.append(Paragraph("Data Overview", self.styles['heading1']))
        elements.append(HRFlowable(width="100%", thickness=1, color=CARFUL_BLUE))
        elements.append(Spacer(1, 0.2 * inch))

        summary = self.result.get('summary', {})
        breakdown = self.result.get('score_breakdown', {})

        # Overview stats table
        file_size = summary.get('file_size', 0)
        if file_size > 1_048_576:
            file_size_str = f"{file_size / 1_048_576:.1f} MB"
        elif file_size > 1024:
            file_size_str = f"{file_size / 1024:.1f} KB"
        else:
            file_size_str = f"{file_size} bytes"

        date_start = summary.get('date_range_start', 'N/A')
        date_end = summary.get('date_range_end', 'N/A')
        date_range = f"{date_start} to {date_end}" if date_start and date_end and date_start != 'N/A' else 'Not available'

        overview_data = [
            ['Metric', 'Value'],
            ['Total Records', f"{summary.get('total_records', 0):,}"],
            ['Unique Users', f"{summary.get('unique_users', 0):,}"],
            ['Date Range', date_range],
            ['File Size', file_size_str],
            ['Processing Time', f"{summary.get('processing_time', 0)}s"],
            ['Columns Detected', str(len(summary.get('columns', [])))],
        ]

        overview_table = Table(overview_data, colWidths=[2.5 * inch, 3.5 * inch])
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), CARFUL_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, GRAY_200),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))

        elements.append(overview_table)
        elements.append(Spacer(1, 0.3 * inch))

        # Score breakdown
        if breakdown:
            elements.append(Paragraph("Score Breakdown", self.styles['heading2']))
            elements.append(Paragraph(
                "The overall compliance score is a weighted average of four categories:",
                self.styles['body']
            ))
            elements.append(Spacer(1, 0.1 * inch))

            score_data = [
                ['Category', 'Score', 'Weight'],
                ['TIN Validation', f"{breakdown.get('tin_validation', 0)}%", '40%'],
                ['Code Mapping', f"{breakdown.get('code_mapping', 0)}%", '25%'],
                ['Required Columns', f"{breakdown.get('required_columns', 0)}%", '15%'],
                ['Data Quality', f"{breakdown.get('data_quality', 0)}%", '20%'],
            ]

            score_table = Table(score_data, colWidths=[2.5 * inch, 1.5 * inch, 1 * inch])
            score_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), CARFUL_DARK),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, GRAY_200),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f9ff')]),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))

            elements.append(score_table)

        elements.append(PageBreak())
        return elements

    def _build_upgrade_cta_section(self) -> List:
        """Build the CARFul Pro upgrade call-to-action section."""
        elements = []

        elements.append(Spacer(1, 0.3 * inch))
        elements.append(HRFlowable(width="100%", thickness=1, color=GRAY_200))
        elements.append(Spacer(1, 0.3 * inch))

        elements.append(Paragraph("Upgrade to CARFul Pro", self.styles['heading1']))
        elements.append(Spacer(1, 0.1 * inch))

        elements.append(Paragraph(
            "Unlock advanced features to streamline your CARF compliance workflow:",
            self.styles['body']
        ))
        elements.append(Spacer(1, 0.15 * inch))

        # Feature comparison table
        feature_data = [
            ['Feature', 'Free', 'Pro'],
            ['Health Check Reports', 'Yes', 'Yes'],
            ['CSV Import & Validation', 'Yes', 'Yes'],
            ['XML Export (Single Entity)', 'Yes', 'Yes'],
            ['Multi-Entity Management', '-', 'Yes'],
            ['Batch Folder Processing', '-', 'Yes'],
            ['Automated Scheduling', '-', 'Yes'],
            ['Priority Support', '-', 'Yes'],
            ['White-Label Branding', '-', 'Yes'],
        ]

        feature_table = Table(feature_data, colWidths=[3 * inch, 1.25 * inch, 1.25 * inch])
        feature_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), CARFUL_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, GRAY_200),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f9ff')]),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ]))

        elements.append(feature_table)
        elements.append(Spacer(1, 0.3 * inch))

        elements.append(Paragraph(
            "Contact us to learn more about CARFul Pro licensing.",
            self.styles['body_bold']
        ))
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(HRFlowable(width="80%", thickness=1, color=GRAY_200))
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph(
            "Generated by CARFul - CARF Compliance Tool  |  All data processed locally",
            self.styles['footer']
        ))

        return elements

    def _get_grade(self, score: int) -> str:
        """Get letter grade from score."""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        return 'F'

    def generate(self, output_path: str) -> None:
        """
        Generate the PDF report.

        Args:
            output_path: Path to save the PDF file
        """
        output = Path(output_path)

        # Create document
        doc = SimpleDocTemplate(
            str(output),
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build content
        elements = []
        elements.extend(self._build_cover_page())
        elements.extend(self._build_executive_summary())
        elements.extend(self._build_data_overview_section())
        elements.extend(self._build_tin_validation_section())
        elements.extend(self._build_transaction_analysis_section())
        elements.extend(self._build_data_quality_section())
        elements.extend(self._build_recommendations_section())
        elements.extend(self._build_upgrade_cta_section())

        # Build PDF
        doc.build(elements)

        # Count pages (approximate)
        self.page_count = 8  # Cover + Summary + Overview + TIN + Tx Analysis + Quality + Recs + CTA

        logger.info(f"Health check PDF report saved to {output}")


def generate_health_check_pdf(
    health_check_result: Dict[str, Any],
    output_path: str,
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function to generate a health check PDF.

    Args:
        health_check_result: Results from health.check RPC
        output_path: Where to save the PDF
        company_name: Optional company name for the report

    Returns:
        Dict with file path and page count
    """
    generator = PDFHealthCheckReport(health_check_result, company_name)
    generator.generate(output_path)

    return {
        'file': output_path,
        'pages': generator.page_count,
    }
