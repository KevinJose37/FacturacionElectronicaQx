import logging
from dotenv import load_dotenv

from core.email_listener import EmailListener

def main() -> None:
    """Punto de entrada principal de la aplicación."""
    # Cargar variables de entorno (como EMAIL_PASSWORD y credenciales AWS)
    load_dotenv()
    
    listener = EmailListener()
    listener.run()

if __name__ == "__main__":
    main()
