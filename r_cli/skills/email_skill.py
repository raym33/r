"""
Email Skill for R CLI.

Send emails:
- Send via SMTP
- Attachment support
- Email templates
"""

import os
import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class EmailSkill(Skill):
    """Skill for sending emails via SMTP."""

    name = "email"
    description = "Send emails via SMTP with attachment support"

    # Default configuration
    DEFAULT_SMTP_PORT = 587
    DEFAULT_SMTP_SSL_PORT = 465

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="send_email",
                description="Send an email via SMTP",
                parameters={
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Recipient(s) separated by comma",
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject",
                        },
                        "body": {
                            "type": "string",
                            "description": "Message body",
                        },
                        "html": {
                            "type": "boolean",
                            "description": "Whether the body is HTML",
                        },
                        "attachments": {
                            "type": "string",
                            "description": "Attachment file paths separated by comma",
                        },
                        "cc": {
                            "type": "string",
                            "description": "CC recipients",
                        },
                    },
                    "required": ["to", "subject", "body"],
                },
                handler=self.send_email,
            ),
            Tool(
                name="email_config",
                description="Show or configure SMTP settings",
                parameters={
                    "type": "object",
                    "properties": {
                        "smtp_server": {
                            "type": "string",
                            "description": "SMTP server",
                        },
                        "smtp_port": {
                            "type": "integer",
                            "description": "SMTP port",
                        },
                        "username": {
                            "type": "string",
                            "description": "SMTP username",
                        },
                        "password": {
                            "type": "string",
                            "description": "SMTP password",
                        },
                        "from_email": {
                            "type": "string",
                            "description": "Sender email",
                        },
                        "use_ssl": {
                            "type": "boolean",
                            "description": "Use direct SSL instead of STARTTLS",
                        },
                    },
                },
                handler=self.email_config,
            ),
            Tool(
                name="test_smtp",
                description="Test SMTP connection",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.test_smtp,
            ),
        ]

    def _get_smtp_config(self) -> dict:
        """Get SMTP configuration from environment variables or config."""
        return {
            "server": os.environ.get("SMTP_SERVER", ""),
            "port": int(os.environ.get("SMTP_PORT", self.DEFAULT_SMTP_PORT)),
            "username": os.environ.get("SMTP_USERNAME", ""),
            "password": os.environ.get("SMTP_PASSWORD", ""),
            "from_email": os.environ.get("SMTP_FROM", ""),
            "use_ssl": os.environ.get("SMTP_SSL", "false").lower() == "true",
        }

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: bool = False,
        attachments: Optional[str] = None,
        cc: Optional[str] = None,
    ) -> str:
        """Send an email."""
        try:
            config = self._get_smtp_config()

            if not config["server"]:
                return "Error: SMTP not configured. Use email_config or environment variables:\n  SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM"

            # Create message
            msg = MIMEMultipart()
            msg["From"] = config["from_email"] or config["username"]
            msg["To"] = to
            msg["Subject"] = subject

            if cc:
                msg["Cc"] = cc

            # Body
            content_type = "html" if html else "plain"
            msg.attach(MIMEText(body, content_type, "utf-8"))

            # Attachments
            if attachments:
                for attachment_path in attachments.split(","):
                    path = Path(attachment_path.strip()).expanduser()
                    if not path.exists():
                        return f"Error: Attachment not found: {path}"

                    if path.stat().st_size > 25 * 1024 * 1024:  # 25MB
                        return f"Error: File too large: {path.name} (>25MB)"

                    with open(path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())

                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={path.name}",
                    )
                    msg.attach(part)

            # Recipients
            recipients = [addr.strip() for addr in to.split(",")]
            if cc:
                recipients.extend([addr.strip() for addr in cc.split(",")])

            # Send
            if config["use_ssl"]:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    config["server"],
                    config.get("port", self.DEFAULT_SMTP_SSL_PORT),
                    context=context,
                    timeout=30,
                ) as server:
                    server.login(config["username"], config["password"])
                    server.sendmail(msg["From"], recipients, msg.as_string())
            else:
                with smtplib.SMTP(config["server"], config["port"], timeout=30) as server:
                    server.starttls()
                    server.login(config["username"], config["password"])
                    server.sendmail(msg["From"], recipients, msg.as_string())

            return f"✅ Email sent to: {to}"

        except smtplib.SMTPAuthenticationError:
            return "Error: SMTP authentication failed. Check username and password."
        except smtplib.SMTPException as e:
            return f"SMTP Error: {e}"
        except Exception as e:
            return f"Error sending email: {e}"

    def email_config(
        self,
        smtp_server: Optional[str] = None,
        smtp_port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_email: Optional[str] = None,
        use_ssl: Optional[bool] = None,
    ) -> str:
        """Show or configure SMTP."""
        # If no parameters, show current configuration
        if all(
            v is None for v in [smtp_server, smtp_port, username, password, from_email, use_ssl]
        ):
            config = self._get_smtp_config()

            masked_password = "****" if config["password"] else "(not configured)"

            return f"""📧 SMTP Configuration:

Server: {config["server"] or "(not configured)"}
Port: {config["port"]}
Username: {config["username"] or "(not configured)"}
Password: {masked_password}
Sender: {config["from_email"] or "(uses username)"}
SSL: {"Yes" if config["use_ssl"] else "No (STARTTLS)"}

To configure, use environment variables:
  export SMTP_SERVER="smtp.gmail.com"
  export SMTP_PORT="587"
  export SMTP_USERNAME="your@email.com"
  export SMTP_PASSWORD="your_password"
  export SMTP_FROM="your@email.com"
  export SMTP_SSL="false"

Common providers:
  Gmail: smtp.gmail.com:587 (requires App Password)
  Outlook: smtp.office365.com:587
  Yahoo: smtp.mail.yahoo.com:587
"""

        # Configure (only shows how to do it)
        env_vars = []
        if smtp_server:
            env_vars.append(f'export SMTP_SERVER="{smtp_server}"')
        if smtp_port:
            env_vars.append(f'export SMTP_PORT="{smtp_port}"')
        if username:
            env_vars.append(f'export SMTP_USERNAME="{username}"')
        if password:
            env_vars.append('export SMTP_PASSWORD="****"  # For security')
        if from_email:
            env_vars.append(f'export SMTP_FROM="{from_email}"')
        if use_ssl is not None:
            env_vars.append(f'export SMTP_SSL="{"true" if use_ssl else "false"}"')

        return "To apply this configuration, run:\n\n" + "\n".join(env_vars)

    def test_smtp(self) -> str:
        """Test SMTP connection."""
        try:
            config = self._get_smtp_config()

            if not config["server"]:
                return "Error: SMTP not configured"

            # Try connection
            if config["use_ssl"]:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    config["server"],
                    config.get("port", self.DEFAULT_SMTP_SSL_PORT),
                    context=context,
                    timeout=10,
                ) as server:
                    server.login(config["username"], config["password"])
                    server.noop()
            else:
                with smtplib.SMTP(config["server"], config["port"], timeout=10) as server:
                    server.starttls()
                    server.login(config["username"], config["password"])
                    server.noop()

            return f"✅ SMTP connection successful to {config['server']}:{config['port']}"

        except smtplib.SMTPAuthenticationError:
            return "❌ Error: Authentication failed"
        except smtplib.SMTPConnectError:
            return "❌ Error: Could not connect to SMTP server"
        except Exception as e:
            return f"❌ Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "config")

        if action == "send":
            to = kwargs.get("to", "")
            subject = kwargs.get("subject", "")
            body = kwargs.get("body", "")
            if not all([to, subject, body]):
                return "Error: to, subject and body are required"
            return self.send_email(to, subject, body)
        elif action == "config":
            return self.email_config()
        elif action == "test":
            return self.test_smtp()
        else:
            return f"Unrecognized action: {action}"
