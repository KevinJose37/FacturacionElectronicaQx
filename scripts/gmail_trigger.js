/**
 * Google Apps Script para disparar el Webhook de Ingesta de Facturas.
 * 
 * 1. Ve a https://script.google.com/
 * 2. Crea un nuevo proyecto.
 * 3. Pega este código.
 * 4. Configura el TRIGGER (Reloj) para que corra cada minuto o según prefieras.
 */

const API_URL = "https://tu-url-de-ngrok-o-servidor.com/webhook/gmail";
const WEBHOOK_SECRET = "una_clave_aleatoria_y_segura_aqui"; // Debe coincidir con la del .env

function checkForNewEmails() {
  Logger.log("Buscando correos no leídos...");
  
  // Buscamos correos no leídos que tengan la palabra 'Factura' o 'Electrónica'
  // Puedes ajustar este filtro según necesites
  const query = "is:unread (factura OR electronica)";
  const threads = GmailApp.search(query);
  
  if (threads.length === 0) {
    Logger.log("No se encontraron correos nuevos.");
    return;
  }
  
  Logger.log("Se encontraron " + threads.length + " hilos nuevos. Disparando webhook...");
  
  const options = {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'x-webhook-secret': WEBHOOK_SECRET
    },
    payload: JSON.stringify({
      event: 'new_email_detected',
      count: threads.length
    }),
    muteHttpExceptions: true
  };
  
  try {
    const response = UrlFetchApp.fetch(API_URL, options);
    Logger.log("Respuesta del servidor: " + response.getContentText());
  } catch (e) {
    Logger.log("Error al llamar al webhook: " + e.toString());
  }
}
