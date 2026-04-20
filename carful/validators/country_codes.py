"""
CARFul - ISO 3166-1 Alpha-2 Country Code Validator

This module provides validation for country codes used in CARF XML Schema.
The CARF schema requires ISO 3166-1 Alpha-2 (2-character) codes.

IMPORTANT: Use 'GB' for United Kingdom, NOT 'UK'.
"""

from typing import Optional, Tuple
from enum import Enum


# Complete ISO 3166-1 Alpha-2 Country Codes
# Source: ISO 3166 Maintenance Agency (as of 2025)
ISO_3166_1_ALPHA_2: dict[str, str] = {
    # A
    "AD": "Andorra",
    "AE": "United Arab Emirates",
    "AF": "Afghanistan",
    "AG": "Antigua and Barbuda",
    "AI": "Anguilla",
    "AL": "Albania",
    "AM": "Armenia",
    "AO": "Angola",
    "AQ": "Antarctica",
    "AR": "Argentina",
    "AS": "American Samoa",
    "AT": "Austria",
    "AU": "Australia",
    "AW": "Aruba",
    "AX": "Åland Islands",
    "AZ": "Azerbaijan",
    # B
    "BA": "Bosnia and Herzegovina",
    "BB": "Barbados",
    "BD": "Bangladesh",
    "BE": "Belgium",
    "BF": "Burkina Faso",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "BI": "Burundi",
    "BJ": "Benin",
    "BL": "Saint Barthélemy",
    "BM": "Bermuda",
    "BN": "Brunei Darussalam",
    "BO": "Bolivia",
    "BQ": "Bonaire, Sint Eustatius and Saba",
    "BR": "Brazil",
    "BS": "Bahamas",
    "BT": "Bhutan",
    "BV": "Bouvet Island",
    "BW": "Botswana",
    "BY": "Belarus",
    "BZ": "Belize",
    # C
    "CA": "Canada",
    "CC": "Cocos (Keeling) Islands",
    "CD": "Congo, Democratic Republic of the",
    "CF": "Central African Republic",
    "CG": "Congo",
    "CH": "Switzerland",
    "CI": "Côte d'Ivoire",
    "CK": "Cook Islands",
    "CL": "Chile",
    "CM": "Cameroon",
    "CN": "China",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "CU": "Cuba",
    "CV": "Cabo Verde",
    "CW": "Curaçao",
    "CX": "Christmas Island",
    "CY": "Cyprus",
    "CZ": "Czechia",
    # D
    "DE": "Germany",
    "DJ": "Djibouti",
    "DK": "Denmark",
    "DM": "Dominica",
    "DO": "Dominican Republic",
    "DZ": "Algeria",
    # E
    "EC": "Ecuador",
    "EE": "Estonia",
    "EG": "Egypt",
    "EH": "Western Sahara",
    "ER": "Eritrea",
    "ES": "Spain",
    "ET": "Ethiopia",
    # F
    "FI": "Finland",
    "FJ": "Fiji",
    "FK": "Falkland Islands (Malvinas)",
    "FM": "Micronesia, Federated States of",
    "FO": "Faroe Islands",
    "FR": "France",
    # G
    "GA": "Gabon",
    "GB": "United Kingdom",  # NOTE: Use GB, not UK!
    "GD": "Grenada",
    "GE": "Georgia",
    "GF": "French Guiana",
    "GG": "Guernsey",
    "GH": "Ghana",
    "GI": "Gibraltar",
    "GL": "Greenland",
    "GM": "Gambia",
    "GN": "Guinea",
    "GP": "Guadeloupe",
    "GQ": "Equatorial Guinea",
    "GR": "Greece",
    "GS": "South Georgia and the South Sandwich Islands",
    "GT": "Guatemala",
    "GU": "Guam",
    "GW": "Guinea-Bissau",
    "GY": "Guyana",
    # H
    "HK": "Hong Kong",
    "HM": "Heard Island and McDonald Islands",
    "HN": "Honduras",
    "HR": "Croatia",
    "HT": "Haiti",
    "HU": "Hungary",
    # I
    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IM": "Isle of Man",
    "IN": "India",
    "IO": "British Indian Ocean Territory",
    "IQ": "Iraq",
    "IR": "Iran",
    "IS": "Iceland",
    "IT": "Italy",
    # J
    "JE": "Jersey",
    "JM": "Jamaica",
    "JO": "Jordan",
    "JP": "Japan",
    # K
    "KE": "Kenya",
    "KG": "Kyrgyzstan",
    "KH": "Cambodia",
    "KI": "Kiribati",
    "KM": "Comoros",
    "KN": "Saint Kitts and Nevis",
    "KP": "Korea, Democratic People's Republic of",
    "KR": "Korea, Republic of",
    "KW": "Kuwait",
    "KY": "Cayman Islands",
    "KZ": "Kazakhstan",
    # L
    "LA": "Lao People's Democratic Republic",
    "LB": "Lebanon",
    "LC": "Saint Lucia",
    "LI": "Liechtenstein",
    "LK": "Sri Lanka",
    "LR": "Liberia",
    "LS": "Lesotho",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "LY": "Libya",
    # M
    "MA": "Morocco",
    "MC": "Monaco",
    "MD": "Moldova",
    "ME": "Montenegro",
    "MF": "Saint Martin (French part)",
    "MG": "Madagascar",
    "MH": "Marshall Islands",
    "MK": "North Macedonia",
    "ML": "Mali",
    "MM": "Myanmar",
    "MN": "Mongolia",
    "MO": "Macao",
    "MP": "Northern Mariana Islands",
    "MQ": "Martinique",
    "MR": "Mauritania",
    "MS": "Montserrat",
    "MT": "Malta",
    "MU": "Mauritius",
    "MV": "Maldives",
    "MW": "Malawi",
    "MX": "Mexico",
    "MY": "Malaysia",
    "MZ": "Mozambique",
    # N
    "NA": "Namibia",
    "NC": "New Caledonia",
    "NE": "Niger",
    "NF": "Norfolk Island",
    "NG": "Nigeria",
    "NI": "Nicaragua",
    "NL": "Netherlands",
    "NO": "Norway",
    "NP": "Nepal",
    "NR": "Nauru",
    "NU": "Niue",
    "NZ": "New Zealand",
    # O
    "OM": "Oman",
    # P
    "PA": "Panama",
    "PE": "Peru",
    "PF": "French Polynesia",
    "PG": "Papua New Guinea",
    "PH": "Philippines",
    "PK": "Pakistan",
    "PL": "Poland",
    "PM": "Saint Pierre and Miquelon",
    "PN": "Pitcairn",
    "PR": "Puerto Rico",
    "PS": "Palestine, State of",
    "PT": "Portugal",
    "PW": "Palau",
    "PY": "Paraguay",
    # Q
    "QA": "Qatar",
    # R
    "RE": "Réunion",
    "RO": "Romania",
    "RS": "Serbia",
    "RU": "Russian Federation",
    "RW": "Rwanda",
    # S
    "SA": "Saudi Arabia",
    "SB": "Solomon Islands",
    "SC": "Seychelles",
    "SD": "Sudan",
    "SE": "Sweden",
    "SG": "Singapore",
    "SH": "Saint Helena, Ascension and Tristan da Cunha",
    "SI": "Slovenia",
    "SJ": "Svalbard and Jan Mayen",
    "SK": "Slovakia",
    "SL": "Sierra Leone",
    "SM": "San Marino",
    "SN": "Senegal",
    "SO": "Somalia",
    "SR": "Suriname",
    "SS": "South Sudan",
    "ST": "Sao Tome and Principe",
    "SV": "El Salvador",
    "SX": "Sint Maarten (Dutch part)",
    "SY": "Syrian Arab Republic",
    "SZ": "Eswatini",
    # T
    "TC": "Turks and Caicos Islands",
    "TD": "Chad",
    "TF": "French Southern Territories",
    "TG": "Togo",
    "TH": "Thailand",
    "TJ": "Tajikistan",
    "TK": "Tokelau",
    "TL": "Timor-Leste",
    "TM": "Turkmenistan",
    "TN": "Tunisia",
    "TO": "Tonga",
    "TR": "Türkiye",
    "TT": "Trinidad and Tobago",
    "TV": "Tuvalu",
    "TW": "Taiwan, Province of China",
    "TZ": "Tanzania, United Republic of",
    # U
    "UA": "Ukraine",
    "UG": "Uganda",
    "UM": "United States Minor Outlying Islands",
    "US": "United States of America",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    # V
    "VA": "Holy See",
    "VC": "Saint Vincent and the Grenadines",
    "VE": "Venezuela",
    "VG": "Virgin Islands (British)",
    "VI": "Virgin Islands (U.S.)",
    "VN": "Viet Nam",
    "VU": "Vanuatu",
    # W
    "WF": "Wallis and Futuna",
    "WS": "Samoa",
    # X - Reserved codes (not used in standard)
    # Y
    "YE": "Yemen",
    "YT": "Mayotte",
    # Z
    "ZA": "South Africa",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
}

# Common mistakes to catch
COMMON_ERRORS: dict[str, str] = {
    "UK": "GB",  # United Kingdom should be GB
    "ENG": None,  # England is not a country code
    "SCO": None,  # Scotland is not a country code
    "WAL": None,  # Wales is not a country code
    "NIR": None,  # Northern Ireland is not a country code
    "EN": None,  # Not a valid code
    "USA": "US",  # Should be 2 characters
    "CAN": "CA",  # Should be 2 characters
    "GER": "DE",  # Germany
    "FRA": "FR",  # France
    "ITA": "IT",  # Italy
    "ESP": "ES",  # Spain
    "POR": "PT",  # Portugal
    "NED": "NL",  # Netherlands
    "BEL": "BE",  # Belgium
    "SWI": "CH",  # Switzerland
    "AUS": "AU",  # Australia (not Austria!)
    "AUT": "AT",  # Austria
    "BRA": "BR",  # Brazil
    "CHN": "CN",  # China
    "JPN": "JP",  # Japan
    "KOR": "KR",  # South Korea
    "MEX": "MX",  # Mexico
    "RUS": "RU",  # Russia
    "IND": "IN",  # India
}


def is_valid_country_code(code: str) -> bool:
    """
    Check if a country code is a valid ISO 3166-1 Alpha-2 code.

    Args:
        code: The country code to validate

    Returns:
        True if valid, False otherwise
    """
    if not code or not isinstance(code, str):
        return False

    return code.upper().strip() in ISO_3166_1_ALPHA_2


def validate_country_code(code: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate a country code and provide feedback.

    Args:
        code: The country code to validate

    Returns:
        Tuple of (is_valid, corrected_code, error_message)
        - is_valid: Whether the code is valid
        - corrected_code: Suggested correction if invalid but correctable
        - error_message: Human-readable error if invalid
    """
    if not code or not isinstance(code, str):
        return (False, None, "Country code is required")

    normalized = code.upper().strip()

    # Check if it's already valid
    if normalized in ISO_3166_1_ALPHA_2:
        return (True, normalized, None)

    # Check for common mistakes
    if normalized in COMMON_ERRORS:
        suggestion = COMMON_ERRORS[normalized]
        if suggestion:
            return (
                False,
                suggestion,
                f"'{code}' is not valid. Did you mean '{suggestion}' ({ISO_3166_1_ALPHA_2[suggestion]})?",
            )
        else:
            return (False, None, f"'{code}' is not a valid ISO 3166-1 Alpha-2 country code")

    # Check length
    if len(normalized) != 2:
        return (
            False,
            None,
            f"Country code must be exactly 2 characters, got {len(normalized)}",
        )

    # Unknown code
    return (False, None, f"'{code}' is not a recognized ISO 3166-1 Alpha-2 country code")


def get_country_name(code: str) -> Optional[str]:
    """
    Get the country name for a valid country code.

    Args:
        code: ISO 3166-1 Alpha-2 country code

    Returns:
        Country name or None if invalid
    """
    if not code:
        return None
    return ISO_3166_1_ALPHA_2.get(code.upper().strip())


def get_all_codes() -> list[str]:
    """
    Get all valid ISO 3166-1 Alpha-2 country codes.

    Returns:
        Sorted list of all valid country codes
    """
    return sorted(ISO_3166_1_ALPHA_2.keys())


def generate_sql_insert_statements() -> str:
    """
    Generate SQL INSERT statements for the country_codes table.

    Returns:
        SQL string with INSERT statements
    """
    lines = ["-- ISO 3166-1 Alpha-2 Country Codes", "-- Auto-generated for CARFul", ""]
    lines.append("INSERT INTO country_codes (code, name, is_active) VALUES")

    values = []
    for code in sorted(ISO_3166_1_ALPHA_2.keys()):
        name = ISO_3166_1_ALPHA_2[code].replace("'", "''")  # Escape quotes
        values.append(f"    ('{code}', '{name}', 1)")

    lines.append(",\n".join(values) + ";")

    return "\n".join(lines)


# Pre-computed set for fast lookup
VALID_CODES_SET: frozenset[str] = frozenset(ISO_3166_1_ALPHA_2.keys())


if __name__ == "__main__":
    # Generate SQL for database seeding
    print(generate_sql_insert_statements())
