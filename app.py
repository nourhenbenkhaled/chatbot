#app.py
import auth
import os
import sqlite3
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

import rag  # ⭐ ton fichier rag.py (même dossier)

DB = "chat.db"
# ---------- AUTHENTIFICATION ----------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    auth.show_auth_page()
    st.stop()
    
    
    
# ---------- BASE DE DONNÉES ----------
def requete(sql, params=(), fetch=False):
    """Exécute une requête SQL. Si fetch=True, renvoie les résultats."""
    conn = sqlite3.connect(DB)
    cur = conn.execute(sql, params)
    resultat = cur.fetchall() if fetch else cur.lastrowid
    conn.commit()
    conn.close()
    return resultat

def init_db():
    requete("""CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    requete("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id)
    )""")

def creer_conversation(titre):
    return requete("INSERT INTO conversations (titre) VALUES (?)", (titre,))

def lister_conversations():
    return requete("SELECT id, titre FROM conversations ORDER BY id DESC", fetch=True)

def charger_messages(conv_id):
    lignes = requete(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id",
        (conv_id,),
        fetch=True,
    )
    return [{"role": r, "content": c} for r, c in lignes]

def ajouter_message(conv_id, role, content):
    requete(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (conv_id, role, content),
    )

def supprimer_conversation(conv_id):
    requete("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
    requete("DELETE FROM conversations WHERE id = ?", (conv_id,))


def transcrire(audio):
    resultat = client.audio.transcriptions.create(
        file=(audio.name or "voix.wav", audio.getvalue()),
        model=MODELE_WHISPER,
        language="fr",
        response_format="text",
    )
    return (
        resultat if isinstance(resultat, str) else resultat.text
    ).strip()


# ---------- CONFIG ----------
st.set_page_config(page_title="chatbot", page_icon="")
st.title(" Mon chatbot")

load_dotenv()
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

init_db()

# conv_id = conversation ouverte (None = nouvelle conversation vide)
if "conv_id" not in st.session_state:
    st.session_state.conv_id = None
if "audio_key" not in st.session_state:
    st.session_state.audio_key = 0
# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("⚙️ Paramètres")
    modele = st.selectbox("Modèle", ["openai/gpt-oss-120b"])
    temperature = st.slider("Créativité", 0.0, 1.0, 0.7, 0.1)
    consigne = st.text_area(
        "Consigne du bot",
        value="Tu es un assistant sympa qui répond en français.",
    )

    
    st.divider()
    st.header("📚 Documents (RAG)")
    utiliser_rag = st.toggle("Utiliser mes documents", value=True)

    fichiers = st.file_uploader(
        "Ajouter des fichiers",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        key="documents_upload",
    )

    images = st.file_uploader(
        "Importer des images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="img_upload",
    )

    st.header(":studio_microphone: Voix")
    audio = st.audio_input(
        "Parle, puis arrête l'enregistrement",
        key=f"audio_{st.session_state.audio_key}",
    )


    if images:
        for image in images:
            st.image(image, caption=image.name, use_container_width=True)

    if st.button("📥 Indexer les fichiers", use_container_width=True):
        if fichiers or images:
            with st.spinner("Indexation des fichiers..."):
                for f in fichiers or []:
                    nb = rag.ajouter_document(f)
                    st.success(f"{f.name} : {nb} morceaux")

                for image in images or []:
                    st.warning(
                        f"{image.name} : image importée, "
                        "mais l'indexation du contenu visuel nécessite "
                        "une fonction OCR ou un modèle vision."
                    )
        else:
            st.warning("Importe d'abord un fichier PDF, TXT ou une image.")

    st.caption(f"Morceaux en base : {rag.nombre_morceaux()}")

    if st.button("🧹 Vider les documents", use_container_width=True):
        rag.supprimer_documents()
        st.success("Documents supprimés.")
        st.rerun()
    
    
    
    st.divider()
    st.header("💬 Conversations")

    if st.button("➕ Nouvelle conversation", use_container_width=True):
        st.session_state.conv_id = None
        st.rerun()

    for conv_id, titre in lister_conversations():
        col1, col2 = st.columns([4, 1])
        actif = conv_id == st.session_state.conv_id

        if col1.button(
            titre,
            key=f"open_{conv_id}",
            use_container_width=True,
            type="primary" if actif else "secondary",
        ):
            st.session_state.conv_id = conv_id
            st.rerun()

        if col2.button("🗑️", key=f"del_{conv_id}"):
            supprimer_conversation(conv_id)
            if actif:
                st.session_state.conv_id = None
            st.rerun()
    if st.button("🚪 Se déconnecter", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.conv_id = None
        st.rerun()


st.write(f"👤 Connecté : {st.session_state.user['username']}")


    
    
# ---------- AFFICHER L'HISTORIQUE ----------
if st.session_state.conv_id is not None:
    for message in charger_messages(st.session_state.conv_id):
        with st.chat_message(message["role"]):
            st.write(message["content"])

# ---------- SAISIE ----------
question = st.chat_input("Écris ta question ici...")

if question:
    nouvelle = st.session_state.conv_id is None

    # Si c'est une nouvelle conversation, on la crée (titre = début de la question)
    if nouvelle:
        titre = question[:30] + ("..." if len(question) > 30 else "")
        st.session_state.conv_id = creer_conversation(titre)

    conv_id = st.session_state.conv_id

    with st.chat_message("user"):
        st.write(question)
    ajouter_message(conv_id, "user", question)

    # ⭐ RAG : chercher les morceaux proches et les ajouter à la consigne
    morceaux = rag.chercher(question) if utiliser_rag else []
    system_prompt = consigne
    if morceaux:
        contexte = "\n\n---\n\n".join(morceaux)
        system_prompt += (
            "\n\nUtilise le CONTEXTE ci-dessous pour répondre. "
            "Si la réponse ne s'y trouve pas, dis que tu ne sais pas.\n\n"
            f"CONTEXTE :\n{contexte}"
        )

    with st.chat_message("assistant"):
        with st.spinner("Je réfléchis..."):
            response = client.chat.completions.create(
                model=modele,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},  # ⭐ au lieu de consigne
                    *charger_messages(conv_id),
                ],
            )
            reponse = response.choices[0].message.content
        st.write(reponse)

        # ⭐ RAG : afficher les morceaux utilisés
        if morceaux:
            with st.expander("📄 Sources utilisées"):
                for texte in morceaux:
                    st.write(texte[:300] + "...")

    ajouter_message(conv_id, "assistant", reponse)

    # Recharger pour que la nouvelle conversation apparaisse dans la sidebar
    if nouvelle:
        st.rerun()