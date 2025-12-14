"""
Skill de Email para R CLI.

Permite enviar emails:
- Envío via SMTP
- Soporte para adjuntos
- Templates de email
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
    """Skill para envío de emails via SMTP."""

    name = "email"
    description = "Envío de emails via SMTP con soporte para adjuntos"

    # Configuración por defecto
    DEFAULT_SMTP_PORT = 587
    DEFAULT_SMTP_SSL_PORT = 465

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="send_email",
                description="Envía un email via SMTP",
                parameters={
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Destinatario(s) separados por coma",
                        },
                        "subject": {
                            "type": "string",
                            "description": "Asunto del email",
                        },
                        "body": {
                            "type": "string",
                            "description": "Cuerpo del mensaje",
                        },
                        "html": {
                            "type": "boolean",
                            "description": "Si el cuerpo es HTML",
                        },
                        "attachments": {
                            "type": "string",
                            "description": "Rutas de archivos adjuntos separadas por coma",
                        },
                        "cc": {
                            "type": "string",
                            "description": "Destinatarios en copia",
                        },
                    },
                    "required": ["to", "subject", "body"],
                },
                handler=self.send_email,
            ),
            Tool(
                name="email_config",
                description="Muestra o configura los ajustes SMTP",
                parameters={
                    "type": "object",
                    "properties": {
                        "smtp_server": {
                            "type": "string",
                            "description": "Servidor SMTP",
                        },
                        "smtp_port": {
                            "type": "integer",
                            "description": "Puerto SMTP",
                        },
                        "username": {
                            "type": "string",
                            "description": "Usuario SMTP",
                        },
                        "password": {
                            "type": "string",
                            "description": "Contraseña SMTP",
                        },
                        "from_email": {
                            "type": "string",
                            "description": "Email del remitente",
                        },
                        "use_ssl": {
                            "type": "boolean",
                            "description": "Usar SSL directo en vez de STARTTLS",
                        },
                    },
                },
                handler=self.email_config,
            ),
            Tool(
                name="test_smtp",
                description="Prueba la conexión SMTP",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.test_smtp,
            ),
        ]

    def _get_smtp_config(self) -> dict:
        """Obtiene la configuración SMTP de variables de entorno o config."""
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
        """Envía un email."""
        try:
            config = self._get_smtp_config()

            if not config["server"]:
                return "Error: SMTP no configurado. Usa email_config o variables de entorno:\n  SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM"

            # Crear mensaje
            msg = MIMEMultipart()
            msg["From"] = config["from_email"] or config["username"]
            msg["To"] = to
            msg["Subject"] = subject

            if cc:
                msg["Cc"] = cc

            # Cuerpo
            content_type = "html" if html else "plain"
            msg.attach(MIMEText(body, content_type, "utf-8"))

            # Adjuntos
            if attachments:
                for attachment_path in attachments.split(","):
                    path = Path(attachment_path.strip()).expanduser()
                    if not path.exists():
                        return f"Error: Archivo adjunto no encontrado: {path}"

                    if path.stat().st_size > 25 * 1024 * 1024:  # 25MB
                        return f"Error: Archivo muy grande: {path.name} (>25MB)"

                    with open(path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())

                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={path.name}",
                    )
                    msg.attach(part)

            # Destinatarios
            recipients = [addr.strip() for addr in to.split(",")]
            if cc:
                recipients.extend([addr.strip() for addr in cc.split(",")])

            # Enviar
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

            return f"✅ Email enviado a: {to}"

        except smtplib.SMTPAuthenticationError:
            return "Error: Autenticación SMTP fallida. Verifica usuario y contraseña."
        except smtplib.SMTPException as e:
            return f"Error SMTP: {e}"
        except Exception as e:
            return f"Error enviando email: {e}"

    def email_config(
        self,
        smtp_server: Optional[str] = None,
        smtp_port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_email: Optional[str] = None,
        use_ssl: Optional[bool] = None,
    ) -> str:
        """Muestra o configura SMTP."""
        # Si no hay parámetros, mostrar configuración actual
        if all(
            v is None for v in [smtp_server, smtp_port, username, password, from_email, use_ssl]
        ):
            config = self._get_smtp_config()

            masked_password = "****" if config["password"] else "(no configurada)"

            return f"""📧 Configuración SMTP:

Servidor: {config["server"] or "(no configurado)"}
Puerto: {config["port"]}
Usuario: {config["username"] or "(no configurado)"}
Contraseña: {masked_password}
Remitente: {config["from_email"] or "(usa username)"}
SSL: {"Sí" if config["use_ssl"] else "No (STARTTLS)"}

Para configurar, usa variables de entorno:
  export SMTP_SERVER="smtp.gmail.com"
  export SMTP_PORT="587"
  export SMTP_USERNAME="tu@email.com"
  export SMTP_PASSWORD="tu_contraseña"
  export SMTP_FROM="tu@email.com"
  export SMTP_SSL="false"

Proveedores comunes:
  Gmail: smtp.gmail.com:587 (requiere App Password)
  Outlook: smtp.office365.com:587
  Yahoo: smtp.mail.yahoo.com:587
"""

        # Configurar (solo muestra cómo hacerlo)
        env_vars = []
        if smtp_server:
            env_vars.append(f'export SMTP_SERVER="{smtp_server}"')
        if smtp_port:
            env_vars.append(f'export SMTP_PORT="{smtp_port}"')
        if username:
            env_vars.append(f'export SMTP_USERNAME="{username}"')
        if password:
            env_vars.append('export SMTP_PASSWORD="****"  # Por seguridad')
        if from_email:
            env_vars.append(f'export SMTP_FROM="{from_email}"')
        if use_ssl is not None:
            env_vars.append(f'export SMTP_SSL="{"true" if use_ssl else "false"}"')

        return "Para aplicar esta configuración, ejecuta:\n\n" + "\n".join(env_vars)

    def test_smtp(self) -> str:
        """Prueba la conexión SMTP."""
        try:
            config = self._get_smtp_config()

            if not config["server"]:
                return "Error: SMTP no configurado"

            # Intentar conexión
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

            return f"✅ Conexión SMTP exitosa a {config['server']}:{config['port']}"

        except smtplib.SMTPAuthenticationError:
            return "❌ Error: Autenticación fallida"
        except smtplib.SMTPConnectError:
            return "❌ Error: No se pudo conectar al servidor SMTP"
        except Exception as e:
            return f"❌ Error: {e}"

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        action = kwargs.get("action", "config")

        if action == "send":
            to = kwargs.get("to", "")
            subject = kwargs.get("subject", "")
            body = kwargs.get("body", "")
            if not all([to, subject, body]):
                return "Error: Se requiere to, subject y body"
            return self.send_email(to, subject, body)
        elif action == "config":
            return self.email_config()
        elif action == "test":
            return self.test_smtp()
        else:
            return f"Acción no reconocida: {action}"
