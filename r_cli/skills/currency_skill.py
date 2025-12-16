"""
Currency Skill for R CLI.

Currency utilities:
- Convert between currencies
- Get exchange rates
- Uses free APIs (no key required)
"""

import json
import urllib.request
import urllib.error
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class CurrencySkill(Skill):
    """Skill for currency operations."""

    name = "currency"
    description = "Currency: convert, exchange rates"

    # Common currency codes
    CURRENCIES = {
        "USD": "US Dollar", "EUR": "Euro", "GBP": "British Pound",
        "JPY": "Japanese Yen", "CHF": "Swiss Franc", "CAD": "Canadian Dollar",
        "AUD": "Australian Dollar", "CNY": "Chinese Yuan", "INR": "Indian Rupee",
        "MXN": "Mexican Peso", "BRL": "Brazilian Real", "KRW": "South Korean Won",
        "SGD": "Singapore Dollar", "HKD": "Hong Kong Dollar", "NOK": "Norwegian Krone",
        "SEK": "Swedish Krona", "DKK": "Danish Krone", "NZD": "New Zealand Dollar",
        "ZAR": "South African Rand", "RUB": "Russian Ruble", "TRY": "Turkish Lira",
        "PLN": "Polish Zloty", "THB": "Thai Baht", "IDR": "Indonesian Rupiah",
        "MYR": "Malaysian Ringgit", "PHP": "Philippine Peso", "CZK": "Czech Koruna",
        "ILS": "Israeli Shekel", "CLP": "Chilean Peso", "AED": "UAE Dirham",
    }

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="currency_convert",
                description="Convert amount between currencies",
                parameters={
                    "type": "object",
                    "properties": {
                        "amount": {
                            "type": "number",
                            "description": "Amount to convert",
                        },
                        "from_currency": {
                            "type": "string",
                            "description": "Source currency code (e.g., USD)",
                        },
                        "to_currency": {
                            "type": "string",
                            "description": "Target currency code (e.g., EUR)",
                        },
                    },
                    "required": ["amount", "from_currency", "to_currency"],
                },
                handler=self.currency_convert,
            ),
            Tool(
                name="currency_rates",
                description="Get exchange rates for a base currency",
                parameters={
                    "type": "object",
                    "properties": {
                        "base": {
                            "type": "string",
                            "description": "Base currency code (default: USD)",
                        },
                        "targets": {
                            "type": "string",
                            "description": "Comma-separated target currencies (optional)",
                        },
                    },
                },
                handler=self.currency_rates,
            ),
            Tool(
                name="currency_list",
                description="List available currency codes",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.currency_list,
            ),
        ]

    def _fetch_rates(self, base: str = "USD") -> tuple[bool, dict]:
        """Fetch exchange rates from free API."""
        try:
            # Using exchangerate.host (free, no API key)
            url = f"https://api.exchangerate.host/latest?base={base.upper()}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "R-CLI/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                if data.get("success", True):
                    return True, data.get("rates", {})
                return False, {}
        except Exception:
            pass

        # Fallback: frankfurter.app (also free)
        try:
            url = f"https://api.frankfurter.app/latest?from={base.upper()}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "R-CLI/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                rates = data.get("rates", {})
                rates[base.upper()] = 1.0
                return True, rates
        except Exception as e:
            return False, {"error": str(e)}

    def currency_convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
    ) -> str:
        """Convert between currencies."""
        try:
            from_curr = from_currency.upper()
            to_curr = to_currency.upper()

            success, rates = self._fetch_rates(from_curr)
            if not success:
                return f"Error fetching rates: {rates.get('error', 'Unknown error')}"

            if to_curr not in rates:
                return f"Currency not found: {to_curr}"

            rate = rates[to_curr]
            converted = amount * rate

            return json.dumps({
                "amount": amount,
                "from": from_curr,
                "to": to_curr,
                "rate": round(rate, 6),
                "result": round(converted, 2),
                "formatted": f"{amount:,.2f} {from_curr} = {converted:,.2f} {to_curr}",
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def currency_rates(
        self,
        base: str = "USD",
        targets: Optional[str] = None,
    ) -> str:
        """Get exchange rates."""
        try:
            success, rates = self._fetch_rates(base.upper())
            if not success:
                return f"Error fetching rates: {rates.get('error', 'Unknown error')}"

            if targets:
                target_list = [t.strip().upper() for t in targets.split(",")]
                rates = {k: v for k, v in rates.items() if k in target_list}
            else:
                # Show common currencies
                common = ["EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY", "INR", "MXN", "BRL"]
                rates = {k: v for k, v in rates.items() if k in common}

            # Round rates
            rates = {k: round(v, 4) for k, v in sorted(rates.items())}

            return json.dumps({
                "base": base.upper(),
                "rates": rates,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def currency_list(self) -> str:
        """List currencies."""
        return json.dumps(self.CURRENCIES, indent=2)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "rates")
        if action == "rates":
            return self.currency_rates()
        elif action == "convert":
            return self.currency_convert(
                kwargs.get("amount", 1),
                kwargs.get("from", "USD"),
                kwargs.get("to", "EUR"),
            )
        return f"Unknown action: {action}"
