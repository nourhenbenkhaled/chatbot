
# auth.py
import sqlite3
import hashlib
import hmac
import streamlit as st

DB = "chat.db"


# ---------- BASE DE DONNÉES ----------
def init_auth_db():
    with sqlite3.connect(DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


# ---------- SÉCURITÉ DU MOT DE PASSE ----------
def hash_password(password, salt=None):
    if salt is None:
        import os
        salt = os.urandom(16)

    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        600_000
    )

    return salt.hex() + "$" + hashed.hex()


def verify_password(password, stored_password):
    try:
        salt_hex, hash_hex = stored_password.split("$")
        salt = bytes.fromhex(salt_hex)

        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            600_000
        )

        return hmac.compare_digest(candidate.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


# ---------- INSCRIPTION ----------
def register_user(username, password):
    username = username.strip()

    if len(username) < 3:
        return False, "Le nom d'utilisateur doit contenir au moins 3 caractères."

    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères."

    password_hash = hash_password(password)

    try:
        with sqlite3.connect(DB) as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash)
            )
        return True, "Compte créé avec succès !"
    except sqlite3.IntegrityError:
        return False, "Ce nom d'utilisateur existe déjà."


# ---------- CONNEXION ----------
def login_user(username, password):
    with sqlite3.connect(DB) as conn:
        user = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username.strip(),)
        ).fetchone()

    if user and verify_password(password, user[2]):
        return {
            "id": user[0],
            "username": user[1]
        }

    return None


# ---------- PAGE AUTH ----------
def show_auth_page():
    init_auth_db()

    st.title("🤖 Mon Chatbot")
    st.subheader("Bienvenue !")

    choix = st.radio(
        "Choisir une option",
        ["Connexion", "Inscription"],
        horizontal=True
    )

    if choix == "Connexion":
        with st.form("login_form"):
            username = st.text_input("Nom d'utilisateur")
            password = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button(
                "Se connecter",
                use_container_width=True
            )

        if submitted:
            if not username.strip() or not password:
                st.warning("Remplis tous les champs.")
            else:
                user = login_user(username, password)

                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.success(f"Bienvenue, {user['username']} !")
                    st.rerun()
                else:
                    st.error("Nom d'utilisateur ou mot de passe incorrect.")

    else:
        with st.form("register_form"):
            username = st.text_input("Choisir un nom d'utilisateur")
            password = st.text_input(
                "Choisir un mot de passe",
                type="password"
            )
            confirm_password = st.text_input(
                "Confirmer le mot de passe",
                type="password"
            )

            submitted = st.form_submit_button(
                "Créer mon compte",
                use_container_width=True
            )

        if submitted:
            if not username.strip() or not password or not confirm_password:
                st.warning("Remplis tous les champs.")
            elif password != confirm_password:
                st.error("Les mots de passe ne correspondent pas.")
            else:
                success, message = register_user(username, password)

                if success:
                    st.success(message + " Tu peux maintenant te connecter.")
                else:
                    st.error(message)
