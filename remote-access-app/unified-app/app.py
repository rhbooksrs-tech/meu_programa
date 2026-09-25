"""
Remote Access App - Versão Unificada

Roda IGUAL nos dois computadores (o seu e o do cliente). Cada instância:
  - Mostra sua própria ID (para receber acessos)
  - Tem um campo para digitar a ID de outra máquina (para fazer acessos)

Ou seja: qualquer computador pode ser "host" (tela sendo acessada) ou
"viewer" (quem está acessando), exatamente como o AnyDesk/TeamViewer.

Dependências: pip install -r requirements.txt
"""

import asyncio
import hashlib
import json
import locale
import os
import platform
import queue
import random
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import uuid
import webbrowser
from datetime import datetime, timedelta
from fractions import Fraction
from tkinter import messagebox, filedialog, ttk

import cv2
import mss
import numpy as np
import psutil
import requests
import websockets
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
    RTCConfiguration,
    RTCIceServer,
)
from aiortc.sdp import candidate_from_sdp, candidate_to_sdp
from av import VideoFrame
from PIL import Image, ImageTk
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key

SIGNALING_SERVER_URL = "wss://meu-programa.onrender.com"
LICENSE_SERVER_URL = "https://meu-programa.onrender.com"
RENEWAL_URL = "https://SUA-PAGINA-DE-RENOVACAO-NA-KIWIFY.com"  # ajuste para o link real de renovação
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".remote_access_agent_id")
LICENSE_FILE = os.path.join(os.path.expanduser("~"), ".remote_access_license.json")
LANGUAGE_FILE = os.path.join(os.path.expanduser("~"), ".henndesk_language.json")

APP_VERSION = "1.0.0"  # atualize este número a cada nova versão que você distribuir

# ============================================================
# IDIOMAS
# ============================================================
TRANSLATIONS = {
    "pt": {
        "your_id": "Sua ID",
        "copy_id": "Copiar ID",
        "access_other": "Acessar outra máquina",
        "connect": "Conectar",
        "save_favorite_btn": "☆ Salvar este ID nos Favoritos",
        "favorites_title": "⭐ Acessos Favoritos",
        "access_selected": "Acessar selecionado",
        "remove": "Remover",
        "history_btn": "📋 Histórico de sessões",
        "language_btn": "🌐 Idioma",
        "status_connecting_server": "Conectando ao servidor...",
        "status_ready": "Pronto. Sua ID é {id}.",
        "status_requesting": "Solicitando acesso a {id}...",
        "status_declined": "Acesso recusado pelo outro lado.",
        "status_accepted_connecting": "Aceito! Conectando...",
        "status_sharing_screen": "Compartilhando sua tela...",
        "status_session_ended": "Sessão encerrada.",
        "id_required_title": "ID necessária",
        "id_required_message": "Digite o ID da máquina no campo acima antes de salvar nos favoritos.",
        "save_favorite_title": "Salvar Favorito",
        "saving_id": "Salvando ID: {id}",
        "name_prompt": "Dê um nome para identificar esta máquina:",
        "save": "Salvar",
        "no_favorite_title": "Nenhum favorito selecionado",
        "no_favorite_message": "Selecione um favorito na lista primeiro.",
        "remove_favorite_title": "Remover favorito",
        "remove_favorite_message": 'Remover "{name}" dos favoritos?',
        "incoming_request_title": "Solicitação de Acesso Remoto",
        "incoming_request_message": '"{name}" quer acessar e controlar este computador.\n\nEsta sessão será registrada (vídeo e relatório) para fins de suporte técnico.\n\nAceitar?',
        "history_window_title": "Histórico de Sessões",
        "tab_sessions": "Sessões",
        "tab_tips": "💡 Dica de Uso",
        "col_datetime": "Data/Hora",
        "col_role": "Papel",
        "col_remote_id": "ID Remoto",
        "col_duration": "Duração",
        "col_rating": "Avaliação",
        "role_you_accessed": "Você acessou",
        "role_was_accessed": "Foi acessado",
        "no_sessions_yet": "Nenhuma sessão registrada ainda.",
        "open_video": "▶ Abrir vídeo",
        "open_report": "📄 Abrir relatório",
        "save_copy": "💾 Salvar cópia em...",
        "delete": "🗑 Excluir",
        "open_videos_folder": "Abrir pasta de vídeos",
        "video_unavailable_title": "Vídeo indisponível",
        "video_unavailable_message": "Não há vídeo salvo para esta sessão.",
        "report_unavailable_title": "Relatório indisponível",
        "report_unavailable_message": "Não há relatório em texto para esta sessão.",
        "choose_folder_title": "Escolha a pasta (pen drive, HD externo, etc.)",
        "copied_title": "Copiado",
        "copied_message": "Arquivos salvos em:",
        "confirm_delete_title": "Excluir sessão",
        "confirm_delete_message": "Isso apaga o vídeo e o relatório desta sessão permanentemente. Confirma?",
        "tips_text": (
            "💡 Dica de uso\n\n"
            "Os vídeos das sessões ficam salvos no seu computador e podem ocupar bastante "
            "espaço com o tempo.\n\n"
            "É importante, de tempos em tempos, excluir sessões antigas que não precisa mais "
            "guardar, ou salvar uma cópia em um pen drive ou HD externo antes de apagar do "
            "computador — use os botões \"Salvar cópia em...\" e \"Excluir\" na aba Sessões.\n\n"
            "Isso evita que o disco do computador fique cheio com o passar do tempo."
        ),
        "controlling_title": "Controlando {id}",
        "activate_license_title": "Ativar Licença",
        "activate_license_header": "🔑 Ativar Licença",
        "activate_license_prompt": "Cole abaixo a chave de licença que você recebeu por e-mail.",
        "cancel": "Cancelar",
        "activate": "Ativar",
        "connection_error_message": "Não foi possível conectar ao servidor. Verifique sua internet e tente novamente.",
        "already_activated_message": "Esta chave já está ativada em outro computador. Cada licença funciona em apenas um computador.",
        "not_found_message": "Chave de licença não encontrada. Confira se digitou corretamente.",
        "generic_activation_error": "Não foi possível ativar. Tente novamente.",
        "license_offline_title": "Aviso",
        "license_offline_message": "Não foi possível confirmar sua licença agora (sem conexão com o servidor). O programa vai abrir mesmo assim.",
        "license_expired_title": "Licença Expirada",
        "license_expired_message": "Sua licença expirou. Renove para continuar usando o programa.",
        "license_wrong_machine_title": "Licença Inválida",
        "license_wrong_machine_message": "Esta chave está registrada em outro computador.",
        "license_generic_invalid_message": "Não foi possível validar sua licença. Entre em contato com o suporte.",
        "renew_now": "Renovar agora",
        "close": "Fechar",
        "mandatory_update_title": "Atualização Obrigatória",
        "mandatory_update_message": "Esta versão do programa ({version}) não é mais suportada.\nÉ necessário atualizar para continuar usando.",
        "new_version_title": "Nova versão disponível",
        "new_version_message": "Existe uma versão mais nova do programa ({version}).\nDeseja baixar agora?",
        "choose_language_title": "Escolher Idioma",
        "error_id_not_found": "ID não encontrado ou máquina offline.",
        "send_file_btn": "📁 Enviar arquivo",
        "sending_file": "Enviando {name}... {percent}%",
        "file_sent": "Arquivo enviado: {name}",
        "receiving_file": "Recebendo {name}... {percent}%",
        "file_received_title": "Arquivo Recebido",
        "file_received_message": "Arquivo \"{name}\" recebido e salvo em:\n{path}",
        "open_folder": "Abrir pasta",
        "file_channel_not_ready": "Conexão de arquivos ainda não está pronta. Aguarde alguns segundos e tente de novo.",
        "tab_billing": "💰 Horas p/ Cobrança",
        "period_this_month": "Este mês",
        "period_last_month": "Mês passado",
        "period_all": "Todos os registros",
        "col_client": "Cliente",
        "col_sessions": "Sessões",
        "col_total_time": "Tempo Total",
        "col_estimated_value": "Valor Estimado",
        "hourly_rate_label": "Valor por hora:",
        "save_rate": "Salvar",
        "rate_saved": "Valor por hora salvo.",
        "export_billing_csv": "⬇ Exportar CSV",
        "no_billing_data": "Nenhum atendimento registrado neste período.",
        "billing_exported_title": "Exportado",
        "billing_exported_message": "Relatório salvo em:",
        "diagnostics_waiting": "ℹ Aguardando diagnóstico...",
        "diagnostics_title": "Diagnóstico do Sistema",
        "diag_hostname": "Nome do PC:",
        "diag_os": "Sistema:",
        "diag_cpu": "Processador:",
        "diag_ram": "Memória RAM:",
        "diag_uptime": "Ligado há:",
        "rating_dialog_title": "Avalie o Atendimento",
        "rating_question": "Como foi o atendimento que você recebeu agora?",
        "skip_rating": "Pular",
        "submit_rating": "Enviar",
        "rating_received_status": "Cliente avaliou o atendimento: {stars}",
        "edit_client_btn": "✎ Editar",
        "edit_client_title": "Editar Cadastro do Cliente",
        "phone_label": "Telefone:",
        "email_label": "E-mail:",
        "notes_label": "Observações:",
    },
    "en": {
        "your_id": "Your ID",
        "copy_id": "Copy ID",
        "access_other": "Access another computer",
        "connect": "Connect",
        "save_favorite_btn": "☆ Save this ID to Favorites",
        "favorites_title": "⭐ Favorite Access",
        "access_selected": "Access selected",
        "remove": "Remove",
        "history_btn": "📋 Session History",
        "language_btn": "🌐 Language",
        "status_connecting_server": "Connecting to server...",
        "status_ready": "Ready. Your ID is {id}.",
        "status_requesting": "Requesting access to {id}...",
        "status_declined": "Access declined by the other side.",
        "status_accepted_connecting": "Accepted! Connecting...",
        "status_sharing_screen": "Sharing your screen...",
        "status_session_ended": "Session ended.",
        "id_required_title": "ID required",
        "id_required_message": "Enter the machine ID in the field above before saving to favorites.",
        "save_favorite_title": "Save Favorite",
        "saving_id": "Saving ID: {id}",
        "name_prompt": "Give a name to identify this computer:",
        "save": "Save",
        "no_favorite_title": "No favorite selected",
        "no_favorite_message": "Select a favorite from the list first.",
        "remove_favorite_title": "Remove favorite",
        "remove_favorite_message": 'Remove "{name}" from favorites?',
        "incoming_request_title": "Remote Access Request",
        "incoming_request_message": '"{name}" wants to access and control this computer.\n\nThis session will be recorded (video and report) for technical support purposes.\n\nAccept?',
        "history_window_title": "Session History",
        "tab_sessions": "Sessions",
        "tab_tips": "💡 Usage Tip",
        "col_datetime": "Date/Time",
        "col_role": "Role",
        "col_remote_id": "Remote ID",
        "col_duration": "Duration",
        "col_rating": "Rating",
        "role_you_accessed": "You accessed",
        "role_was_accessed": "Was accessed",
        "no_sessions_yet": "No sessions recorded yet.",
        "open_video": "▶ Open video",
        "open_report": "📄 Open report",
        "save_copy": "💾 Save copy to...",
        "delete": "🗑 Delete",
        "open_videos_folder": "Open videos folder",
        "video_unavailable_title": "Video unavailable",
        "video_unavailable_message": "There is no saved video for this session.",
        "report_unavailable_title": "Report unavailable",
        "report_unavailable_message": "There is no text report for this session.",
        "choose_folder_title": "Choose folder (USB drive, external HDD, etc.)",
        "copied_title": "Copied",
        "copied_message": "Files saved to:",
        "confirm_delete_title": "Delete session",
        "confirm_delete_message": "This permanently deletes the video and report for this session. Confirm?",
        "tips_text": (
            "💡 Usage tip\n\n"
            "Session videos are saved on your computer and can take up significant "
            "space over time.\n\n"
            "It's important to periodically delete old sessions you no longer need, "
            "or save a copy to a USB drive or external HDD before deleting them from "
            "the computer — use the \"Save copy to...\" and \"Delete\" buttons on the Sessions tab.\n\n"
            "This prevents your computer's disk from filling up over time."
        ),
        "controlling_title": "Controlling {id}",
        "activate_license_title": "Activate License",
        "activate_license_header": "🔑 Activate License",
        "activate_license_prompt": "Paste below the license key you received by email.",
        "cancel": "Cancel",
        "activate": "Activate",
        "connection_error_message": "Could not connect to the server. Check your internet and try again.",
        "already_activated_message": "This key is already activated on another computer. Each license works on only one computer.",
        "not_found_message": "License key not found. Check that you typed it correctly.",
        "generic_activation_error": "Could not activate. Please try again.",
        "license_offline_title": "Notice",
        "license_offline_message": "Could not confirm your license right now (no connection to the server). The program will open anyway.",
        "license_expired_title": "License Expired",
        "license_expired_message": "Your license has expired. Renew to keep using the program.",
        "license_wrong_machine_title": "Invalid License",
        "license_wrong_machine_message": "This key is registered on another computer.",
        "license_generic_invalid_message": "Could not validate your license. Please contact support.",
        "renew_now": "Renew now",
        "close": "Close",
        "mandatory_update_title": "Mandatory Update",
        "mandatory_update_message": "This version of the program ({version}) is no longer supported.\nYou must update to continue using it.",
        "new_version_title": "New version available",
        "new_version_message": "A newer version of the program is available ({version}).\nDownload now?",
        "choose_language_title": "Choose Language",
        "error_id_not_found": "ID not found or machine offline.",
        "send_file_btn": "📁 Send file",
        "sending_file": "Sending {name}... {percent}%",
        "file_sent": "File sent: {name}",
        "receiving_file": "Receiving {name}... {percent}%",
        "file_received_title": "File Received",
        "file_received_message": "File \"{name}\" received and saved to:\n{path}",
        "open_folder": "Open folder",
        "file_channel_not_ready": "File connection isn't ready yet. Wait a few seconds and try again.",
        "tab_billing": "💰 Billable Hours",
        "period_this_month": "This month",
        "period_last_month": "Last month",
        "period_all": "All records",
        "col_client": "Client",
        "col_sessions": "Sessions",
        "col_total_time": "Total Time",
        "col_estimated_value": "Estimated Value",
        "hourly_rate_label": "Hourly rate:",
        "save_rate": "Save",
        "rate_saved": "Hourly rate saved.",
        "export_billing_csv": "⬇ Export CSV",
        "no_billing_data": "No sessions recorded in this period.",
        "billing_exported_title": "Exported",
        "billing_exported_message": "Report saved to:",
        "diagnostics_waiting": "ℹ Waiting for diagnostics...",
        "diagnostics_title": "System Diagnostics",
        "diag_hostname": "PC name:",
        "diag_os": "System:",
        "diag_cpu": "Processor:",
        "diag_ram": "RAM Memory:",
        "diag_uptime": "Uptime:",
        "rating_dialog_title": "Rate the Service",
        "rating_question": "How was the service you just received?",
        "skip_rating": "Skip",
        "submit_rating": "Submit",
        "rating_received_status": "Client rated the service: {stars}",
        "edit_client_btn": "✎ Edit",
        "edit_client_title": "Edit Client Record",
        "phone_label": "Phone:",
        "email_label": "Email:",
        "notes_label": "Notes:",
    },
    "es": {
        "your_id": "Tu ID",
        "copy_id": "Copiar ID",
        "access_other": "Acceder a otra computadora",
        "connect": "Conectar",
        "save_favorite_btn": "☆ Guardar este ID en Favoritos",
        "favorites_title": "⭐ Accesos Favoritos",
        "access_selected": "Acceder al seleccionado",
        "remove": "Eliminar",
        "history_btn": "📋 Historial de sesiones",
        "language_btn": "🌐 Idioma",
        "status_connecting_server": "Conectando al servidor...",
        "status_ready": "Listo. Tu ID es {id}.",
        "status_requesting": "Solicitando acceso a {id}...",
        "status_declined": "Acceso rechazado por el otro lado.",
        "status_accepted_connecting": "¡Aceptado! Conectando...",
        "status_sharing_screen": "Compartiendo tu pantalla...",
        "status_session_ended": "Sesión finalizada.",
        "id_required_title": "ID requerida",
        "id_required_message": "Ingresa el ID de la máquina en el campo de arriba antes de guardar en favoritos.",
        "save_favorite_title": "Guardar Favorito",
        "saving_id": "Guardando ID: {id}",
        "name_prompt": "Dale un nombre para identificar esta computadora:",
        "save": "Guardar",
        "no_favorite_title": "Ningún favorito seleccionado",
        "no_favorite_message": "Selecciona primero un favorito de la lista.",
        "remove_favorite_title": "Eliminar favorito",
        "remove_favorite_message": '¿Eliminar "{name}" de favoritos?',
        "incoming_request_title": "Solicitud de Acceso Remoto",
        "incoming_request_message": '"{name}" quiere acceder y controlar esta computadora.\n\nEsta sesión quedará registrada (video e informe) con fines de soporte técnico.\n\n¿Aceptar?',
        "history_window_title": "Historial de Sesiones",
        "tab_sessions": "Sesiones",
        "tab_tips": "💡 Consejo de Uso",
        "col_datetime": "Fecha/Hora",
        "col_role": "Rol",
        "col_remote_id": "ID Remoto",
        "col_duration": "Duración",
        "col_rating": "Calificación",
        "role_you_accessed": "Tú accediste",
        "role_was_accessed": "Fue accedido",
        "no_sessions_yet": "Aún no hay sesiones registradas.",
        "open_video": "▶ Abrir video",
        "open_report": "📄 Abrir informe",
        "save_copy": "💾 Guardar copia en...",
        "delete": "🗑 Eliminar",
        "open_videos_folder": "Abrir carpeta de videos",
        "video_unavailable_title": "Video no disponible",
        "video_unavailable_message": "No hay video guardado para esta sesión.",
        "report_unavailable_title": "Informe no disponible",
        "report_unavailable_message": "No hay informe de texto para esta sesión.",
        "choose_folder_title": "Elige la carpeta (pendrive, disco externo, etc.)",
        "copied_title": "Copiado",
        "copied_message": "Archivos guardados en:",
        "confirm_delete_title": "Eliminar sesión",
        "confirm_delete_message": "Esto borra permanentemente el video y el informe de esta sesión. ¿Confirmas?",
        "tips_text": (
            "💡 Consejo de uso\n\n"
            "Los videos de las sesiones se guardan en tu computadora y pueden ocupar "
            "bastante espacio con el tiempo.\n\n"
            "Es importante eliminar de vez en cuando las sesiones antiguas que ya no "
            "necesitas, o guardar una copia en un pendrive o disco externo antes de "
            "borrarlas — usa los botones \"Guardar copia en...\" y \"Eliminar\" en la pestaña Sesiones.\n\n"
            "Esto evita que el disco de la computadora se llene con el tiempo."
        ),
        "controlling_title": "Controlando {id}",
        "activate_license_title": "Activar Licencia",
        "activate_license_header": "🔑 Activar Licencia",
        "activate_license_prompt": "Pega abajo la clave de licencia que recibiste por correo electrónico.",
        "cancel": "Cancelar",
        "activate": "Activar",
        "connection_error_message": "No se pudo conectar al servidor. Verifica tu conexión e intenta nuevamente.",
        "already_activated_message": "Esta clave ya está activada en otra computadora. Cada licencia funciona en una sola computadora.",
        "not_found_message": "Clave de licencia no encontrada. Verifica que la escribiste correctamente.",
        "generic_activation_error": "No se pudo activar. Intenta nuevamente.",
        "license_offline_title": "Aviso",
        "license_offline_message": "No se pudo confirmar tu licencia ahora (sin conexión con el servidor). El programa se abrirá de todos modos.",
        "license_expired_title": "Licencia Vencida",
        "license_expired_message": "Tu licencia venció. Renueva para seguir usando el programa.",
        "license_wrong_machine_title": "Licencia Inválida",
        "license_wrong_machine_message": "Esta clave está registrada en otra computadora.",
        "license_generic_invalid_message": "No se pudo validar tu licencia. Contacta al soporte.",
        "renew_now": "Renovar ahora",
        "close": "Cerrar",
        "mandatory_update_title": "Actualización Obligatoria",
        "mandatory_update_message": "Esta versión del programa ({version}) ya no es compatible.\nDebes actualizar para continuar usándolo.",
        "new_version_title": "Nueva versión disponible",
        "new_version_message": "Hay una versión más nueva del programa disponible ({version}).\n¿Descargar ahora?",
        "choose_language_title": "Elegir Idioma",
        "error_id_not_found": "ID no encontrado o máquina fuera de línea.",
        "send_file_btn": "📁 Enviar archivo",
        "sending_file": "Enviando {name}... {percent}%",
        "file_sent": "Archivo enviado: {name}",
        "receiving_file": "Recibiendo {name}... {percent}%",
        "file_received_title": "Archivo Recibido",
        "file_received_message": "Archivo \"{name}\" recibido y guardado en:\n{path}",
        "open_folder": "Abrir carpeta",
        "file_channel_not_ready": "La conexión de archivos aún no está lista. Espera unos segundos e intenta de nuevo.",
        "tab_billing": "💰 Horas Facturables",
        "period_this_month": "Este mes",
        "period_last_month": "Mes pasado",
        "period_all": "Todos los registros",
        "col_client": "Cliente",
        "col_sessions": "Sesiones",
        "col_total_time": "Tiempo Total",
        "col_estimated_value": "Valor Estimado",
        "hourly_rate_label": "Valor por hora:",
        "save_rate": "Guardar",
        "rate_saved": "Valor por hora guardado.",
        "export_billing_csv": "⬇ Exportar CSV",
        "no_billing_data": "No hay sesiones registradas en este período.",
        "billing_exported_title": "Exportado",
        "billing_exported_message": "Informe guardado en:",
        "diagnostics_waiting": "ℹ Esperando diagnóstico...",
        "diagnostics_title": "Diagnóstico del Sistema",
        "diag_hostname": "Nombre del PC:",
        "diag_os": "Sistema:",
        "diag_cpu": "Procesador:",
        "diag_ram": "Memoria RAM:",
        "diag_uptime": "Encendido hace:",
        "rating_dialog_title": "Califica el Servicio",
        "rating_question": "¿Cómo fue el servicio que acabas de recibir?",
        "skip_rating": "Omitir",
        "submit_rating": "Enviar",
        "rating_received_status": "El cliente calificó el servicio: {stars}",
        "edit_client_btn": "✎ Editar",
        "edit_client_title": "Editar Registro del Cliente",
        "phone_label": "Teléfono:",
        "email_label": "Correo electrónico:",
        "notes_label": "Notas:",
    },
}

CURRENT_LANG = "pt"  # valor padrão, ajustado em tempo de execução por init_language()


def t(key, **kwargs):
    """Busca o texto traduzido para o idioma atual."""
    text = TRANSLATIONS.get(CURRENT_LANG, TRANSLATIONS["en"]).get(key, TRANSLATIONS["pt"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def detect_system_language():
    """Detecta o idioma do sistema operacional e mapeia para pt/en/es (padrão: en)."""
    try:
        lang_code = locale.getdefaultlocale()[0] or ""
    except Exception:
        lang_code = ""
    lang_code = lang_code.lower()
    if lang_code.startswith("pt"):
        return "pt"
    if lang_code.startswith("es"):
        return "es"
    return "en"


def load_saved_language():
    if os.path.exists(LANGUAGE_FILE):
        try:
            with open(LANGUAGE_FILE, "r") as f:
                lang = json.load(f).get("language")
                if lang in TRANSLATIONS:
                    return lang
        except Exception:
            pass
    return None


def save_language(lang):
    with open(LANGUAGE_FILE, "w") as f:
        json.dump({"language": lang}, f)


def init_language():
    """Chamado uma vez no início do programa: usa idioma salvo, ou detecta do sistema."""
    global CURRENT_LANG
    saved = load_saved_language()
    CURRENT_LANG = saved if saved else detect_system_language()


def set_language(lang):
    global CURRENT_LANG
    if lang in TRANSLATIONS:
        CURRENT_LANG = lang
        save_language(lang)

# Pasta onde ficam salvos os registros e vídeos das sessões
DATA_DIR = os.path.join(os.path.expanduser("~"), "RemoteAccessLogs")
VIDEOS_DIR = os.path.join(DATA_DIR, "videos")
LOG_FILE = os.path.join(DATA_DIR, "session_log.jsonl")
RECEIVED_FILES_DIR = os.path.join(os.path.expanduser("~"), "HennDesk Recebidos")
FILE_TRANSFER_CHUNK_SIZE = 16 * 1024  # 16KB por pedaço
FILE_TRANSFER_BUFFER_THRESHOLD = 256 * 1024  # pausa o envio se o buffer passar disso
os.makedirs(VIDEOS_DIR, exist_ok=True)

mouse_ctrl = MouseController()
keyboard_ctrl = KeyboardController()

SPECIAL_KEYS = {
    "Return": Key.enter, "BackSpace": Key.backspace, "Tab": Key.tab,
    "Escape": Key.esc, "Shift_L": Key.shift, "Control_L": Key.ctrl, "Alt_L": Key.alt,
    "Up": Key.up, "Down": Key.down, "Left": Key.left, "Right": Key.right,
    "Delete": Key.delete, "Home": Key.home, "End": Key.end,
    "Prior": Key.page_up, "Next": Key.page_down, "space": Key.space,
}

# ===== CORREÇÃO: bug do aiortc no Python 3.14 (o mesmo do agent.py) =====
import aiortc.rtcpeerconnection as _rpc

_original_and_direction = _rpc.and_direction

def _safe_and_direction(a, b):
    try:
        return _original_and_direction(a, b)
    except ValueError:
        return "sendrecv"

_rpc.and_direction = _safe_and_direction

# ===== CORREÇÃO: converte candidatos ICE vindos do navegador/painel web =====
def ice_candidate_from_json(data):
    try:
        line = data.get("candidate", "")
        if not line.startswith("candidate:"):
            return None
        candidate = candidate_from_sdp(line[len("candidate:"):])
        candidate.sdpMid = data.get("sdpMid")
        candidate.sdpMLineIndex = data.get("sdpMLineIndex")
        candidate.usernameFragment = data.get("usernameFragment")
        return candidate
    except Exception:
        return None

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


def apply_control_command(cmd, screen_width, screen_height):
    cmd_type = cmd.get("type")
    if cmd_type == "mousemove":
        mouse_ctrl.position = (int(cmd["x"] * screen_width), int(cmd["y"] * screen_height))
    elif cmd_type == "mousedown":
        mouse_ctrl.position = (int(cmd["x"] * screen_width), int(cmd["y"] * screen_height))
        btn = Button.left if cmd.get("button", 0) == 0 else (Button.right if cmd.get("button") == 2 else Button.middle)
        mouse_ctrl.press(btn)
    elif cmd_type == "mouseup":
        btn = Button.left if cmd.get("button", 0) == 0 else (Button.right if cmd.get("button") == 2 else Button.middle)
        mouse_ctrl.release(btn)
    elif cmd_type == "scroll":
        mouse_ctrl.scroll(0, -1 if cmd.get("deltaY", 0) > 0 else 1)
    elif cmd_type == "keydown":
        key = SPECIAL_KEYS.get(cmd["key"], cmd["key"] if len(cmd["key"]) == 1 else None)
        if key:
            try:
                keyboard_ctrl.press(key)
            except Exception:
                pass
    elif cmd_type == "keyup":
        key = SPECIAL_KEYS.get(cmd["key"], cmd["key"] if len(cmd["key"]) == 1 else None)
        if key:
            try:
                keyboard_ctrl.release(key)
            except Exception:
                pass


def parse_version(v):
    """Converte '1.2.3' em (1, 2, 3) para poder comparar corretamente."""
    try:
        return tuple(int(p) for p in v.strip().split("."))
    except Exception:
        return (0, 0, 0)


def check_for_updates():
    """
    Consulta o servidor por uma versão mais nova. Não bloqueia o uso a menos
    que a versão atual esteja abaixo do mínimo exigido (para correções urgentes).
    Retorna True se pode continuar, False se deve encerrar (versão muito antiga).
    """
    try:
        resp = requests.get(f"{LICENSE_SERVER_URL}/version", timeout=8)
        data = resp.json()
    except Exception:
        return True  # sem internet/servidor fora do ar — não trava o uso por isso

    current = parse_version(APP_VERSION)
    latest = parse_version(data.get("latestVersion", APP_VERSION))
    minimum = parse_version(data.get("minRequiredVersion", APP_VERSION))
    download_url = data.get("downloadUrl", "")

    if current < minimum:
        show_blocking_message(
            t("mandatory_update_title"),
            t("mandatory_update_message", version=APP_VERSION),
            allow_renew=False,
        )
        if download_url:
            webbrowser.open(download_url)
        return False

    if current < latest:
        # Aviso simples, não bloqueia o uso
        win = tk.Tk()
        win.withdraw()
        go_update = messagebox.askyesno(
            t("new_version_title"),
            t("new_version_message", version=data.get("latestVersion")),
        )
        win.destroy()
        if go_update and download_url:
            webbrowser.open(download_url)

    return True


def get_machine_fingerprint():
    """Gera um identificador único e estável deste computador."""
    raw = f"{platform.node()}-{uuid.getnode()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def load_saved_license_key():
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r") as f:
                return json.load(f).get("licenseKey")
        except Exception:
            return None
    return None


def save_license_key(key):
    with open(LICENSE_FILE, "w") as f:
        json.dump({"licenseKey": key}, f)


def call_license_api(path, payload):
    try:
        resp = requests.post(f"{LICENSE_SERVER_URL}{path}", json=payload, timeout=15)
        return resp.json(), None
    except Exception as e:
        return None, str(e)


def prompt_for_license_key(error_message=None):
    """Janela simples pedindo a chave de licença. Retorna a chave digitada, ou None se cancelado."""
    result = {"key": None}
    win = tk.Tk()
    win.title(t("activate_license_title"))
    win.geometry("420x220")
    win.resizable(False, False)

    tk.Label(win, text=t("activate_license_header"), font=("Segoe UI", 14, "bold")).pack(pady=(20, 6))
    tk.Label(win, text=t("activate_license_prompt"),
             font=("Segoe UI", 9), fg="#555").pack()

    if error_message:
        tk.Label(win, text=error_message, font=("Segoe UI", 9), fg="#c0392b", wraplength=380).pack(pady=(8, 0))

    entry = tk.Entry(win, font=("Segoe UI", 12), justify="center", width=28)
    entry.pack(pady=14)
    entry.focus_set()

    def submit():
        result["key"] = entry.get().strip()
        win.destroy()

    def cancel():
        win.destroy()

    btn_frame = tk.Frame(win)
    btn_frame.pack(pady=6)
    tk.Button(btn_frame, text=t("cancel"), command=cancel, width=12).pack(side="left", padx=6)
    tk.Button(btn_frame, text=t("activate"), command=submit, width=12, bg="#2f6fed", fg="white").pack(side="left", padx=6)
    win.bind("<Return>", lambda e: submit())

    win.mainloop()
    return result["key"]


def show_blocking_message(title, message, allow_renew=False):
    win = tk.Tk()
    win.title(title)
    win.geometry("420x200")
    win.resizable(False, False)
    tk.Label(win, text=title, font=("Segoe UI", 13, "bold")).pack(pady=(20, 6))
    tk.Label(win, text=message, font=("Segoe UI", 10), wraplength=380, justify="center").pack(pady=4)

    def open_renewal():
        webbrowser.open(RENEWAL_URL)

    btn_frame = tk.Frame(win)
    btn_frame.pack(pady=14)
    if allow_renew:
        tk.Button(btn_frame, text=t("renew_now"), command=open_renewal, bg="#2f6fed", fg="white", width=14).pack(side="left", padx=6)
    tk.Button(btn_frame, text=t("close"), command=win.destroy, width=14).pack(side="left", padx=6)
    win.mainloop()


def ensure_valid_license():
    """
    Roda ANTES de abrir o app principal. Garante que existe uma licença válida
    para este computador. Retorna True se pode continuar, False se deve encerrar.
    """
    fingerprint = get_machine_fingerprint()
    key = load_saved_license_key()

    # Caso 1: ainda não ativado neste computador -> pede a chave
    if not key:
        while True:
            typed_key = prompt_for_license_key()
            if not typed_key:
                return False  # usuário cancelou
            result, error = call_license_api("/license/activate", {
                "licenseKey": typed_key,
                "machineFingerprint": fingerprint,
                "machineName": platform.node(),
            })
            if error:
                prompt_for_license_key(error_message=t("connection_error_message"))
                continue
            if result.get("ok"):
                save_license_key(typed_key)
                return True
            reason = result.get("reason")
            if reason == "already_activated_elsewhere":
                msg = t("already_activated_message")
            elif reason == "not_found":
                msg = t("not_found_message")
            else:
                msg = t("generic_activation_error")
            # tenta de novo, mostrando o motivo
            typed_key_retry = prompt_for_license_key(error_message=msg)
            if not typed_key_retry:
                return False
            result2, error2 = call_license_api("/license/activate", {
                "licenseKey": typed_key_retry,
                "machineFingerprint": fingerprint,
                "machineName": platform.node(),
            })
            if not error2 and result2.get("ok"):
                save_license_key(typed_key_retry)
                return True
            # se continuar falhando, volta ao início do loop
            key = None
            continue

    # Caso 2: já tem chave salva -> valida com o servidor
    result, error = call_license_api("/license/validate", {"licenseKey": key, "machineFingerprint": fingerprint})

    if error:
        # sem internet/servidor fora do ar — permite seguir com aviso (não trava o técnico em campo)
        show_blocking_message(t("license_offline_title"), t("license_offline_message"))
        return True

    if result.get("valid"):
        return True

    reason = result.get("reason")
    if reason == "expired":
        show_blocking_message(t("license_expired_title"), t("license_expired_message"), allow_renew=True)
        return False
    elif reason == "wrong_machine":
        show_blocking_message(t("license_wrong_machine_title"), t("license_wrong_machine_message"))
        return False
    else:
        show_blocking_message(t("license_wrong_machine_title"), t("license_generic_invalid_message"))
        return False


class SessionRecord:
    """Controla o log, o relatório em texto e a gravação de vídeo de UMA sessão."""

    def __init__(self, local_id, remote_id, role):
        self.session_id = str(uuid.uuid4())
        self.local_id = local_id
        self.remote_id = remote_id
        self.role = role  # 'host' ou 'viewer'
        self.start_time = datetime.now()
        self.video_writer = None
        self.video_path = None
        self.rating = None
        self.rating_comment = None

    def set_rating(self, rating, comment):
        self.rating = rating
        self.rating_comment = comment

    def _base_filename(self):
        ts = self.start_time.strftime("%Y%m%d_%H%M%S")
        return f"sessao_{ts}_{self.role}_{self.remote_id}"

    def ensure_writer(self, width, height, fps=15):
        if self.video_writer is None:
            self.video_path = os.path.join(VIDEOS_DIR, self._base_filename() + ".mp4")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.video_writer = cv2.VideoWriter(self.video_path, fourcc, fps, (width, height))

    def write_frame_bgr(self, img_bgr):
        try:
            h, w = img_bgr.shape[:2]
            self.ensure_writer(w, h)
            self.video_writer.write(img_bgr)
        except Exception as e:
            print("Erro ao gravar frame:", e)

    def _write_text_report(self, entry):
        text_path = os.path.join(VIDEOS_DIR, self._base_filename() + ".txt")
        papel_desc = "Você acessou o computador remoto" if entry["role"] == "viewer" else "Este computador foi acessado remotamente"
        rating_line = ""
        if entry.get("rating"):
            stars = "★" * entry["rating"] + "☆" * (5 - entry["rating"])
            rating_line = f"\nAvaliação do cliente: {stars} ({entry['rating']}/5)"
            if entry.get("rating_comment"):
                rating_line += f'\nComentário: "{entry["rating_comment"]}"'
            rating_line += "\n"
        content = (
            "RELATÓRIO DE SESSÃO - ACESSO REMOTO\n"
            "====================================\n\n"
            f"Data/hora de início: {entry['start']}\n"
            f"Data/hora de término: {entry['end']}\n"
            f"Duração: {entry['duration_seconds'] // 60} min {entry['duration_seconds'] % 60} s\n\n"
            f"{papel_desc}\n"
            f"ID deste computador: {entry['local_id']}\n"
            f"ID do computador remoto: {entry['remote_id']}\n"
            f"{rating_line}\n"
            f"Vídeo da sessão: {os.path.basename(entry['video_file']) if entry['video_file'] else '(não gerado)'}\n"
        )
        try:
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            print("Erro ao salvar relatório em texto:", e)
            return None
        return text_path

    def close_and_log(self):
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

        end_time = datetime.now()
        entry = {
            "id": self.session_id,
            "start": self.start_time.isoformat(timespec="seconds"),
            "end": end_time.isoformat(timespec="seconds"),
            "duration_seconds": int((end_time - self.start_time).total_seconds()),
            "local_id": self.local_id,
            "remote_id": self.remote_id,
            "role": self.role,  # 'host' = esta máquina foi acessada | 'viewer' = esta máquina acessou a outra
            "video_file": self.video_path,
            "rating": self.rating,
            "rating_comment": self.rating_comment,
        }
        entry["text_file"] = self._write_text_report(entry)

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print("Erro ao salvar log:", e)
        return entry


def update_last_session_rating(remote_id, rating, comment):
    """
    Roda no lado do TÉCNICO ao receber uma avaliação, tempos depois do fim
    da sessão. Encontra a sessão mais recente com esse cliente e anexa a
    avaliação retroativamente (a sessão já estava salva sem nota).
    """
    if not os.path.exists(LOG_FILE):
        return False

    entries = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    # procura de trás para frente (mais recente primeiro) a última sessão
    # como viewer com esse remote_id que ainda não tem avaliação
    target_index = None
    for i in range(len(entries) - 1, -1, -1):
        e = entries[i]
        if e.get("role") == "viewer" and e.get("remote_id") == remote_id and not e.get("rating"):
            target_index = i
            break

    if target_index is None:
        return False

    entries[target_index]["rating"] = rating
    entries[target_index]["rating_comment"] = comment

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # também atualiza o relatório em texto, se existir
    text_file = entries[target_index].get("text_file")
    if text_file and os.path.exists(text_file):
        try:
            stars = "★" * rating + "☆" * (5 - rating)
            with open(text_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n[Avaliação recebida após o fechamento do relatório]\n")
                f.write(f"Avaliação do cliente: {stars} ({rating}/5)\n")
                if comment:
                    f.write(f'Comentário: "{comment}"\n')
        except Exception as e:
            print("Erro ao atualizar relatório em texto com avaliação:", e)

    return True


BILLING_RATE_FILE = os.path.join(os.path.expanduser("~"), ".henndesk_billing_rate.json")


def load_hourly_rate():
    if os.path.exists(BILLING_RATE_FILE):
        try:
            with open(BILLING_RATE_FILE, "r") as f:
                return json.load(f).get("hourly_rate", 0.0)
        except Exception:
            return 0.0
    return 0.0


def save_hourly_rate(rate):
    with open(BILLING_RATE_FILE, "w") as f:
        json.dump({"hourly_rate": rate}, f)


def _period_bounds(period):
    """Retorna (início, fim) do período como objetos datetime, ou (None, None) para 'todos'."""
    now = datetime.now()
    if period == "this_month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if period == "last_month":
        first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_of_previous = first_of_this_month - timedelta(seconds=1)
        start = last_of_previous.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, last_of_previous
    return None, None  # "todos"


def compute_billing_summary(entries, period="all", favorites=None):
    """
    Agrupa as sessões em que VOCÊ acessou outra máquina (role='viewer' —
    ou seja, prestou serviço) por ID remoto, somando tempo total e contando
    sessões, dentro do período pedido. Usa o nome do favorito quando existe.
    """
    start, end = _period_bounds(period)
    favorites = favorites or []
    id_to_name = {f["id"]: f["name"] for f in favorites}

    grouped = {}
    for entry in entries:
        if entry.get("role") != "viewer":
            continue
        try:
            entry_time = datetime.fromisoformat(entry["start"])
        except Exception:
            continue
        if start and entry_time < start:
            continue
        if end and entry_time > end:
            continue

        remote_id = entry.get("remote_id", "desconhecido")
        if remote_id not in grouped:
            grouped[remote_id] = {
                "remote_id": remote_id,
                "name": id_to_name.get(remote_id),
                "session_count": 0,
                "total_seconds": 0,
            }
        grouped[remote_id]["session_count"] += 1
        grouped[remote_id]["total_seconds"] += entry.get("duration_seconds", 0)

    result = list(grouped.values())
    result.sort(key=lambda r: r["total_seconds"], reverse=True)
    return result


def format_hours_minutes(total_seconds):
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours}h {minutes:02d}min"


def load_session_log():
    if not os.path.exists(LOG_FILE):
        return []
    entries = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
    return list(reversed(entries))  # mais recente primeiro


def delete_session_entry(session_id):
    """Remove a entrada do log e apaga os arquivos de vídeo/texto associados."""
    if not os.path.exists(LOG_FILE):
        return
    entries = []
    target = None
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("id") == session_id:
                target = entry
                continue
            entries.append(entry)

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if target:
        for key in ("video_file", "text_file"):
            path = target.get(key)
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"Erro ao apagar {path}:", e)


FAVORITES_FILE = os.path.join(os.path.expanduser("~"), ".henndesk_favorites.json")


def load_favorites():
    if not os.path.exists(FAVORITES_FILE):
        return []
    try:
        with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_favorites(favorites):
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(favorites, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Erro ao salvar favoritos:", e)


def open_file(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
    except Exception as e:
        print("Não foi possível abrir o arquivo:", e)


def open_folder(path):
    open_file(path)


def collect_system_diagnostics():
    """
    Coleta informações básicas da máquina (rodada no lado que está sendo
    acessado), para mostrar ao técnico assim que a conexão é estabelecida.
    Cada informação é coletada de forma isolada — se uma falhar, as outras
    continuam disponíveis.
    """
    info = {"type": "system-info"}

    try:
        info["hostname"] = platform.node()
    except Exception:
        info["hostname"] = "?"

    try:
        info["os"] = f"{platform.system()} {platform.release()}"
    except Exception:
        info["os"] = "?"

    try:
        vm = psutil.virtual_memory()
        info["ram_total_gb"] = round(vm.total / (1024 ** 3), 1)
        info["ram_used_percent"] = vm.percent
    except Exception:
        info["ram_total_gb"] = None
        info["ram_used_percent"] = None

    try:
        info["cpu_percent"] = psutil.cpu_percent(interval=0.3)
        info["cpu_cores"] = psutil.cpu_count(logical=True)
    except Exception:
        info["cpu_percent"] = None
        info["cpu_cores"] = None

    disks = []
    try:
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "drive": part.device,
                    "total_gb": round(usage.total / (1024 ** 3), 1),
                    "free_gb": round(usage.free / (1024 ** 3), 1),
                    "percent_used": usage.percent,
                })
            except Exception:
                continue
    except Exception:
        pass
    info["disks"] = disks

    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        info["uptime_hours"] = round(uptime.total_seconds() / 3600, 1)
    except Exception:
        info["uptime_hours"] = None

    return info


def format_diagnostics_summary(info):
    """Resumo curto, de uma linha, para mostrar na barra de ferramentas."""
    parts = []
    if info.get("os"):
        parts.append(info["os"])
    if info.get("ram_used_percent") is not None:
        parts.append(f'RAM {info["ram_used_percent"]:.0f}%')
    if info.get("disks"):
        main_disk = info["disks"][0]
        parts.append(f'{main_disk["drive"]} {main_disk["free_gb"]}GB livres')
    return " · ".join(parts) if parts else "—"


class ScreenShareTrack(VideoStreamTrack):
    """Usado quando ESTA máquina está sendo acessada (papel de host)."""

    def __init__(self, fps=15, on_frame=None):
        super().__init__()
        self.fps = fps
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]
        self._frame_count = 0
        self.on_frame = on_frame  # callback(img_bgr) opcional, usado para gravação

    async def recv(self):
        self._frame_count += 1
        pts = int(self._frame_count * (90000 / self.fps))
        time_base = Fraction(1, 90000)

        img = np.array(self.sct.grab(self.monitor))[:, :, :3]

        if self.on_frame is not None:
            try:
                self.on_frame(img)
            except Exception as e:
                print("Erro no callback de gravação:", e)

        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        return frame


class FileTransferManager:
    """
    Cuida do envio e recebimento de arquivos pela conexão WebRTC (canal de
    dados separado do canal de controle de mouse/teclado). Suporta um
    arquivo por vez, em pedaços de 16KB, com controle de fluxo simples para
    não sobrecarregar o buffer da conexão.
    """

    def __init__(self, gui_queue, asyncio_loop_getter):
        self.gui_queue = gui_queue
        self.get_loop = asyncio_loop_getter
        self.file_channel = None
        self.receiving = None  # dict com handle do arquivo, nome, tamanho, bytes recebidos

    def set_channel(self, channel):
        self.file_channel = channel

        @channel.on("message")
        def on_message(message):
            self._handle_incoming(message)

    def _unique_path(self, filename):
        os.makedirs(RECEIVED_FILES_DIR, exist_ok=True)
        base_path = os.path.join(RECEIVED_FILES_DIR, filename)
        if not os.path.exists(base_path):
            return base_path
        name, ext = os.path.splitext(filename)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(RECEIVED_FILES_DIR, f"{name}_{ts}{ext}")

    def _handle_incoming(self, message):
        if isinstance(message, (bytes, bytearray)):
            if self.receiving:
                self.receiving["handle"].write(message)
                self.receiving["received"] += len(message)
                percent = int((self.receiving["received"] / self.receiving["size"]) * 100) if self.receiving["size"] else 100
                self.gui_queue.put(("file-progress", {
                    "direction": "receiving", "name": self.receiving["name"], "percent": percent
                }))
            return

        try:
            data = json.loads(message)
        except Exception:
            return

        if data.get("type") == "file-start":
            safe_path = self._unique_path(data["name"])
            self.receiving = {
                "handle": open(safe_path, "wb"),
                "name": os.path.basename(safe_path),
                "path": safe_path,
                "size": data.get("size", 0),
                "received": 0,
            }
            self.gui_queue.put(("file-progress", {"direction": "receiving", "name": self.receiving["name"], "percent": 0}))

        elif data.get("type") == "file-end":
            if self.receiving:
                self.receiving["handle"].close()
                self.gui_queue.put(("file-received", {"name": self.receiving["name"], "path": self.receiving["path"]}))
                self.receiving = None

    async def send_file(self, filepath):
        if not self.file_channel or self.file_channel.readyState != "open":
            self.gui_queue.put(("file-error", t("file_channel_not_ready")))
            return

        transfer_id = str(uuid.uuid4())
        name = os.path.basename(filepath)
        size = os.path.getsize(filepath)

        self.file_channel.send(json.dumps({"type": "file-start", "id": transfer_id, "name": name, "size": size}))

        sent = 0
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(FILE_TRANSFER_CHUNK_SIZE)
                if not chunk:
                    break
                while self.file_channel.bufferedAmount > FILE_TRANSFER_BUFFER_THRESHOLD:
                    await asyncio.sleep(0.01)
                self.file_channel.send(chunk)
                sent += len(chunk)
                percent = int((sent / size) * 100) if size else 100
                self.gui_queue.put(("file-progress", {"direction": "sending", "name": name, "percent": percent}))

        self.file_channel.send(json.dumps({"type": "file-end", "id": transfer_id}))
        self.gui_queue.put(("file-sent", {"name": name}))


class RemoteAccessApp:
    def __init__(self):
        self.machine_id = get_or_create_machine_id()
        self.ws = None
        self.asyncio_loop = None
        self.pc = None
        self.role = None  # 'host' ou 'viewer'
        self.gui_queue = queue.Queue()   # asyncio -> tkinter
        self.video_queue = queue.Queue(maxsize=2)  # frames recebidos -> tkinter (papel de viewer)
        self.data_channel = None
        self.screen_w, self.screen_h = mss.mss().monitors[1]["width"], mss.mss().monitors[1]["height"]

        self.viewer_window = None
        self.viewer_canvas = None
        self.viewer_photo = None
        self.file_transfer_label = None
        self.diagnostics_label = None
        self.last_diagnostics = None

        self.current_session = None  # SessionRecord da sessão em andamento

        self.file_transfer = FileTransferManager(self.gui_queue, lambda: self.asyncio_loop)

        self._build_gui()
        self._start_asyncio_thread()
        self.root.after(100, self._poll_gui_queue)
        self.root.after(50, self._poll_video_queue)

    # ---------------- GUI ----------------
    def _build_gui(self):
        self.root = tk.Tk()
        self.root.title("HennDesk")
        self.root.geometry("380x510")
        self.root.resizable(False, False)

        top_bar = tk.Frame(self.root)
        top_bar.pack(fill="x", padx=10, pady=(6, 0))
        tk.Button(top_bar, text=t("language_btn"), command=self._open_language_selector,
                  font=("Segoe UI", 8)).pack(side="right")

        self.id_title_label = tk.Label(self.root, text=t("your_id"), font=("Segoe UI", 11))
        self.id_title_label.pack(pady=(10, 0))
        self.id_label = tk.Label(self.root, text=self.machine_id, font=("Segoe UI", 22, "bold"), fg="#2f6fed")
        self.id_label.pack(pady=(0, 4))
        self.copy_id_btn = tk.Button(self.root, text=t("copy_id"), command=self._copy_id)
        self.copy_id_btn.pack()

        tk.Frame(self.root, height=2, bg="#ddd").pack(fill="x", pady=12, padx=20)

        self.access_other_label = tk.Label(self.root, text=t("access_other"), font=("Segoe UI", 11))
        self.access_other_label.pack()
        entry_frame = tk.Frame(self.root)
        entry_frame.pack(pady=6)
        self.target_entry = tk.Entry(entry_frame, font=("Segoe UI", 13), width=14, justify="center")
        self.target_entry.pack(side="left", padx=4)
        self.connect_btn = tk.Button(entry_frame, text=t("connect"), command=self._on_connect_clicked)
        self.connect_btn.pack(side="left", padx=4)

        self.save_favorite_btn = tk.Button(self.root, text=t("save_favorite_btn"), command=self._on_add_favorite,
                                            font=("Segoe UI", 9))
        self.save_favorite_btn.pack(pady=(0, 6))

        tk.Frame(self.root, height=2, bg="#ddd").pack(fill="x", pady=8, padx=20)

        self.favorites_title_label = tk.Label(self.root, text=t("favorites_title"), font=("Segoe UI", 11, "bold"))
        self.favorites_title_label.pack()

        fav_frame = tk.Frame(self.root)
        fav_frame.pack(pady=(6, 0), padx=20, fill="both")
        fav_scrollbar = tk.Scrollbar(fav_frame, orient="vertical")
        self.favorites_list = tk.Listbox(fav_frame, height=6, font=("Segoe UI", 10),
                                          yscrollcommand=fav_scrollbar.set)
        fav_scrollbar.config(command=self.favorites_list.yview)
        self.favorites_list.pack(side="left", fill="both", expand=True)
        fav_scrollbar.pack(side="right", fill="y")
        self.favorites_list.bind("<Double-1>", self._on_favorite_double_click)

        fav_btn_frame = tk.Frame(self.root)
        fav_btn_frame.pack(pady=6)
        self.access_selected_btn = tk.Button(fav_btn_frame, text=t("access_selected"), command=self._on_connect_favorite)
        self.access_selected_btn.pack(side="left", padx=4)
        self.edit_favorite_btn = tk.Button(fav_btn_frame, text=t("edit_client_btn"), command=self._on_edit_favorite)
        self.edit_favorite_btn.pack(side="left", padx=4)
        self.remove_favorite_btn = tk.Button(fav_btn_frame, text=t("remove"), command=self._on_remove_favorite, fg="#c0392b")
        self.remove_favorite_btn.pack(side="left", padx=4)

        self.status_label = tk.Label(self.root, text=t("status_connecting_server"), fg="#888", font=("Segoe UI", 9))
        self.status_label.pack(pady=(10, 0))

        self.history_btn = tk.Button(self.root, text=t("history_btn"), command=self._open_history_window)
        self.history_btn.pack(pady=(8, 0))

        self._refresh_favorites_list()

    def _apply_language_to_main_window(self):
        """Atualiza os textos fixos da janela principal após trocar o idioma."""
        self.id_title_label.config(text=t("your_id"))
        self.copy_id_btn.config(text=t("copy_id"))
        self.access_other_label.config(text=t("access_other"))
        self.connect_btn.config(text=t("connect"))
        self.save_favorite_btn.config(text=t("save_favorite_btn"))
        self.favorites_title_label.config(text=t("favorites_title"))
        self.access_selected_btn.config(text=t("access_selected"))
        self.edit_favorite_btn.config(text=t("edit_client_btn"))
        self.remove_favorite_btn.config(text=t("remove"))
        self.history_btn.config(text=t("history_btn"))

    def _open_language_selector(self):
        win = tk.Toplevel(self.root)
        win.title(t("choose_language_title"))
        win.geometry("260x180")
        win.resizable(False, False)

        def choose(lang):
            set_language(lang)
            self._apply_language_to_main_window()
            win.destroy()

        tk.Label(win, text="🌐", font=("Segoe UI", 24)).pack(pady=(16, 6))
        tk.Button(win, text="Português", width=18, command=lambda: choose("pt")).pack(pady=4)
        tk.Button(win, text="English", width=18, command=lambda: choose("en")).pack(pady=4)
        tk.Button(win, text="Español", width=18, command=lambda: choose("es")).pack(pady=4)

    def _refresh_favorites_list(self):
        self.favorites_list.delete(0, tk.END)
        self._favorites_cache = load_favorites()
        for fav in self._favorites_cache:
            self.favorites_list.insert(tk.END, f'{fav["name"]}  —  {fav["id"]}')

    def _on_add_favorite(self):
        target_id = self.target_entry.get().strip()
        if not target_id:
            messagebox.showinfo(t("id_required_title"), t("id_required_message"))
            return

        win = tk.Toplevel(self.root)
        win.title(t("save_favorite_title"))
        win.geometry("320x160")
        win.resizable(False, False)
        tk.Label(win, text=t("saving_id", id=target_id), font=("Segoe UI", 10)).pack(pady=(16, 4))
        tk.Label(win, text=t("name_prompt"), font=("Segoe UI", 9), fg="#555").pack()
        name_entry = tk.Entry(win, font=("Segoe UI", 12), justify="center", width=24)
        name_entry.pack(pady=10)
        name_entry.focus_set()

        def save():
            name = name_entry.get().strip()
            if not name:
                return
            favorites = load_favorites()
            favorites.append({"name": name, "id": target_id, "phone": "", "email": "", "notes": ""})
            save_favorites(favorites)
            self._refresh_favorites_list()
            win.destroy()

        tk.Button(win, text=t("save"), command=save, bg="#2f6fed", fg="white", width=14).pack(pady=4)
        win.bind("<Return>", lambda e: save())

    def _get_selected_favorite(self):
        selection = self.favorites_list.curselection()
        if not selection:
            messagebox.showinfo(t("no_favorite_title"), t("no_favorite_message"))
            return None
        return self._favorites_cache[selection[0]]

    def _on_edit_favorite(self):
        fav = self._get_selected_favorite()
        if not fav:
            return

        win = tk.Toplevel(self.root)
        win.title(t("edit_client_title"))
        win.geometry("360x420")
        win.resizable(False, False)

        tk.Label(win, text=f'ID: {fav["id"]}', font=("Segoe UI", 9), fg="#888").pack(pady=(16, 8))

        tk.Label(win, text=t("name_prompt"), font=("Segoe UI", 9), fg="#555").pack(anchor="w", padx=24)
        name_entry = tk.Entry(win, font=("Segoe UI", 11), width=30)
        name_entry.insert(0, fav.get("name", ""))
        name_entry.pack(padx=24, pady=(2, 10), fill="x")

        tk.Label(win, text=t("phone_label"), font=("Segoe UI", 9), fg="#555").pack(anchor="w", padx=24)
        phone_entry = tk.Entry(win, font=("Segoe UI", 11), width=30)
        phone_entry.insert(0, fav.get("phone", ""))
        phone_entry.pack(padx=24, pady=(2, 10), fill="x")

        tk.Label(win, text=t("email_label"), font=("Segoe UI", 9), fg="#555").pack(anchor="w", padx=24)
        email_entry = tk.Entry(win, font=("Segoe UI", 11), width=30)
        email_entry.insert(0, fav.get("email", ""))
        email_entry.pack(padx=24, pady=(2, 10), fill="x")

        tk.Label(win, text=t("notes_label"), font=("Segoe UI", 9), fg="#555").pack(anchor="w", padx=24)
        notes_text = tk.Text(win, font=("Segoe UI", 10), width=30, height=5)
        notes_text.insert("1.0", fav.get("notes", ""))
        notes_text.pack(padx=24, pady=(2, 10), fill="both")

        def save_edit():
            favorites = load_favorites()
            for f in favorites:
                if f["id"] == fav["id"]:
                    f["name"] = name_entry.get().strip() or f["name"]
                    f["phone"] = phone_entry.get().strip()
                    f["email"] = email_entry.get().strip()
                    f["notes"] = notes_text.get("1.0", "end").strip()
                    break
            save_favorites(favorites)
            self._refresh_favorites_list()
            win.destroy()

        tk.Button(win, text=t("save"), command=save_edit, bg="#2f6fed", fg="white", width=16).pack(pady=8)

    def _on_connect_favorite(self):
        fav = self._get_selected_favorite()
        if not fav:
            return
        self.target_entry.delete(0, tk.END)
        self.target_entry.insert(0, fav["id"])
        self._initiate_connection(fav["id"])

    def _on_favorite_double_click(self, event):
        self._on_connect_favorite()

    def _on_remove_favorite(self):
        fav = self._get_selected_favorite()
        if not fav:
            return
        if messagebox.askyesno(t("remove_favorite_title"), t("remove_favorite_message", name=fav["name"])):
            favorites = load_favorites()
            favorites = [f for f in favorites if not (f["name"] == fav["name"] and f["id"] == fav["id"])]
            save_favorites(favorites)
            self._refresh_favorites_list()


    def _open_history_window(self):
        win = tk.Toplevel(self.root)
        win.title(t("history_window_title"))
        win.geometry("660x500")

        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        sessions_tab = tk.Frame(notebook)
        billing_tab = tk.Frame(notebook)
        tips_tab = tk.Frame(notebook)
        notebook.add(sessions_tab, text=t("tab_sessions"))
        notebook.add(billing_tab, text=t("tab_billing"))
        notebook.add(tips_tab, text=t("tab_tips"))

        # ---- Aba de sessões ----
        columns = (t("col_datetime"), t("col_role"), t("col_remote_id"), t("col_duration"), t("col_rating"))
        tree_frame = tk.Frame(sessions_tab)
        tree_frame.pack(fill="both", expand=True, padx=6, pady=(10, 6))

        tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=110)
        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        row_to_entry = {}

        def refresh_list():
            tree.delete(*tree.get_children())
            row_to_entry.clear()
            entries = load_session_log()
            for entry in entries:
                role_label = t("role_you_accessed") if entry["role"] == "viewer" else t("role_was_accessed")
                duration = f'{entry["duration_seconds"] // 60}min {entry["duration_seconds"] % 60}s'
                rating_display = "★" * entry["rating"] if entry.get("rating") else "-"
                row_id = tree.insert("", "end", values=(entry["start"], role_label, entry["remote_id"], duration, rating_display))
                row_to_entry[row_id] = entry
            if not entries:
                empty_label.pack(pady=20)
            else:
                empty_label.pack_forget()

        empty_label = tk.Label(sessions_tab, text=t("no_sessions_yet"), fg="#888")

        def get_selected_entry():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo(t("no_favorite_title"), t("no_favorite_message"))
                return None
            return row_to_entry.get(selected[0])

        def on_open_video():
            entry = get_selected_entry()
            if not entry:
                return
            path = entry.get("video_file")
            if path and os.path.exists(path):
                open_file(path)
            else:
                messagebox.showinfo(t("video_unavailable_title"), t("video_unavailable_message"))

        def on_open_report():
            entry = get_selected_entry()
            if not entry:
                return
            path = entry.get("text_file")
            if path and os.path.exists(path):
                open_file(path)
            else:
                messagebox.showinfo(t("report_unavailable_title"), t("report_unavailable_message"))

        def on_save_copy():
            entry = get_selected_entry()
            if not entry:
                return
            dest_dir = filedialog.askdirectory(title=t("choose_folder_title"))
            if not dest_dir:
                return
            copied = []
            for key in ("video_file", "text_file"):
                src = entry.get(key)
                if src and os.path.exists(src):
                    try:
                        shutil.copy2(src, dest_dir)
                        copied.append(os.path.basename(src))
                    except Exception as e:
                        messagebox.showerror("Error", str(e))
            if copied:
                messagebox.showinfo(t("copied_title"), t("copied_message") + "\n" + dest_dir + "\n\n" + "\n".join(copied))

        def on_delete():
            entry = get_selected_entry()
            if not entry:
                return
            if messagebox.askyesno(t("confirm_delete_title"), t("confirm_delete_message")):
                delete_session_entry(entry["id"])
                refresh_list()

        btn_frame = tk.Frame(sessions_tab)
        btn_frame.pack(fill="x", padx=6, pady=(0, 10))
        tk.Button(btn_frame, text=t("open_video"), command=on_open_video).pack(side="left", padx=4)
        tk.Button(btn_frame, text=t("open_report"), command=on_open_report).pack(side="left", padx=4)
        tk.Button(btn_frame, text=t("save_copy"), command=on_save_copy).pack(side="left", padx=4)
        tk.Button(btn_frame, text=t("delete"), command=on_delete, fg="#c0392b").pack(side="left", padx=4)
        tk.Button(btn_frame, text=t("open_videos_folder"), command=lambda: open_folder(VIDEOS_DIR)).pack(side="right", padx=4)

        refresh_list()

        # ---- Aba de relatório de horas (cobrança) ----
        top_billing = tk.Frame(billing_tab)
        top_billing.pack(fill="x", padx=10, pady=(10, 4))

        period_var = tk.StringVar(value="this_month")
        period_options = [
            (t("period_this_month"), "this_month"),
            (t("period_last_month"), "last_month"),
            (t("period_all"), "all"),
        ]
        for label, value in period_options:
            tk.Radiobutton(top_billing, text=label, variable=period_var, value=value,
                            command=lambda: refresh_billing()).pack(side="left", padx=4)

        rate_frame = tk.Frame(billing_tab)
        rate_frame.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(rate_frame, text=t("hourly_rate_label")).pack(side="left")
        rate_entry = tk.Entry(rate_frame, width=10, justify="center")
        rate_entry.insert(0, str(load_hourly_rate()))
        rate_entry.pack(side="left", padx=6)

        def on_save_rate():
            try:
                rate = float(rate_entry.get().replace(",", "."))
            except ValueError:
                rate = 0.0
            save_hourly_rate(rate)
            refresh_billing()

        tk.Button(rate_frame, text=t("save_rate"), command=on_save_rate).pack(side="left")

        billing_tree_frame = tk.Frame(billing_tab)
        billing_tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        billing_columns = (t("col_client"), t("col_sessions"), t("col_total_time"), t("col_estimated_value"))
        billing_tree = ttk.Treeview(billing_tree_frame, columns=billing_columns, show="headings")
        for col in billing_columns:
            billing_tree.heading(col, text=col)
            billing_tree.column(col, width=140)
        billing_tree.pack(side="left", fill="both", expand=True)

        billing_scrollbar = ttk.Scrollbar(billing_tree_frame, orient="vertical", command=billing_tree.yview)
        billing_tree.configure(yscrollcommand=billing_scrollbar.set)
        billing_scrollbar.pack(side="right", fill="y")

        billing_empty_label = tk.Label(billing_tab, text=t("no_billing_data"), fg="#888")
        billing_summary_cache = []

        def refresh_billing():
            nonlocal billing_summary_cache
            billing_tree.delete(*billing_tree.get_children())
            entries = load_session_log()
            favorites = load_favorites()
            rate = load_hourly_rate()
            summary = compute_billing_summary(entries, period=period_var.get(), favorites=favorites)
            billing_summary_cache = summary

            for row in summary:
                label = row["name"] or row["remote_id"]
                hours_decimal = row["total_seconds"] / 3600
                value_str = f'{hours_decimal * rate:.2f}' if rate else "-"
                billing_tree.insert("", "end", values=(
                    label, row["session_count"], format_hours_minutes(row["total_seconds"]), value_str
                ))

            if not summary:
                billing_empty_label.pack(pady=20)
            else:
                billing_empty_label.pack_forget()

        def on_export_billing():
            dest = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if not dest:
                return
            rate = load_hourly_rate()
            with open(dest, "w", encoding="utf-8") as f:
                f.write(f'{t("col_client")},{t("col_sessions")},{t("col_total_time")},{t("col_estimated_value")}\n')
                for row in billing_summary_cache:
                    label = row["name"] or row["remote_id"]
                    hours_decimal = row["total_seconds"] / 3600
                    value_str = f'{hours_decimal * rate:.2f}' if rate else ""
                    f.write(f'{label},{row["session_count"]},{format_hours_minutes(row["total_seconds"])},{value_str}\n')
            messagebox.showinfo(t("billing_exported_title"), t("billing_exported_message") + "\n" + dest)

        billing_btn_frame = tk.Frame(billing_tab)
        billing_btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(billing_btn_frame, text=t("export_billing_csv"), command=on_export_billing).pack(side="right")

        refresh_billing()

        # ---- Aba de dicas ----
        tips_label = tk.Label(tips_tab, text=t("tips_text"), justify="left", wraplength=560, padx=16, pady=16)
        tips_label.pack(anchor="w", fill="both", expand=True)

    def _copy_id(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.machine_id)

    def _set_status(self, text):
        self.gui_queue.put(("status", text))

    def _on_connect_clicked(self):
        target_id = self.target_entry.get().strip()
        if not target_id:
            return
        self._initiate_connection(target_id)

    def _initiate_connection(self, target_id):
        self.connect_btn.config(state="disabled")
        self._set_status(t("status_requesting", id=target_id))
        asyncio.run_coroutine_threadsafe(self._request_connect(target_id), self.asyncio_loop)

    def _poll_gui_queue(self):
        try:
            while True:
                kind, payload = self.gui_queue.get_nowait()
                if kind == "status":
                    self.status_label.config(text=payload)
                elif kind == "incoming-request":
                    self._show_incoming_request_dialog(payload)
                elif kind == "reenable-connect":
                    self.connect_btn.config(state="normal")
                elif kind == "open-viewer":
                    self._open_viewer_window()
                elif kind == "close-viewer":
                    self._close_viewer_window()
                elif kind == "file-progress":
                    self._update_file_transfer_label(payload)
                elif kind == "file-sent":
                    self._on_file_transfer_finished(t("file_sent", name=payload["name"]))
                elif kind == "file-received":
                    self._on_file_transfer_finished(f'{t("file_received_title")}: {payload["name"]}')
                    messagebox.showinfo(t("file_received_title"), t("file_received_message", name=payload["name"], path=payload["path"]))
                elif kind == "file-error":
                    self._on_file_transfer_finished(payload)
                elif kind == "system-info":
                    self._on_system_info_received(payload)
                elif kind == "request-rating":
                    self._show_rating_dialog()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_gui_queue)

    def _on_system_info_received(self, info):
        self.last_diagnostics = info
        if hasattr(self, "diagnostics_label") and self.diagnostics_label is not None:
            self.diagnostics_label.config(text="ℹ " + format_diagnostics_summary(info))

    def _update_file_transfer_label(self, payload):
        if not hasattr(self, "file_transfer_label") or self.file_transfer_label is None:
            return
        key = "sending_file" if payload["direction"] == "sending" else "receiving_file"
        self.file_transfer_label.config(text=t(key, name=payload["name"], percent=payload["percent"]))

    def _on_file_transfer_finished(self, message):
        if hasattr(self, "file_transfer_label") and self.file_transfer_label is not None:
            self.file_transfer_label.config(text=message)

    def _poll_video_queue(self):
        try:
            img = self.video_queue.get_nowait()
            if self.viewer_canvas is not None:
                canvas_w = self.viewer_canvas.winfo_width() or 960
                canvas_h = self.viewer_canvas.winfo_height() or 600
                pil_img = Image.fromarray(img).resize((canvas_w, canvas_h))
                self.viewer_photo = ImageTk.PhotoImage(pil_img)
                self.viewer_canvas.create_image(0, 0, anchor="nw", image=self.viewer_photo)
        except queue.Empty:
            pass
        self.root.after(40, self._poll_video_queue)

    def _show_incoming_request_dialog(self, technician_name):
        result = messagebox.askyesno(
            t("incoming_request_title"),
            t("incoming_request_message", name=technician_name)
        )
        asyncio.run_coroutine_threadsafe(self._respond_request(result), self.asyncio_loop)

    def _show_rating_dialog(self):
        win = tk.Toplevel(self.root)
        win.title(t("rating_dialog_title"))
        win.geometry("360x260")
        win.resizable(False, False)
        win.attributes("-topmost", True)

        tk.Label(win, text="⭐", font=("Segoe UI", 28)).pack(pady=(18, 4))
        tk.Label(win, text=t("rating_question"), font=("Segoe UI", 11), wraplength=320, justify="center").pack(pady=(0, 12))

        rating_var = tk.IntVar(value=0)
        stars_frame = tk.Frame(win)
        stars_frame.pack()

        star_buttons = []

        def set_rating(n):
            rating_var.set(n)
            for i, btn in enumerate(star_buttons, start=1):
                btn.config(text="★" if i <= n else "☆", fg="#f5a623" if i <= n else "#bbb")

        for i in range(1, 6):
            btn = tk.Button(stars_frame, text="☆", font=("Segoe UI", 18), fg="#bbb", bd=0,
                             command=lambda n=i: set_rating(n))
            btn.pack(side="left", padx=2)
            star_buttons.append(btn)

        comment_entry = tk.Entry(win, font=("Segoe UI", 10), width=36)
        comment_entry.pack(pady=12)

        def submit():
            rating = rating_var.get()
            comment = comment_entry.get().strip()
            win.destroy()
            if rating > 0:
                asyncio.run_coroutine_threadsafe(self._finalize_host_session(rating, comment), self.asyncio_loop)
            else:
                asyncio.run_coroutine_threadsafe(self._finalize_host_session(None, None), self.asyncio_loop)

        def skip():
            win.destroy()
            asyncio.run_coroutine_threadsafe(self._finalize_host_session(None, None), self.asyncio_loop)

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=6)
        tk.Button(btn_frame, text=t("skip_rating"), command=skip, width=12).pack(side="left", padx=6)
        tk.Button(btn_frame, text=t("submit_rating"), command=submit, width=12, bg="#2f6fed", fg="white").pack(side="left", padx=6)

        # não trava o cliente pra sempre — se ignorado, encerra sozinho depois de um tempo
        win.after(30000, skip)

    async def _finalize_host_session(self, rating, comment):
        if rating and self.ws:
            try:
                await self.ws.send(json.dumps({"type": "submit-rating", "rating": rating, "comment": comment or ""}))
            except Exception as e:
                print("Erro ao enviar avaliação:", e)

        if self.current_session is not None:
            if rating:
                self.current_session.set_rating(rating, comment)
            self.current_session.close_and_log()
            self.current_session = None

        if self.pc:
            await self.pc.close()
            self.pc = None

    # ---------------- Janela do viewer (quando VOCÊ está acessando outra máquina) ----------------
    def _open_viewer_window(self):
        self.viewer_window = tk.Toplevel(self.root)
        self.viewer_window.title(t("controlling_title", id=self.current_target_id))
        self.viewer_window.geometry("960x630")

        toolbar = tk.Frame(self.viewer_window, bg="#222")
        toolbar.pack(fill="x", side="top")
        tk.Button(toolbar, text=t("send_file_btn"), command=self._on_send_file_clicked).pack(side="left", padx=6, pady=4)
        self.file_transfer_label = tk.Label(toolbar, text="", bg="#222", fg="#ddd", font=("Segoe UI", 9))
        self.file_transfer_label.pack(side="left", padx=10)

        self.last_diagnostics = None
        self.diagnostics_label = tk.Label(toolbar, text=t("diagnostics_waiting"), bg="#222", fg="#999",
                                           font=("Segoe UI", 9), cursor="hand2")
        self.diagnostics_label.pack(side="right", padx=10)
        self.diagnostics_label.bind("<Button-1>", lambda e: self._open_diagnostics_details())

        self.viewer_canvas = tk.Canvas(self.viewer_window, bg="black", cursor="crosshair")
        self.viewer_canvas.pack(fill="both", expand=True)

        self.viewer_canvas.bind("<Motion>", self._on_viewer_mouse_move)
        self.viewer_canvas.bind("<ButtonPress-1>", lambda e: self._on_viewer_mouse_btn(e, "mousedown", 0))
        self.viewer_canvas.bind("<ButtonRelease-1>", lambda e: self._on_viewer_mouse_btn(e, "mouseup", 0))
        self.viewer_canvas.bind("<ButtonPress-3>", lambda e: self._on_viewer_mouse_btn(e, "mousedown", 2))
        self.viewer_canvas.bind("<ButtonRelease-3>", lambda e: self._on_viewer_mouse_btn(e, "mouseup", 2))
        self.viewer_canvas.bind("<MouseWheel>", self._on_viewer_scroll)
        self.viewer_window.bind("<KeyPress>", lambda e: self._on_viewer_key(e, "keydown"))
        self.viewer_window.bind("<KeyRelease>", lambda e: self._on_viewer_key(e, "keyup"))
        self.viewer_window.protocol("WM_DELETE_WINDOW", self._on_viewer_close)
        self.viewer_canvas.focus_set()

    def _open_diagnostics_details(self):
        if not self.last_diagnostics:
            return
        info = self.last_diagnostics
        win = tk.Toplevel(self.viewer_window)
        win.title(t("diagnostics_title"))
        win.geometry("360x340")
        win.resizable(False, False)

        tk.Label(win, text="ℹ " + t("diagnostics_title"), font=("Segoe UI", 13, "bold")).pack(pady=(16, 10))

        rows_frame = tk.Frame(win)
        rows_frame.pack(fill="both", expand=True, padx=20)

        def add_row(label, value):
            row = tk.Frame(rows_frame)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, font=("Segoe UI", 9), fg="#666", anchor="w", width=16).pack(side="left")
            tk.Label(row, text=value, font=("Segoe UI", 9, "bold"), anchor="w").pack(side="left")

        add_row(t("diag_hostname"), info.get("hostname", "-"))
        add_row(t("diag_os"), info.get("os", "-"))
        if info.get("cpu_cores") is not None:
            add_row(t("diag_cpu"), f'{info["cpu_cores"]} núcleos, {info.get("cpu_percent", 0):.0f}% em uso')
        if info.get("ram_total_gb") is not None:
            add_row(t("diag_ram"), f'{info["ram_total_gb"]}GB total, {info["ram_used_percent"]:.0f}% em uso')
        if info.get("uptime_hours") is not None:
            add_row(t("diag_uptime"), f'{info["uptime_hours"]:.1f}h')

        for disk in info.get("disks", []):
            add_row(disk["drive"], f'{disk["free_gb"]}GB livres de {disk["total_gb"]}GB ({disk["percent_used"]:.0f}% usado)')

        tk.Button(win, text=t("close"), command=win.destroy).pack(pady=14)

    def _on_send_file_clicked(self):
        filepath = filedialog.askopenfilename()
        if not filepath:
            return
        asyncio.run_coroutine_threadsafe(self.file_transfer.send_file(filepath), self.asyncio_loop)

    def _close_viewer_window(self):
        if self.viewer_window is not None:
            self.viewer_window.destroy()
            self.viewer_window = None
            self.viewer_canvas = None
            self.file_transfer_label = None
            self.diagnostics_label = None
            self.last_diagnostics = None

    def _on_viewer_close(self):
        asyncio.run_coroutine_threadsafe(self._end_session(), self.asyncio_loop)
        self._close_viewer_window()

    def _rel_xy(self, event):
        w = self.viewer_canvas.winfo_width() or 1
        h = self.viewer_canvas.winfo_height() or 1
        return max(0, min(1, event.x / w)), max(0, min(1, event.y / h))

    def _send_control(self, cmd):
        if self.data_channel is not None and self.asyncio_loop is not None:
            self.asyncio_loop.call_soon_threadsafe(self._safe_send, json.dumps(cmd))

    def _safe_send(self, data):
        try:
            if self.data_channel and self.data_channel.readyState == "open":
                self.data_channel.send(data)
        except Exception:
            pass

    def _on_viewer_mouse_move(self, event):
        x, y = self._rel_xy(event)
        self._send_control({"type": "mousemove", "x": x, "y": y})

    def _on_viewer_mouse_btn(self, event, kind, button):
        x, y = self._rel_xy(event)
        self._send_control({"type": kind, "x": x, "y": y, "button": button})

    def _on_viewer_scroll(self, event):
        self._send_control({"type": "scroll", "deltaY": -event.delta})

    def _on_viewer_key(self, event, kind):
        key = event.keysym
        self._send_control({"type": kind, "key": key})

    # ---------------- Asyncio / rede (roda em thread separada) ----------------
    def _start_asyncio_thread(self):
        def runner():
            self.asyncio_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.asyncio_loop)
            self.asyncio_loop.run_until_complete(self._main_async())

        threading.Thread(target=runner, daemon=True).start()

    async def _main_async(self):
        async with websockets.connect(SIGNALING_SERVER_URL) as ws:
            self.ws = ws
            await ws.send(json.dumps({"type": "register-agent", "machineId": self.machine_id}))
            self._set_status(t("status_ready", id=self.machine_id))
            async for raw in ws:
                await self._handle_message(json.loads(raw))

    async def _handle_message(self, msg):
        msg_type = msg.get("type")

        if msg_type == "registered":
            self.machine_id = msg["machineId"]
            self._set_status(t("status_ready", id=self.machine_id))

        elif msg_type == "incoming-request":
            technician_name = msg.get("technicianName", "Outro computador")
            # nosso próprio app envia "Computador <ID>" como nome — extraímos a ID para o log
            self.current_target_id = technician_name.replace("Computador ", "").strip()
            self.gui_queue.put(("incoming-request", technician_name))

        elif msg_type == "error":
            code = msg.get("code")
            error_message = t("error_id_not_found") if code == "id_not_found" else msg.get("message", "Erro.")
            self._set_status(error_message)
            self.gui_queue.put(("reenable-connect", None))

        elif msg_type == "request-declined":
            self._set_status(t("status_declined"))
            self.gui_queue.put(("reenable-connect", None))

        elif msg_type == "request-accepted":
            self._set_status(t("status_accepted_connecting"))
            self.role = "viewer"
            self.current_target_id = msg["targetId"]
            self.current_session = SessionRecord(self.machine_id, msg["targetId"], "viewer")
            await self._start_viewer_session(msg["targetId"])

        elif msg_type == "signal":
            await self._handle_signal(msg["payload"])

        elif msg_type == "session-ended":
            self._set_status(t("status_session_ended"))

            if self.role == "host" and self.current_session is not None:
                # Antes de encerrar de vez, pede uma avaliação rápida ao cliente
                self.gui_queue.put(("request-rating", None))
            else:
                self.gui_queue.put(("close-viewer", None))
                self.gui_queue.put(("reenable-connect", None))
                if self.current_session is not None:
                    self.current_session.close_and_log()
                    self.current_session = None
                if self.pc:
                    await self.pc.close()
                    self.pc = None

        elif msg_type == "rating-received":
            # Chega no lado do TÉCNICO, possivelmente segundos/minutos depois
            # do fim da sessão — aplicada retroativamente ao histórico local.
            rating = msg.get("rating")
            comment = msg.get("comment", "")
            from_id = msg.get("fromId")
            if rating:
                applied = update_last_session_rating(from_id, rating, comment)
                if applied:
                    stars = "⭐" * rating
                    self._set_status(t("rating_received_status", stars=stars))

    async def _request_connect(self, target_id):
        self.current_target_id = target_id
        await self.ws.send(json.dumps({"type": "request-connect", "targetId": target_id, "technicianName": f"Computador {self.machine_id}"}))

    async def _respond_request(self, accepted):
        await self.ws.send(json.dumps({"type": "respond-request", "accepted": accepted}))
        if accepted:
            self.role = "host"
            self._set_status(t("status_sharing_screen"))

    async def _end_session(self):
        await self.ws.send(json.dumps({"type": "end-session", "targetId": self.current_target_id}))
        if self.current_session is not None:
            self.current_session.close_and_log()
            self.current_session = None
        if self.pc:
            await self.pc.close()
            self.pc = None
        self.gui_queue.put(("reenable-connect", None))

    async def _start_viewer_session(self, target_id):
        self.pc = RTCPeerConnection(
            configuration=RTCConfiguration(
                iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")]
            )
        )

        @self.pc.on("track")
        def on_track(track):
            asyncio.ensure_future(self._read_remote_track(track))

        self.data_channel = self.pc.createDataChannel("control")

        @self.data_channel.on("message")
        def on_control_message(message):
            try:
                data = json.loads(message)
            except Exception:
                return
            if data.get("type") == "system-info":
                self.gui_queue.put(("system-info", data))

        file_channel = self.pc.createDataChannel("file")
        self.file_transfer.set_channel(file_channel)

        # CORREÇÃO: garante seção de vídeo na oferta (sem isso a tela nunca é negociada)
        self.pc.addTransceiver("video", direction="recvonly")

        self.gui_queue.put(("open-viewer", None))

        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)

        # CORREÇÃO: envia localDescription (com candidatos ICE embutidos), não o offer cru
        await self.ws.send(json.dumps({
            "type": "signal",
            "targetId": target_id,
            "payload": {"kind": "offer", "sdp": {"sdp": self.pc.localDescription.sdp, "type": self.pc.localDescription.type}}
        }))

    async def _send_system_diagnostics(self, channel):
        try:
            info = collect_system_diagnostics()
            channel.send(json.dumps(info))
        except Exception as e:
            print("Erro ao enviar diagnóstico do sistema:", e)

    async def _read_remote_track(self, track):
        while True:
            try:
                frame = await track.recv()
            except Exception:
                break
            img_rgb = frame.to_ndarray(format="rgb24")

            if self.current_session is not None:
                img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
                self.current_session.write_frame_bgr(img_bgr)

            try:
                self.video_queue.put_nowait(img_rgb)
            except queue.Full:
                pass

    # ---- Papel de HOST (outra máquina está te acessando) ----
    async def _handle_signal(self, payload):
        if payload["kind"] == "offer":
            self.pc = RTCPeerConnection(
                configuration=RTCConfiguration(
                    iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")]
                )
            )
            self.current_session = SessionRecord(self.machine_id, self.current_target_id or "desconhecido", "host")
            self.pc.addTrack(ScreenShareTrack(on_frame=self.current_session.write_frame_bgr))

            @self.pc.on("datachannel")
            def on_datachannel(channel):
                if channel.label == "file":
                    self.file_transfer.set_channel(channel)
                    return

                diagnostics_sent = {"done": False}

                async def send_diagnostics_once():
                    if diagnostics_sent["done"]:
                        return
                    diagnostics_sent["done"] = True
                    await self._send_system_diagnostics(channel)

                @channel.on("open")
                def on_control_open():
                    asyncio.ensure_future(send_diagnostics_once())

                if channel.readyState == "open":
                    # em alguns casos o canal já está aberto quando este evento dispara
                    asyncio.ensure_future(send_diagnostics_once())

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

        elif payload["kind"] == "answer" and self.pc:
            answer = RTCSessionDescription(sdp=payload["sdp"]["sdp"], type=payload["sdp"]["type"])
            await self.pc.setRemoteDescription(answer)

        elif payload["kind"] == "ice-candidate" and self.pc:
            try:
                candidate = ice_candidate_from_json(payload["candidate"])
                if candidate is not None:
                    await self.pc.addIceCandidate(candidate)
            except Exception as e:
                print("Erro ao adicionar ICE candidate:", e)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    init_language()
    if not check_for_updates():
        sys.exit(0)
    if not ensure_valid_license():
        sys.exit(0)
    app = RemoteAccessApp()
    app.run()
