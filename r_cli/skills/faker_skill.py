"""
Faker Skill for R CLI.

Random data generation:
- Names, emails, addresses
- Phone numbers, dates
- Lorem ipsum, sentences
- Custom patterns
"""

import json
import random
import string
from datetime import datetime, timedelta
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class FakerSkill(Skill):
    """Skill for generating fake data."""

    name = "faker"
    description = "Faker: generate random names, emails, addresses, etc."

    # Data pools
    FIRST_NAMES = [
        "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael",
        "Linda", "William", "Elizabeth", "David", "Barbara", "Richard", "Susan",
        "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Daniel",
        "Nancy", "Matthew", "Lisa", "Anthony", "Betty", "Mark", "Margaret",
        "Emma", "Olivia", "Ava", "Sophia", "Isabella", "Mia", "Charlotte",
        "Liam", "Noah", "Oliver", "Elijah", "Lucas", "Mason", "Logan",
    ]

    LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    ]

    DOMAINS = [
        "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "example.com",
        "company.com", "work.org", "mail.net", "inbox.com", "email.io",
    ]

    STREETS = [
        "Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Park Rd", "Lake Blvd",
        "Hill St", "River Rd", "Forest Ave", "Valley Dr", "Spring Ln",
    ]

    CITIES = [
        "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
        "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Seattle",
        "Denver", "Boston", "Miami", "Atlanta", "Portland", "Las Vegas",
    ]

    STATES = [
        "CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI",
        "NJ", "VA", "WA", "AZ", "MA", "CO", "TN", "IN", "MO", "MD",
    ]

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="faker_name",
                description="Generate random name",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of names (default: 1)",
                        },
                    },
                },
                handler=self.faker_name,
            ),
            Tool(
                name="faker_email",
                description="Generate random email address",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of emails",
                        },
                        "domain": {
                            "type": "string",
                            "description": "Specific domain to use",
                        },
                    },
                },
                handler=self.faker_email,
            ),
            Tool(
                name="faker_address",
                description="Generate random address",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of addresses",
                        },
                    },
                },
                handler=self.faker_address,
            ),
            Tool(
                name="faker_phone",
                description="Generate random phone number",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of phone numbers",
                        },
                        "format": {
                            "type": "string",
                            "description": "Format: us, intl (default: us)",
                        },
                    },
                },
                handler=self.faker_phone,
            ),
            Tool(
                name="faker_date",
                description="Generate random date",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of dates",
                        },
                        "start": {
                            "type": "string",
                            "description": "Start date (YYYY-MM-DD)",
                        },
                        "end": {
                            "type": "string",
                            "description": "End date (YYYY-MM-DD)",
                        },
                    },
                },
                handler=self.faker_date,
            ),
            Tool(
                name="faker_sentence",
                description="Generate random sentence(s)",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of sentences",
                        },
                    },
                },
                handler=self.faker_sentence,
            ),
            Tool(
                name="faker_uuid",
                description="Generate random UUID",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of UUIDs",
                        },
                    },
                },
                handler=self.faker_uuid,
            ),
            Tool(
                name="faker_username",
                description="Generate random username",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of usernames",
                        },
                    },
                },
                handler=self.faker_username,
            ),
            Tool(
                name="faker_company",
                description="Generate random company name",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of company names",
                        },
                    },
                },
                handler=self.faker_company,
            ),
            Tool(
                name="faker_credit_card",
                description="Generate fake credit card number (for testing)",
                parameters={
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Card type: visa, mastercard, amex",
                        },
                    },
                },
                handler=self.faker_credit_card,
            ),
        ]

    def faker_name(self, count: int = 1) -> str:
        """Generate random names."""
        names = []
        for _ in range(count):
            first = random.choice(self.FIRST_NAMES)
            last = random.choice(self.LAST_NAMES)
            names.append(f"{first} {last}")

        if count == 1:
            return names[0]
        return json.dumps(names, indent=2)

    def faker_email(self, count: int = 1, domain: Optional[str] = None) -> str:
        """Generate random emails."""
        emails = []
        for _ in range(count):
            first = random.choice(self.FIRST_NAMES).lower()
            last = random.choice(self.LAST_NAMES).lower()
            num = random.randint(1, 999)
            dom = domain or random.choice(self.DOMAINS)

            patterns = [
                f"{first}.{last}@{dom}",
                f"{first}{last}{num}@{dom}",
                f"{first[0]}{last}@{dom}",
                f"{first}_{last}@{dom}",
            ]
            emails.append(random.choice(patterns))

        if count == 1:
            return emails[0]
        return json.dumps(emails, indent=2)

    def faker_address(self, count: int = 1) -> str:
        """Generate random addresses."""
        addresses = []
        for _ in range(count):
            num = random.randint(100, 9999)
            street = random.choice(self.STREETS)
            city = random.choice(self.CITIES)
            state = random.choice(self.STATES)
            zip_code = random.randint(10000, 99999)

            addresses.append({
                "street": f"{num} {street}",
                "city": city,
                "state": state,
                "zip": str(zip_code),
                "full": f"{num} {street}, {city}, {state} {zip_code}",
            })

        if count == 1:
            return json.dumps(addresses[0], indent=2)
        return json.dumps(addresses, indent=2)

    def faker_phone(self, count: int = 1, format: str = "us") -> str:
        """Generate random phone numbers."""
        phones = []
        for _ in range(count):
            if format == "us":
                area = random.randint(200, 999)
                exchange = random.randint(200, 999)
                number = random.randint(1000, 9999)
                phones.append(f"({area}) {exchange}-{number}")
            else:
                country = random.randint(1, 99)
                number = "".join(str(random.randint(0, 9)) for _ in range(10))
                phones.append(f"+{country} {number}")

        if count == 1:
            return phones[0]
        return json.dumps(phones, indent=2)

    def faker_date(
        self,
        count: int = 1,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> str:
        """Generate random dates."""
        if start:
            start_date = datetime.strptime(start, "%Y-%m-%d")
        else:
            start_date = datetime.now() - timedelta(days=365 * 5)

        if end:
            end_date = datetime.strptime(end, "%Y-%m-%d")
        else:
            end_date = datetime.now()

        delta = (end_date - start_date).days

        dates = []
        for _ in range(count):
            random_days = random.randint(0, delta)
            date = start_date + timedelta(days=random_days)
            dates.append(date.strftime("%Y-%m-%d"))

        if count == 1:
            return dates[0]
        return json.dumps(dates, indent=2)

    def faker_sentence(self, count: int = 1) -> str:
        """Generate random sentences."""
        words = [
            "the", "a", "an", "this", "that", "it", "is", "was", "are", "were",
            "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "quick", "brown", "lazy", "red", "blue", "green", "big", "small",
            "fox", "dog", "cat", "bird", "fish", "tree", "house", "car", "book",
            "jumps", "runs", "walks", "flies", "swims", "reads", "writes", "eats",
            "over", "under", "through", "around", "between", "near", "far", "with",
        ]

        sentences = []
        for _ in range(count):
            length = random.randint(5, 12)
            sentence = " ".join(random.choice(words) for _ in range(length))
            sentence = sentence.capitalize() + "."
            sentences.append(sentence)

        if count == 1:
            return sentences[0]
        return "\n".join(sentences)

    def faker_uuid(self, count: int = 1) -> str:
        """Generate random UUIDs."""
        import uuid
        uuids = [str(uuid.uuid4()) for _ in range(count)]

        if count == 1:
            return uuids[0]
        return json.dumps(uuids, indent=2)

    def faker_username(self, count: int = 1) -> str:
        """Generate random usernames."""
        adjectives = ["cool", "super", "mega", "ultra", "pro", "epic", "swift", "dark", "light", "cyber"]
        nouns = ["ninja", "dragon", "wolf", "eagle", "tiger", "phoenix", "storm", "shadow", "blade", "star"]

        usernames = []
        for _ in range(count):
            adj = random.choice(adjectives)
            noun = random.choice(nouns)
            num = random.randint(1, 999)
            patterns = [
                f"{adj}{noun}{num}",
                f"{adj}_{noun}",
                f"{noun}{num}",
                f"{adj}{noun}",
            ]
            usernames.append(random.choice(patterns))

        if count == 1:
            return usernames[0]
        return json.dumps(usernames, indent=2)

    def faker_company(self, count: int = 1) -> str:
        """Generate random company names."""
        prefixes = ["Global", "Tech", "Smart", "Digital", "Cloud", "Data", "Net", "Cyber", "Meta", "Quantum"]
        suffixes = ["Systems", "Solutions", "Labs", "Corp", "Inc", "Tech", "Group", "Industries", "Software", "AI"]

        companies = []
        for _ in range(count):
            prefix = random.choice(prefixes)
            suffix = random.choice(suffixes)
            last = random.choice(self.LAST_NAMES)
            patterns = [
                f"{prefix} {suffix}",
                f"{last} {suffix}",
                f"{prefix}{last}",
                f"{last} & {random.choice(self.LAST_NAMES)}",
            ]
            companies.append(random.choice(patterns))

        if count == 1:
            return companies[0]
        return json.dumps(companies, indent=2)

    def faker_credit_card(self, type: str = "visa") -> str:
        """Generate fake credit card (for testing only)."""
        if type == "visa":
            prefix = "4"
            length = 16
        elif type == "mastercard":
            prefix = random.choice(["51", "52", "53", "54", "55"])
            length = 16
        elif type == "amex":
            prefix = random.choice(["34", "37"])
            length = 15
        else:
            prefix = "4"
            length = 16

        # Generate remaining digits (without valid checksum)
        remaining = length - len(prefix) - 1
        number = prefix + "".join(str(random.randint(0, 9)) for _ in range(remaining))

        # Calculate Luhn checksum
        def luhn_checksum(card_number):
            digits = [int(d) for d in card_number]
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            total = sum(odd_digits)
            for d in even_digits:
                total += sum(divmod(d * 2, 10))
            return total % 10

        check = (10 - luhn_checksum(number + "0")) % 10
        number += str(check)

        # Format
        if type == "amex":
            formatted = f"{number[:4]} {number[4:10]} {number[10:]}"
        else:
            formatted = " ".join(number[i:i+4] for i in range(0, len(number), 4))

        return json.dumps({
            "number": number,
            "formatted": formatted,
            "type": type,
            "expiry": f"{random.randint(1, 12):02d}/{random.randint(24, 29)}",
            "cvv": "".join(str(random.randint(0, 9)) for _ in range(3 if type != "amex" else 4)),
            "note": "FAKE - For testing only",
        }, indent=2)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "name")
        if action == "name":
            return self.faker_name()
        elif action == "email":
            return self.faker_email()
        return f"Unknown action: {action}"
