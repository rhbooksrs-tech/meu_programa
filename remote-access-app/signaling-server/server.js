/**
 * Servidor de sinalização - Remote Access App
 *
 * Responsabilidades:
 *  - Manter registro de quais agentes (clientes) estão online, por ID
 *  - Encaminhar pedidos de conexão do técnico para o agente certo
 *  - Encaminhar aceite/recusa do agente de volta ao técnico
 *  - Repassar as mensagens de sinalização WebRTC (offer/answer/ICE) entre as duas pontas
 *
 * Depois que a conexão WebRTC é estabelecida, o vídeo da tela e os comandos de
 * mouse/teclado NÃO passam mais por este servidor - vão direto entre técnico e
 * cliente (ou via um servidor TURN, se a rede for muito restritiva).
 */

const WebSocket = require('ws');

const PORT = process.env.PORT || 8080;
const wss = new WebSocket.Server({ port: PORT });

// id da máquina (string) -> { ws, connectedTechnician }
const agents = new Map();

// id da máquina (string) -> ws do técnico atualmente tentando conectar
const pendingTechnicians = new Map();

function send(ws, data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

function generateId() {
  // formato tipo AnyDesk: 9 dígitos
  let id;
  do {
    id = Math.floor(100000000 + Math.random() * 900000000).toString();
  } while (agents.has(id));
  return id;
}

wss.on('connection', (ws) => {
  ws.role = null;
  ws.machineId = null;

  ws.on('message', (raw) => {
    let msg;
    try {
      msg = JSON.parse(raw);
    } catch (e) {
      return;
    }

    switch (msg.type) {
      // ---- Agente (computador do cliente) se registra ----
      case 'register-agent': {
        const id = msg.machineId && !agents.has(msg.machineId) ? msg.machineId : generateId();
        ws.role = 'agent';
        ws.machineId = id;
        agents.set(id, { ws, connectedTechnician: null });
        send(ws, { type: 'registered', machineId: id });
        console.log(`[agente registrado] ID ${id}`);
        break;
      }

      // ---- Técnico pede para acessar um ID ----
      case 'request-connect': {
        ws.role = 'technician';
        const target = agents.get(msg.targetId);
        if (!target) {
          send(ws, { type: 'error', message: 'ID não encontrado ou máquina offline.' });
          return;
        }
        pendingTechnicians.set(msg.targetId, ws);
        send(target.ws, {
          type: 'incoming-request',
          technicianName: msg.technicianName || 'Técnico',
        });
        console.log(`[pedido de conexão] técnico -> ${msg.targetId}`);
        break;
      }

      // ---- Agente aceita ou recusa ----
      case 'respond-request': {
        const techWs = pendingTechnicians.get(ws.machineId);
        pendingTechnicians.delete(ws.machineId);
        if (!techWs) return;

        if (msg.accepted) {
          const agent = agents.get(ws.machineId);
          if (agent) agent.connectedTechnician = techWs;
          send(techWs, { type: 'request-accepted', targetId: ws.machineId });
          console.log(`[aceito] ${ws.machineId} aceitou a conexão`);
        } else {
          send(techWs, { type: 'request-declined', targetId: ws.machineId });
          console.log(`[recusado] ${ws.machineId} recusou a conexão`);
        }
        break;
      }

      // ---- Repasse de sinalização WebRTC (offer/answer/ice) ----
      case 'signal': {
        // msg.targetId identifica pra quem repassar
        const target = agents.get(msg.targetId);
        if (target && target.ws !== ws) {
          send(target.ws, { type: 'signal', payload: msg.payload, from: ws.machineId || 'technician' });
        } else if (ws.role === 'agent') {
          // agente respondendo pro técnico conectado a ele
          const agent = agents.get(ws.machineId);
          if (agent && agent.connectedTechnician) {
            send(agent.connectedTechnician, { type: 'signal', payload: msg.payload, from: ws.machineId });
          }
        }
        break;
      }

      case 'end-session': {
        if (ws.role === 'agent') {
          const agent = agents.get(ws.machineId);
          if (agent && agent.connectedTechnician) {
            send(agent.connectedTechnician, { type: 'session-ended' });
            agent.connectedTechnician = null;
          }
        } else {
          const target = agents.get(msg.targetId);
          if (target) {
            send(target.ws, { type: 'session-ended' });
            target.connectedTechnician = null;
          }
        }
        break;
      }

      default:
        break;
    }
  });

  ws.on('close', () => {
    if (ws.role === 'agent' && ws.machineId) {
      agents.delete(ws.machineId);
      pendingTechnicians.delete(ws.machineId);
      console.log(`[agente desconectado] ID ${ws.machineId}`);
    }
  });
});

console.log(`Servidor de sinalização rodando na porta ${PORT}`);
