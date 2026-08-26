"""
Agente de Acesso Remoto - roda no computador do CLIENTE.

Fluxo:
  1. Gera (ou recupera) um ID fixo para esta máquina e mostra na tela.
  2. Conecta ao servidor de sinalização e fica "escutando".
  3. Quando um técnico solicita acesso, mostra um popup: Aceitar / Recusar.
  4. Se aceito, inicia uma conexão WebRTC: transmite a tela e escuta comandos
     de mouse/teclado vindos do técnico, aplicando-os no sistema.

Dependências (ver requirements.txt):
  pip install aiortc websockets mss pynput av numpy pillow
"""

import asyncio
import json
import os
import random
import threading
import tkinter as tk
from fractions import Fraction

import mss
import numpy as np
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key

SIGNALING_SERVER_URL = "ws://localhost:8080"  # troque pelo endereço do seu servidor (wss:// em produção)
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".remote_access_agent_id")

mouse = MouseController()
keyboard = KeyboardController()

# Mapa simples de teclas especiais do navegador -> pynput
SPECIAL_KEYS = {
    "Enter": Key.enter, "Backspace": Key.backspace, "Tab": Key.tab,
    "Escape": Key.esc, "Shift": Key.shift, "Control": Key.ctrl, "Alt": Key.alt,
    "ArrowUp": Key.up, "ArrowDown": Key.down, "ArrowLeft": Key.left, "ArrowRight": Key.right,
    "Delete": Key.delete, "Home": Key.home, "End": Key.end,
    "PageUp": Key.page_up, "PageDown": Key.page_down, " ": Key.space,
}


def get_or_create_machine_id():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            saved = f.read().strip()
            if saved.isdigit() and len(saved) == 9:
                return saved
    new_id = str(random.randint(100000000, 999999999))
    with open(CONFIG_FILE, "w") as f:
        f.write(new_id)
    return new_id


class ScreenShareTrack(VideoStreamTrack):
    """Captura a tela e entrega os frames como um "vídeo" ao WebRTC."""

    def __init__(self, fps=15):
        super().__init__()
        self.fps = fps
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]  # tela principal

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        img = np.array(self.sct.grab(self.monitor))  # BGRA
        img = img[:, :, :3]  # descarta canal alfa -> BGR

        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        return frame

    async def next_timestamp(self):
        if not hasattr(self, "_start"):
            self._start = asyncio.get_event_loop().time()
            self._frame_count = 0
        self._frame_count += 1
        pts = int(self._frame_count * (90000 / self.fps))
        return pts, Fraction(1, 90000)


def apply_control_command(cmd, screen_width, screen_height):
    """Aplica um comando de mouse/teclado recebido do técnico."""
    t = cmd.get("type")

    if t == "mousemove":
        mouse.position = (int(cmd["x"] * screen_width), int(cmd["y"] * screen_height))

    elif t == "mousedown":
        mouse.position = (int(cmd["x"] * screen_width), int(cmd["y"] * screen_height))
        btn = Button.left if cmd.get("button", 0) == 0 else (Button.right if cmd.get("button") == 2 else Button.middle)
        mouse.press(btn)

    elif t == "mouseup":
        btn = Button.left if cmd.get("button", 0) == 0 else (Button.right if cmd.get("button") == 2 else Button.middle)
        mouse.release(btn)

    elif t == "scroll":
        mouse.scroll(0, -1 if cmd.get("deltaY", 0) > 0 else 1)

    elif t == "keydown":
        key = SPECIAL_KEYS.get(cmd["key"], cmd["key"] if len(cmd["key"]) == 1 else None)
        if key:
            try:
                keyboard.press(key)
            except Exception:
                pass

    elif t == "keyup":
        key = SPECIAL_KEYS.get(cmd["key"], cmd["key"] if len(cmd["key"]) == 1 else None)
        if key:
            try:
                keyboard.release(key)
            except Exception:
                pass


def ask_user_permission(technician_name, result_holder):
    """Mostra um popup nativo perguntando se o cliente aceita o acesso."""

    def on_accept():
        result_holder["accepted"] = True
        root.destroy()

    def on_decline():
        result_holder["accepted"] = False
        root.destroy()

    root = tk.Tk()
    root.title("Solicitação de Acesso Remoto")
    root.attributes("-topmost", True)
    root.geometry("380x160")
    root.resizable(False, False)

    tk.Label(root, text="🔒 Solicitação de Acesso Remoto", font=("Segoe UI", 13, "bold")).pack(pady=(16, 4))
    tk.Label(root, text=f'"{technician_name}" quer acessar\ne controlar este computador.',
             font=("Segoe UI", 10)).pack(pady=4)

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=16)
    tk.Button(btn_frame, text="Recusar", width=12, command=on_decline, bg="#ff5f5f", fg="white").pack(side="left", padx=8)
    tk.Button(btn_frame, text="Aceitar", width=12, command=on_accept, bg="#3ecf8e", fg="white").pack(side="left", padx=8)

    root.mainloop()


class Agent:
    def __init__(self, machine_id):
        self.machine_id = machine_id
        self.ws = None
        self.pc = None
        self.sct = mss.mss()
        self.screen_w = self.sct.monitors[1]["width"]
        self.screen_h = self.sct.monitors[1]["height"]

    async def run(self):
        async with websockets.connect(SIGNALING_SERVER_URL) as ws:
            self.ws = ws
            await ws.send(json.dumps({"type": "register-agent", "machineId": self.machine_id}))
            print(f"Conectado ao servidor. Aguardando confirmação de ID...")

            async for raw in ws:
                msg = json.loads(raw)
                await self.handle_message(msg)

    async def handle_message(self, msg):
        t = msg.get("type")

        if t == "registered":
            self.machine_id = msg["machineId"]
            print("=" * 40)
            print(f"  SEU ID DE ACESSO REMOTO: {self.machine_id}")
            print("=" * 40)
            print("Repasse este ID ao técnico para permitir o acesso.")

        elif t == "incoming-request":
            technician_name = msg.get("technicianName", "Um técnico")
            result_holder = {}
            # tkinter precisa rodar na thread principal
            thread = threading.Thread(target=ask_user_permission, args=(technician_name, result_holder))
            thread.start()
            thread.join()

            accepted = result_holder.get("accepted", False)
            await self.ws.send(json.dumps({"type": "respond-request", "accepted": accepted}))

            if accepted:
                await self.start_webrtc()

        elif t == "signal":
            await self.handle_signal(msg["payload"])

        elif t == "session-ended":
            if self.pc:
                await self.pc.close()
                self.pc = None
            print("Sessão encerrada.")

    async def start_webrtc(self):
        self.pc = RTCPeerConnection()
        self.pc.addTrack(ScreenShareTrack())

        @self.pc.on("datachannel")
        def on_datachannel(channel):
            @channel.on("message")
            def on_message(message):
                try:
                    cmd = json.loads(message)
                    apply_control_command(cmd, self.screen_w, self.screen_h)
                except Exception as e:
                    print("Erro ao aplicar comando:", e)

        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if candidate:
                await self.ws.send(json.dumps({
                    "type": "signal",
                    "targetId": self.machine_id,
                    "payload": {"kind": "ice-candidate", "candidate": candidate.to_json()}
                }))

        print("Aguardando oferta de conexão do técnico...")

    async def handle_signal(self, payload):
        if payload["kind"] == "offer":
            if not self.pc:
                self.pc = RTCPeerConnection()
                self.pc.addTrack(ScreenShareTrack())

                @self.pc.on("datachannel")
                def on_datachannel(channel):
                    @channel.on("message")
                    def on_message(message):
                        try:
                            cmd = json.loads(message)
                            apply_control_command(cmd, self.screen_w, self.screen_h)
                        except Exception as e:
                            print("Erro ao aplicar comando:", e)

            offer = RTCSessionDescription(sdp=payload["sdp"]["sdp"], type=payload["sdp"]["type"])
            await self.pc.setRemoteDescription(offer)
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)

            await self.ws.send(json.dumps({
                "type": "signal",
                "targetId": self.machine_id,
                "payload": {"kind": "answer", "sdp": {"sdp": self.pc.localDescription.sdp, "type": self.pc.localDescription.type}}
            }))
            print("Conexão estabelecida! Compartilhando tela.")

        elif payload["kind"] == "ice-candidate" and self.pc:
            try:
                await self.pc.addIceCandidate(payload["candidate"])
            except Exception as e:
                print("Erro ao adicionar ICE candidate:", e)


def main():
    machine_id = get_or_create_machine_id()
    agent = Agent(machine_id)
    print("Iniciando agente de acesso remoto...")
    asyncio.run(agent.run())


if __name__ == "__main__":
    main()
